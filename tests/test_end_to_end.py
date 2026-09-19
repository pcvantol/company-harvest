"""Synthetische end-to-end-tests; nooit live KVK- of brondownloads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_pre_kvk import _full_sources, _raw

from company_harvest import cli, end_to_end, pre_kvk_kvk, prepare
from company_harvest.audit import verify
from company_harvest.console import active as console_active
from company_harvest.core import (
    HarvestError,
    Run,
    initialize_run,
    open_run,
    read_tsv,
    sha256,
    write_tsv,
)
from company_harvest.kvk import KvkError, ProviderResult
from company_harvest.kvk_scope import bind_kvk_scope, scope_details
from company_harvest.pre_kvk import build_pre_kvk_list
from company_harvest.pre_kvk_filter import build_pre_kvk_filter
from company_harvest.sources import RAW_HEADERS
from company_harvest.workflow import export, outcome_metrics, report, write_xlsx


def _prepare(run: Run) -> tuple[Path, Path, Path, Path, Path]:
    if not run.latest_artifact("02", "source_ind_arbeid"):
        _full_sources(run)
    master, master_report = build_pre_kvk_list(run)
    eligible, excluded, metadata = build_pre_kvk_filter(run)
    return master, master_report, eligible, excluded, metadata


def _response(run: Run, query: str, number: str, sequence: int) -> ProviderResult:
    evidence = run.path / "evidence" / f"synthetic-e2e-{sequence}.json"
    evidence.write_text("{}", encoding="utf-8")
    assert query == number and query.isdecimal() and len(query) == 8
    name = {"34567890": "Delta B.V.", "23456789": "Gamma B.V."}.get(query, f"Synthetic {int(query) - 40000000:03d} B.V.")
    return ProviderResult(query, [{
        "naam": name, "kvkNummer": number, "plaats": "Utrecht", "land": "Nederland",
        "rechtsvorm": "Besloten vennootschap", "status": "Actief",
    }], True, "public-http", str(evidence.relative_to(run.path)))


def test_holding_label_survives_number_only_e2e_with_renamed_kvk_result(
    run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    _full_sources(run)
    original = run.latest_artifact("02", "source_ind_arbeid")
    assert original is not None
    rows = read_tsv(original)
    next(row for row in rows if row["source_kvk_hint"] == "34567890")["original_name"] = "Delta Holding B.V."
    updated = run.artifact_path("02", "source_ind_holding", "csv")
    write_tsv(updated, RAW_HEADERS, rows)
    run.register_artifact(updated, "02", "source_ind_arbeid")
    observations = run.metadata()["runtime_config"]["source_observations"]
    observations["ind_arbeid"]["source_artifact"] = {
        "path": str(updated.relative_to(run.path)), "sha256": sha256(updated), "size": updated.stat().st_size,
    }
    run.record_config("source_observations", observations)
    monkeypatch.setattr(end_to_end, "prepare_pre_kvk", _prepare)
    calls: list[str] = []

    def search(provider: object, query: str) -> ProviderResult:
        calls.append(query)
        assert query == "34567890"
        evidence = provider.run.path / "evidence" / "holding-number-response.json"  # type: ignore[attr-defined]
        evidence.write_text("{}")
        return ProviderResult(query, [{"naam": "Delta Operations B.V.", "kvkNummer": query,
                                       "plaats": "Utrecht", "land": "Nederland",
                                       "rechtsvorm": "Besloten vennootschap", "status": "Actief"}],
                              True, "public-http", str(evidence.relative_to(run.path)))

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", search)
    result = end_to_end.run_end_to_end(run, 1)
    assert calls == ["34567890"] and result["audit_valid"] and result["delivery_rows"] == 1
    labels = run.latest_artifact("03", "pre_kvk_review_labels")
    assert labels is not None
    label_rows = read_tsv(labels)
    assert len(label_rows) == 1 and label_rows[0]["review_label"] == "HOLDING_OR_MANAGEMENT"
    delivered = read_tsv(Path(result["outputset_manifest"]).parent / "companies_delivery_full.csv")
    assert delivered[0]["candidate_id"] == label_rows[0]["candidate_id"]
    assert delivered[0]["Bedrijfsnaam"] == "Delta Operations B.V."


def test_cli_e2e_bounded_from_empty_run_resumes_and_audits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_calls: list[str] = []
    monkeypatch.setattr(prepare, "discover", lambda _run: source_calls.append("discover"))

    def collect_sources(check_run: Run, **_kwargs: object) -> None:
        source_calls.append("ind")
        _full_sources(check_run)

    monkeypatch.setattr(prepare, "collect", collect_sources)
    monkeypatch.setattr(prepare, "collect_gleif", lambda _run, **_kw: source_calls.append("gleif"))
    monkeypatch.setattr(prepare, "collect_public_register", lambda _run, source, **_kw: source_calls.append(source))
    monkeypatch.setattr(prepare, "collect_tenderned", lambda _run, **_kw: source_calls.append("tenderned_awards"))
    calls: list[str] = []

    def search(provider: object, query: str) -> ProviderResult:
        calls.append(query)
        number = query
        return _response(provider.run, query, number, len(calls))  # type: ignore[attr-defined]

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", search)
    args = ["--data-dir", str(tmp_path), "run", "e2e", "--limit-kvk-check", "1"]
    assert cli.main(args) == 0
    captured = capsys.readouterr()
    output = captured.out
    progress_log = captured.err
    for phase in ("Broncatalogus controleren", "IND-bron verzamelen", "GLEIF-bron verzamelen",
                  "ANBI-bron verzamelen", "DUO-bron verzamelen", "TenderNed-bron verzamelen",
                  "Pre-KVK-filter toepassen",
                  "KVK-cohort binden", "KVK-kandidaten controleren", "Eenmanszaken uitsluiten",
                  "Definitieve eindlijst exporteren", "Rapport en eindaudit afronden"):
        assert phase in progress_log
    assert "KVK-checkpoint" in progress_log and "1/1" in progress_log
    assert "Delta B.V." not in progress_log and "34567890" not in progress_log
    run_path = Path(json.loads(output.splitlines()[0])["run_dir"])
    run = open_run(run_path)
    scope = scope_details(run)
    assert scope is not None
    assert scope["limit_kvk_check"] == 1 and scope["selected_rows"] == 1
    assert scope["full_eligible_rows"] == 2 and scope["not_checked_rows"] == 1
    assert source_calls == ["discover", "ind", "gleif", "anbi_register", "duo_education_organisations", "tenderned_awards"]
    assert len(calls) == 1
    assert run.metadata()["status"] == "PARTIAL_EXPORTED"
    assert verify(run)["valid"]
    assert outcome_metrics(run)["counts"]["kvk_not_checked_out_of_scope"] == 1
    assert outcome_metrics(run)["count_closure"]["transitions"]["candidates_to_kvk_terminal"]["status"] == "CLOSED"
    with run.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM kvk_requests").fetchone()[0] == 1
    assert len(read_tsv(run_path / "pre_kvk_kvk_matches.tsv")) == 1
    legacy_config = dict(run.metadata()["runtime_config"]["end_to_end"])
    run.record_config("end_to_end", {**legacy_config, "export_limit": 1})
    assert cli.main(args[:-2] + ["--run-dir", str(run_path), "--limit-kvk-check", "1"]) == 0
    capsys.readouterr()
    assert len(calls) == 1
    assert cli.main(["run", "e2e", "--run-dir", str(run_path), "--limit-kvk-check", "2"]) == 3
    assert "niet wijzigen" in capsys.readouterr().err
    assert cli.main(["run", "e2e", "--run-dir", str(run_path),
                     "--limit-kvk-check", "1", "--interval", "3"]) == 3
    assert "niet wijzigen" in capsys.readouterr().err
    pre_kvk_kvk.run_pre_kvk(run, max_requests=100)
    assert len(calls) == 1


def test_e2e_unresolved_requires_explicit_partial_and_does_not_invent_match(
    run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(end_to_end, "prepare_pre_kvk", _prepare)
    calls = 0

    def search(provider: object, query: str) -> ProviderResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            number = query
            return _response(provider.run, query, number, calls)  # type: ignore[attr-defined]
        evidence = run.path / "evidence" / "synthetic-empty.json"
        evidence.write_text("{}")
        return ProviderResult(query, [], True, "public-http", str(evidence.relative_to(run.path)))

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", search)
    with pytest.raises(HarvestError, match="allow-partial"):
        end_to_end.run_end_to_end(run, 2)
    assert calls == 2 and run.latest_artifact("08", "outputset_manifest") is None
    result = end_to_end.run_end_to_end(run, 2, allow_partial=True)
    assert calls == 2 and result["delivery_rows"] == 1
    assert result["status"] == "PARTIAL_EXPORTED" and result["audit_valid"]
    assert len(read_tsv(Path(result["delivery_csv"]))) == 1


@pytest.mark.parametrize(
    "tamper",
    ["missing_manifest_status", "missing_selection_policy", "changed_file", "changed_light_file", "wrong_file_status", "run_not_exported"],
)
def test_audit_checks_newest_partial_manifest_and_its_registered_files(
    run: Run, monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    monkeypatch.setattr(end_to_end, "prepare_pre_kvk", _prepare)
    monkeypatch.setattr(
        pre_kvk_kvk.PublicHttpProvider,
        "search",
        lambda provider, query: _response(
            provider.run, query, query, 1
        ),
    )
    result = end_to_end.run_end_to_end(run, 1)
    first_manifest = Path(result["outputset_manifest"])
    assert result["status"] == "PARTIAL_EXPORTED" and result["audit_valid"]
    assert run.latest_artifact("08", "outputset_manifest") is None

    newest_manifest = export(run, allow_partial=True)[-1]
    assert newest_manifest != first_manifest
    report(run)
    assert verify(run)["valid"]
    with run.connect() as connection:
        latest = connection.execute(
            "SELECT path,status FROM artifacts WHERE step='08' AND kind='outputset_manifest' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert latest["path"] == str(newest_manifest.relative_to(run.path))
    assert latest["status"] == "PARTIAL"

    if tamper == "missing_manifest_status":
        payload = json.loads(newest_manifest.read_text(encoding="utf-8"))
        del payload["status"]
        newest_manifest.write_text(json.dumps(payload), encoding="utf-8")
        changed = newest_manifest
        expected = "OUTPUTSET:status_mismatch"
    elif tamper == "missing_selection_policy":
        payload = json.loads(newest_manifest.read_text(encoding="utf-8"))
        del payload["selection_policy"]
        newest_manifest.write_text(json.dumps(payload), encoding="utf-8")
        changed = newest_manifest
        expected = "OUTPUTSET:selection_policy_missing"
    elif tamper == "changed_file":
        changed = newest_manifest.parent / "companies_delivery.csv"
        changed.write_text("Bedrijfsnaam\tKVK-nummer\nAnders\t23456789\n", encoding="utf-8")
        expected = "OUTPUTSET:companies_delivery.csv"
    elif tamper == "changed_light_file":
        changed = newest_manifest.parent / "companies_delivery_light.csv"
        changed.write_text("Bedrijfsnaam\tKVK-nummer\nAnders\t23456789\n", encoding="utf-8")
        expected = "OUTPUTSET:companies_delivery_light.csv"
    elif tamper == "wrong_file_status":
        changed = None
        expected = "OUTPUTSET:companies_delivery.csv"
    else:
        changed = None
        expected = "OUTPUTSET:status_mismatch"
        run.update_status("IN_PROGRESS", "08")
    with run.connect() as connection:
        if changed is not None:
            connection.execute(
                "UPDATE artifacts SET sha256=?,size=? WHERE path=?",
                (sha256(changed), changed.stat().st_size, str(changed.relative_to(run.path))),
            )
        elif tamper == "wrong_file_status":
            connection.execute(
                "UPDATE artifacts SET status='COMPLETE' WHERE path=?",
                (str((newest_manifest.parent / "companies_delivery.csv").relative_to(run.path)),),
            )
    with pytest.raises(HarvestError) as error:
        verify(run)
    assert expected in json.loads(str(error.value))["errors"]


def test_e2e_stops_at_block_and_never_exports(
    run: Run, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(end_to_end, "prepare_pre_kvk", _prepare)
    calls = 0

    def blocked(_provider: object, _query: str) -> ProviderResult:
        nonlocal calls
        calls += 1
        raise KvkError("PUBLIC_ACCESS_BLOCKED", "synthetic blocked")

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", blocked)
    with pytest.raises(HarvestError, match="BLOCKED") as error:
        with console_active():
            end_to_end.run_end_to_end(run, 2)
    assert error.value.exit_code == 4 and calls == 1
    progress_log = capsys.readouterr().err
    assert "KVK-kandidaten controleren gestopt" in progress_log
    assert "synthetic blocked" not in progress_log
    assert run.latest_artifact("07", "active") is None
    with pytest.raises(HarvestError, match="blokkade"):
        end_to_end.run_end_to_end(run, 2)
    assert calls == 1


def test_scope_rejects_changes_and_existing_journal(run: Run) -> None:
    _prepare(run)
    scope = bind_kvk_scope(run, 1)
    assert bind_kvk_scope(run, 1) == scope
    with pytest.raises(HarvestError, match="limiet"):
        bind_kvk_scope(run, 2)
    scoped = run.path / str(scope["scoped_path"])
    scoped.write_text("changed", encoding="utf-8")
    with pytest.raises(HarvestError, match="artefact|cohort"):
        scope_details(run)
    other = initialize_run(run.path.parent, 1)
    _prepare(other)
    with other.connect() as connection:
        connection.execute("INSERT INTO kvk_requests(candidate_id,state) VALUES('x','IN_FLIGHT')")
    with pytest.raises(HarvestError, match="achteraf"):
        bind_kvk_scope(other, 1)


def test_e2e_rejects_invalid_scope_and_nonharvest(run: Run) -> None:
    for limit, interval in ((0, 2.0), (1, 1.9)):
        with pytest.raises(HarvestError, match="positieve"):
            end_to_end.run_end_to_end(run, limit, interval)
    other = initialize_run(run.path.parent, 1, "MERGE_LISTS")
    with pytest.raises(HarvestError, match="preflight"):
        end_to_end.run_end_to_end(other, 1)


def test_old_export_cap_only_migrates_when_it_could_not_bind(
    run: Run, monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = {
        "limit_kvk_check": 2, "interval": 2.0,
        "export_limit": 1, "provider": "public-http",
    }
    run.record_config("end_to_end", legacy)
    with pytest.raises(HarvestError, match="oude E2E-run.*exportlimiet"):
        end_to_end.run_end_to_end(run, 2)
    assert run.metadata()["runtime_config"]["end_to_end"] == legacy

    run.record_config("end_to_end", {**legacy, "export_limit": 2})
    monkeypatch.setattr(
        end_to_end, "prepare_pre_kvk",
        lambda _run: (_ for _ in ()).throw(HarvestError("prepare reached")),
    )
    with pytest.raises(HarvestError, match="prepare reached"):
        end_to_end.run_end_to_end(run, 2)
    assert run.metadata()["runtime_config"]["end_to_end"] == {
        "limit_kvk_check": 2, "interval": 2.0, "provider": "public-http",
    }


def test_all_kvk_exports_all_and_legacy_nonempty_reserve_remains_auditable(
    run: Run, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(end_to_end, "prepare_pre_kvk", _prepare)
    monkeypatch.setattr(pre_kvk_kvk, "_pace_request", lambda _run, _interval: None)
    calls = 0

    def search(provider: object, query: str) -> ProviderResult:
        nonlocal calls
        calls += 1
        number = query
        return _response(provider.run, query, number, calls)  # type: ignore[attr-defined]

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", search)
    result = end_to_end.run_end_to_end(run, None)
    assert calls == 2 and result["delivery_rows"] == 2 and result["audit_valid"]
    manifest = Path(result["outputset_manifest"])
    payload = json.loads(manifest.read_text())
    assert payload["selection_policy"] == "ALL_ACTIVE"
    assert read_tsv(manifest.parent / "companies_reserve.csv") == []

    # Simuleer een intacte oude v2-outputset: 1 levering, 1 reserve, geen policy.
    full = read_tsv(manifest.parent / "companies_delivery_full.csv")
    assert len(full) == 2
    minimal = ["Bedrijfsnaam", "KVK-nummer"]
    full_headers = list(full[0])
    write_tsv(manifest.parent / "companies_delivery.csv", minimal, full[:1])
    write_xlsx(manifest.parent / "companies_delivery.xlsx", minimal, full[:1])
    write_tsv(manifest.parent / "companies_delivery_full.csv", full_headers, full[:1])
    write_xlsx(manifest.parent / "companies_delivery_full.xlsx", full_headers, full[:1])
    write_tsv(manifest.parent / "companies_reserve.csv", full_headers, full[1:])
    del payload["selection_policy"]
    del payload["active_rows"]
    payload["schema"] = 1
    payload["files"] = [entry for entry in payload["files"] if entry["kind"] not in {"delivery_light_csv", "delivery_light_xlsx"}]
    payload.pop("light_source", None)
    with run.connect() as connection:
        for entry in payload["files"]:
            path = manifest.parent / entry["path"]
            entry["sha256"] = sha256(path)
            entry["size"] = path.stat().st_size
            connection.execute(
                "UPDATE artifacts SET sha256=?,size=? WHERE path=?",
                (entry["sha256"], entry["size"], str(path.relative_to(run.path))),
            )
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        connection.execute(
            "UPDATE artifacts SET sha256=?,size=? WHERE path=?",
            (sha256(manifest), manifest.stat().st_size, str(manifest.relative_to(run.path))),
        )
    run.record_config("export", {"limit": 1, "allow_partial": False})
    old_e2e_config = dict(run.metadata()["runtime_config"]["end_to_end"])
    run.record_config("end_to_end", {**old_e2e_config, "export_limit": 1})
    assert verify(run)["valid"]
    resumed = end_to_end.run_end_to_end(run, None)
    assert resumed["delivery_rows"] == 1 and resumed["audit_valid"] and calls == 2


def test_bounded_progress_records_only_selected_count(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare(run)
    bind_kvk_scope(run, 1)
    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", lambda provider, query: _response(
        provider.run, query, query, 1))
    _, _, progress = pre_kvk_kvk.run_pre_kvk(run, max_requests=100)
    state = json.loads(progress.read_text(encoding="utf-8"))
    assert state["status"] == "COMPLETE" and state["eligible_rows"] == 1
    assert state["journal_rows"] == 1 and state["remaining"] == 0
    assert verify(run)["valid"]


def test_limit_50_is_total_run_cap_and_output_cap(
    run: Run, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def prepare_many(check_run: Run) -> tuple[Path, Path, Path, Path, Path]:
        _full_sources(check_run)
        rows = [_raw("ind_arbeid", index + 10, f"Synthetic {index:03d} B.V.", f"{40000000 + index:08d}")
                for index in range(60)]
        old = check_run.latest_artifact("02", "source_ind_arbeid")
        assert old is not None
        path = check_run.artifact_path("02", "source_ind_arbeid_more", "csv")
        write_tsv(path, RAW_HEADERS, read_tsv(old) + rows)
        check_run.register_artifact(path, "02", "source_ind_arbeid")
        observations = check_run.metadata()["runtime_config"]["source_observations"]
        observations["ind_arbeid"]["source_artifact"] = {
            "path": str(path.relative_to(check_run.path)), "sha256": sha256(path),
            "size": path.stat().st_size,
        }
        check_run.record_config("source_observations", observations)
        master, master_report = build_pre_kvk_list(check_run)
        eligible, excluded, metadata = build_pre_kvk_filter(check_run)
        return master, master_report, eligible, excluded, metadata

    monkeypatch.setattr(end_to_end, "prepare_pre_kvk", prepare_many)
    monkeypatch.setattr(pre_kvk_kvk, "_pace_request", lambda _run, _interval: None)
    calls = 0

    def search(provider: object, query: str) -> ProviderResult:
        nonlocal calls
        calls += 1
        number = query
        return _response(provider.run, query, number, calls)  # type: ignore[attr-defined]

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", search)
    with console_active():
        result = end_to_end.run_end_to_end(run, 50)
    progress_log = capsys.readouterr().err
    for checkpoint in ("1/50", "10/50", "20/50", "30/50", "40/50", "50/50"):
        assert checkpoint in progress_log
    assert "Synthetic 000" not in progress_log and "40000000" not in progress_log
    assert calls == 50 and result["delivery_rows"] == 50
    scope = result["scope"]
    assert scope["full_eligible_rows"] == 62 and scope["not_checked_rows"] == 12
    manifest = json.loads(Path(result["outputset_manifest"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "PARTIAL"
    assert manifest["selection_policy"] == "ALL_ACTIVE" and manifest["active_rows"] == 50
    assert read_tsv(Path(result["outputset_manifest"]).parent / "companies_reserve.csv") == []
    assert manifest["kvk_scope"]["limit_kvk_check"] == 50
    assert verify(run)["valid"]
    with run.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM kvk_requests").fetchone()[0] == 50


def test_new_run_does_not_bypass_prior_access_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prior = initialize_run(tmp_path, 1)
    with prior.connect() as connection:
        connection.execute("INSERT INTO kvk_requests(candidate_id,state,error) "
                           "VALUES('prior','FAILED','PUBLIC_ACCESS_BLOCKED')")
    later = initialize_run(tmp_path, 1)
    monkeypatch.setattr(end_to_end, "prepare_pre_kvk", lambda _run: pytest.fail("broninname mag niet beginnen"))
    with pytest.raises(HarvestError, match="eerdere KVK-toegangsblokkade") as error:
        end_to_end.run_end_to_end(later, 1)
    assert error.value.exit_code == 4


def test_block_during_source_prep_stops_before_first_get(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prior = initialize_run(tmp_path, 1)
    later = initialize_run(tmp_path, 1)
    calls = 0

    def prepare_while_other_run_blocks(check_run: Run) -> tuple[Path, Path, Path, Path, Path]:
        result = _prepare(check_run)
        with prior.connect() as connection:
            connection.execute("INSERT INTO kvk_requests(candidate_id,state,error) "
                               "VALUES('prior','FAILED','PUBLIC_ACCESS_BLOCKED')")
        return result

    def search(_provider: object, _query: str) -> ProviderResult:
        nonlocal calls
        calls += 1
        pytest.fail("na een blokkade in dezelfde datamap mag geen GET volgen")

    monkeypatch.setattr(end_to_end, "prepare_pre_kvk", prepare_while_other_run_blocks)
    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", search)
    with pytest.raises(HarvestError, match="toegangsblokkade") as error:
        end_to_end.run_end_to_end(later, 1)
    assert error.value.exit_code == 4 and calls == 0
    with later.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM kvk_requests").fetchone()[0] == 0


def test_report_crash_after_export_is_repaired_on_resume(
    run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(end_to_end, "prepare_pre_kvk", _prepare)
    calls = 0

    def search(provider: object, query: str) -> ProviderResult:
        nonlocal calls
        calls += 1
        return _response(provider.run, query, query, calls)  # type: ignore[attr-defined]

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", search)
    original_report = end_to_end.report
    monkeypatch.setattr(end_to_end, "report", lambda _run: (_ for _ in ()).throw(OSError("report crash")))
    with pytest.raises(OSError, match="report crash"):
        end_to_end.run_end_to_end(run, 1)
    assert run.metadata()["status"] == "PARTIAL_EXPORTED" and calls == 1
    with pytest.raises(HarvestError, match="outcome_report_after_outputset"):
        verify(run)
    monkeypatch.setattr(end_to_end, "report", original_report)
    result = end_to_end.run_end_to_end(run, 1)
    assert result["audit_valid"] and calls == 1
    with run.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM artifacts WHERE kind='outputset_manifest'").fetchone()[0] == 1


def test_full_e2e_requires_explicit_partial_export_for_unresolved(
    run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(end_to_end, "prepare_pre_kvk", _prepare)
    monkeypatch.setattr(pre_kvk_kvk, "_pace_request", lambda _run, _interval: None)
    calls = 0

    def no_match(provider: object, query: str) -> ProviderResult:
        nonlocal calls
        calls += 1
        evidence = provider.run.path / "evidence" / f"no-match-{calls}.json"  # type: ignore[attr-defined]
        evidence.write_text("{}")
        return ProviderResult(query, [], True, "public-http", str(evidence.relative_to(run.path)))

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", no_match)
    with pytest.raises(HarvestError, match="allow-partial"):
        end_to_end.run_end_to_end(run, None)
    assert calls == 2
    result = end_to_end.run_end_to_end(run, None, allow_partial=True)
    assert calls == 2 and result["status"] == "PARTIAL_EXPORTED"
    assert result["scope"] is None and result["delivery_rows"] == 0
    assert result["audit_valid"]
