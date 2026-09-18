"""Integriteitscontrole en lokale herleidbaarheid."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from company_harvest.core import HarvestError, Run, read_tsv, sha256, validate_kvk


def verify(run: Run) -> dict[str, Any]:
    errors: list[str] = []
    checked = 0
    with run.connect() as connection:
        artifacts = connection.execute("SELECT path,sha256,size,status FROM artifacts ORDER BY id").fetchall()
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
    expected_config = hashlib.sha256(json.dumps({"workflow": metadata["workflow"], "target": metadata["target"]}, sort_keys=True).encode()).hexdigest()
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
        active = run.latest_artifact("07", "active")
        delivery = run.latest_artifact("08", "delivery_full_csv")
        reserve = run.latest_artifact("08", "reserve")
        if active and delivery and reserve:
            active_numbers = {row["KVK-nummer"] for row in read_tsv(active)}
            exported_numbers = {row["KVK-nummer"] for row in read_tsv(delivery)} | {row["KVK-nummer"] for row in read_tsv(reserve)}
            if active_numbers != exported_numbers:
                errors.append("RELATION:active_delivery_reserve_mismatch")
        canonical = run.latest_artifact("05", "canonical")
        non_sole = run.latest_artifact("06", "non_sole")
        sole = run.latest_artifact("06", "sole_excluded")
        legal_review = run.latest_artifact("06", "legal_form_review")
        if canonical and non_sole and sole and legal_review:
            before = {row["KVK-nummer"] for row in read_tsv(canonical)}
            after = {row["KVK-nummer"] for path in (non_sole, sole, legal_review) for row in read_tsv(path)}
            if before != after:
                errors.append("RELATION:legal_form_partition_mismatch")
        inactive = run.latest_artifact("07", "inactive_excluded")
        status_review = run.latest_artifact("07", "status_review")
        if non_sole and active and inactive and status_review:
            before = {row["KVK-nummer"] for row in read_tsv(non_sole)}
            after = {row["KVK-nummer"] for path in (active, inactive, status_review) for row in read_tsv(path)}
            if before != after:
                errors.append("RELATION:status_partition_mismatch")
    result = {"run": run.path.name, "checked_artifacts": checked, "errors": errors, "valid": not errors}
    run.log("INFO" if not errors else "ERROR", "audit_verify", **result)
    if errors:
        raise HarvestError(json.dumps(result, ensure_ascii=False), 7)
    return result


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
