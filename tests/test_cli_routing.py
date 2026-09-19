"""Regressies voor de gedragsbehoudende routering van CLI-commandofamilies."""

from pathlib import Path

import pytest

from company_harvest import cli
from company_harvest.core import Run


@pytest.mark.parametrize(("command", "service", "plain"), [
    (["run", "preflight"], "run_preflight", False),
    (["sources", "discover"], "discover", False),
    (["sources", "list"], "list_sources", False),
    (["sources", "collect", "--only-source", "ind_arbeid"], "collect", False),
    (["sources", "measure", "--wikidata-limit", "3"], "measure_sources", False),
    (["sources", "gleif"], "collect_gleif", False),
    (["sources", "anbi"], "collect_public_register", False),
    (["sources", "duo"], "collect_public_register", False),
    (["sources", "import", "--input", "unused.csv", "--source-id", "test",
      "--name-column", "name"], "import_source", True),
    (["companies", "sample"], "build_sample", False),
    (["companies", "sample-review", "--input", "unused.csv"], "record_sample_review", False),
    (["companies", "pre-kvk-list"], "build_pre_kvk_list", False),
    (["companies", "pre-kvk-filter"], "build_pre_kvk_filter", False),
    (["companies", "exclude-sole-proprietorships"], "exclude_sole_proprietorships", False),
    (["companies", "active-only"], "active_only", False),
    (["kvk", "preflight"], "kvk_preflight", True),
    (["kvk", "pilot"], "run_matching_pilot", False),
    (["kvk", "pilot-review", "--input", "unused.csv"], "record_matching_review", False),
    (["kvk", "resolve"], "resolve", False),
    (["kvk", "pre-kvk-batch"], "resolve_pre_kvk", False),
    (["kvk", "pre-kvk-run", "--max-requests", "1"], "run_pre_kvk", False),
    (["kvk", "consolidate"], "consolidate", True),
    (["export"], "export", False),
    (["report"], "report", True),
    (["audit", "trace", "--kvk-number", "12345678"], "trace", False),
])
def test_command_family_routes_to_same_service_and_output_style(
    command: list[str], service: str, plain: bool, run: Run,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[tuple[object, ...]] = []

    def fake_service(*args: object) -> str:
        calls.append(args)
        return "ROUTED"

    monkeypatch.setattr(cli, service, fake_service)
    assert cli.main([*command, "--run-dir", str(run.path)]) == 0
    assert len(calls) == 1 and isinstance(calls[0][0], Run)
    assert calls[0][0].path == run.path
    assert capsys.readouterr().out.strip() == ("ROUTED" if plain else '"ROUTED"')


@pytest.mark.parametrize(("command", "service", "forwarded"), [
    (["sources", "collect", "--only-source", "ind_arbeid", "--skip-source", "gleif_golden_copy",
      "--limit", "2", "--refresh"], "collect", (["ind_arbeid"], ["gleif_golden_copy"], 2, True)),
    (["sources", "gleif", "--archive", "archive.zip", "--limit", "5", "--refresh"],
     "collect_gleif", (Path("archive.zip"), 5, True)),
    (["sources", "anbi", "--archive", "archive.zip", "--limit", "5", "--refresh"],
     "collect_public_register", ("anbi_register", Path("archive.zip"), 5, True)),
    (["sources", "duo", "--archive", "archive.zip", "--limit", "5", "--refresh"],
     "collect_public_register", ("duo_education_organisations", Path("archive.zip"), 5, True)),
    (["sources", "import", "--input", "unused.csv", "--source-id", "custom",
      "--name-column", "Naam", "--kvk-column", "KVK", "--sheet", "Blad1"],
     "import_source", (Path("unused.csv"), "custom", "Naam", "KVK", "Blad1")),
    (["companies", "sample", "--size", "100", "--review-size", "5", "--pilot-size", "10"],
     "build_sample", (100, 5, 10)),
    (["companies", "sample-review", "--input", "review.csv"],
     "record_sample_review", (Path("review.csv"),)),
    (["kvk", "pilot", "--provider", "public-browser", "--interval", "3",
      "--refresh", "--review-size", "7", "--max-live", "2"],
     "run_matching_pilot", ("public-browser", 3.0, True, 7, 2)),
    (["kvk", "resolve", "--provider", "public-http", "--limit", "4", "--resume",
      "--refresh", "--headed", "--interval", "2.5"],
     "resolve", ("public-http", 4, True, True, True, 2.5)),
    (["kvk", "pre-kvk-batch", "--limit", "7", "--interval", "3"],
     "resolve_pre_kvk", (7, 3.0)),
    (["kvk", "pre-kvk-run", "--max-requests", "6", "--interval", "3"],
     "run_pre_kvk", (3.0, 6)),
    (["export", "--limit", "11", "--allow-partial"], "export", (11, True)),
    (["audit", "trace", "--kvk-number", "12345678"], "trace", ("12345678",)),
])
def test_nontrivial_options_reach_services_unchanged(
    command: list[str], service: str, forwarded: tuple[object, ...], run: Run,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    def fake_service(*args: object) -> str:
        calls.append(args)
        return "ROUTED"

    monkeypatch.setattr(cli, service, fake_service)
    assert cli.main([*command, "--run-dir", str(run.path)]) == 0
    assert len(calls) == 1 and isinstance(calls[0][0], Run)
    assert calls[0][0].path == run.path
    assert calls[0][1:] == forwarded


def test_execute_route_keeps_preparation_batch_and_provider_gate(
    run: Run, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli, "prepare_pre_kvk", lambda _run: calls.append("prepare") or ["PREPARED"])
    monkeypatch.setattr(cli, "resolve_pre_kvk", lambda _run, _limit: calls.append("kvk") or ["BATCH"])
    args = ["run", "execute", "--run-dir", str(run.path), "--limit", "1"]
    assert cli.main(args) == 0
    assert calls == ["prepare", "kvk"]
    assert '"pre_kvk": [\n    "PREPARED"\n  ]' in capsys.readouterr().out
    assert cli.main([*args, "--kvk-provider", "public-browser"]) == 3
    assert calls == ["prepare", "kvk"]
