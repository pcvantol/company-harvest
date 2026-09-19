"""Begrensde, expliciete KVK-Web-API-controle van de vierbronnenmaster."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path

from company_harvest.core import HarvestError, Run, atomic_write, normalize_name, sha256, write_tsv
from company_harvest.kvk import (
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
