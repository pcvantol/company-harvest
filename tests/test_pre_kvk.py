"""Synthetische gates voor de volledige, verliesvrije pre-KVK-lijst."""

import csv
import json
from pathlib import Path

import pytest

from company_harvest.core import HarvestError, Run, read_tsv, sha256, write_tsv
from company_harvest.pre_kvk import SOURCE_IDS, build_blocked_pre_kvk_preview, build_pre_kvk_list
from company_harvest.sources import RAW_HEADERS


def _raw(source_id: str, row: int, name: str, hint: str = "") -> dict[str, str]:
    value = {header: "" for header in RAW_HEADERS}
    value.update(
        original_name=name,
        country="Nederland",
        nl_evidence="synthetisch; plaats=Utrecht",
        source_kvk_hint=hint,
        source_id=source_id,
        source_url=f"https://example.org/{source_id}",
        source_row=str(row),
        evidence_reference=f"{source_id}.dat",
    )
    return value


def _full_sources(run: Run) -> dict[str, Path]:
    rows = {
        "ind_arbeid": [_raw("ind_arbeid", 1, "Alpha B.V.", "12345678")],
        "wikidata_nl_companies": [_raw("wikidata_nl_companies", 1, "Alpha B.V.", "12345678")],
        "gleif_golden_copy": [_raw("gleif_golden_copy", 1, "Alpha B.V.", "87654321")],
        "anbi_register": [_raw("anbi_register", 1, "Beta Stichting")],
        "duo_education_organisations": [_raw("duo_education_organisations", 1, "Beta Stichting")],
    }
    paths: dict[str, Path] = {}
    observations: dict[str, object] = {}
    for source_id in SOURCE_IDS:
        path = run.artifact_path("02", f"source_{source_id}_companies", "csv")
        write_tsv(path, RAW_HEADERS, rows[source_id])
        run.register_artifact(path, "02", f"source_{source_id}")
        paths[source_id] = path
        bound = {"path": str(path.relative_to(run.path)), "sha256": sha256(path),
                 "size": path.stat().st_size}
        evidence = run.path / "evidence" / f"{source_id}.dat"
        evidence.write_bytes(b"synthetische bronrespons")
        run.register_artifact(evidence, "02", f"evidence_{source_id}")
        if source_id in {"ind_arbeid", "wikidata_nl_companies"}:
            observations[source_id] = {
                "limit": None, "collection_complete": True, "response_count": 1,
                "source_artifact": bound,
                "evidence_artifacts": [{"path": str(evidence.relative_to(run.path)),
                                        "sha256": sha256(evidence),
                                        "size": evidence.stat().st_size}],
            }
        else:
            report = {
                "source_id": source_id, "scope": "FULL_ARCHIVE", "configured_limit": None,
                "count_closure": {"source_partition": "CLOSED"},
                "candidate_artifact": bound,
                "evidence_file": evidence.name, "evidence_sha256": sha256(evidence),
                "counts": {"candidate_records": len(rows[source_id])},
            }
            report_kind = "gleif_ingest_report" if source_id == "gleif_golden_copy" else f"{source_id}_ingest_report"
            report_path = run.artifact_path("02", report_kind, "json")
            report_path.write_text(json.dumps(report), encoding="utf-8")
            run.register_artifact(report_path, "02", report_kind)
    run.record_config("source_observations", observations)
    return paths


def test_full_pre_kvk_list_preserves_conflicts_and_closes(run: Run) -> None:
    _full_sources(run)
    path, report_path = build_pre_kvk_list(run)
    rows = read_tsv(path)
    report = json.loads(report_path.read_text())
    assert path.suffix == ".tsv" and len(rows) == 4
    assert sum(int(row["source_count"]) for row in rows) == 5
    assert report["counts"]["input_source_rows"] == 5
    assert report["counts"]["merged_source_rows"] == 1
    assert report["closure"] == "CLOSED" and report["kvk_requests"] == 0
    assert report["master_sha256"] == sha256(path)
    alpha = [row for row in rows if row["original_name"] == "Alpha B.V."]
    assert len(alpha) == 2
    assert {row["source_kvk_hint"] for row in alpha} == {"12345678", "87654321"}
    assert all(row["kvk_queue_status"] == "REVIEW_REQUIRED" for row in alpha)
    assert len([row for row in rows if row["original_name"] == "Beta Stichting"]) == 2
    merged = next(row for row in alpha if row["source_count"] == "2")
    assert len(json.loads(merged["source_payloads_json"])) == 2
    assert run.latest_artifact("03", "pre_kvk_master") == path


