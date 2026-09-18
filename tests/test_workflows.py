from pathlib import Path

import pytest
from openpyxl import load_workbook

from company_harvest.audit import _overlap, trace, verify
from company_harvest.core import HarvestError, read_tsv, write_tsv
from company_harvest.workflow import (
    active_only,
    consolidate,
    exclude_sole_proprietorships,
    export,
    merge_candidates,
    report,
    write_xlsx,
)


def _register(run, step, kind, headers, rows):
    path = run.artifact_path(step, kind, "csv")
    write_tsv(path, headers, rows)
    run.register_artifact(path, step, kind)
    return path


def test_harvest_offline_pipeline(run) -> None:
    headers = ["original_name", "country", "nl_evidence", "employees_raw", "employees_date", "employees_scope", "website", "sector", "source_kvk_hint", "source_id", "source_url", "fetched_at", "source_row", "evidence_reference"]
    base = {"country": "Nederland", "nl_evidence": "register", "employees_raw": "", "employees_date": "", "employees_scope": "", "website": "", "sector": "", "source_url": "https://example.invalid", "fetched_at": "now", "evidence_reference": "local"}
    rows = [{**base, "original_name": "Alpha B.V.", "source_kvk_hint": "01234567", "source_id": "a", "source_row": "1"}, {**base, "original_name": " Alpha   B.V. ", "source_kvk_hint": "01234567", "source_id": "a", "source_row": "2"}]
    _register(run, "02", "source_a", headers, rows)
    candidates, decisions, conflicts = merge_candidates(run)
    assert len(read_tsv(candidates)) == 1 and read_tsv(decisions)[0]["decision"] == "MERGED_IDENTICAL"
    assert read_tsv(conflicts) == []
    candidate_id = read_tsv(candidates)[0]["candidate_id"]
    match_headers = ["candidate_id", "Bedrijfsnaam", "KVK-nummer", "raw_legal_form", "raw_status", "city", "country", "match_method", "provider", "checked_at", "response_json", "source_relations"]
    _register(run, "04", "kvk_matches", match_headers, [{"candidate_id": candidate_id, "Bedrijfsnaam": "Alpha B.V.", "KVK-nummer": "01234567", "raw_legal_form": "Besloten vennootschap", "raw_status": "Actief", "city": "Utrecht", "country": "Nederland", "match_method": "SOURCE_KVK_CONFIRMED", "provider": "mock", "checked_at": "now", "response_json": "{}", "source_relations": "[]"}])
    canonical = consolidate(run)
    assert read_tsv(canonical)[0]["KVK-nummer"] == "01234567"
    assert len(read_tsv(exclude_sole_proprietorships(run)[0])) == 1
    assert len(read_tsv(active_only(run)[0])) == 1
    outputs = export(run, 100)
    assert load_workbook(outputs[1])["Bedrijven"]["B2"].value == "01234567"
    assert report(run).is_file()
    assert verify(run)["valid"]
    with run.connect() as connection:
        connection.execute(
            "INSERT INTO kvk_requests(candidate_id,query,state,attempt,request_fingerprint,provider) VALUES(?,?,'SUCCEEDED',1,?,?)",
            (candidate_id, "Alpha B.V.", "fingerprint", "mock"),
        )
    traced = trace(run, "01234567")
    assert traced["trace"] and traced["request_journal"]


def test_filters_partial_and_integrity(run) -> None:
    headers = ["Bedrijfsnaam", "KVK-nummer", "raw_legal_form", "raw_status"]
    _register(run, "05", "canonical", headers, [{"Bedrijfsnaam": "Een", "KVK-nummer": "11111111", "raw_legal_form": "eenmanszaak", "raw_status": "actief"}, {"Bedrijfsnaam": "Onbekend", "KVK-nummer": "22222222", "raw_legal_form": "mystery", "raw_status": ""}, {"Bedrijfsnaam": "Inactief BV", "KVK-nummer": "33333333", "raw_legal_form": "BV", "raw_status": "inactief"}])
    included, excluded, review = exclude_sole_proprietorships(run)
    assert len(read_tsv(included)) == 1 and len(read_tsv(excluded)) == 1 and len(read_tsv(review)) == 1
    active, inactive, status_review = active_only(run)
    assert read_tsv(active) == [] and len(read_tsv(inactive)) == 1 and read_tsv(status_review) == []
    unresolved = _register(run, "05", "kvk_unresolved", ["candidate_id", "reason"], [{"candidate_id": "x", "reason": "NOT_FOUND"}])
    with pytest.raises(HarvestError):
        export(run, 10)
    assert export(run, 10, allow_partial=True)
    unresolved.write_text("changed")
    with pytest.raises(HarvestError) as error:
        verify(run)
    assert error.value.exit_code == 7
    with pytest.raises(HarvestError):
        trace(run, "99999999")


def test_excel_safe_text(tmp_path: Path) -> None:
    path = tmp_path / "safe.xlsx"
    write_xlsx(path, ["Bedrijfsnaam", "KVK-nummer"], [{"Bedrijfsnaam": "=cmd", "KVK-nummer": "00123456"}])
    sheet = load_workbook(path)["Bedrijven"]
    assert sheet["A2"].value == "'=cmd" and sheet.freeze_panes == "A2"


def test_partition_overlap_and_atomic_export_failure(run, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _overlap([[{"KVK-nummer": "01234567"}], [{"KVK-nummer": "01234567"}]])
    _register(run, "07", "active", ["Bedrijfsnaam", "KVK-nummer"], [{"Bedrijfsnaam": "Alpha", "KVK-nummer": "01234567"}])
    monkeypatch.setattr("company_harvest.workflow.write_xlsx", lambda *args: (_ for _ in ()).throw(OSError("fault")))
    with pytest.raises(OSError):
        export(run, 1)
    assert not list((run.path / "artifacts").glob("*_08_delivery_outputset"))
    assert not list((run.path / "artifacts").glob(".*_08_delivery_outputset.tmp"))
