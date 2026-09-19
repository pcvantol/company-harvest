"""Bounded R8 identity-matching pilot over the deterministic R6 selection."""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from company_lookup.core import (
    HarvestError,
    Run,
    atomic_write,
    normalize_name,
    read_tsv,
    sha256,
    validate_kvk,
    write_tsv,
)
from company_lookup.kvk import (
    KvkError,
    Provider,
    ProviderLock,
    ProviderResult,
    _check_cooldown,
    _provider_for_run,
)
from company_lookup.sampling import (
    _even_allocation,
    _latest_sources,
    _require_registered_integrity,
)

PILOT_REPORT_SCHEMA_VERSION = 1
PILOT_OUTCOMES = {
    "MATCHED",
    "NO_MATCH",
    "AMBIGUOUS",
    "SOURCE_CONFLICT",
    "TECHNICAL_ERROR",
}
RESULT_HEADERS = [
    "candidate_id",
    "original_name",
    "source_families",
    "terminal_outcome",
    "provisional_kvk",
    "match_method",
    "evidence_fields",
    "provider",
    "reason",
    "detail",
    "checked_at",
    "evidence_reference",
    "source_relations",
    "observed_legal_form",
    "observed_status",
    "observed_city",
    "verification_status",
]
REVIEW_HEADERS = [
    "queue_sha256",
    "review_id",
    "candidate_id",
    "source_families",
    "terminal_outcome",
    "original_name",
    "provisional_kvk",
    "match_method",
    "evidence_fields",
    "evidence_reference",
    "review_verdict",
    "review_seconds",
    "review_notes",
]
REVIEW_VERDICTS = {"CONFIRMED", "FALSE_MATCH", "UNCERTAIN"}


def _website_host(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"//{text}")
    host = (parsed.hostname or "").casefold().removeprefix("www.")
    return host


def _source_place(row: dict[str, str]) -> str:
    evidence = row.get("nl_evidence", "")
    marker = "; plaats="
    if marker not in evidence:
        return ""
    return normalize_name(evidence.rsplit(marker, 1)[1])


def _candidate_features(
    candidate: dict[str, str], sample_by_relation: dict[tuple[str, str], dict[str, str]]
) -> tuple[set[str], set[str]]:
    websites: set[str] = set()
    places: set[str] = set()
    try:
        relations = json.loads(candidate.get("source_relations", "[]"))
    except json.JSONDecodeError:
        relations = []
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        row = sample_by_relation.get(
            (str(relation.get("source_id", "")), str(relation.get("row", "")))
        )
        if not row:
            continue
        website = _website_host(row.get("website"))
        place = _source_place(row)
        if website:
            websites.add(website)
        if place:
            places.add(place)
    return websites, places


def _valid_number(row: dict[str, str]) -> str | None:
    try:
        return validate_kvk(row.get("source_kvk_hint"))
    except ValueError:
        return None


