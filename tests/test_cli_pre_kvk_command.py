"""De geïntegreerde bronvoorbereiding stopt aantoonbaar vóór iedere KVK-aanroep."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_pre_kvk import _full_sources
from test_tenderned import mock_official_download, snapshots

from company_lookup import cli, prepare
from company_lookup.core import HarvestError, Run, initialize_run, open_run, read_tsv
from company_lookup.pre_kvk_kvk import PublicHttpProvider
from company_lookup.tenderned import collect_tenderned


def _offline_sources(monkeypatch: pytest.MonkeyPatch, calls: list[str], root: Path) -> None:
    xlsx, json_file = snapshots(root)
    mock_official_download(monkeypatch, xlsx, json_file)
    monkeypatch.setattr(prepare, "discover", lambda _run: calls.append("discover"))

    def collect(check_run: Run, **_kwargs: object) -> None:
        calls.append("ind")
        if not check_run.latest_artifact("02", "source_ind_arbeid"):
            _full_sources(check_run, legacy_scope=False)

    monkeypatch.setattr(prepare, "collect", collect)
    monkeypatch.setattr(prepare, "collect_gleif", lambda _run, **_kw: calls.append("gleif"))
    monkeypatch.setattr(prepare, "collect_public_register", lambda _run, source, **_kw: calls.append(source))
    def tenderned(check_run: Run, **_kwargs: object) -> None:
        calls.append("tenderned_awards")
        collect_tenderned(check_run)

    monkeypatch.setattr(prepare, "collect_tenderned", tenderned)


def _forbid_kvk(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("pre-KVK-commando mag geen KVK-verzoek doen")

    monkeypatch.setattr(PublicHttpProvider, "search", forbidden)
    monkeypatch.setattr(cli, "run_end_to_end", forbidden)


def test_one_command_builds_five_source_kvk_input_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    _offline_sources(monkeypatch, calls, tmp_path)
    _forbid_kvk(monkeypatch)
    assert cli.main(["--data-dir", str(tmp_path), "run", "pre-kvk"]) == 0
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    start = json.loads(lines[0])
    result = json.loads("\n".join(lines[1:]))
    run_path = Path(start["run_dir"])
    run = open_run(run_path)
    assert start["phase"] == "STARTING"
    assert result["status"] == "PRE_KVK_READY" and result["run_dir"] == str(run_path)
    assert result["counts"]["master_rows"] == result["counts"]["eligible_rows"] + result["counts"]["excluded_rows"]
    assert len(read_tsv(Path(result["kvk_input"]))) == result["counts"]["eligible_rows"]
    master_report = json.loads(Path(result["master_report"]).read_text(encoding="utf-8"))
    assert master_report["scope"] == [
        "ind_arbeid", "gleif_golden_copy", "anbi_register",
        "duo_education_organisations", "tenderned_awards",
    ]
    assert master_report["sources"]["tenderned_awards"]["candidate_records"] == 4
    assert any(row["original_name"] == "Tweede Gunning B.V." for row in read_tsv(Path(result["kvk_input"])))
    assert all(Path(result[key]).is_file() for key in ("master", "master_report", "kvk_input", "excluded", "filter_metadata"))
    assert calls == ["discover", "ind", "gleif", "anbi_register", "duo_education_organisations", "tenderned_awards"]
    assert "KVK-kandidaten controleren" not in captured.err
    with run.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM kvk_requests").fetchone()[0] == 0
        artifact_count = connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    assert run.latest_artifact("04", "kvk_matches") is None

    assert cli.main(["run", "pre-kvk", "--run-dir", str(run_path)]) == 0
    resumed = capsys.readouterr()
    resumed_result = json.loads("\n".join(resumed.out.splitlines()[1:]))
    assert resumed_result == result
    assert calls.count("discover") == 1
    with run.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == artifact_count
        assert connection.execute("SELECT COUNT(*) FROM kvk_requests").fetchone()[0] == 0


def test_one_command_can_resume_after_source_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    _forbid_kvk(monkeypatch)
    monkeypatch.setattr(prepare, "discover", lambda _run: None)

    def blocked(_run: Run, **_kwargs: object) -> None:
        raise HarvestError("bron tijdelijk niet beschikbaar")

    monkeypatch.setattr(prepare, "collect", blocked)
    assert cli.main(["--data-dir", str(tmp_path), "run", "pre-kvk"]) == 3
    failed = capsys.readouterr()
    run_path = Path(json.loads(failed.out.splitlines()[0])["run_dir"])
    assert run_path.is_dir() and "Ongeldige invoer of runstatus" in failed.err
    assert "bron tijdelijk niet beschikbaar" not in failed.err
    calls: list[str] = []
    _offline_sources(monkeypatch, calls, tmp_path)
    assert cli.main(["run", "pre-kvk", "--run-dir", str(run_path)]) == 0
    result = json.loads("\n".join(capsys.readouterr().out.splitlines()[1:]))
    assert result["status"] == "PRE_KVK_READY"
    with open_run(run_path).connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM kvk_requests").fetchone()[0] == 0


def test_one_command_rejects_wrong_workflow_before_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    run = initialize_run(tmp_path, 1, "MERGE_LISTS")
    monkeypatch.setattr(cli, "prepare_pre_kvk", lambda _run: pytest.fail("bronnen mogen niet starten"))
    assert cli.main(["run", "pre-kvk", "--run-dir", str(run.path)]) == 3
    output = capsys.readouterr()
    assert json.loads(output.out.splitlines()[0])["run_dir"] == str(run.path)
    assert "Ongeldige invoer of runstatus" in output.err


def test_one_command_rejects_host_not_ready_before_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    run = initialize_run(tmp_path, 1)
    monkeypatch.setattr(cli, "run_preflight", lambda _run, _workflow: {"ready": False})
    monkeypatch.setattr(cli, "prepare_pre_kvk", lambda _run: pytest.fail("bronnen mogen niet starten"))
    assert cli.main(["run", "pre-kvk", "--run-dir", str(run.path)]) == 3
    assert "Ongeldige invoer of runstatus" in capsys.readouterr().err
