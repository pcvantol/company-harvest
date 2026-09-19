"""Verticale filtertests: behoud, redenen en fail-closed KVK-routing."""

import json

import pytest
from test_pre_kvk import _full_sources

from company_harvest.core import HarvestError, Run, read_tsv, sha256
from company_harvest.pre_kvk import build_pre_kvk_list
from company_harvest.pre_kvk_filter import (
    RULE_VERSION,
    _reasons,
    build_pre_kvk_filter,
    validated_filter,
)
from company_harvest.pre_kvk_kvk import resolve_pre_kvk


def _row(name: str, sources: list[str] | None = None, hint: str = "12345678",
         queue: str = "READY_FOR_KVK_VERIFICATION", sector: str = "") -> dict[str, str]:
    return {"original_name": name, "source_kvk_hint": hint, "sector": sector,
            "kvk_queue_status": queue,
            "source_relations": json.dumps([{"source_id": source} for source in (sources or ["ind_arbeid"])])}


@pytest.mark.parametrize(("name", "reason"), [
    ("Acme Holding B.V.", "HOLDING_OR_MANAGEMENT"),
    ("Acme Beheermaatschappij B.V.", "HOLDING_OR_MANAGEMENT"),
    ("Acme Beheersmaatschappij B.V.", "HOLDING_OR_MANAGEMENT"),
    ("Acme Beheer B.V.", "HOLDING_OR_MANAGEMENT"),
    ("Stichting Acme", "FOUNDATION_OR_ASSOCIATION"),
    ("Acme Vereniging", "FOUNDATION_OR_ASSOCIATION"),
    ("Acme Buurtvereniging", "FOUNDATION_OR_ASSOCIATION"),
    ("Acme Pensioenstichting", "FOUNDATION_OR_ASSOCIATION"),
    ("Acme Hogeschool", "SCHOOL_OR_UNIVERSITY"),
    ("Acme Vrijeschool", "SCHOOL_OR_UNIVERSITY"),
    ("Acme Bank N.V.", "BANK"),
    ("Acme Spaarbank N.V.", "BANK"),
    ("Acme Hypotheekbank N.V.", "BANK"),
    ("Acme Pensioenfonds", "PENSION_FUND"),
    ("Acme Bedrijfstakpensioenfonds", "PENSION_FUND"),
    ("Acme Equity Europe Pool", "FUND_OR_EQUITY_NAME"),
    ("Acme Fonds", "FUND_OR_EQUITY_NAME"),
    ("Acme Investeringsfonds", "FUND_OR_EQUITY_NAME"),
    ("Kerkgenootschap Acme", "RELIGIOUS_ORGANISATION"),
    ("Acme Dorpskerk", "RELIGIOUS_ORGANISATION"),
    ("Diaconie te Utrecht", "RELIGIOUS_ORGANISATION"),
    ("Jehovah's Getuigen Utrecht", "RELIGIOUS_ORGANISATION"),
    ("ChristenUnie Twenterand", "POLITICAL_PARTY"),
])
def test_named_exclusions(name: str, reason: str) -> None:
    reasons, sources = _reasons(_row(name))
    assert reason in reasons and sources == ["ind_arbeid"]


def test_source_and_missing_hint_rules_and_false_positive_boundaries() -> None:
    reasons, sources = _reasons(_row("Acme Fund", ["anbi_register", "duo_education_organisations"], ""))
    assert reasons[:3] == ["ANBI_SOURCE", "EDUCATION_SOURCE", "NO_DIRECT_KVK_HINT"]
    assert sources == ["anbi_register", "duo_education_organisations"]
    assert "FUND_OR_EQUITY_NAME" in reasons
    assert _reasons(_row("Algemeen nut beogende instelling", sector="algemeen nut beogende instelling"))[0] == ["ANBI_SOURCE"]
    assert _reasons(_row("Banketbakkerij De Pool B.V."))[0] == []
    assert _reasons(_row("Acme Werkbank B.V."))[0] == []
    assert _reasons(_row("Acme Nieuwkerk B.V."))[0] == []
    assert _reasons(_row("Acme Project Beheer en Onderhoud B.V."))[0] == []
    assert _reasons(_row("Acme B.V.", hint=""))[0] == ["NO_DIRECT_KVK_HINT"]
    assert _reasons(_row("Acme B.V.", queue="REVIEW_REQUIRED"))[0] == ["SOURCE_CONFLICT_REVIEW"]