def _offline_index(
    run: Run, pilot: list[dict[str, str]]
) -> tuple[dict[str, list[dict[str, str]]], list[dict[str, Any]], str]:
    names = {normalize_name(row["original_name"]) for row in pilot}
    indexed: dict[str, list[dict[str, str]]] = defaultdict(list)
    artifacts: list[dict[str, Any]] = []
    for path, kind, expected_hash in _latest_sources(run):
        if not path.is_file() or sha256(path) != expected_hash:
            raise HarvestError(f"bronartefact voor {kind} ontbreekt of wijkt af van de registratie")
        relative_path = str(path.relative_to(run.path))
        artifact_size = path.stat().st_size
        descriptor = {
            "path": relative_path,
            "kind": kind,
            "sha256": expected_hash,
            "size": artifact_size,
        }
        artifacts.append(descriptor)
        for row in read_tsv(path):
            normalized = normalize_name(row.get("original_name", ""))
            if normalized in names and _valid_number(row):
                indexed[normalized].append(
                    {
                        **row,
                        "_artifact_path": relative_path,
                        "_artifact_kind": kind,
                        "_artifact_sha256": expected_hash,
                        "_artifact_size": str(artifact_size),
                    }
                )
    fingerprint = hashlib.sha256(
        json.dumps(
            artifacts,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return indexed, artifacts, fingerprint


def _base_result(candidate: dict[str, str]) -> dict[str, str]:
    return {
        "candidate_id": candidate["candidate_id"],
        "original_name": candidate["original_name"],
        "source_families": candidate.get("source_families", "unclassified"),
        "terminal_outcome": "",
        "provisional_kvk": "",
        "match_method": "",
        "evidence_fields": "",
        "provider": "",
        "reason": "",
        "detail": "",
        "checked_at": datetime.now(UTC).isoformat(),
        "evidence_reference": "",
        "source_relations": candidate.get("source_relations", ""),
        "observed_legal_form": "",
        "observed_status": "",
        "observed_city": "",
        "verification_status": "UNKNOWN",
    }


def _offline_reference_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    references: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["_artifact_path"], row.get("source_id", ""), row.get("source_row", ""))
        references[key] = {
            "artifact_kind": row["_artifact_kind"],
            "artifact_path": row["_artifact_path"],
            "artifact_sha256": row["_artifact_sha256"],
            "artifact_size": int(row["_artifact_size"]),
            "source_id": row.get("source_id", ""),
            "source_row": row.get("source_row", ""),
        }
    return [references[key] for key in sorted(references)]


def _offline_references(rows: list[dict[str, str]]) -> str:
    return json.dumps(_offline_reference_rows(rows), ensure_ascii=False)


def _evidence_file(run: Run, reference: str) -> Path | None:
    if not reference or reference.lstrip().startswith(("[", "{")):
        return None
    path = run.path / reference
    try:
        return path if path.is_file() else None
    except OSError:
        return None


def _offline_match(
    candidate: dict[str, str],
    features: tuple[set[str], set[str]],
    indexed: dict[str, list[dict[str, str]]],
) -> dict[str, str] | None:
    websites, places = features
    supporting: dict[str, set[str]] = defaultdict(set)
    rows_by_number: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in indexed.get(normalize_name(candidate["original_name"]), []):
        number = _valid_number(row)
        assert number is not None
        row_website = _website_host(row.get("website"))
        row_place = _source_place(row)
        if row_website and row_website in websites:
            supporting[number].add("EXACT_NORMALIZED_NAME+WEBSITE_HOST")
            rows_by_number[number].append(row)
        if row_place and row_place in places:
            supporting[number].add("EXACT_NORMALIZED_NAME+SOURCE_PLACE")
            rows_by_number[number].append(row)
    if not supporting:
        return None
    result = _base_result(candidate)
    if len(supporting) != 1:
        result.update(
            terminal_outcome="SOURCE_CONFLICT",
            match_method="OFFLINE_STRONG_FIELDS",
            evidence_fields=json.dumps(
                {number: sorted(fields) for number, fields in sorted(supporting.items())}
            ),
            reason="MULTIPLE_OFFLINE_KVK_CANDIDATES",
            detail="sterke offline velden koppelen aan meerdere KVK-nummers",
            evidence_reference=json.dumps(
                {
                    number: _offline_reference_rows(rows)
                    for number, rows in sorted(rows_by_number.items())
                },
                ensure_ascii=False,
            ),
        )
        return result
    number, evidence_fields = next(iter(supporting.items()))
    rows = rows_by_number[number]
    result.update(
        terminal_outcome="MATCHED",
        provisional_kvk=number,
        match_method="OFFLINE_STRONG_FIELDS",
        evidence_fields=json.dumps(sorted(evidence_fields), ensure_ascii=False),
        provider="collected-sources",
        reason="UNIQUE_STRONG_OFFLINE_MATCH",
        detail="naam plus exact bronveld koppelen uniek aan één KVK-nummer",
        evidence_reference=_offline_references(rows),
        verification_status="PROVISIONAL_SOURCE_IDENTITY_MATCH",
    )
    return result


def _hit_value(hit: dict[str, Any], keys: tuple[str, ...]) -> str:
    return str(next((hit[key] for key in keys if hit.get(key) is not None), "")).strip()


def _public_match(
    candidate: dict[str, str],
    features: tuple[set[str], set[str]],
    result: ProviderResult,
) -> dict[str, str]:
    output = _base_result(candidate)
    output["provider"] = str(result.transport)
    output["evidence_reference"] = str(result.evidence)
    if not result.complete:
        output.update(
            terminal_outcome="TECHNICAL_ERROR",
            reason="TRUNCATED_RESULTS",
            detail="zoekresultaat was niet aantoonbaar volledig",
        )
        return output
    websites, places = features
    exact_name_hits: list[tuple[dict[str, Any], str]] = []
    for hit in result.hits:
        name = _hit_value(hit, ("naam", "name", "handelsnaam"))
        number_raw = _hit_value(hit, ("kvkNummer", "kvk_number", "kvk", "nummer"))
        try:
            number = validate_kvk(number_raw)
        except ValueError:
            continue
        if normalize_name(name) == normalize_name(candidate["original_name"]):
            exact_name_hits.append((hit, number))
    if not exact_name_hits:
        output.update(
            terminal_outcome="NO_MATCH",
            reason="NO_EXACT_NAME_HIT",
            detail="volledige zoekactie zonder exact genormaliseerde naam",
        )
        return output

    supported: dict[str, tuple[dict[str, Any], set[str]]] = {}
    for hit, number in exact_name_hits:
        fields: set[str] = set()
        city = normalize_name(_hit_value(hit, ("plaats", "city")))
        website = _website_host(_hit_value(hit, ("website", "url")))
        if city and city in places:
            fields.add("EXACT_NORMALIZED_NAME+SOURCE_PLACE")
        if website and website in websites:
            fields.add("EXACT_NORMALIZED_NAME+WEBSITE_HOST")
        if fields:
            if number in supported:
                supported[number][1].update(fields)
            else:
                supported[number] = (hit, fields)
    if not supported:
        output.update(
            terminal_outcome="AMBIGUOUS",
            match_method="EXACT_NORMALIZED_NAME_ONLY",
            evidence_fields=json.dumps(["EXACT_NORMALIZED_NAME"]),
            reason="SECOND_IDENTITY_FIELD_MISSING",
            detail="naam alleen is onvoldoende voor automatische KVK-koppeling",
        )
        return output
    if len(supported) != 1:
        output.update(
            terminal_outcome="AMBIGUOUS",
            match_method="PUBLIC_FRONTEND_STRONG_FIELDS",
            evidence_fields=json.dumps(
                {number: sorted(fields) for number, (_hit, fields) in sorted(supported.items())}
            ),
            reason="MULTIPLE_PUBLIC_KVK_CANDIDATES",
            detail="meerdere KVK-nummers voldoen aan sterke identiteitsvelden",
        )
        return output
    number, (hit, fields) = next(iter(supported.items()))
    output.update(
        terminal_outcome="MATCHED",
        provisional_kvk=number,
        match_method="PUBLIC_FRONTEND_STRONG_FIELDS",
        evidence_fields=json.dumps(sorted(fields), ensure_ascii=False),
        reason="UNIQUE_STRONG_PUBLIC_MATCH",
        detail="exacte naam plus onafhankelijk bronveld koppelen uniek aan één KVK-nummer",
        observed_legal_form=_hit_value(hit, ("rechtsvorm", "legalForm")),
        observed_status=_hit_value(hit, ("status", "ondernemingsstatus")),
        observed_city=_hit_value(hit, ("plaats", "city")),
        verification_status="PROVISIONAL_PUBLIC_FRONTEND_IDENTITY_MATCH",
    )
    return output


def _technical_result(candidate: dict[str, str], reason: str, detail: str) -> dict[str, str]:
    result = _base_result(candidate)
    result.update(terminal_outcome="TECHNICAL_ERROR", reason=reason, detail=detail)
    return result


def _review_queue(results: list[dict[str, str]], size: int) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for result in results:
        key = f"{result['source_families']}|{result['terminal_outcome']}"
        groups[key].append(result)
    for rows in groups.values():
        rows.sort(
            key=lambda row: hashlib.sha256(("r8-review\0" + row["candidate_id"]).encode()).hexdigest()
        )
    allocation = _even_allocation({key: len(rows) for key, rows in groups.items()}, size)
    selected = [
        row for key in sorted(groups) for row in groups[key][: allocation.get(key, 0)]
    ]
    queue: list[dict[str, str]] = []
    for result in selected:
        queue.append(
            {
                "queue_sha256": "",
                "review_id": hashlib.sha256(
                    ("r8-review\0" + result["candidate_id"] + "\0" + result["terminal_outcome"]).encode()
                ).hexdigest()[:20],
                "candidate_id": result["candidate_id"],
                "source_families": result["source_families"],
                "terminal_outcome": result["terminal_outcome"],
                "original_name": result["original_name"],
                "provisional_kvk": result["provisional_kvk"],
                "match_method": result["match_method"],
                "evidence_fields": result["evidence_fields"],
                "evidence_reference": result["evidence_reference"],
                "review_verdict": "",
                "review_seconds": "",
                "review_notes": "",
            }
        )
    return sorted(queue, key=lambda row: (row["source_families"], row["terminal_outcome"], row["review_id"]))


def _outcome_metrics(results: list[dict[str, str]]) -> dict[str, Any]:
    counts = Counter(row["terminal_outcome"] for row in results)
    per_family: dict[str, dict[str, int]] = {}
    for family in sorted({row["source_families"] for row in results}):
        rows = [row for row in results if row["source_families"] == family]
        per_family[family] = {
            "total": len(rows),
            **{outcome: sum(row["terminal_outcome"] == outcome for row in rows) for outcome in sorted(PILOT_OUTCOMES)},
        }
    total = len(results)
    return {
        "total": total,
        "terminal_counts": {outcome: counts[outcome] for outcome in sorted(PILOT_OUTCOMES)},
        "terminal_outcome_closure": sum(counts.values()) == total,
        "match_rate": counts["MATCHED"] / total,
        "no_match_rate": counts["NO_MATCH"] / total,
        "ambiguous_rate": counts["AMBIGUOUS"] / total,
        "source_conflict_rate": counts["SOURCE_CONFLICT"] / total,
        "technical_error_rate": counts["TECHNICAL_ERROR"] / total,
        "review_rate": sum(
            counts[outcome] for outcome in ("MATCHED", "AMBIGUOUS", "SOURCE_CONFLICT")
        )
        / total,
        "per_source_family": per_family,
    }


def _publish_pilot_outputset(
    run: Run, entries: list[tuple[Path, str, str, str]]
) -> None:
    """Publish the complete pilot and invalidate old review/downstream in one transaction."""
    created_at = datetime.now(UTC).isoformat()
    with run.connect() as connection:
        connection.execute(
            "UPDATE artifacts SET status='STALE' WHERE step='04' AND kind IN "
            "('r8_matching_results','r8_review_queue','r8_matching_report',"
            "'r8_matching_report_md','r8_review_assessment','r8_review_report',"
            "'r8_review_report_md') AND status IN ('COMPLETE','PARTIAL')"
        )
        connection.execute(
            "UPDATE artifacts SET status='STALE' "
            "WHERE CAST(step AS INTEGER)>=5 AND status IN ('COMPLETE','PARTIAL')"
        )
        connection.executemany(
            "INSERT INTO artifacts(path, step, kind, sha256, size, status, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            [
                (
                    str(path.relative_to(run.path)),
                    step,
                    kind,
                    sha256(path),
                    path.stat().st_size,
                    status,
                    created_at,
                )
                for path, step, kind, status in entries
            ],
        )


