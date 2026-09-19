"""Begrensde, expliciete KVK-Web-API-controle van de vierbronnenmaster."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from company_harvest.core import HarvestError, Run, atomic_write, normalize_name, sha256, write_tsv
from company_harvest.kvk import (
    UNRESOLVED_HEADERS,
    KvkError,
    ProviderLock,
    PublicHttpProvider,
    _check_cooldown,
    _has_source_conflict,
    _match,
)
from company_harvest.pre_kvk import MASTER_HEADERS, validated_master
from company_harvest.pre_kvk_filter import validated_filter

MATCH_HEADERS = [
    "candidate_id", "Bedrijfsnaam", "KVK-nummer", "raw_legal_form", "raw_status",
    "city", "country", "match_method", "provider", "checked_at", "response_json",
    "source_relations",
]
OUTCOME_HEADERS = ["candidate_id", "original_name", "reason", "detail", "checked_at"]
PROGRESS_NAME = "pre_kvk_kvk_progress.json"


def _pace_request(run: Run, interval: float) -> None:
    """Bewaar globale requeststart vóór de GET; aanroepen gebeuren onder ProviderLock."""
    path = run.path.parent.parent / ".local" / "kvk-last-request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            previous = float(json.loads(path.read_text(encoding="utf-8"))["started_epoch"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HarvestError("KVK-pacingjournal is ongeldig; geen verzoek verstuurd", 7) from exc
        now = time.time()
        if not math.isfinite(previous) or previous > now + 60:
            raise HarvestError("KVK-pacingjournal heeft een ongeldige tijd", 7)
        remaining = interval - (now - previous)
        if remaining > 0:
            time.sleep(remaining)
    atomic_write(path, json.dumps({"started_epoch": time.time()}) + "\n")


def _master(run: Run) -> tuple[Path, str]:
    return validated_master(run)


def _queue(run: Run) -> tuple[Path, str, str]:
    _master_path, master_hash = _master(run)
    eligible, eligible_hash, _excluded, _excluded_hash, _metadata = validated_filter(run, master_hash)
    return eligible, eligible_hash, master_hash


def resolve_pre_kvk(run: Run, limit: int = 10, interval: float = 2.0) -> tuple[Path, Path, Path]:
    """Verwerk maximaal tien nieuwe rijen; nooit impliciet een volledige harvest."""
    with run.lock():
        return _resolve_pre_kvk_locked(run, limit, interval)


def _resolve_pre_kvk_locked(run: Run, limit: int, interval: float) -> tuple[Path, Path, Path]:
    if not 1 <= limit <= 10 or not math.isfinite(interval) or interval < 2.0:
        raise HarvestError("KVK-batch vereist 1–10 verzoeken en minimaal 2 seconden interval")
    master, digest, master_hash = _queue(run)
    config = run.metadata().get("runtime_config", {}).get("pre_kvk_kvk")
    if config and (config.get("master_sha256") != master_hash
                   or config.get("eligible_sha256") != digest):
        raise HarvestError("KVK-journal hoort bij een andere pre-KVK-filterset")
    with run.connect() as connection:
        if not config and connection.execute("SELECT 1 FROM kvk_requests LIMIT 1").fetchone():
            raise HarvestError("KVK-journal hoort mogelijk bij een andere kandidatenlijst")
        prior_block = connection.execute(
            "SELECT error FROM kvk_requests WHERE state='FAILED' AND error IN "
            "('PUBLIC_ACCESS_BLOCKED','RATE_LIMITED') LIMIT 1"
        ).fetchone()
        if prior_block:
            raise HarvestError(f"eerdere KVK-blokkade vereist eerst een afzonderlijk besluit: {prior_block['error']}", 4)
    matches: list[dict[str, str]] = []
    outcomes: list[dict[str, str]] = []
    attempted = 0
    blocked = False
    with run.lock(), ProviderLock(run):
        locked_master, locked_digest, locked_master_hash = _queue(run)
        if (locked_master, locked_digest, locked_master_hash) != (master, digest, master_hash):
            raise HarvestError("pre-KVK-filter veranderde vóór de KVK-batch")
        locked_config = run.metadata().get("runtime_config", {}).get("pre_kvk_kvk")
        if locked_config and (locked_config.get("master_sha256") != master_hash
                              or locked_config.get("eligible_sha256") != digest):
            raise HarvestError("KVK-journal hoort bij een andere pre-KVK-filterset")
        with run.connect() as connection:
            if not locked_config and connection.execute("SELECT 1 FROM kvk_requests LIMIT 1").fetchone():
                raise HarvestError("KVK-journal hoort mogelijk bij een andere kandidatenlijst")
            if connection.execute("SELECT 1 FROM kvk_requests WHERE state='FAILED' AND error IN "
                                  "('PUBLIC_ACCESS_BLOCKED','RATE_LIMITED') LIMIT 1").fetchone():
                raise HarvestError("eerdere KVK-blokkade vereist eerst een afzonderlijk besluit", 4)
        if not config:
            run.record_config("pre_kvk_kvk", {"master_sha256": master_hash,
                                               "eligible_sha256": digest,
                                               "provider": "public-http"})
        with run.connect() as connection:
            connection.execute(
                "UPDATE kvk_requests SET state='SENT_OUTCOME_UNKNOWN',error='INTERRUPTED_BEFORE_DURABLE_OUTCOME' "
                "WHERE state='IN_FLIGHT'"
            )
        with master.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if not set(MASTER_HEADERS).issubset(reader.fieldnames or []):
                raise HarvestError("pre-KVK-KVK-wachtrij mist verplichte kolommen")
            for candidate in reader:
                if attempted >= limit or blocked:
                    break
                if candidate["kvk_queue_status"] not in {"READY_FOR_KVK_MATCHING", "READY_FOR_KVK_VERIFICATION"}:
                    continue
                candidate_id = candidate["candidate_id"]
                with run.connect() as connection:
                    prior = connection.execute("SELECT state,error FROM kvk_requests WHERE candidate_id=?", (candidate_id,)).fetchone()
                if prior:
                    if prior["state"] in {"FAILED", "SENT_OUTCOME_UNKNOWN"}:
                        outcomes.append({"candidate_id": candidate_id,
                                         "original_name": candidate["original_name"],
                                         "reason": prior["state"], "detail": prior["error"] or "",
                                         "checked_at": ""})
                    continue
                _check_cooldown(run)
                _pace_request(run, interval)
                fingerprint = hashlib.sha256(f"{digest}\0{candidate_id}\0{candidate['original_name']}".encode()).hexdigest()
                with run.connect() as connection:
                    connection.execute(
                        "INSERT INTO kvk_requests(candidate_id,query,state,attempt,request_fingerprint,provider) "
                        "VALUES(?,?,'IN_FLIGHT',1,?,'public-http')",
                        (candidate_id, candidate["original_name"], fingerprint),
                    )
                attempted += 1
                try:
                    result = PublicHttpProvider(run, max_pages=1, max_attempts=1).search(candidate["original_name"])
                    evidence = run.path / result.evidence
                    if evidence.is_file():
                        run.register_artifact(evidence, "04", "evidence_public-http")
                    match = _match(candidate, result) if result.complete else None
                    if match and not candidate["source_kvk_hint"]:
                        if not candidate["city"] or normalize_name(candidate["city"]) != normalize_name(match["city"]):
                            match = None
                    if match:
                        matches.append(match)
                        reason, detail, state = "MATCHED", "", "SUCCEEDED"
                    elif not result.complete:
                        reason, detail, state = "TRUNCATED_RESULTS", "onvolledige zoekresultaten", "UNRESOLVED"
                    elif _has_source_conflict(candidate, result):
                        reason, detail, state = "SOURCE_CONFLICT", "KVK-hint wijkt af", "UNRESOLVED"
                    else:
                        reason, detail, state = "NO_VERIFIED_MATCH", "geen unieke match met onafhankelijk veld", "UNRESOLVED"
                    with run.connect() as connection:
                        connection.execute(
                            "UPDATE kvk_requests SET state=?,checked_at=?,result_json=?,evidence_path=?,error=? "
                            "WHERE candidate_id=?",
                            (state, datetime.now(UTC).isoformat(), json.dumps(match) if match else None,
                             result.evidence, None if match else reason, candidate_id),
                        )
                except KvkError as exc:
                    reason, detail = exc.reason, str(exc)
                    with run.connect() as connection:
                        connection.execute("UPDATE kvk_requests SET state='FAILED',error=?,evidence_path=? WHERE candidate_id=?",
                                           (reason, exc.evidence, candidate_id))
                    blocked = True
                except BaseException:
                    with run.connect() as connection:
                        connection.execute("UPDATE kvk_requests SET state='SENT_OUTCOME_UNKNOWN',error='INTERRUPTED' WHERE candidate_id=?", (candidate_id,))
                    raise
                outcomes.append({"candidate_id": candidate_id, "original_name": candidate["original_name"],
                                 "reason": reason, "detail": detail, "checked_at": datetime.now(UTC).isoformat()})
    with run.lock():
        if _queue(run) != (master, digest, master_hash) or sha256(master) != digest:
            raise HarvestError("pre-KVK-filter veranderde tijdens de KVK-batch")
        match_path = run.artifact_path("04", "pre_kvk_kvk_batch_matches", "tsv")
        outcome_path = run.artifact_path("04", "pre_kvk_kvk_batch_outcomes", "tsv")
        report_path = run.artifact_path("04", "pre_kvk_kvk_batch_report", "json")
        write_tsv(match_path, MATCH_HEADERS, matches)
        write_tsv(outcome_path, OUTCOME_HEADERS, outcomes)
        with run.connect() as connection:
            journal_states = {row["state"]: row["count"] for row in connection.execute(
                "SELECT state,COUNT(*) AS count FROM kvk_requests GROUP BY state"
            )}
        report_path.write_text(json.dumps({"master_sha256": master_hash,
                                           "eligible_sha256": digest, "attempted": attempted,
                                           "matched": len(matches), "blocked": blocked,
                                           "complete": False, "provider": "public-http",
                                           "journal_states": journal_states}, indent=2) + "\n", encoding="utf-8")
        run.register_artifact_set([(match_path, "04", "pre_kvk_kvk_batch_matches", "PARTIAL"),
                                   (outcome_path, "04", "pre_kvk_kvk_batch_outcomes", "PARTIAL"),
                                   (report_path, "04", "pre_kvk_kvk_batch_report", "PARTIAL")])
        return match_path, outcome_path, report_path


def _progress(run: Run, digest: str, total: int, states: Counter[str],
              last_candidate_id: str, status: str) -> Path:
    """De SQLite-journal is leidend; dit atomische bestand is de leesbare checkpoint."""
    path = run.path / PROGRESS_NAME
    processed = sum(states.values())
    atomic_write(path, json.dumps({
        "schema_version": 1, "eligible_sha256": digest, "eligible_rows": total,
        "journal_rows": processed, "remaining": total - processed,
        "states": dict(sorted(states.items())), "last_candidate_id": last_candidate_id,
        "status": status, "updated_at": datetime.now(UTC).isoformat(),
        "verification_status": "ALL_MATCHED" if states.get("SUCCEEDED") == total else "PARTIAL_OR_PENDING",
        "resumption": "start hetzelfde commando opnieuw; bestaande verzoeken worden niet herhaald",
    }, ensure_ascii=False, indent=2) + "\n")
    return path


def _snapshot(run: Run, eligible: Path, total: int, states: Counter[str],
              digest: str, *, finalize: bool) -> tuple[Path, Path]:
    """Reconstrueer output uitsluitend uit de duurzame journal en de gebonden input."""
    matches = run.path / "pre_kvk_kvk_matches.tsv"
    unresolved = run.path / "pre_kvk_kvk_unresolved.tsv"
    match_tmp = matches.with_name(f".{matches.name}.tmp")
    unresolved_tmp = unresolved.with_name(f".{unresolved.name}.tmp")
    seen = 0
    try:
        with (eligible.open(encoding="utf-8-sig", newline="") as source,
              match_tmp.open("w", encoding="utf-8", newline="") as match_file,
              unresolved_tmp.open("w", encoding="utf-8", newline="") as unresolved_file,
              run.connect() as connection):
            reader = csv.DictReader(source, delimiter="\t")
            if not set(MASTER_HEADERS).issubset(reader.fieldnames or []):
                raise HarvestError("pre-KVK-KVK-wachtrij mist verplichte kolommen")
            match_writer = csv.DictWriter(match_file, fieldnames=MATCH_HEADERS, delimiter="\t", extrasaction="ignore")
            unresolved_writer = csv.DictWriter(unresolved_file, fieldnames=UNRESOLVED_HEADERS, delimiter="\t", extrasaction="ignore")
            match_writer.writeheader()
            unresolved_writer.writeheader()
            for candidate in reader:
                seen += 1
                row = connection.execute(
                    "SELECT state,result_json,error,checked_at FROM kvk_requests WHERE candidate_id=?",
                    (candidate["candidate_id"],),
                ).fetchone()
                if row is None:
                    if finalize:
                        raise HarvestError("KVK-journal is nog niet volledig; geen COMPLETE-output")
                    continue
                if row["state"] == "SUCCEEDED":
                    if not row["result_json"]:
                        raise HarvestError("KVK-journal mist een geslaagde match")
                    match_writer.writerow(json.loads(row["result_json"]))
                else:
                    unresolved_writer.writerow({
                        "candidate_id": candidate["candidate_id"],
                        "original_name": candidate["original_name"],
                        "reason": row["error"] if row["state"] == "UNRESOLVED" else row["state"],
                        "detail": row["error"] or "",
                        "resumable": "false",
                        "checked_at": row["checked_at"] or "",
                    })
            for handle in (match_file, unresolved_file):
                handle.flush()
                os.fsync(handle.fileno())
        if seen != total:
            raise HarvestError("pre-KVK-wachtrij heeft een gewijzigd aantal rijen")
        os.replace(match_tmp, matches)
        os.replace(unresolved_tmp, unresolved)
    finally:
        match_tmp.unlink(missing_ok=True)
        unresolved_tmp.unlink(missing_ok=True)
    if finalize:
        if states.get("IN_FLIGHT"):
            raise HarvestError("lopende KVK-verzoeken verhinderen gesloten output")
        if sum(states.values()) != total or sha256(eligible) != digest:
            raise HarvestError("KVK-input/journal is niet gesloten; geen COMPLETE-output")
        if run.latest_artifact("04", "kvk_matches") is None:
            run.register_artifact_set([
                (matches, "04", "kvk_matches", "COMPLETE"),
                (unresolved, "05", "kvk_unresolved", "COMPLETE"),
            ])
            run.update_status("IN_PROGRESS", "04")
    return matches, unresolved


def _append_output(run: Run, candidate: dict[str, str], state: str,
                   match: dict[str, str] | None, error: str | None) -> None:
    """Append na de DB-commit; hervatten reconstrueert eventuele gemiste append."""
    if state == "SUCCEEDED":
        path = run.path / "pre_kvk_kvk_matches.tsv"
        headers = MATCH_HEADERS
        record = match
    else:
        path = run.path / "pre_kvk_kvk_unresolved.tsv"
        headers = UNRESOLVED_HEADERS
        record = {
            "candidate_id": candidate["candidate_id"], "original_name": candidate["original_name"],
            "reason": (error or "NO_VERIFIED_MATCH") if state == "UNRESOLVED" else state,
            "detail": error or "",
            "resumable": "false",
            "checked_at": datetime.now(UTC).isoformat(),
        }
    if record is None:
        raise HarvestError("KVK-match ontbreekt na geslaagd verzoek")
    with path.open("a", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=headers, delimiter="\t", extrasaction="ignore").writerow(record)
        handle.flush()
        os.fsync(handle.fileno())


def run_pre_kvk(run: Run, interval: float = 2.0, max_requests: int | None = None) -> tuple[Path, Path, Path]:
    """Hervatbare frontendcheck: onbeperkt alleen na expliciete CLI-keuze."""
    if not math.isfinite(interval) or interval < 2.0 or (max_requests is not None and max_requests < 1):
        raise HarvestError("KVK-run vereist minimaal 2 seconden interval en een positieve verzoeklimiet")
    with run.lock(), ProviderLock(run):
        eligible, digest, master_hash = _queue(run)
        metadata_path = validated_filter(run, master_hash)[4]
        total = json.loads(metadata_path.read_text(encoding="utf-8"))["counts"]["eligible_rows"]
        config = run.metadata().get("runtime_config", {}).get("pre_kvk_kvk")
        if config and (config.get("master_sha256") != master_hash or config.get("eligible_sha256") != digest):
            raise HarvestError("KVK-journal hoort bij een andere pre-KVK-filterset")
        with run.connect() as connection:
            if not config and connection.execute("SELECT 1 FROM kvk_requests LIMIT 1").fetchone():
                raise HarvestError("KVK-journal hoort mogelijk bij een andere kandidatenlijst")
            blocked = connection.execute(
                "SELECT error FROM kvk_requests WHERE state='FAILED' AND error IN "
                "('PUBLIC_ACCESS_BLOCKED','RATE_LIMITED') LIMIT 1"
            ).fetchone()
            if blocked:
                raise HarvestError(f"eerdere KVK-blokkade vereist eerst een afzonderlijk besluit: {blocked['error']}", 4)
            connection.execute(
                "UPDATE kvk_requests SET state='SENT_OUTCOME_UNKNOWN',error='INTERRUPTED_BEFORE_DURABLE_OUTCOME' "
                "WHERE state='IN_FLIGHT'"
            )
            states = Counter({row["state"]: row["count"] for row in connection.execute(
                "SELECT state,COUNT(*) AS count FROM kvk_requests GROUP BY state"
            )})
        if not config:
            run.record_config("pre_kvk_kvk", {"master_sha256": master_hash,
                                               "eligible_sha256": digest, "provider": "public-http"})
        _snapshot(run, eligible, total, states, digest, finalize=False)
        progress = _progress(run, digest, total, states, "", "RUNNING")
        attempted = 0
        last_id = ""
        stop_reason = "PAUSED"
        try:
            with eligible.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                if not set(MASTER_HEADERS).issubset(reader.fieldnames or []):
                    raise HarvestError("pre-KVK-KVK-wachtrij mist verplichte kolommen")
                for candidate in reader:
                    candidate_id = candidate["candidate_id"]
                    last_id = candidate_id
                    if candidate["kvk_queue_status"] not in {"READY_FOR_KVK_MATCHING", "READY_FOR_KVK_VERIFICATION"}:
                        raise HarvestError("pre-KVK-filter bevat niet-toegelaten kandidaten")
                    with run.connect() as connection:
                        prior = connection.execute("SELECT state FROM kvk_requests WHERE candidate_id=?", (candidate_id,)).fetchone()
                    if prior:
                        continue
                    if max_requests is not None and attempted >= max_requests:
                        break
                    _check_cooldown(run)
                    _pace_request(run, interval)
                    fingerprint = hashlib.sha256(f"{digest}\0{candidate_id}\0{candidate['original_name']}".encode()).hexdigest()
                    with run.connect() as connection:
                        connection.execute(
                            "INSERT INTO kvk_requests(candidate_id,query,state,attempt,request_fingerprint,provider) "
                            "VALUES(?,?,'IN_FLIGHT',1,?,'public-http')",
                            (candidate_id, candidate["original_name"], fingerprint),
                        )
                    states["IN_FLIGHT"] += 1
                    attempted += 1
                    _progress(run, digest, total, states, candidate_id, "IN_FLIGHT")
                    try:
                        match = None
                        result = PublicHttpProvider(run, max_pages=1, max_attempts=1).search(candidate["original_name"])
                        evidence = run.path / result.evidence
                        if evidence.is_file():
                            run.register_artifact(evidence, "04", "evidence_public-http")
                        match = _match(candidate, result) if result.complete else None
                        if match and not candidate["source_kvk_hint"]:
                            if not candidate["city"] or normalize_name(candidate["city"]) != normalize_name(match["city"]):
                                match = None
                        if match:
                            state, error = "SUCCEEDED", None
                        elif not result.complete:
                            state, error = "UNRESOLVED", "TRUNCATED_RESULTS"
                        elif _has_source_conflict(candidate, result):
                            state, error = "UNRESOLVED", "SOURCE_CONFLICT"
                        else:
                            state, error = "UNRESOLVED", "NO_VERIFIED_MATCH"
                        with run.connect() as connection:
                            connection.execute(
                                "UPDATE kvk_requests SET state=?,checked_at=?,result_json=?,evidence_path=?,error=? "
                                "WHERE candidate_id=?",
                                (state, datetime.now(UTC).isoformat(), json.dumps(match) if match else None,
                                 result.evidence, error, candidate_id),
                            )
                    except KvkError as exc:
                        state = "FAILED"
                        error = exc.reason
                        with run.connect() as connection:
                            connection.execute(
                                "UPDATE kvk_requests SET state='FAILED',error=?,evidence_path=? WHERE candidate_id=?",
                                (exc.reason, exc.evidence, candidate_id),
                            )
                        stop_reason = "BLOCKED" if exc.reason in {"PUBLIC_ACCESS_BLOCKED", "RATE_LIMITED"} else "FAILED"
                    except BaseException:
                        with run.connect() as connection:
                            connection.execute(
                                "UPDATE kvk_requests SET state='SENT_OUTCOME_UNKNOWN',error='INTERRUPTED' WHERE candidate_id=?",
                                (candidate_id,),
                            )
                        states["IN_FLIGHT"] -= 1
                        states["SENT_OUTCOME_UNKNOWN"] += 1
                        _append_output(run, candidate, "SENT_OUTCOME_UNKNOWN", None, "INTERRUPTED")
                        _progress(run, digest, total, states, candidate_id, "INTERRUPTED")
                        raise
                    states["IN_FLIGHT"] -= 1
                    states[state] += 1
                    _append_output(run, candidate, state, match, error)
                    _progress(run, digest, total, states, candidate_id, stop_reason if state == "FAILED" else "RUNNING")
                    if state == "FAILED":
                        break
            if sum(states.values()) == total and not states["IN_FLIGHT"] and stop_reason != "BLOCKED":
                stop_reason = "COMPLETE"
        except KeyboardInterrupt:
            stop_reason = "INTERRUPTED"
            raise
        finally:
            _progress(run, digest, total, states, last_id,
                      "FINALIZING" if stop_reason == "COMPLETE" else stop_reason)
            _snapshot(run, eligible, total, states, digest, finalize=stop_reason == "COMPLETE")
            if stop_reason == "COMPLETE":
                _progress(run, digest, total, states, last_id, "COMPLETE")
        return run.path / "pre_kvk_kvk_matches.tsv", run.path / "pre_kvk_kvk_unresolved.tsv", progress
