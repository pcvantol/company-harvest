"""Maak één verliesvrije, voorlopig gededupliceerde bronlijst vóór KVK-verificatie."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from company_harvest.core import (
    HarvestError,
    Run,
    atomic_write,
    normalize_name,
    sha256,
    timestamp,
    validate_kvk,
)
from company_harvest.sources import RAW_HEADERS

SOURCE_IDS = (
    "ind_arbeid",
    "wikidata_nl_companies",
    "gleif_golden_copy",
    "anbi_register",
    "duo_education_organisations",
)
MASTER_HEADERS = [
    "candidate_id", "original_name", "normalized_name", "source_kvk_hint",
    "country", "city", "website", "sector", "source_relations",
    "source_payloads_json", "source_count", "dedup_status", "kvk_queue_status",
    "conflict_reason",
]


def _registered(run: Run, step: str, kind: str) -> tuple[Path, str]:
    path = run.latest_artifact(step, kind)
    if path is None or not path.is_file():
        raise HarvestError(f"volledig bronartefact ontbreekt: {kind}")
    with run.connect() as connection:
        entry = connection.execute(
            "SELECT sha256,size,status FROM artifacts WHERE path=? AND step=? AND kind=?",
            (str(path.relative_to(run.path)), step, kind),
        ).fetchone()
    digest = sha256(path)
    if not entry or entry["status"] != "COMPLETE" or entry["size"] != path.stat().st_size or entry["sha256"] != digest:
        raise HarvestError(f"bronartefact wijkt af van COMPLETE-registratie: {kind}")
    return path, digest


def _validate_scope(run: Run, source_id: str, path: Path, digest: str) -> dict[str, Any]:
    if source_id in {"ind_arbeid", "wikidata_nl_companies"}:
        observations = run.metadata().get("runtime_config", {}).get("source_observations", {})
        observation = observations.get(source_id) if isinstance(observations, dict) else None
        if not isinstance(observation, dict) or observation.get("limit") is not None or observation.get("collection_complete") is not True:
            raise HarvestError(f"{source_id} is niet aantoonbaar volledig verzameld")
        bound = observation.get("source_artifact")
        if bound != {"path": str(path.relative_to(run.path)), "sha256": digest, "size": path.stat().st_size}:
            raise HarvestError(f"{source_id} heeft geen actuele full-scope-bronbinding")
        expected = observation.get("response_count")
        bound_evidence = observation.get("evidence_artifacts")
        if (not isinstance(expected, int) or expected < 1
                or not isinstance(bound_evidence, list) or len(bound_evidence) != expected
                or len({str(item.get("path")) for item in bound_evidence if isinstance(item, dict)}) != expected):
            raise HarvestError(f"{source_id} mist volledige response-evidence")
        for bound_entry in bound_evidence:
            if not isinstance(bound_entry, dict):
                raise HarvestError(f"{source_id} heeft ongeldige response-evidencebinding")
            with run.connect() as connection:
                entry = connection.execute(
                    "SELECT path,sha256,size FROM artifacts WHERE path=? AND step='02' AND kind=? AND status='COMPLETE'",
                    (bound_entry.get("path"), f"evidence_{source_id}"),
                ).fetchone()
            if not entry:
                raise HarvestError(f"{source_id} mist geregistreerde response-evidence")
            evidence_path = run.path / entry["path"]
            if (not evidence_path.is_file() or
                    bound_entry != {"path": entry["path"], "sha256": entry["sha256"], "size": entry["size"]} or
                    evidence_path.stat().st_size != entry["size"] or sha256(evidence_path) != entry["sha256"]):
                raise HarvestError(f"{source_id} heeft afwijkende response-evidence")
        return {"scope": "FULL_SOURCE", "response_count": expected}
    report_kind = "gleif_ingest_report" if source_id == "gleif_golden_copy" else f"{source_id}_ingest_report"
    report_path, report_hash = _registered(run, "02", report_kind)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    closure = report.get("count_closure")
    if (report.get("source_id") != source_id or report.get("scope") != "FULL_ARCHIVE"
            or report.get("configured_limit") is not None or not isinstance(closure, dict)
            or not closure or set(closure.values()) != {"CLOSED"}):
        raise HarvestError(f"{source_id} heeft geen complete full-archive-inname")
    if report.get("candidate_artifact") != {"path": str(path.relative_to(run.path)),
                                           "sha256": digest, "size": path.stat().st_size}:
        raise HarvestError(f"{source_id} heeft geen actuele full-archive-bronbinding")
    evidence_path, evidence_hash = _registered(run, "02", f"evidence_{source_id}")
    if evidence_path.name != report.get("evidence_file") or evidence_hash != report.get("evidence_sha256"):
        raise HarvestError(f"{source_id} heeft afwijkende archivevidence")
    return {"scope": "FULL_ARCHIVE", "report_sha256": report_hash,
            "evidence_sha256": evidence_hash,
            "candidate_records": report.get("counts", {}).get("candidate_records")}


def _source_inputs(run: Run, source_ids: tuple[str, ...] = SOURCE_IDS) -> list[tuple[str, Path, str, dict[str, Any]]]:
    inputs = []
    for source_id in source_ids:
        path, digest = _registered(run, "02", f"source_{source_id}")
        scope = _validate_scope(run, source_id, path, digest)
        inputs.append((source_id, path, digest, scope))
    return inputs


def _write_group(
    writer: csv.DictWriter[str], rows: list[dict[str, str]],
    cross_name_hints: set[str], stats: Counter[str], preview: bool = False
) -> None:
    normalized = rows[0]["normalized_name"]
    hints = {row["source_kvk_hint"] for row in rows if row["source_kvk_hint"]}
    by_hint: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row["source_kvk_hint"]:
            by_hint.setdefault(row["source_kvk_hint"], []).append(row)
        else:
            by_hint[f"NO_HINT:{row['source_id']}:{row['source_row']}"] = [row]
    for key, group in sorted(by_hint.items()):
        hint = "" if key.startswith("NO_HINT:") else key
        payloads = [json.loads(row["payload_json"]) for row in group]
        chosen = payloads[0]
        relations = [
            {"source_id": item["source_id"], "row": item["source_row"],
             "url": item["source_url"], "name": item["original_name"],
             "evidence_reference": item["evidence_reference"]}
            for item in payloads
        ]
        stable = "\0".join(f"{item['source_id']}:{item['source_row']}" for item in payloads)
        candidate_id = hashlib.sha256(f"pre-kvk-v1\0{normalized}\0{hint}\0{stable}".encode()).hexdigest()[:24]
        conflict = len(hints) > 1 or hint in cross_name_hints
        status = ("SOURCE_CONFLICT" if conflict else "MERGED_DIRECT_HINT"
                  if len(group) > 1 else "KEPT_SINGLE")
        queue = ("BLOCKED_SOURCE_INCOMPLETE" if preview else "REVIEW_REQUIRED" if conflict
                 else "READY_FOR_KVK_MATCHING" if not hint else "READY_FOR_KVK_VERIFICATION")
        evidence = chosen.get("nl_evidence", "")
        city = evidence.rsplit("; plaats=", 1)[1] if "; plaats=" in evidence else ""
        writer.writerow({
            "candidate_id": candidate_id,
            "original_name": chosen["original_name"],
            "normalized_name": normalized,
            "source_kvk_hint": hint,
            "country": chosen.get("country", ""),
            "city": city,
            "website": chosen.get("website", ""),
            "sector": chosen.get("sector", ""),
            "source_relations": json.dumps(relations, ensure_ascii=False, separators=(",", ":")),
            "source_payloads_json": json.dumps(payloads, ensure_ascii=False, separators=(",", ":")),
            "source_count": len(group),
            "dedup_status": status,
            "kvk_queue_status": queue,
            "conflict_reason": ("SAME_NORMALIZED_NAME_MULTIPLE_KVK_HINTS" if len(hints) > 1
                                else "SAME_KVK_HINT_DIFFERENT_NORMALIZED_NAMES" if hint in cross_name_hints
                                else ""),
        })
        stats["master_rows"] += 1
        stats["represented_source_rows"] += len(group)
        stats[status] += 1
        stats[queue] += 1
        stats["merged_source_rows"] += len(group) - 1


def _build_pre_kvk_list_unlocked(run: Run, preview: bool = False) -> tuple[Path, Path]:
    """Fail-closed op vijf volledige bronnen; geen netwerk en geen KVK-aanroep."""
    source_ids = tuple(source_id for source_id in SOURCE_IDS if source_id != "wikidata_nl_companies") if preview else SOURCE_IDS
    inputs = _source_inputs(run, source_ids)
    required_space = max(512 * 1024 * 1024, 6 * sum(path.stat().st_size for _, path, _, _ in inputs))
    if shutil.disk_usage(run.path).free < required_space:
        raise HarvestError("onvoldoende vrije ruimte voor verliesvrije pre-KVK-lijst")
    output_kind = "pre_kvk_blocked_preview" if preview else "pre_kvk_master"
    report_kind = "pre_kvk_blocked_preview_report" if preview else "pre_kvk_report"
    output = run.artifact_path("03", output_kind, "tsv")
    report_path = run.artifact_path("03", report_kind, "json")
    temporary = output.with_name(f".{output.name}.tmp")
    spool = run.path / f".{timestamp()}_pre_kvk.sqlite3"
    counts: Counter[str] = Counter()
    per_source: dict[str, int] = {}
    try:
        with sqlite3.connect(spool) as connection:
            connection.execute(
                "CREATE TABLE raw(normalized_name TEXT NOT NULL, source_kvk_hint TEXT NOT NULL, "
                "source_id TEXT NOT NULL, source_row TEXT NOT NULL, payload_json TEXT NOT NULL, "
                "UNIQUE(source_id,source_row))"
            )
            for source_id, path, _digest, scope in inputs:
                source_count = 0
                with path.open(encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle, delimiter="\t")
                    if not set(RAW_HEADERS).issubset(reader.fieldnames or []):
                        raise HarvestError(f"{source_id} mist verplichte ruwe kolommen")
                    for row in reader:
                        if row["source_id"] != source_id or not row["source_row"] or not normalize_name(row["original_name"]):
                            raise HarvestError(f"{source_id} bevat ongeldige bronidentiteit")
                        hint = row["source_kvk_hint"]
                        if hint:
                            try:
                                validate_kvk(hint)
                            except ValueError as exc:
                                raise HarvestError(f"{source_id} bevat ongeldige directe KVK-hint") from exc
                        connection.execute(
                            "INSERT INTO raw VALUES (?,?,?,?,?)",
                            (normalize_name(row["original_name"]), hint, source_id,
                             row["source_row"], json.dumps(row, ensure_ascii=False, separators=(",", ":"))),
                        )
                        source_count += 1
                if "candidate_records" in scope and scope["candidate_records"] != source_count:
                    raise HarvestError(f"{source_id} bronrapport en kandidaataantal wijken af")
                per_source[source_id] = source_count
                counts["input_source_rows"] += source_count
            connection.execute("CREATE INDEX raw_name ON raw(normalized_name,source_kvk_hint,source_id,source_row)")
            cross_name_hints = {
                row[0] for row in connection.execute(
                    "SELECT source_kvk_hint FROM raw WHERE source_kvk_hint<>'' "
                    "GROUP BY source_kvk_hint HAVING COUNT(DISTINCT normalized_name)>1"
                )
            }
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=MASTER_HEADERS, delimiter="\t")
                writer.writeheader()
                current_name = ""
                group: list[dict[str, str]] = []
                for normalized, hint, source_id, source_row, payload in connection.execute(
                    "SELECT normalized_name,source_kvk_hint,source_id,source_row,payload_json "
                    "FROM raw ORDER BY normalized_name,source_kvk_hint,source_id,source_row"
                ):
                    if current_name and normalized != current_name:
                        _write_group(writer, group, cross_name_hints, counts, preview)
                        group = []
                    current_name = normalized
                    group.append({"normalized_name": normalized, "source_kvk_hint": hint,
                                  "source_id": source_id, "source_row": source_row,
                                  "payload_json": payload})
                if group:
                    _write_group(writer, group, cross_name_hints, counts, preview)
                handle.flush()
                os.fsync(handle.fileno())
        if counts["represented_source_rows"] != counts["input_source_rows"]:
            raise HarvestError("pre-KVK-input sluit niet op masterlijst")
        if _source_inputs(run, source_ids) != inputs:
            raise HarvestError("pre-KVK-bronnen veranderden tijdens lijstbouw")
        os.replace(temporary, output)
        report = {
            "schema_version": 1,
            "status": "BLOCKED_PREVIEW_NOT_KVK_READY" if preview else "COMPLETE_PRE_KVK_NOT_VERIFIED",
            "run_id": run.path.name,
            "scope": list(source_ids),
            "excluded_incomplete_sources": ["wikidata_nl_companies"] if preview else [],
            "sources": {source_id: {"candidate_rows": per_source[source_id],
                                     "artifact_sha256": digest, **scope}
                        for source_id, _path, digest, scope in inputs},
            "counts": dict(counts),
            "closure": "CLOSED_INCLUDED_SCOPE_ONLY" if preview else "CLOSED",
            "master_sha256": sha256(output),
            "master_bytes": output.stat().st_size,
            "kvk_requests": 0,
        }
        atomic_write(report_path, json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        run.register_artifact_set([
            (output, "03", output_kind, "COMPLETE"),
            (report_path, "03", report_kind, "COMPLETE"),
        ])
        run.record_config("pre_kvk_preview" if preview else "pre_kvk_list",
                          {"source_sha256": {sid: digest for sid, _p, digest, _s in inputs},
                           "master_sha256": report["master_sha256"]})
        if not preview:
            run.update_status("PRE_KVK_COMPLETE", "03")
        return output, report_path
    except sqlite3.IntegrityError as exc:
        raise HarvestError("dubbele bronrij-identiteit in pre-KVK-input") from exc
    finally:
        temporary.unlink(missing_ok=True)
        spool.unlink(missing_ok=True)


def build_pre_kvk_list(run: Run) -> tuple[Path, Path]:
    """Bouw offline onder run-lock; gewijzigde inputs stoppen publicatie."""
    with run.lock():
        return _build_pre_kvk_list_unlocked(run)


def build_blocked_pre_kvk_preview(run: Run) -> tuple[Path, Path]:
    """Maak alleen de vier complete bronnen zichtbaar; nooit KVK-klaar."""
    with run.lock():
        if run.metadata().get("status") != "PRE_KVK_BLOCKED":
            raise HarvestError("voorlopige vierbronnenlijst vereist een geblokkeerde run")
        if run.latest_artifact("02", "source_wikidata_nl_companies") is not None:
            raise HarvestError("Wikidata heeft al een bronartefact; bouw de vijfbronnenlijst")
        return _build_pre_kvk_list_unlocked(run, preview=True)