def test_pre_kvk_rejects_limited_and_replaced_source(run: Run) -> None:
    paths = _full_sources(run)
    observations = run.metadata()["runtime_config"]["source_observations"]
    observations["wikidata_nl_companies"]["collection_complete"] = False
    run.record_config("source_observations", observations)
    with pytest.raises(HarvestError, match="volledig"):
        build_pre_kvk_list(run)
    observations["wikidata_nl_companies"]["collection_complete"] = True
    run.record_config("source_observations", observations)
    imported = run.artifact_path("02", "source_ind_arbeid_import", "csv")
    write_tsv(imported, RAW_HEADERS, [_raw("ind_arbeid", 99, "Import B.V.")])
    run.register_artifact(imported, "02", "source_ind_arbeid")
    with pytest.raises(HarvestError, match="bronbinding"):
        build_pre_kvk_list(run)
    assert paths["ind_arbeid"].is_file()
    assert run.latest_artifact("03", "pre_kvk_master") is None


def test_pre_kvk_checks_evidence_and_allows_historical_evidence(run: Run) -> None:
    _full_sources(run)
    old = run.path / "evidence" / "older_ind.dat"
    old.write_bytes(b"historisch")
    run.register_artifact(old, "02", "evidence_ind_arbeid")
    build_pre_kvk_list(run)

    current = run.path / "evidence" / "wikidata_nl_companies.dat"
    current.write_bytes(b"beschadigd")
    with pytest.raises(HarvestError, match="response-evidence"):
        build_pre_kvk_list(run)


def test_pre_kvk_refuses_changed_input_before_publish(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _full_sources(run)
    from company_harvest import pre_kvk

    original = pre_kvk._write_group
    changed = False

    def change_source(writer: csv.DictWriter[str], rows: list[dict[str, str]],
                      hints: set[str], stats, preview: bool = False) -> None:
        nonlocal changed
        original(writer, rows, hints, stats, preview)
        if not changed:
            with paths["ind_arbeid"].open("a", encoding="utf-8") as handle:
                handle.write("\n")
            changed = True

    monkeypatch.setattr(pre_kvk, "_write_group", change_source)
    with pytest.raises(HarvestError, match="registratie|veranderden"):
        build_pre_kvk_list(run)
    assert run.latest_artifact("03", "pre_kvk_master") is None


def test_blocked_preview_is_closed_but_never_kvk_ready(run: Run) -> None:
    _full_sources(run)
    with pytest.raises(HarvestError, match="geblokkeerde run"):
        build_blocked_pre_kvk_preview(run)
    with run.connect() as connection:
        connection.execute("DELETE FROM artifacts WHERE kind='source_wikidata_nl_companies'")
    run.update_status("PRE_KVK_BLOCKED")
    path, report_path = build_blocked_pre_kvk_preview(run)
    rows = read_tsv(path)
    report = json.loads(report_path.read_text())
    assert len(rows) == 4
    assert sum(int(row["source_count"]) for row in rows) == 4
    assert all(row["kvk_queue_status"] == "BLOCKED_SOURCE_INCOMPLETE" for row in rows)
    assert report["status"] == "BLOCKED_PREVIEW_NOT_KVK_READY"
    assert report["closure"] == "CLOSED_INCLUDED_SCOPE_ONLY"
    assert report["excluded_incomplete_sources"] == ["wikidata_nl_companies"]
    assert report["kvk_requests"] == 0
    assert run.latest_artifact("03", "pre_kvk_master") is None
    assert run.metadata()["status"] == "PRE_KVK_BLOCKED"