def _publish_review_outputset(
    run: Run,
    entries: list[tuple[Path, str, str, str]],
    queue_path: Path,
    queue_hash: str,
) -> None:
    """Replace the active R8 review as one database transaction."""
    created_at = datetime.now(UTC).isoformat()
    with run.connect() as connection:
        current = connection.execute(
            "SELECT path,sha256,size FROM artifacts WHERE step='04' "
            "AND kind='r8_review_queue' AND status='COMPLETE' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        expected_path = str(queue_path.relative_to(run.path))
        if (
            current is None
            or current["path"] != expected_path
            or current["sha256"] != queue_hash
            or int(current["size"]) != queue_path.stat().st_size
        ):
            raise HarvestError("R8-reviewqueue veranderde tijdens de beoordeling")
        connection.execute(
            "UPDATE artifacts SET status='STALE' "
            "WHERE step='04' AND kind IN "
            "('r8_review_assessment','r8_review_report','r8_review_report_md') "
            "AND status IN ('COMPLETE','PARTIAL')"
        )
        connection.executemany(
            "INSERT INTO artifacts(path, step, kind, sha256, size, status, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            [
                (
                    str(path.relative_to(run.path)),
                    step,
                    kind,
                    sha256(path),
                    path.stat().st_size,
                    status,
                    created_at,
                )
                for path, step, kind, status in entries
            ],
        )