@pytest.mark.parametrize("relations", ["not json", "[]", '[{"source_id":"wikidata_nl_companies"}]'])
def test_bad_source_relations_fail_closed(relations: str) -> None:
    row = _row("Acme B.V.")
    row["source_relations"] = relations
    with pytest.raises(HarvestError, match="bronrelaties"):
        _reasons(row)


def test_bad_queue_status_fails_closed() -> None:
    with pytest.raises(HarvestError, match="wachtrijstatus"):
        _reasons(_row("Acme B.V.", queue="BLOCKED_SOURCE_INCOMPLETE"))


def test_filter_vertical_slice_retains_master_and_exclusion_ledger(run: Run) -> None:
    _full_sources(run)
    master, _ = build_pre_kvk_list(run)
    original_hash = sha256(master)
    with pytest.raises(HarvestError, match="pre_kvk_eligible"):
        resolve_pre_kvk(run, 1)
    eligible, excluded, metadata_path = build_pre_kvk_filter(run)
    metadata = json.loads(metadata_path.read_text())
    assert sha256(master) == original_hash
    assert len(read_tsv(master)) == 6
    assert {row["original_name"] for row in read_tsv(eligible)} == {"Gamma B.V.", "Delta B.V."}
    ledger = read_tsv(excluded)
    assert len(ledger) == 4
    assert {row["original_name"] for row in ledger} == {"Alpha B.V.", "Beta Stichting"}
    assert all(json.loads(row["all_reasons_json"]) for row in ledger)
    assert metadata["rule_version"] == RULE_VERSION
    assert metadata["counts"] == {"master_rows": 6, "excluded_rows": 4, "eligible_rows": 2}
    assert metadata["count_closure"] == "CLOSED"
    assert metadata["master_sha256"] == original_hash
    assert metadata["eligible_sha256"] == sha256(eligible)
    assert metadata["excluded_sha256"] == sha256(excluded)
    assert build_pre_kvk_filter(run) == (eligible, excluded, metadata_path)
    assert validated_filter(run, original_hash)[:4] == (eligible, sha256(eligible), excluded, sha256(excluded))


def test_filter_rejects_modified_ledger_and_active_journal(run: Run) -> None:
    _full_sources(run)
    build_pre_kvk_list(run)
    _eligible, excluded, _metadata = build_pre_kvk_filter(run)
    excluded.write_text(excluded.read_text() + "extra\n")
    with pytest.raises(HarvestError, match="COMPLETE-registratie"):
        resolve_pre_kvk(run, 1)
    with run.connect() as connection:
        connection.execute("INSERT INTO kvk_requests(candidate_id,query,state,attempt,provider) "
                           "VALUES('test-id','Acme','SUCCEEDED',1,'public-http')")
    with pytest.raises(HarvestError, match="migratiebesluit"):
        build_pre_kvk_filter(run)


def test_filter_rejects_registered_but_inconsistent_metadata(run: Run) -> None:
    _full_sources(run)
    build_pre_kvk_list(run)
    _eligible, _excluded, metadata_path = build_pre_kvk_filter(run)
    metadata = json.loads(metadata_path.read_text())
    metadata["counts"]["excluded_rows"] += 1
    corrupt = run.artifact_path("03", "pre_kvk_filter_metadata_wrong_counts", "json")
    corrupt.write_text(json.dumps(metadata))
    run.register_artifact(corrupt, "03", "pre_kvk_filter_metadata")
    with pytest.raises(HarvestError, match="gesloten aantallen"):
        resolve_pre_kvk(run, 1)


def test_filter_rejects_registered_but_different_pattern(run: Run) -> None:
    _full_sources(run)
    build_pre_kvk_list(run)
    _eligible, _excluded, metadata_path = build_pre_kvk_filter(run)
    metadata = json.loads(metadata_path.read_text())
    metadata["patterns"]["BANK"]["regex"] = r"\b(?:bank|banken)\b"
    changed = run.artifact_path("03", "pre_kvk_filter_metadata_different_pattern", "json")
    changed.write_text(json.dumps(metadata))
    run.register_artifact(changed, "03", "pre_kvk_filter_metadata")
    with pytest.raises(HarvestError, match="niet actueel"):
        resolve_pre_kvk(run, 1)
