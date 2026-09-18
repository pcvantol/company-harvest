"""HARVEST-normalisatie, filters, export en rapportage."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from company_harvest.core import (
    HarvestError,
    Run,
    normalize_name,
    read_tsv,
    validate_kvk,
    write_tsv,
)


def merge_candidates(run: Run) -> tuple[Path, Path, Path]:
    with run.connect() as connection:
        artifact_rows = connection.execute("SELECT path,kind FROM artifacts WHERE step='02' AND status='COMPLETE' ORDER BY id").fetchall()
    source_paths = [(run.path / row["path"], row["kind"]) for row in artifact_rows if row["kind"].startswith("source_")]
    if not source_paths:
        raise HarvestError("geen verzamelde bronlijsten; voer sources collect uit")
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    decisions: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    for path, _ in source_paths:
        for row in read_tsv(path):
            key = (normalize_name(row["original_name"]), row.get("source_kvk_hint", ""))
            grouped.setdefault(key, []).append(row)
    candidates: list[dict[str, str]] = []
    for key, rows in grouped.items():
        names = {row["original_name"] for row in rows}
        hints = {row["source_kvk_hint"] for row in rows if row.get("source_kvk_hint")}
        if len(hints) > 1:
            for row in rows:
                conflicts.append({"original_name": row["original_name"], "source_id": row["source_id"], "reason": "SAME_NORMALIZED_NAME_MULTIPLE_KVK_HINTS", "source_kvk_hint": row["source_kvk_hint"]})
            continue
        chosen = rows[0]
        candidate_id = hashlib.sha256((key[0] + "\0" + key[1] + "\0" + chosen["source_id"] + "\0" + chosen["source_row"]).encode()).hexdigest()[:20]
        relations = [{"source_id": row["source_id"], "row": row["source_row"], "url": row["source_url"], "name": row["original_name"]} for row in rows]
        candidates.append({"candidate_id": candidate_id, "original_name": chosen["original_name"], "normalized_name": key[0], "source_kvk_hint": next(iter(hints), ""), "country": chosen.get("country", ""), "city": "", "website": chosen.get("website", ""), "sector": chosen.get("sector", ""), "source_relations": json.dumps(relations, ensure_ascii=False, separators=(",", ":"))})
        decisions.append({"candidate_id": candidate_id, "decision": "MERGED_IDENTICAL" if len(rows) > 1 else "KEPT_SINGLE", "input_count": str(len(rows)), "names": json.dumps(sorted(names), ensure_ascii=False)})
    candidates.sort(key=lambda row: (normalize_name(row["original_name"]), row["source_kvk_hint"], row["candidate_id"]))
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
    source = run.latest_artifact("07", "active")
    if not source:
        raise HarvestError("voer eerst active-only uit")
    rows = read_tsv(source)
    unresolved = run.latest_artifact("05", "kvk_unresolved")
    if unresolved and read_tsv(unresolved) and not allow_partial:
        raise HarvestError("run bevat unresolved/onverwerkte kandidaten; gebruik bewust --allow-partial")
    ranked = sorted(rows, key=lambda row: hashlib.sha256(("company-harvest-v1\0" + row["KVK-nummer"]).encode()).digest())
    selected = ranked[:limit]
    reserve = ranked[limit:]
    selected.sort(key=lambda row: (normalize_name(row["Bedrijfsnaam"]), row["KVK-nummer"]))
    headers = list(rows[0]) if rows else ["Bedrijfsnaam", "KVK-nummer"]
    minimal = ["Bedrijfsnaam", "KVK-nummer"]
    paths = [
        run.artifact_path("08", "companies_delivery", "csv"), run.artifact_path("08", "companies_delivery", "xlsx"),
        run.artifact_path("08", "companies_delivery_full", "csv"), run.artifact_path("08", "companies_delivery_full", "xlsx"),
        run.artifact_path("08", "companies_reserve", "csv"),
    ]
    write_tsv(paths[0], minimal, selected)
    write_xlsx(paths[1], minimal, selected)
    write_tsv(paths[2], headers, selected)
    write_xlsx(paths[3], headers, selected)
    write_tsv(paths[4], headers, reserve)
    for path, kind in zip(paths, ("delivery_csv", "delivery_xlsx", "delivery_full_csv", "delivery_full_xlsx", "reserve"), strict=True):
        run.register_artifact(path, "08", kind, "PARTIAL" if allow_partial else "COMPLETE")
    run.update_status("PARTIAL_EXPORTED" if allow_partial else "EXPORT_COMPLETE", "08")
    return paths


def report(run: Run) -> Path:
    metadata = run.metadata()
    with run.connect() as connection:
        artifacts = connection.execute("SELECT step,kind,status,path,sha256,size FROM artifacts ORDER BY id").fetchall()
        states = connection.execute("SELECT state,COUNT(*) AS count FROM kvk_requests GROUP BY state").fetchall()
    path = run.artifact_path("08", "run_report", "md")
    active_path = run.latest_artifact("07", "active")
    unresolved_path = run.latest_artifact("05", "kvk_unresolved")
    active_count = len(read_tsv(active_path)) if active_path else 0
    unresolved_count = len(read_tsv(unresolved_path)) if unresolved_path else 0
    input_complete = unresolved_count == 0
    target_reached = active_count >= int(metadata["target"])
    lines = ["# Runrapport", "", f"- Run: `{metadata['run_id']}`", f"- Workflow: `{metadata['workflow']}`", f"- Doel: {metadata['target']}", f"- Actieve eindpopulatie: {active_count}", f"- Alle input verwerkt: **{str(input_complete).lower()}**", f"- Doelaantal bereikt: **{str(target_reached).lower()}**", f"- Uitvoering/export voltooid: **{str(metadata.get('status') in {'EXPORT_COMPLETE', 'COMPLETE'}).lower()}**", f"- Gegenereerd: {datetime.now(UTC).isoformat()}", "", "## KVK-requeststatus", ""]
    lines.extend(f"- {row['state']}: {row['count']}" for row in states)
    lines.extend(["", "## Artefacten", "", "| Stap | Type | Status | Bestand | SHA-256 | Bytes |", "|---|---|---|---|---|---:|"])
    lines.extend(f"| {row['step']} | {row['kind']} | {row['status']} | `{row['path']}` | `{row['sha256']}` | {row['size']} |" for row in artifacts)
    lines.extend(["", "Uitvoering voltooid, alle input verwerkt en doelaantal bereikt zijn afzonderlijke begrippen. Raadpleeg unresolved- en reviewbestanden.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    run.register_artifact(path, "08", "run_report")
    return path