def run_matching_pilot(
    run: Run,
    provider_name: str = "auto",
    interval: float = 2.0,
    refresh: bool = False,
    review_size: int = 20,
    max_live: int | None = None,
    provider_override: Provider | None = None,
) -> tuple[Path, Path, Path, Path]:
    """Execute the bounded R8 pilot with strong-field matching and terminal closure."""
    if (
        not math.isfinite(interval)
        or interval < 0
        or (provider_override is None and interval < 2.0)
        or review_size < 1
        or (max_live is not None and max_live < 0)
    ):
        raise HarvestError("R8 interval-, review- en livelimieten zijn ongeldig")
    pilot_path = run.latest_artifact("03", "r8_pilot_selection")
    sample_path = run.latest_artifact("03", "r6_source_sample")
    queue_path = run.latest_artifact("03", "r6_review_queue")
    review_report_path = run.latest_artifact("03", "r6_review_report")
    if (
        pilot_path is None
        or sample_path is None
        or queue_path is None
        or review_report_path is None
    ):
        raise HarvestError("R8 vereist een complete en beoordeelde R6-sample")
    pilot_hash = _require_registered_integrity(run, pilot_path, "03", "r8_pilot_selection")
    _require_registered_integrity(run, sample_path, "03", "r6_source_sample")
    queue_hash = _require_registered_integrity(run, queue_path, "03", "r6_review_queue")
    _require_registered_integrity(run, review_report_path, "03", "r6_review_report")
    review_report = json.loads(review_report_path.read_text(encoding="utf-8"))
    review_config = run.metadata().get("runtime_config", {}).get("r6_review", {})
    if (
        review_report.get("status") != "PASS"
        or review_report.get("queue_sha256") != queue_hash
        or not isinstance(review_config, dict)
        or review_config.get("status") != "PASS"
        or review_config.get("queue_sha256") != queue_hash
    ):
        raise HarvestError("R8 vereist een actuele R6-review met status PASS")

    pilot = read_tsv(pilot_path)
    sample = read_tsv(sample_path)
    if not pilot:
        raise HarvestError("R8-pilotselectie is leeg")
    if any(row.get("source_kvk_hint") for row in pilot):
        raise HarvestError("R8-pilot bevat onverwacht al een direct KVK-nummer")
    sample_by_relation = {(row["source_id"], row["source_row"]): row for row in sample}
    indexed, source_artifacts, source_artifacts_fingerprint = _offline_index(run, pilot)
    provider = provider_override or _provider_for_run(run, provider_name)
    results: list[dict[str, str]] = []
    live_calls = 0
    evidence_paths: set[Path] = set()
    started = time.monotonic()
    stop_reason: str | None = None
    with run.lock(), ProviderLock(run):
        if refresh:
            with run.connect() as connection:
                connection.execute("DELETE FROM kvk_requests WHERE candidate_id LIKE 'r8:%'")
        with run.connect() as connection:
            connection.execute(
                "UPDATE kvk_requests SET state='SENT_OUTCOME_UNKNOWN',error='INTERRUPTED_BEFORE_DURABLE_OUTCOME' "
                "WHERE candidate_id LIKE 'r8:%' AND state='IN_FLIGHT'"
            )
        for candidate in pilot:
            journal_id = f"r8:{candidate['candidate_id']}"
            features = _candidate_features(candidate, sample_by_relation)
            fingerprint = hashlib.sha256(
                json.dumps(
                    {
                        "candidate": candidate,
                        "features": [sorted(features[0]), sorted(features[1])],
                        "pilot_sha256": pilot_hash,
                        "provider": provider.name,
                        "query_policy": "DIRECT_KVK_ONLY_V1",
                        "source_artifacts_fingerprint": source_artifacts_fingerprint,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            outcome: dict[str, str] | None = None
            if stop_reason:
                outcome = _technical_result(
                    candidate, "NOT_PROCESSED_INTERRUPTED", stop_reason
                )
            else:
                with run.connect() as connection:
                    prior = connection.execute(
                        "SELECT state,result_json,request_fingerprint FROM kvk_requests "
                        "WHERE candidate_id=?",
                        (journal_id,),
                    ).fetchone()
                if (
                    prior
                    and prior["state"] == "SUCCEEDED"
                    and prior["result_json"]
                    and prior["request_fingerprint"] == fingerprint
                    and not refresh
                ):
                    previous = json.loads(prior["result_json"])
                    previous_evidence = str(previous.get("evidence_reference", ""))
                    previous_path = _evidence_file(run, previous_evidence)
                    if previous_path is not None:
                        evidence_paths.add(previous_path)
                    results.append(previous)
                    continue
                outcome = _offline_match(candidate, features, indexed)
            if outcome is None and not candidate.get("source_kvk_hint"):
                outcome = _technical_result(
                    candidate, "NO_DIRECT_KVK_HINT",
                    "geen direct bron-KVK-nummer; publieke naamzoeking uitgeschakeld",
                )
            if outcome is None and max_live is not None and live_calls >= max_live:
                outcome = _technical_result(
                    candidate,
                    "PILOT_LIVE_LIMIT_NOT_ATTEMPTED",
                    "ingestelde begrensde live-calllimiet bereikt",
                )
            if outcome is None:
                with run.connect() as connection:
                    connection.execute(
                        "INSERT INTO kvk_requests(candidate_id,query,state,attempt,request_fingerprint,provider) "
                        "VALUES(?,?,'IN_FLIGHT',1,?,?) ON CONFLICT(candidate_id) DO UPDATE SET "
                        "state='IN_FLIGHT',attempt=attempt+1,request_fingerprint=excluded.request_fingerprint,"
                        "provider=excluded.provider,result_json=NULL,error=NULL",
                        (journal_id, validate_kvk(candidate["source_kvk_hint"]), fingerprint, provider.name),
                    )
                try:
                    _check_cooldown(run)
                    provider_result = provider.search(validate_kvk(candidate["source_kvk_hint"]))
                    live_calls += 1
                    evidence_path = run.path / provider_result.evidence
                    if evidence_path.is_file():
                        evidence_paths.add(evidence_path)
                        run.register_artifact(evidence_path, "04", f"evidence_{provider_result.transport}")
                    outcome = _public_match(candidate, features, provider_result)
                except KvkError as exc:
                    live_calls += 1
                    outcome = _technical_result(candidate, exc.reason, str(exc))
                    outcome["provider"] = provider.name
                    if exc.reason in {"PUBLIC_ACCESS_BLOCKED", "RATE_LIMITED", "PROVIDER_LOCKED"}:
                        stop_reason = exc.reason
                except HarvestError as exc:
                    outcome = _technical_result(candidate, "RATE_LIMITED", str(exc))
                    outcome["provider"] = provider.name
                    stop_reason = "RATE_LIMITED"
                except KeyboardInterrupt:
                    with run.connect() as connection:
                        connection.execute(
                            "UPDATE kvk_requests SET state='SENT_OUTCOME_UNKNOWN',error='INTERRUPTED' "
                            "WHERE candidate_id=?",
                            (journal_id,),
                        )
                    raise
                if interval > 0 and not stop_reason:
                    time.sleep(interval + random.uniform(0, min(0.25, interval / 4)))
            assert outcome is not None
            evidence_reference = outcome.get("evidence_reference", "")
            current_evidence_path = _evidence_file(run, evidence_reference)
            if current_evidence_path is not None:
                evidence_paths.add(current_evidence_path)
            results.append(outcome)
            terminal_outcome = outcome["terminal_outcome"]
            if outcome["reason"] == "NO_DIRECT_KVK_HINT":
                journal_state = "SUCCEEDED"  # afgeronde offline beslissing, geen GET
            elif terminal_outcome == "TECHNICAL_ERROR":
                journal_state = (
                    "DEFERRED"
                    if outcome["reason"]
                    in {"NOT_PROCESSED_INTERRUPTED", "PILOT_LIVE_LIMIT_NOT_ATTEMPTED"}
                    else "FAILED"
                )
            else:
                journal_state = "SUCCEEDED"
            with run.connect() as connection:
                connection.execute(
                    "INSERT INTO kvk_requests(candidate_id,query,state,attempt,request_fingerprint,provider,"
                    "checked_at,result_json,evidence_path,error) VALUES(?,?,?,1,?,?,?, ?,?,?) "
                    "ON CONFLICT(candidate_id) DO UPDATE SET state=excluded.state,checked_at=excluded.checked_at,"
                    "result_json=excluded.result_json,evidence_path=excluded.evidence_path,error=excluded.error,"
                    "request_fingerprint=excluded.request_fingerprint,provider=excluded.provider",
                    (
                        journal_id,
                        candidate.get("source_kvk_hint", ""),
                        journal_state,
                        fingerprint,
                        outcome["provider"] or provider.name,
                        outcome["checked_at"],
                        json.dumps(outcome, ensure_ascii=False, separators=(",", ":")),
                        outcome["evidence_reference"],
                        "" if journal_state == "SUCCEEDED" else outcome["reason"],
                    ),
                )

    results.sort(key=lambda row: row["candidate_id"])
    metrics = _outcome_metrics(results)
    if not metrics["terminal_outcome_closure"] or len(results) != len(pilot):
        raise HarvestError("R8 terminale outcome-closure is niet gesloten")
    review = _review_queue(results, min(review_size, len(results)))
    result_path = run.artifact_path("04", "r8_matching_results", "csv")
    review_path = run.artifact_path("04", "r8_review_queue", "csv")
    report_path = run.artifact_path("04", "r8_matching_report", "json")
    md_path = run.artifact_path("04", "r8_matching_report", "md")
    write_tsv(result_path, RESULT_HEADERS, results)
    write_tsv(review_path, REVIEW_HEADERS, review)
    report = {
        "r8_matching_report_schema_version": PILOT_REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "pilot_sha256": pilot_hash,
        "source_artifacts": source_artifacts,
        "source_artifacts_fingerprint": source_artifacts_fingerprint,
        "r6_review_queue_sha256": queue_hash,
        "provider": provider.name,
        "configured_interval_seconds": interval,
        "configured_max_live": max_live,
        "live_calls": live_calls,
        "metrics": metrics,
        "review": {"status": "PENDING", "records": len(review)},
        "threshold_policy": {
            "status": "PREDECLARED_FORMULA",
            "set_after_review_only_if_technical_error_rate_at_most": 0.05,
            "match_rate_floor": "max(0.10, floor(measured_match_rate*0.8, 2 decimals))",
            "ambiguous_rate_ceiling": "min(0.50, ceil(measured_ambiguous_rate+0.10, 2 decimals))",
            "false_match_count": 0,
            "terminal_outcome_closure": 1.0,
        },
        "semantics": {
            "kvk_numbers": "PROVISIONAL_IDENTITY_MATCH_UNTIL_SEPARATE_VERIFICATION",
            "legal_form": "SOURCE_OBSERVATION_NOT_VERIFIED",
            "status": "SOURCE_OBSERVATION_NOT_VERIFIED",
            "name_only_auto_match": False,
        },
        "resources": {
            "duration_seconds": round(time.monotonic() - started, 6),
            "seconds_per_candidate": round((time.monotonic() - started) / len(results), 6),
            "evidence_bytes": sum(path.stat().st_size for path in evidence_paths),
        },
    }
    atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    atomic_write(
        md_path,
        "\n".join(
            [
                "# R8 KVK-nummermatchingpilot",
                "",
                f"- Kandidaten / closure: {len(results)} / {metrics['terminal_outcome_closure']}",
                f"- Matches: {metrics['terminal_counts']['MATCHED']}",
                f"- No-match / ambigu: {metrics['terminal_counts']['NO_MATCH']} / {metrics['terminal_counts']['AMBIGUOUS']}",
                f"- Bronconflict / technisch: {metrics['terminal_counts']['SOURCE_CONFLICT']} / {metrics['terminal_counts']['TECHNICAL_ERROR']}",
                f"- Live calls: {live_calls}",
                f"- Reviewqueue: {len(review)} (PENDING)",
                "",
                "KVK-nummers zijn voorlopige identiteitsmatches; rechtsvorm en status blijven bronobservaties.",
                "",
            ]
        ),
    )
    outputset = [
        (result_path, "04", "r8_matching_results", "COMPLETE"),
        (review_path, "04", "r8_review_queue", "COMPLETE"),
        (report_path, "04", "r8_matching_report", "COMPLETE"),
        (md_path, "04", "r8_matching_report_md", "COMPLETE"),
    ]
    config = {
        "pilot_sha256": pilot_hash,
        "source_artifacts_fingerprint": source_artifacts_fingerprint,
        "provider": provider_name,
        "interval": interval,
        "max_live": max_live,
        "refresh": refresh,
        "report_sha256": sha256(report_path),
    }
    run.record_config("r8_matching", {**config, "status": "PUBLISHING"})
    run.record_config("r8_review", {"status": "PENDING", "queue_sha256": sha256(review_path)})
    _publish_pilot_outputset(run, outputset)
    run.log("INFO", "downstream_invalidated", from_step=5, reason="r8_pilot_changed")
    run.record_config(
        "r8_matching",
        {**config, "status": "COMPLETE"},
    )
    run.update_status("IN_PROGRESS", "04")
    return result_path, review_path, report_path, md_path


def record_matching_review(run: Run, assessment: Path) -> tuple[Path, Path, Path]:
    """Record manual R8 review and derive R9 thresholds using the predeclared formula."""
    queue_path = run.latest_artifact("04", "r8_review_queue")
    report_path = run.latest_artifact("04", "r8_matching_report")
    results_path = run.latest_artifact("04", "r8_matching_results")
    if not queue_path or not report_path or not results_path:
        raise HarvestError("geen complete R8-pilot om te beoordelen")
    queue_hash = _require_registered_integrity(run, queue_path, "04", "r8_review_queue")
    _require_registered_integrity(run, report_path, "04", "r8_matching_report")
    _require_registered_integrity(run, results_path, "04", "r8_matching_results")
    source = assessment.expanduser().resolve()
    if not source.is_file():
        raise HarvestError("R8-reviewassessment ontbreekt")
    queue = read_tsv(queue_path)
    if len({row["review_id"] for row in queue}) != len(queue):
        raise HarvestError("R8-reviewqueue bevat dubbele review-ID's")
    supplied = read_tsv(source)
    required = {"queue_sha256", "review_id", "review_verdict", "review_seconds", "review_notes"}
    if not supplied or not required.issubset(supplied[0]):
        raise HarvestError("R8-reviewassessment mist verplichte kolommen")
    by_id: dict[str, dict[str, str]] = {}
    for row in supplied:
        if row["queue_sha256"].strip() != queue_hash:
            raise HarvestError("R8-reviewassessment hoort niet bij de actuele queue")
        review_id = row["review_id"].strip()
        verdict = row["review_verdict"].strip().upper()
        try:
            seconds = float(row["review_seconds"])
        except ValueError as exc:
            raise HarvestError("R8-reviewtijd is geen getal") from exc
        if not review_id or review_id in by_id or not math.isfinite(seconds) or seconds < 0:
            raise HarvestError("R8-review bevat lege/dubbele ID of ongeldige tijd")
        if verdict not in REVIEW_VERDICTS:
            raise HarvestError("R8-review bevat een onbekend verdict")
        by_id[review_id] = {
            "queue_sha256": queue_hash,
            "review_id": review_id,
            "review_verdict": verdict,
            "review_seconds": f"{seconds:.3f}",
            "review_notes": row["review_notes"].strip(),
        }
    expected = {row["review_id"] for row in queue}
    if set(by_id) != expected:
        raise HarvestError("R8-review sluit niet exact op de actuele queue")
    rows = [by_id[key] for key in sorted(by_id)]
    counts = Counter(row["review_verdict"] for row in rows)
    pilot_report = json.loads(report_path.read_text(encoding="utf-8"))
    metrics = pilot_report["metrics"]
    pilot_results = read_tsv(results_path)
    if (
        len({row["candidate_id"] for row in pilot_results}) != len(pilot_results)
        or any(row["terminal_outcome"] not in PILOT_OUTCOMES for row in pilot_results)
        or _outcome_metrics(pilot_results) != metrics
    ):
        raise HarvestError("R8-resultaten sluiten niet op het geregistreerde pilotrapport")
    technical_ok = float(metrics["technical_error_rate"]) <= 0.05
    review_pass = not counts["FALSE_MATCH"] and not counts["UNCERTAIN"]
    status = "PASS" if technical_ok and review_pass else "CHANGES_REQUIRED"
    thresholds: dict[str, Any]
    if status == "PASS":
        match_floor = max(0.10, int(float(metrics["match_rate"]) * 80) / 100)
        ambiguous_ceiling = min(
            0.50, (int((float(metrics["ambiguous_rate"]) + 0.10) * 100 + 0.999999)) / 100
        )
        thresholds = {
            "terminal_outcome_closure": 1.0,
            "false_match_count": 0,
            "technical_error_rate_max": 0.05,
            "match_rate_min": match_floor,
            "ambiguous_rate_max": ambiguous_ceiling,
        }
    else:
        thresholds = {"status": "NOT_SET_UNSUCCESSFUL_PILOT"}
    pilot_decision = (
        "GO_R9_METRICS"
        if status == "PASS"
        and float(metrics["match_rate"]) >= float(thresholds["match_rate_min"])
        and float(metrics["ambiguous_rate"]) <= float(thresholds["ambiguous_rate_max"])
        else "NO_GO_R8_QUALITY_OR_YIELD"
    )
    assessment_path = run.artifact_path("04", "r8_review_assessment", "csv")
    output_report = run.artifact_path("04", "r8_review_report", "json")
    md_path = run.artifact_path("04", "r8_review_report", "md")
    write_tsv(
        assessment_path,
        ["queue_sha256", "review_id", "review_verdict", "review_seconds", "review_notes"],
        rows,
    )
    total_seconds = sum(float(row["review_seconds"]) for row in rows)
    report = {
        "r8_review_report_schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "queue_sha256": queue_hash,
        "reviewed_records": len(rows),
        "verdict_counts": dict(sorted(counts.items())),
        "review_seconds_total": round(total_seconds, 3),
        "review_seconds_per_record": round(total_seconds / len(rows), 3),
        "closure": "CLOSED",
        "status": status,
        "pilot_decision": pilot_decision,
        "r9_thresholds": thresholds,
    }
    atomic_write(output_report, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    atomic_write(
        md_path,
        "\n".join(
            [
                "# R8 handmatige review en R9-thresholds",
                "",
                f"- Beoordeeld: {len(rows)}",
                f"- Confirmed / false / uncertain: {counts['CONFIRMED']} / {counts['FALSE_MATCH']} / {counts['UNCERTAIN']}",
                f"- Reviewseconden totaal/per record: {total_seconds:.3f} / {total_seconds / len(rows):.3f}",
                f"- Status: **{status}**",
                f"- Pilotbesluit: **{pilot_decision}**",
                f"- R9-thresholds: `{json.dumps(thresholds, sort_keys=True)}`",
                "",
            ]
        ),
    )
    _publish_review_outputset(
        run,
        [
            (assessment_path, "04", "r8_review_assessment", "COMPLETE"),
            (output_report, "04", "r8_review_report", "COMPLETE"),
            (md_path, "04", "r8_review_report_md", "COMPLETE"),
        ],
        queue_path,
        queue_hash,
    )
    run.record_config(
        "r8_review",
        {
            "status": status,
            "pilot_decision": pilot_decision,
            "queue_sha256": queue_hash,
            "thresholds": thresholds,
        },
    )
    return assessment_path, output_report, md_path
