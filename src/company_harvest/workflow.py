"""HARVEST-normalisatie, filters, export en rapportage."""

from __future__ import annotations

import hashlib
import importlib
import itertools
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from company_harvest.core import (
    HTTP_USER_AGENT,
    HarvestError,
    Run,
    atomic_write,
    normalize_name,
    read_tsv,
    sha256,
    timestamp,
    validate_kvk,
    write_tsv,
)
from company_harvest.kvk_scope import scope_details

OUTCOME_REPORT_SCHEMA_VERSION = 1


def _missing_source_status(value: str | None) -> bool:
    status = (value or "").strip()
    if not status:
        return True
    if status.startswith("entity=") and ";registration=" in status:
        entity, registration = status.split(";registration=", 1)
        return not entity.removeprefix("entity=").strip() or not registration.strip()
    return False


def _deduplicate_rows(
    raw_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Apply the canonical preliminary deduplication rules to an explicit row set."""
    grouped: dict[str, list[dict[str, str]]] = {}
    decisions: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    for row in raw_rows:
        grouped.setdefault(normalize_name(row["original_name"]), []).append(row)
    candidates: list[dict[str, str]] = []
    for normalized_name, name_rows in grouped.items():
        hints = {row["source_kvk_hint"] for row in name_rows if row.get("source_kvk_hint")}
        if len(hints) > 1:
            for row in name_rows:
                conflicts.append({"original_name": row["original_name"], "source_id": row["source_id"], "reason": "SAME_NORMALIZED_NAME_MULTIPLE_KVK_HINTS", "source_kvk_hint": row["source_kvk_hint"]})
            continue
        hint = next(iter(hints), "")
        candidate_groups: list[list[dict[str, str]]] = []
        if hint:
            hinted = [row for row in name_rows if row.get("source_kvk_hint") == hint]
            if hinted:
                candidate_groups.append(hinted)
            candidate_groups.extend([[row] for row in name_rows if not row.get("source_kvk_hint")])
        else:
            candidate_groups.extend([[row] for row in name_rows])
        for rows in candidate_groups:
            names = {row["original_name"] for row in rows}
            chosen = rows[0]
            group_hint = chosen.get("source_kvk_hint", "")
            candidate_id = hashlib.sha256((normalized_name + "\0" + group_hint + "\0" + chosen["source_id"] + "\0" + chosen["source_row"]).encode()).hexdigest()[:20]
            relations = [{"source_id": row["source_id"], "row": row["source_row"], "url": row["source_url"], "name": row["original_name"]} for row in rows]
            candidates.append({"candidate_id": candidate_id, "original_name": chosen["original_name"], "normalized_name": normalized_name, "source_kvk_hint": group_hint, "country": chosen.get("country", ""), "city": "", "website": chosen.get("website", ""), "sector": chosen.get("sector", ""), "source_relations": json.dumps(relations, ensure_ascii=False, separators=(",", ":"))})
            decisions.append({"candidate_id": candidate_id, "decision": "MERGED_IDENTICAL" if len(rows) > 1 else "KEPT_SINGLE", "input_count": str(len(rows)), "names": json.dumps(sorted(names), ensure_ascii=False)})
    candidates.sort(key=lambda row: (normalize_name(row["original_name"]), row["source_kvk_hint"], row["candidate_id"]))
    decisions.sort(key=lambda row: row["candidate_id"])
    conflicts.sort(
        key=lambda row: (
            normalize_name(row["original_name"]), row["source_id"], row["source_kvk_hint"]
        )
    )
    return candidates, decisions, conflicts


def merge_candidates(run: Run) -> tuple[Path, Path, Path]:
    source_paths = _latest_artifact_rows(run, "02", "source_")
    if not source_paths:
        raise HarvestError("geen verzamelde bronlijsten; voer sources collect uit")
    raw_rows = [row for path, _ in source_paths for row in read_tsv(path)]
    candidates, decisions, conflicts = _deduplicate_rows(raw_rows)
    candidate_path = run.artifact_path("03", "companies_candidates", "csv")
    decisions_path = run.artifact_path("03", "dedup_decisions", "csv")
    conflicts_path = run.artifact_path("03", "dedup_conflicts", "csv")
    write_tsv(candidate_path, ["candidate_id", "original_name", "normalized_name", "source_kvk_hint", "country", "city", "website", "sector", "source_relations"], candidates)
    write_tsv(decisions_path, ["candidate_id", "decision", "input_count", "names"], decisions)
    write_tsv(conflicts_path, ["original_name", "source_id", "reason", "source_kvk_hint"], conflicts)
    for path, kind in ((candidate_path, "candidates"), (decisions_path, "dedup_decisions"), (conflicts_path, "dedup_conflicts")):
        run.register_artifact(path, "03", kind)
    run.update_status("IN_PROGRESS", "03")
    return candidate_path, decisions_path, conflicts_path


def consolidate(run: Run) -> Path:
    source = run.latest_artifact("04", "kvk_matches")
    if not source:
        raise HarvestError("geen KVK-matchsnapshot")
    by_kvk: dict[str, dict[str, str]] = {}
    conflicts: list[dict[str, str]] = []
    conflicted_numbers: set[str] = set()
    for row in read_tsv(source):
        number = validate_kvk(row["KVK-nummer"])
        if number in conflicted_numbers:
            conflicts.append({**row, "conflict_reason": "SAME_KVK_DIFFERENT_PROVIDER_FIELDS"})
            continue
        prior = by_kvk.get(number)
        if prior is None:
            by_kvk[number] = row
            continue
        identity = ("Bedrijfsnaam", "raw_legal_form", "raw_status", "city", "country")
        if any(normalize_name(prior.get(field, "")) != normalize_name(row.get(field, "")) for field in identity):
            conflicts.extend([{**prior, "conflict_reason": "SAME_KVK_DIFFERENT_PROVIDER_FIELDS"}, {**row, "conflict_reason": "SAME_KVK_DIFFERENT_PROVIDER_FIELDS"}])
            by_kvk.pop(number, None)
            conflicted_numbers.add(number)
    rows = sorted(by_kvk.values(), key=lambda row: (normalize_name(row["Bedrijfsnaam"]), row["KVK-nummer"]))
    path = run.artifact_path("05", "kvk_companies_canonical", "csv")
    headers = list(rows[0]) if rows else ["Bedrijfsnaam", "KVK-nummer", "raw_legal_form", "raw_status", "city", "country", "match_method", "provider", "checked_at", "response_json", "source_relations"]
    if headers[:2] != ["Bedrijfsnaam", "KVK-nummer"]:
        headers = ["Bedrijfsnaam", "KVK-nummer"] + [header for header in headers if header not in {"Bedrijfsnaam", "KVK-nummer"}]
    write_tsv(path, headers, rows)
    run.register_artifact(path, "05", "canonical")
    conflict_path = run.artifact_path("05", "kvk_canonical_conflicts", "csv")
    conflict_headers = headers + ([] if "conflict_reason" in headers else ["conflict_reason"])
    write_tsv(conflict_path, conflict_headers, conflicts)
    run.register_artifact(conflict_path, "05", "canonical_conflicts")
    run.update_status("IN_PROGRESS", "05")
    return path


def exclude_sole_proprietorships(run: Run) -> tuple[Path, Path, Path]:
    source = run.latest_artifact("05", "canonical")
    if not source:
        raise HarvestError("voer eerst kvk consolidate uit")
    included, excluded, review = [], [], []
    sole_values = {"eenmanszaak", "eenmanszaak met beperkte aansprakelijkheid"}
    non_sole_values = {"besloten vennootschap", "naamloze vennootschap", "stichting", "vereniging", "coöperatie", "bv", "nv"}
    for row in read_tsv(source):
        value = normalize_name(row.get("raw_legal_form", ""))
        if value in sole_values:
            excluded.append({**row, "filter_reason": "CONFIRMED_SOLE_PROPRIETORSHIP"})
        elif value in non_sole_values:
            included.append(row)
        else:
            review.append({**row, "filter_reason": "LEGAL_FORM_UNKNOWN_OR_UNMAPPED"})
    return _write_partition(run, "06", included, excluded, review, "non_sole", "sole_excluded", "legal_form_review")


def active_only(run: Run) -> tuple[Path, Path, Path]:
    source = run.latest_artifact("06", "non_sole")
    if not source:
        raise HarvestError("voer eerst exclude-sole-proprietorships uit")
    active, inactive, review = [], [], []
    active_values = {"actief", "active", "geregistreerd"}
    inactive_values = {"inactief", "inactive", "uitgeschreven", "beëindigd"}
    for row in read_tsv(source):
        value = normalize_name(row.get("raw_status", ""))
        if value in active_values:
            active.append(row)
        elif value in inactive_values:
            inactive.append({**row, "filter_reason": "CONFIRMED_INACTIVE"})
        else:
            review.append({**row, "filter_reason": "STATUS_UNKNOWN_OR_UNMAPPED"})
    return _write_partition(run, "07", active, inactive, review, "active", "inactive_excluded", "status_review")


def _write_partition(run: Run, step: str, included: list[dict[str, str]], excluded: list[dict[str, str]], review: list[dict[str, str]], included_kind: str, excluded_kind: str, review_kind: str) -> tuple[Path, Path, Path]:
    base_headers = list((included or excluded or review or [{"Bedrijfsnaam": "", "KVK-nummer": ""}])[0])
    paths = (run.artifact_path(step, included_kind, "csv"), run.artifact_path(step, excluded_kind, "csv"), run.artifact_path(step, review_kind, "csv"))
    write_tsv(paths[0], base_headers, sorted(included, key=lambda row: (normalize_name(row["Bedrijfsnaam"]), row["KVK-nummer"])))
    for path, rows in ((paths[1], excluded), (paths[2], review)):
        headers = base_headers + ([] if "filter_reason" in base_headers else ["filter_reason"])
        write_tsv(path, headers, rows)
    for path, kind in zip(paths, (included_kind, excluded_kind, review_kind), strict=True):
        run.register_artifact(path, step, kind)
    run.update_status("IN_PROGRESS", step)
    return paths


def _safe_excel_text(value: Any) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def write_xlsx(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Bedrijven"
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([_safe_excel_text(row.get(header, "")) for header in headers])
    for column in sheet.columns:
        letter = column[0].column_letter
        sheet.column_dimensions[letter].width = min(60, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
        for cell in column[1:]:
            cell.number_format = "@"
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    temporary = path.with_name(f".{path.stem}.tmp{path.suffix}")
    workbook.save(temporary)
    temporary.replace(path)


def export(run: Run, limit: int, allow_partial: bool = False) -> list[Path]:
    if type(limit) is not int or limit < 1:
        raise HarvestError("exportlimiet moet positief zijn")
    scope = scope_details(run)
    if scope is not None:
        if int(scope["not_checked_rows"]) > 0 and not allow_partial:
            raise HarvestError("begrensde KVK-proef vereist expliciet --allow-partial")
        limit = min(limit, int(scope["limit_kvk_check"]))
    source = run.latest_artifact("07", "active")
    if not source:
        raise HarvestError("voer eerst active-only uit")
    rows = read_tsv(source)
    if scope is not None and len(rows) > int(scope["selected_rows"]):
        raise HarvestError("actieve KVK-populatie overschrijdt de begrensde cohort")
    unresolved = run.latest_artifact("05", "kvk_unresolved")
    if unresolved and read_tsv(unresolved) and not allow_partial:
        raise HarvestError("run bevat unresolved/onverwerkte kandidaten; gebruik bewust --allow-partial")
    ranked = sorted(rows, key=lambda row: hashlib.sha256(("company-harvest-v1\0" + row["KVK-nummer"]).encode()).digest())
    selected = ranked[:limit]
    reserve = ranked[limit:]
    status = "PARTIAL" if allow_partial else "COMPLETE"
    selected.sort(key=lambda row: (normalize_name(row["Bedrijfsnaam"]), row["KVK-nummer"]))
    headers = list(rows[0]) if rows else ["Bedrijfsnaam", "KVK-nummer"]
    minimal = ["Bedrijfsnaam", "KVK-nummer"]
    set_name = f"{timestamp()}_08_delivery_outputset"
    staging = run.path / "artifacts" / f".{set_name}.tmp"
    final = run.path / "artifacts" / set_name
    staging.mkdir()
    names = ("companies_delivery.csv", "companies_delivery.xlsx", "companies_delivery_full.csv", "companies_delivery_full.xlsx", "companies_reserve.csv")
    staged = [staging / name for name in names]
    try:
        write_tsv(staged[0], minimal, selected)
        write_xlsx(staged[1], minimal, selected)
        write_tsv(staged[2], headers, selected)
        write_xlsx(staged[3], headers, selected)
        write_tsv(staged[4], headers, reserve)
        kinds = ("delivery_csv", "delivery_xlsx", "delivery_full_csv", "delivery_full_xlsx", "reserve")
        manifest_staged = staging / "outputset_manifest.json"
        manifest_payload: dict[str, Any] = {
            "schema": 1,
            "status": status,
            "files": [{"path": path.name, "kind": kind, "sha256": sha256(path), "size": path.stat().st_size} for path, kind in zip(staged, kinds, strict=True)],
        }
        if scope is not None:
            manifest_payload["kvk_scope"] = {
                "limit_kvk_check": scope["limit_kvk_check"],
                "full_eligible_rows": scope["full_eligible_rows"],
                "selected_rows": scope["selected_rows"],
                "not_checked_rows": scope["not_checked_rows"],
                "full_eligible_sha256": scope["full_eligible_sha256"],
                "scoped_sha256": scope["scoped_sha256"],
            }
        manifest_staged.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
        os.replace(staging, final)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    paths = [final / name for name in names]
    kinds = ("delivery_csv", "delivery_xlsx", "delivery_full_csv", "delivery_full_xlsx", "reserve")
    manifest = final / "outputset_manifest.json"
    run.register_artifact_set([(path, "08", kind, status) for path, kind in zip(paths, kinds, strict=True)] + [(manifest, "08", "outputset_manifest", status)])
    run.record_config("export", {"limit": limit, "allow_partial": allow_partial})
    run.update_status("PARTIAL_EXPORTED" if allow_partial else "EXPORT_COMPLETE", "08")
    return paths + [manifest]


def _latest_artifact_rows(run: Run, step: str, kind_prefix: str) -> list[tuple[Path, str]]:
    with run.connect() as connection:
        rows = connection.execute(
            """
            SELECT path,kind FROM artifacts
            WHERE id IN (
              SELECT MAX(id) FROM artifacts
              WHERE step=? AND kind LIKE ? AND status='COMPLETE'
              GROUP BY kind
            ) ORDER BY kind
            """,
            (step, f"{kind_prefix}%"),
        ).fetchall()
    return [(run.path / row["path"], str(row["kind"])) for row in rows]


def _peak_memory() -> tuple[int | None, str]:
    if sys.platform == "win32":
        return None, "UNAVAILABLE_ON_PLATFORM"
    try:
        resource: Any = importlib.import_module("resource")
    except ImportError:
        return None, "UNAVAILABLE_ON_PLATFORM"
    maximum = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return (maximum if sys.platform == "darwin" else maximum * 1024), "MEASURED_PROCESS_MAXRSS"


def outcome_metrics(run: Run) -> dict[str, Any]:
    """Bouw het R1-meetcontract uit de laatste complete artefacten."""
    metadata = run.metadata()
    source_artifacts = _latest_artifact_rows(run, "02", "source_")
    raw_rows: list[dict[str, str]] = []
    for path, _ in source_artifacts:
        raw_rows.extend(read_tsv(path))

    try:
        from company_harvest.sources import read_catalog

        catalog = read_catalog(run)
    except HarvestError:
        catalog = []
    catalog_by_id = {row["source_id"]: row for row in catalog}
    source_ids = sorted({row.get("source_id", "") for row in raw_rows if row.get("source_id")} | set(catalog_by_id))
    per_source: list[dict[str, Any]] = []
    family_counts: dict[str, int] = {}
    valid_numbers_by_source: dict[str, set[str]] = {}
    valid_total = 0
    missing_total = 0
    invalid_total = 0
    for source_id in source_ids:
        rows = [row for row in raw_rows if row.get("source_id") == source_id]
        valid = 0
        missing = 0
        invalid = 0
        valid_numbers: set[str] = set()
        for row in rows:
            try:
                number = validate_kvk(row.get("source_kvk_hint"))
                valid += 1
                valid_numbers.add(number)
            except ValueError:
                status = row.get("registration_validation_status")
                if status == "MISSING":
                    missing += 1
                elif status == "INVALID" or row.get("source_registration_raw", "").strip():
                    invalid += 1
                else:
                    missing += 1
        valid_numbers_by_source[source_id] = valid_numbers
        profile = catalog_by_id.get(source_id, {})
        family = profile.get("source_family") or "unclassified"
        family_counts[family] = family_counts.get(family, 0) + len(rows)
        per_source.append(
            {
                "source_id": source_id,
                "source_family": family,
                "raw_records": len(rows),
                "valid_registration_numbers": valid,
                "missing_registration_numbers": missing,
                "invalid_registration_numbers": invalid,
                "missing_legal_form": sum(not row.get("source_legal_form", "").strip() for row in rows),
                "missing_status": sum(_missing_source_status(row.get("source_status")) for row in rows),
                "catalog_measurement_status": profile.get("live_measurement_status", "NOT_CATALOGED"),
            }
        )
        valid_total += valid
        missing_total += missing
        invalid_total += invalid

    candidate_path = run.latest_artifact("03", "candidates")
    pre_kvk_candidate_path = run.latest_artifact("03", "pre_kvk_eligible")
    scope = scope_details(run)
    decision_path = run.latest_artifact("03", "dedup_decisions")
    conflict_path = run.latest_artifact("03", "dedup_conflicts")
    candidates = read_tsv(candidate_path) if candidate_path else []
    full_eligible_count = (len(read_tsv(pre_kvk_candidate_path))
                           if pre_kvk_candidate_path else len(candidates))
    terminal_candidate_count = (int(scope["selected_rows"]) if scope is not None
                                else full_eligible_count)
    decisions = read_tsv(decision_path) if decision_path else []
    conflicts = read_tsv(conflict_path) if conflict_path else []
    unique_before = {
        (
            normalize_name(row.get("original_name", "")),
            row.get("source_kvk_hint", ""),
            "" if row.get("source_kvk_hint") else f"{row.get('source_id', '')}:{row.get('source_row') or index}",
        )
        for index, row in enumerate(raw_rows)
    }
    merged_inputs = sum(int(row.get("input_count") or 0) for row in decisions)
    dedup_terminal_inputs = merged_inputs + len(conflicts)
    closure_available = bool(candidate_path and decision_path and conflict_path)
    cross_source_candidates = 0
    candidate_family_counts: dict[str, int] = {}
    source_pair_overlap: dict[str, int] = {}
    family_pair_overlap: dict[str, int] = {}
    for candidate in candidates:
        try:
            relations = json.loads(candidate.get("source_relations") or "[]")
        except json.JSONDecodeError:
            relations = []
        relation_sources = {
            str(item.get("source_id"))
            for item in relations
            if isinstance(item, dict) and item.get("source_id")
        }
        relation_families = {
            catalog_by_id.get(source_id, {}).get("source_family") or "unclassified"
            for source_id in relation_sources
        } or {"unclassified"}
        cross_source_candidates += len(relation_sources) > 1
        for family in relation_families:
            candidate_family_counts[family] = candidate_family_counts.get(family, 0) + 1
        for left, right in itertools.combinations(sorted(relation_sources), 2):
            key = f"{left}|{right}"
            source_pair_overlap[key] = source_pair_overlap.get(key, 0) + 1
        for left, right in itertools.combinations(sorted(relation_families), 2):
            key = f"{left}|{right}"
            family_pair_overlap[key] = family_pair_overlap.get(key, 0) + 1

    active_sources = sorted(
        item["source_id"] for item in per_source if item["raw_records"] > 0
    )
    valid_registration_overlap: dict[str, int] = {}
    for left, right in itertools.combinations(active_sources, 2):
        key = f"{left}|{right}"
        source_pair_overlap.setdefault(key, 0)
        valid_registration_overlap[key] = len(
            valid_numbers_by_source.get(left, set())
            & valid_numbers_by_source.get(right, set())
        )
    active_families = sorted(
        family for family, count in family_counts.items() if count > 0
    )
    for left, right in itertools.combinations(active_families, 2):
        family_pair_overlap.setdefault(f"{left}|{right}", 0)

    def count_artifact(step: str, kind: str) -> tuple[Path | None, int | None]:
        artifact = run.latest_artifact(step, kind)
        if artifact is None and step == "08" and metadata.get("status") == "PARTIAL_EXPORTED":
            with run.connect() as connection:
                entry = connection.execute(
                    "SELECT path FROM artifacts WHERE step='08' AND kind=? AND status='PARTIAL' "
                    "ORDER BY id DESC LIMIT 1", (kind,),
                ).fetchone()
            artifact = run.path / entry["path"] if entry else None
        return artifact, len(read_tsv(artifact)) if artifact else None

    matches_path, matches_count = count_artifact("04", "kvk_matches")
    unresolved_path, unresolved_count = count_artifact("05", "kvk_unresolved")
    canonical_path, canonical_count = count_artifact("05", "canonical")
    canonical_conflict_path, canonical_conflict_count = count_artifact("05", "canonical_conflicts")
    non_sole_path, non_sole_count = count_artifact("06", "non_sole")
    sole_path, sole_count = count_artifact("06", "sole_excluded")
    legal_review_path, legal_review_count = count_artifact("06", "legal_form_review")
    active_path, active_count = count_artifact("07", "active")
    inactive_path, inactive_count = count_artifact("07", "inactive_excluded")
    status_review_path, status_review_count = count_artifact("07", "status_review")
    delivery_path, delivery_count = count_artifact("08", "delivery_full_csv")
    reserve_path, reserve_count = count_artifact("08", "reserve")

    def transition(
        input_count: int | None,
        output_counts: list[int | None],
        available: bool,
    ) -> dict[str, Any]:
        if not available or input_count is None or any(count is None for count in output_counts):
            return {"status": "NOT_AVAILABLE", "input": input_count, "output": None, "delta": None}
        output = sum(int(count) for count in output_counts if count is not None)
        return {
            "status": "CLOSED" if output == input_count else "OPEN",
            "input": input_count,
            "output": output,
            "delta": output - input_count,
        }

    closures = {
        "raw_to_dedup": transition(
            len(raw_rows),
            [dedup_terminal_inputs],
            closure_available,
        ),
        "candidates_to_kvk_terminal": transition(
            terminal_candidate_count,
            [matches_count, unresolved_count],
            matches_path is not None and unresolved_path is not None,
        ),
        "matches_to_canonical": transition(
            matches_count,
            [canonical_count, canonical_conflict_count],
            matches_path is not None and canonical_path is not None and canonical_conflict_path is not None,
        ),
        "canonical_to_legal_form_partition": transition(
            canonical_count,
            [non_sole_count, sole_count, legal_review_count],
            canonical_path is not None and all(path is not None for path in (non_sole_path, sole_path, legal_review_path)),
        ),
        "non_sole_to_status_partition": transition(
            non_sole_count,
            [active_count, inactive_count, status_review_count],
            non_sole_path is not None and all(path is not None for path in (active_path, inactive_path, status_review_path)),
        ),
        "active_to_delivery_partition": transition(
            active_count,
            [delivery_count, reserve_count],
            active_path is not None and delivery_path is not None and reserve_path is not None,
        ),
    }
    available_closures = [item for item in closures.values() if item["status"] != "NOT_AVAILABLE"]
    if any(item["status"] == "OPEN" for item in available_closures):
        overall_closure = "OPEN"
    elif not available_closures:
        overall_closure = "NOT_AVAILABLE"
    elif len(available_closures) == len(closures):
        overall_closure = "COMPLETE_CLOSED"
    else:
        overall_closure = "PARTIAL_CLOSED"
    if scope is not None and int(scope["not_checked_rows"]) > 0 and overall_closure == "COMPLETE_CLOSED":
        overall_closure = "BOUNDED_CLOSED"

    peak_memory_bytes, peak_memory_status = _peak_memory()
    created_at = datetime.fromisoformat(str(metadata["created_at"]))
    generated_at = datetime.now(UTC)
    evidence_bytes = sum(path.stat().st_size for path in (run.path / "evidence").glob("**/*") if path.is_file())
    sqlite_bytes = sum(
        path.stat().st_size
        for path in (run.db_path, run.db_path.with_name(run.db_path.name + "-wal"), run.db_path.with_name(run.db_path.name + "-shm"))
        if path.exists()
    )
    largest_family = max(family_counts.values(), default=0)
    largest_candidate_family = max(candidate_family_counts.values(), default=0)
    raw_total = len(raw_rows)
    storage_baseline = metadata.get("storage_baseline")
    baseline_sqlite = storage_baseline.get("sqlite_bytes") if isinstance(storage_baseline, dict) else None
    baseline_evidence = storage_baseline.get("evidence_bytes") if isinstance(storage_baseline, dict) else None
    return {
        "outcome_report_schema_version": OUTCOME_REPORT_SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "run_id": metadata["run_id"],
        "run_schema_version": metadata["schema_version"],
        "http_user_agent": metadata.get("http_user_agent", HTTP_USER_AGENT),
        "source_catalog_schema_version": "2",
        "counts": {
            "raw_records": raw_total,
            "valid_registration_numbers": valid_total,
            "without_direct_registration_number": missing_total + invalid_total,
            "missing_registration_numbers": missing_total,
            "invalid_registration_numbers": invalid_total,
            "unique_candidates_before_deduplication": len(unique_before),
            "unique_candidates_after_deduplication": len(candidates),
            **({"pre_kvk_eligible_candidates": full_eligible_count} if pre_kvk_candidate_path else {}),
            **({"kvk_check_scope_candidates": terminal_candidate_count,
                "kvk_not_checked_out_of_scope": int(scope["not_checked_rows"])} if scope is not None else {}),
            "identical_merges": sum(max(int(row.get("input_count") or 0) - 1, 0) for row in decisions if row.get("decision") == "MERGED_IDENTICAL"),
            "conflict_records": len(conflicts),
            "review_case_records": missing_total + invalid_total + len(conflicts),
            "cross_source_candidates": cross_source_candidates,
        },
        "count_closure": {"status": overall_closure, "transitions": closures},
        "source_diversity": {
            "source_count": len([item for item in per_source if item["raw_records"] > 0]),
            "source_family_count": len([count for count in family_counts.values() if count > 0]),
            "raw_records_by_family": family_counts,
            "largest_raw_family_share": (largest_family / raw_total) if raw_total else 0.0,
            "candidates_by_family": candidate_family_counts,
            "largest_candidate_family_share": (largest_candidate_family / len(candidates)) if candidates else 0.0,
            "measured_candidate_overlap_by_source_pair": source_pair_overlap,
            "measured_candidate_overlap_by_family_pair": family_pair_overlap,
            "measured_valid_registration_overlap_by_source_pair": valid_registration_overlap,
        },
        "resources": {
            "duration_seconds": max(0.0, (generated_at - created_at).total_seconds()),
            "peak_memory_bytes": peak_memory_bytes,
            "peak_memory_status": peak_memory_status,
            "sqlite_bytes_current": sqlite_bytes,
            "sqlite_bytes_baseline": baseline_sqlite,
            "sqlite_growth_bytes": sqlite_bytes - int(baseline_sqlite) if baseline_sqlite is not None else None,
            "evidence_bytes_current": evidence_bytes,
            "evidence_bytes_baseline": baseline_evidence,
            "evidence_growth_bytes": evidence_bytes - int(baseline_evidence) if baseline_evidence is not None else None,
            "storage_growth_status": "MEASURED" if baseline_sqlite is not None and baseline_evidence is not None else "UNAVAILABLE_BASELINE",
        },
        "sources": per_source,
        "thresholds": {"status": "NOT_SET_PENDING_R2_R3_MEASUREMENTS"},
    }


def report(run: Run) -> Path:
    metadata = run.metadata()
    metrics = outcome_metrics(run)
    outcome_path = run.artifact_path("08", "outcome_report", "json")
    atomic_write(outcome_path, json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")
    run.register_artifact(outcome_path, "08", "outcome_report")
    with run.connect() as connection:
        artifacts = connection.execute("SELECT step,kind,status,path,sha256,size FROM artifacts ORDER BY id").fetchall()
        states = connection.execute("SELECT state,COUNT(*) AS count FROM kvk_requests GROUP BY state").fetchall()
    path = run.artifact_path("08", "run_report", "md")
    active_path = run.latest_artifact("07", "active")
    unresolved_path = run.latest_artifact("05", "kvk_unresolved")
    active_count = len(read_tsv(active_path)) if active_path else 0
    unresolved_count = len(read_tsv(unresolved_path)) if unresolved_path else 0
    input_complete = unresolved_count == 0 and metrics["count_closure"]["status"] == "COMPLETE_CLOSED"
    target_reached = active_count >= int(metadata["target"])
    counts = metrics["counts"]
    closure = metrics["count_closure"]
    diversity = metrics["source_diversity"]
    resources = metrics["resources"]
    lines = ["# Runrapport", "", f"- Run: `{metadata['run_id']}`", f"- Workflow: `{metadata['workflow']}`", f"- Doel: {metadata['target']}", f"- HTTP User-Agent: `{metrics['http_user_agent']}`", f"- Actieve eindpopulatie: {active_count}", f"- Alle input verwerkt: **{str(input_complete).lower()}**", f"- Doelaantal bereikt: **{str(target_reached).lower()}**", f"- Uitvoering/export voltooid: **{str(metadata.get('status') in {'EXPORT_COMPLETE', 'COMPLETE'}).lower()}**", f"- Gegenereerd: {metrics['generated_at']}", "", "## Outcome-meting", "", f"- Ruwe records: {counts['raw_records']}", f"- Geldige directe KVK-nummers: {counts['valid_registration_numbers']}", f"- Zonder direct KVK-nummer: {counts['without_direct_registration_number']}", f"- Unieke kandidaten vóór/na deduplicatie: {counts['unique_candidates_before_deduplication']} / {counts['unique_candidates_after_deduplication']}", f"- Identieke merges: {counts['identical_merges']}", f"- Conflict-/reviewrecords: {counts['conflict_records']} / {counts['review_case_records']}", f"- Bronfamilies: {diversity['source_family_count']}; grootste kandidaataandeel: {diversity['largest_candidate_family_share']:.3f}", f"- Count-closure: **{closure['status']}**", f"- Doorlooptijd: {resources['duration_seconds']:.3f}s; piekgeheugen: {resources['peak_memory_bytes']}; SQLite-/evidencegroei: {resources['sqlite_growth_bytes']} / {resources['evidence_growth_bytes']} bytes", f"- Machineleesbaar rapport: `{outcome_path.relative_to(run.path)}`", "", "### Count-closure per overgang", "", "| Overgang | Status | Input | Output | Delta |", "|---|---|---:|---:|---:|"]
    lines.extend(f"| {name} | {item['status']} | {item['input']} | {item['output']} | {item['delta']} |" for name, item in closure["transitions"].items())
    if "kvk_check_scope_candidates" in counts:
        lines.extend(["", "## Begrensde KVK-cohort", "",
                      f"- Geselecteerde kandidaten: {counts['kvk_check_scope_candidates']}",
                      f"- Buiten deze run niet bevraagd: {counts['kvk_not_checked_out_of_scope']}"])
        if counts["kvk_not_checked_out_of_scope"]:
            lines.append("- Dit is een partiële selectie uit de volledige pre-KVK-lijst, geen volledige harvest.")
    lines.extend(["", "### Per bron", "", "| Bron | Familie | Ruw | Geldig KVK | Ontbrekend | Ongeldig | Rechtsvorm ontbreekt | Status ontbreekt |", "|---|---|---:|---:|---:|---:|---:|---:|"])
    lines.extend(f"| {item['source_id']} | {item['source_family']} | {item['raw_records']} | {item['valid_registration_numbers']} | {item['missing_registration_numbers']} | {item['invalid_registration_numbers']} | {item['missing_legal_form']} | {item['missing_status']} |" for item in metrics["sources"])
    lines.extend(["", "Er zijn bewust nog geen succesdrempels vastgesteld; die volgen pas uit R2/R3-metingen.", "", "## KVK-requeststatus", ""])
    lines.extend(f"- {row['state']}: {row['count']}" for row in states)
    lines.extend(["", "## Artefacten", "", "| Stap | Type | Status | Bestand | SHA-256 | Bytes |", "|---|---|---|---|---|---:|"])
    lines.extend(f"| {row['step']} | {row['kind']} | {row['status']} | `{row['path']}` | `{row['sha256']}` | {row['size']} |" for row in artifacts)
    lines.extend(["", "Uitvoering voltooid, alle input verwerkt en doelaantal bereikt zijn afzonderlijke begrippen. Raadpleeg unresolved- en reviewbestanden.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    run.register_artifact(path, "08", "run_report")
    return path
