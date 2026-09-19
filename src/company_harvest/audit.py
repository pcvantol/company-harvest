"""Integriteitscontrole en lokale herleidbaarheid."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from company_harvest.core import HarvestError, Run, read_tsv, sha256, validate_kvk
from company_harvest.kvk_scope import scope_details


def verify(run: Run) -> dict[str, Any]:
    errors: list[str] = []
    checked = 0
    with run.connect() as connection:
        artifacts = connection.execute("SELECT path,kind,sha256,size,status FROM artifacts ORDER BY id").fetchall()
        latest_statuses = connection.execute("SELECT a.id,a.step,a.kind,a.status,a.path FROM artifacts a JOIN (SELECT kind,MAX(id) id FROM artifacts GROUP BY kind) latest ON a.id=latest.id").fetchall()
    latest_by_kind = {row["kind"]: row for row in latest_statuses}
    def current_output(kind: str) -> Any:
        row = latest_by_kind.get(kind)
        return run.path / row["path"] if row and row["status"] in {"COMPLETE", "PARTIAL"} else None

    errors.extend(f"STALE:{row['kind']}" for row in latest_statuses if row["status"] == "STALE")
    for row in artifacts:
        path = run.path / row["path"]
        checked += 1
        if not path.is_file():
            errors.append(f"MISSING:{row['path']}")
            continue
        if path.stat().st_size != row["size"]:
            errors.append(f"SIZE:{row['path']}")
        if sha256(path) != row["sha256"]:
            errors.append(f"HASH:{row['path']}")
    metadata = run.metadata()
    expected_config = hashlib.sha256(json.dumps({"workflow": metadata["workflow"], "target": metadata["target"], "runtime_config": metadata.get("runtime_config", {})}, sort_keys=True).encode()).hexdigest()
    if metadata.get("config_fingerprint") != expected_config:
        errors.append("CONFIG:fingerprint_mismatch")
    registered_paths = {row["path"] for row in artifacts}
    with run.connect() as connection:
        requests = connection.execute("SELECT candidate_id,state,evidence_path FROM kvk_requests ORDER BY id").fetchall()
    for request in requests:
        evidence = request["evidence_path"]
        if evidence and (evidence not in registered_paths or not (run.path / evidence).is_file()):
            errors.append(f"EVIDENCE:{request['candidate_id']}")
    if metadata["workflow"] == "MERGE_LISTS":
        merged = run.latest_artifact("09", "merged_csv")
        conflicts = run.latest_artifact("09", "conflicts")
        if merged:
            merged_rows = read_tsv(merged)
            numbers = [row.get("KVK-nummer", "") for row in merged_rows]
            if len(numbers) != len(set(numbers)):
                errors.append("COUNT:duplicate_kvk_in_merged")
            if conflicts:
                excluded = {row["KVK-nummer"] for row in read_tsv(conflicts) if row.get("included") == "false"}
                if excluded.intersection(numbers):
                    errors.append("RELATION:excluded_conflict_present_in_merged")
    else:
        exported = metadata.get("status") in {"EXPORT_COMPLETE", "PARTIAL_EXPORTED"}
        try:
            scope = scope_details(run)
        except HarvestError:
            scope = None
            errors.append("SCOPE:invalid")
        required_export_kinds = {"candidates", "kvk_matches", "kvk_unresolved", "canonical", "non_sole", "sole_excluded", "legal_form_review", "active", "inactive_excluded", "status_review", "delivery_csv", "delivery_xlsx", "delivery_full_csv", "delivery_full_xlsx", "reserve", "outputset_manifest"}
        if exported:
            for kind in sorted(required_export_kinds):
                if kind == "candidates" and run.latest_artifact("03", "pre_kvk_eligible"):
                    continue
                if kind not in latest_by_kind or latest_by_kind[kind]["status"] not in {"COMPLETE", "PARTIAL"}:
                    errors.append(f"MISSING_REQUIRED:{kind}")
            if metadata.get("runtime_config", {}).get("end_to_end") is not None:
                manifest_row = latest_by_kind.get("outputset_manifest")
                for kind in ("outcome_report", "run_report"):
                    row = latest_by_kind.get(kind)
                    if (not manifest_row or not row or row["status"] != "COMPLETE"
                            or row["id"] <= manifest_row["id"]):
                        errors.append(f"MISSING_REQUIRED:{kind}_after_outputset")
        active = run.latest_artifact("07", "active")
        delivery = current_output("delivery_full_csv")
        reserve = current_output("reserve")
        if active and delivery and reserve:
            active_numbers = Counter(row["KVK-nummer"] for row in read_tsv(active))
            delivery_rows, reserve_rows = read_tsv(delivery), read_tsv(reserve)
            exported_numbers = Counter(row["KVK-nummer"] for row in delivery_rows + reserve_rows)
            if active_numbers != exported_numbers or set(row["KVK-nummer"] for row in delivery_rows).intersection(row["KVK-nummer"] for row in reserve_rows):
                errors.append("RELATION:active_delivery_reserve_mismatch")
        canonical = run.latest_artifact("05", "canonical")
        non_sole = run.latest_artifact("06", "non_sole")
        sole = run.latest_artifact("06", "sole_excluded")
        legal_review = run.latest_artifact("06", "legal_form_review")
        if canonical and non_sole and sole and legal_review:
            partitions = [read_tsv(path) for path in (non_sole, sole, legal_review)]
            before = Counter(row["KVK-nummer"] for row in read_tsv(canonical))
            after = Counter(row["KVK-nummer"] for rows in partitions for row in rows)
            if before != after or _overlap(partitions):
                errors.append("RELATION:legal_form_partition_mismatch")
        inactive = run.latest_artifact("07", "inactive_excluded")
        status_review = run.latest_artifact("07", "status_review")
        if non_sole and active and inactive and status_review:
            partitions = [read_tsv(path) for path in (active, inactive, status_review)]
            before = Counter(row["KVK-nummer"] for row in read_tsv(non_sole))
            after = Counter(row["KVK-nummer"] for rows in partitions for row in rows)
            if before != after or _overlap(partitions):
                errors.append("RELATION:status_partition_mismatch")
        candidates = ((run.path / str(scope["scoped_path"])) if scope is not None
                      else run.latest_artifact("03", "pre_kvk_eligible") or run.latest_artifact("03", "candidates"))
        matches = run.latest_artifact("04", "kvk_matches")
        unresolved = run.latest_artifact("05", "kvk_unresolved")
        if int(metadata.get("last_completed_step", "0")) >= 4 and not (candidates and matches and unresolved):
            errors.append("MISSING_REQUIRED:candidate_terminal_artifacts")
        elif candidates and matches and unresolved:
            candidate_ids = Counter(row["candidate_id"] for row in read_tsv(candidates))
            terminal_ids = Counter(row["candidate_id"] for path in (matches, unresolved) for row in read_tsv(path))
            if candidate_ids != terminal_ids:
                errors.append("RELATION:candidate_terminal_mismatch")
        if scope is not None:
            scoped_ids = {row["candidate_id"] for row in read_tsv(candidates)} if candidates else set()
            journal_ids = {row["candidate_id"] for row in requests}
            if (len(journal_ids) > int(scope["selected_rows"]) or not journal_ids.issubset(scoped_ids)):
                errors.append("SCOPE:journal_exceeds_limit_or_cohort")
            if int(scope["not_checked_rows"]) > 0 and metadata.get("status") == "EXPORT_COMPLETE":
                errors.append("SCOPE:bounded_export_claimed_complete")
            if delivery and len(read_tsv(delivery)) > int(scope["limit_kvk_check"]):
                errors.append("SCOPE:delivery_exceeds_limit")
        output_manifest = current_output("outputset_manifest")
        if exported and not output_manifest:
            errors.append("MISSING_REQUIRED:outputset_manifest")
        elif output_manifest:
            try:
                payload = json.loads(output_manifest.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("outputsetmanifest moet een object zijn")
                manifest_row = latest_by_kind["outputset_manifest"]
                expected_status = (
                    "PARTIAL" if metadata.get("status") == "PARTIAL_EXPORTED"
                    else "COMPLETE" if metadata.get("status") == "EXPORT_COMPLETE"
                    else None
                )
                if (manifest_row["step"] != "08"
                        or expected_status is None
                        or manifest_row["status"] != expected_status
                        or payload.get("status") != manifest_row["status"]):
                    errors.append("OUTPUTSET:status_mismatch")
                if scope is not None:
                    expected_scope = {key: scope[key] for key in (
                        "limit_kvk_check", "full_eligible_rows", "selected_rows",
                        "not_checked_rows", "full_eligible_sha256", "scoped_sha256",
                    )}
                    if payload.get("kvk_scope") != expected_scope:
                        errors.append("OUTPUTSET:scope_mismatch")
                entries = payload.get("files", [])
                if not isinstance(entries, list):
                    entries = []
                expected_kinds = {"delivery_csv", "delivery_xlsx", "delivery_full_csv", "delivery_full_xlsx", "reserve"}
                entry_kinds = [entry.get("kind") for entry in entries if isinstance(entry, dict)]
                if len(entries) != 5 or len(set(entry_kinds)) != 5 or set(entry_kinds) != expected_kinds:
                    errors.append("OUTPUTSET:manifest_not_closed")
                for entry in entries:
                    if not isinstance(entry, dict):
                        errors.append("OUTPUTSET:manifest_invalid_entry")
                        continue
                    kind = entry.get("kind", "")
                    name = entry.get("path")
                    if not isinstance(name, str) or name in {"", ".", ".."} or Path(name).name != name:
                        errors.append("OUTPUTSET:manifest_invalid_entry")
                        continue
                    output = output_manifest.parent / name
                    registered = latest_by_kind.get(kind)
                    if (not registered or registered["step"] != "08"
                            or registered["status"] != manifest_row["status"]
                            or str(output.relative_to(run.path)) != registered["path"]
                            or not output.is_file() or output.stat().st_size != entry.get("size")
                            or sha256(output) != entry.get("sha256")):
                        errors.append(f"OUTPUTSET:{name}")
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                errors.append("OUTPUTSET:manifest_invalid")
    result = {"run": run.path.name, "checked_artifacts": checked, "errors": errors, "valid": not errors}
    run.log("INFO" if not errors else "ERROR", "audit_verify", **result)
    if errors:
        raise HarvestError(json.dumps(result, ensure_ascii=False), 7)
    return result


def _overlap(partitions: list[list[dict[str, str]]]) -> bool:
    seen: set[str] = set()
    for rows in partitions:
        current = {row["KVK-nummer"] for row in rows}
        if seen.intersection(current):
            return True
        seen.update(current)
    return False


def trace(run: Run, kvk_number: str) -> dict[str, Any]:
    number = validate_kvk(kvk_number)
    hits: list[dict[str, Any]] = []
    with run.connect() as connection:
        artifacts = connection.execute("SELECT step,kind,path,sha256 FROM artifacts ORDER BY id").fetchall()
    for artifact in artifacts:
        path = run.path / artifact["path"]
        if path.suffix.lower() != ".csv" or not path.is_file():
            continue
        try:
            for index, row in enumerate(read_tsv(path), 2):
                if row.get("KVK-nummer") == number or row.get("source_kvk_hint") == number:
                    hits.append({"step": artifact["step"], "kind": artifact["kind"], "path": artifact["path"], "sha256": artifact["sha256"], "row": index, "record": row})
        except UnicodeDecodeError:
            continue
    if not hits:
        raise HarvestError(f"geen trace gevonden voor KVK {number}", 5)
    candidate_ids = {item["record"].get("candidate_id") for item in hits if item["record"].get("candidate_id")}
    journal: list[dict[str, Any]] = []
    with run.connect() as connection:
        for candidate_id in candidate_ids:
            row = connection.execute(
                "SELECT candidate_id,query,state,attempt,request_fingerprint,provider,checked_at,evidence_path,error FROM kvk_requests WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if row:
                journal.append(dict(row))
    return {"KVK-nummer": number, "trace": hits, "request_journal": journal, "integrity_boundary": "Lokale hashes detecteren wijzigingen maar beschermen niet tegen een aanvaller met dezelfde schrijfrechten."}
