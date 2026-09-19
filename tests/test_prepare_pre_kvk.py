"""Vierbronnenvoorbereiding en begrensde KVK-koppeling zonder live verkeer."""

import json
import math
from pathlib import Path

import pytest
from test_pre_kvk import _full_sources

from company_harvest import cli, pre_kvk_kvk, prepare
from company_harvest.core import HarvestError, Run, open_run, read_tsv
from company_harvest.kvk import KvkError, ProviderResult
from company_harvest.pre_kvk import build_pre_kvk_list
from company_harvest.pre_kvk_filter import build_pre_kvk_filter


def test_prepare_collects_four_sources_without_wikidata(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(prepare, "discover", lambda _run: calls.append("discover"))
    monkeypatch.setattr(prepare, "collect", lambda _run, **kw: calls.append(kw))
    monkeypatch.setattr(prepare, "collect_gleif", lambda _run, **kw: calls.append("gleif"))
    monkeypatch.setattr(prepare, "collect_public_register", lambda _run, sid, **kw: calls.append(sid))
    monkeypatch.setattr(prepare, "build_pre_kvk_list", lambda _run: (Path("master"), Path("report")))
    monkeypatch.setattr(prepare, "build_pre_kvk_filter", lambda _run: (Path("eligible"), Path("excluded"), Path("metadata")))
    assert prepare.prepare_pre_kvk(run) == (Path("master"), Path("report"), Path("eligible"), Path("excluded"), Path("metadata"))
    assert calls == ["discover", {"only": ("ind_arbeid",), "limit": None, "refresh": False},
                     "gleif", "anbi_register", "duo_education_organisations"]


def test_prepare_stops_before_later_sources_on_error(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prepare, "discover", lambda _run: None)
    monkeypatch.setattr(prepare, "collect", lambda _run, **kw: (_ for _ in ()).throw(HarvestError("blocked")))
    with pytest.raises(HarvestError, match="blocked"):
        prepare.prepare_pre_kvk(run, refresh=True)


def _ready_master(run: Run) -> None:
    _full_sources(run)
    build_pre_kvk_list(run)
    build_pre_kvk_filter(run)


def test_kvk_batch_is_explicit_bounded_and_resumable(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    _ready_master(run)
    calls: list[str] = []
    starts: list[float] = []
    clock = [100.0]

    def search(_provider: object, query: str) -> ProviderResult:
        calls.append(query)
        starts.append(clock[0])
        assert (run.path.parent.parent / ".local" / "kvk-last-request.json").is_file()
        evidence = run.path / "evidence" / f"synthetic-{len(calls)}.json"
        evidence.write_text("{}")
        hint = "34567890" if query == "Delta B.V." else "23456789"
        return ProviderResult(query, [{"naam": query, "kvkNummer": hint, "plaats": "Utrecht",
                                       "land": "Nederland", "rechtsvorm": "Stichting", "status": "Actief"}],
                              True, "public-http", str(evidence.relative_to(run.path)))

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", search)
    waits: list[float] = []

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(pre_kvk_kvk.time, "time", lambda: clock[0])
    monkeypatch.setattr(pre_kvk_kvk.time, "sleep", sleep)
    first = pre_kvk_kvk.resolve_pre_kvk(run, 1)
    assert len(read_tsv(first[0])) == 1 and len(read_tsv(first[1])) == 1
    assert json.loads(first[2].read_text())["complete"] is False
    second = pre_kvk_kvk.resolve_pre_kvk(run, 1)
    assert len(read_tsv(second[0])) == 1 and len(calls) == 2
    assert waits and starts[1] - starts[0] >= 2.0
    assert run.latest_artifact("04", "kvk_matches") is None
    with pytest.raises(HarvestError, match="1–10"):
        pre_kvk_kvk.resolve_pre_kvk(run, 11)
    for invalid_interval in (math.nan, math.inf, -math.inf, 1.9):
        with pytest.raises(HarvestError, match="interval"):
            pre_kvk_kvk.resolve_pre_kvk(run, 1, invalid_interval)


def test_kvk_batch_stops_on_access_block(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    _ready_master(run)
    calls = 0

    def blocked(_provider: object, _query: str) -> ProviderResult:
        nonlocal calls
        calls += 1
        raise KvkError("PUBLIC_ACCESS_BLOCKED", "blocked")

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", blocked)
    paths = pre_kvk_kvk.resolve_pre_kvk(run, 10)
    assert calls == 1
    assert json.loads(paths[2].read_text())["blocked"] is True
    assert read_tsv(paths[1])[0]["reason"] == "PUBLIC_ACCESS_BLOCKED"
    with pytest.raises(HarvestError, match="blokkade"):
        pre_kvk_kvk.resolve_pre_kvk(run, 1)


def test_kvk_batch_surfaces_interrupted_journal(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    _ready_master(run)
    master = run.latest_artifact("03", "pre_kvk_eligible")
    assert master is not None
    first_ready = next(row for row in read_tsv(master) if row["kvk_queue_status"].startswith("READY"))
    digest = pre_kvk_kvk._master(run)[1]
    eligible_digest = pre_kvk_kvk._queue(run)[1]
    run.record_config("pre_kvk_kvk", {"master_sha256": digest,
                                      "eligible_sha256": eligible_digest, "provider": "public-http"})
    with run.connect() as connection:
        connection.execute("INSERT INTO kvk_requests(candidate_id,query,state,attempt,provider) "
                           "VALUES(?,?,'IN_FLIGHT',1,'public-http')",
                           (first_ready["candidate_id"], first_ready["original_name"]))

    def no_match(_provider: object, query: str) -> ProviderResult:
        evidence = run.path / "evidence" / "synthetic-empty.json"
        evidence.write_text("{}")
        return ProviderResult(query, [], True, "public-http", str(evidence.relative_to(run.path)))

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", no_match)
    paths = pre_kvk_kvk.resolve_pre_kvk(run, 1)
    assert any(row["reason"] == "SENT_OUTCOME_UNKNOWN" for row in read_tsv(paths[1]))
    assert json.loads(paths[2].read_text())["journal_states"]["SENT_OUTCOME_UNKNOWN"] == 1


def test_kvk_batch_rechecks_master_after_lock(run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
    _ready_master(run)
    original = pre_kvk_kvk._master
    calls = 0

    def changing(check_run: Run):
        nonlocal calls
        calls += 1
        if calls == 2:
            with check_run.connect() as connection:
                connection.execute("UPDATE artifacts SET status='STALE' WHERE kind='pre_kvk_master'")
        return original(check_run)

    monkeypatch.setattr(pre_kvk_kvk, "_master", changing)
    with pytest.raises(HarvestError, match="COMPLETE|ontbreekt"):
        pre_kvk_kvk.resolve_pre_kvk(run, 1)


def test_kvk_pacing_rejects_corrupt_journal(run: Run) -> None:
    pacing = run.path.parent.parent / ".local" / "kvk-last-request.json"
    pacing.parent.mkdir()
    pacing.write_text("not json")
    with pytest.raises(HarvestError, match="pacingjournal"):
        pre_kvk_kvk._pace_request(run, 2)


def test_kvk_batch_rejects_replaced_master(run: Run) -> None:
    _ready_master(run)
    run.latest_artifact("03", "pre_kvk_master").write_text("changed")  # type: ignore[union-attr]
    with pytest.raises(HarvestError, match="COMPLETE-registratie"):
        pre_kvk_kvk.resolve_pre_kvk(run, 1)


def test_kvk_batch_rejects_stale_source_observation(run: Run) -> None:
    _ready_master(run)
    observations = run.metadata()["runtime_config"]["source_observations"]
    observations["ind_arbeid"]["collection_complete"] = False
    run.record_config("source_observations", observations)
    with pytest.raises(HarvestError, match="volledig"):
        pre_kvk_kvk.resolve_pre_kvk(run, 1)


def test_cli_vertical_slice_from_init_to_batch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert cli.main(["--data-dir", str(tmp_path), "run", "init", "--print-path"]) == 0
    run = open_run(Path(capsys.readouterr().out.strip()))
    _full_sources(run)
    monkeypatch.setattr(prepare, "collect", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(prepare, "collect_gleif", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(prepare, "collect_public_register", lambda *_args, **_kwargs: None)
    assert cli.main(["run", "prepare-pre-kvk", "--run-dir", str(run.path)]) == 0
    assert run.latest_artifact("03", "pre_kvk_master") is not None

    def single_result(_provider: object, query: str) -> ProviderResult:
        evidence = run.path / "evidence" / "cli-synthetic.json"
        evidence.write_text("{}")
        return ProviderResult(query, [{"naam": query, "kvkNummer": "11111111", "plaats": "Utrecht",
                                       "land": "Nederland"}], True, "public-http",
                              str(evidence.relative_to(run.path)))

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", single_result)
    assert cli.main(["kvk", "pre-kvk-batch", "--run-dir", str(run.path), "--limit", "1"]) == 0
    with run.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM kvk_requests").fetchone()[0] == 1
