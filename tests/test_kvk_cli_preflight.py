import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from company_harvest import cli
from company_harvest.core import HarvestError, read_tsv, write_tsv
from company_harvest.kvk import (
    AutoProvider,
    KvkError,
    ProviderLock,
    ProviderResult,
    PublicBrowserProvider,
    PublicHttpProvider,
    _check_cooldown,
    _choose_provider,
    _extract_dom_hits,
    _extract_hits,
    _has_source_conflict,
    _match,
    preflight,
    resolve,
    retry_after,
)
from company_harvest.preflight import host, run_preflight


class FakeProvider:
    name = "fake"

    def preflight(self):
        return {"available": True}

    def search(self, query, headed=False):
        if query == "Blocked":
            raise KvkError("PUBLIC_ACCESS_BLOCKED", "blocked", 4)
        return ProviderResult(query, [{"naam": query, "kvkNummer": "01234567", "rechtsvorm": "BV", "status": "actief", "plaats": "Utrecht", "land": "Nederland"}], True, "fake", "evidence.txt")


def _candidates(run, names):
    path = run.artifact_path("03", "companies_candidates", "csv")
    headers = ["candidate_id", "original_name", "normalized_name", "source_kvk_hint", "country", "city", "website", "sector", "source_relations"]
    rows = [{"candidate_id": str(i), "original_name": name, "normalized_name": name.casefold(), "source_kvk_hint": "01234567", "country": "Nederland", "city": "", "website": "", "sector": "", "source_relations": "[]"} for i, name in enumerate(names)]
    write_tsv(path, headers, rows); run.register_artifact(path, "03", "candidates")


def test_retry_extract_match_and_cooldown(run) -> None:
    assert retry_after("12") == 12
    future = datetime.now(UTC) + timedelta(seconds=5)
    assert 0 <= retry_after(future.strftime("%a, %d %b %Y %H:%M:%S GMT")) <= 5
    assert retry_after("nonsense") is None and retry_after(None) is None
    assert _extract_hits({"results": [{"x": 1}]}) == [{"x": 1}]
    assert _extract_hits([{"x": 1}, "bad"]) == [{"x": 1}]
    assert _extract_hits("bad") == []
    dom = "Alpha B.V.\nKVK-nummer: 01234567\nBesloten Vennootschap\nAdres 1, 1234AB Utrecht\n"
    assert _extract_dom_hits(dom)[0]["plaats"] == "Utrecht"
    candidate = {"candidate_id": "1", "original_name": "Alpha", "source_kvk_hint": "01234567", "source_relations": "[]"}
    result = ProviderResult("Alpha", [{"naam": "Alpha", "kvkNummer": "01234567", "plaats": "Utrecht", "land": "Nederland"}], True, "mock", "x")
    assert _match(candidate, result)["KVK-nummer"] == "01234567"
    assert _match(candidate, ProviderResult("Alpha", [{"naam": "Alpha", "kvkNummer": "01234567"}], True, "mock", "x")) is None
    conflict = ProviderResult("Alpha", [{"naam": "Alpha", "kvkNummer": "99999999", "plaats": "Utrecht", "land": "Nederland"}], True, "mock", "x")
    assert _has_source_conflict(candidate, conflict)
    with run.connect() as connection:
        connection.execute("INSERT INTO cooldowns VALUES('kvk', ?, 'test')", (time.time() + 100,))
    with pytest.raises(HarvestError):
        _check_cooldown(run)


def test_http_preflight_and_resolve(run, monkeypatch: pytest.MonkeyPatch) -> None:
    assert PublicHttpProvider(run).preflight()["status"] == "IMPLEMENTED"
    _candidates(run, ["Alpha", "Blocked", "Later"])
    monkeypatch.setattr("company_harvest.kvk._provider_for_run", lambda *_: FakeProvider())
    matches, unresolved = resolve(run, "auto", None, False, False, False, 0)
    assert len(read_tsv(matches)) == 1
    assert read_tsv(unresolved)[0]["reason"] == "PUBLIC_ACCESS_BLOCKED"
    assert preflight(run, "public-http").is_file()
    with pytest.raises(HarvestError):
        preflight(run, "bad")


class HttpResponse:
    status_code = 200
    content = b'{"data":{"numberOfHits":1,"items":[{"naam":"Alpha","kvkNummer":"01234567","rechtsvormOmschrijving":"Besloten Vennootschap","actief":true,"bezoeklocatie":{"plaats":"Utrecht"}}]}}'
    headers = {"content-type": "application/json"}

    def raise_for_status(self):
        return None

    def json(self):
        return json.loads(self.content)


class HttpClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get(self, *args, **kwargs):
        return HttpResponse()


def test_http_search_observed(run, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = run.path / ".provider"; folder.mkdir()
    (folder / "kvk_observed_http.json").write_text(
        '{"endpoint":"https://www.kvk.nl/public-search","query_parameter":"q"}'
    )
    monkeypatch.setattr("company_harvest.kvk.httpx.Client", HttpClient)
    provider = PublicHttpProvider(run)
    assert provider.preflight()["available"]
    result = provider.search("Alpha")
    assert result.hits and Path(run.path / result.evidence).is_file()
    provider._cooldown(1, "test")
    assert _choose_provider(run, "auto").name == "public-http"
    assert _choose_provider(run, "public-browser").name == "public-browser"
    with pytest.raises(HarvestError):
        _choose_provider(run, "bad")


class Locator:
    @property
    def first(self): return self
    @property
    def last(self): return self
    def count(self): return 1
    def is_visible(self): return True
    def click(self): return None
    def wait_for(self, **kwargs): return None
    def fill(self, query): self.query = query
    def press(self, key): return None
    def inner_text(self, timeout=None): return "Gewone resultatenpagina"


class Page:
    def __init__(self): self.handler = None
    def on(self, event, handler): self.handler = handler
    def goto(self, *args, **kwargs): return None
    def get_by_role(self, *args, **kwargs): return Locator()
    def locator(self, selector): return Locator()
    def wait_for_load_state(self, *args, **kwargs):
        response = SimpleNamespace(
            request=SimpleNamespace(resource_type="fetch"),
            url="https://www.kvk.nl/public-search?q=Alpha",
            headers={"content-type": "application/json"},
            status=200,
            json=lambda: {"results": [{"naam": "Alpha", "kvkNummer": "01234567", "plaats": "Utrecht"}]},
        )
        self.handler(response)


class Browser:
    def new_context(self): return self
    def new_page(self): return Page()
    def close(self): return None


class Chromium:
    executable_path = __file__
    def launch(self, headless=True): return Browser()


class PlaywrightContext:
    def __enter__(self): return SimpleNamespace(chromium=Chromium())
    def __exit__(self, *args): return None


def test_browser_provider(run, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: PlaywrightContext())
    provider = PublicBrowserProvider(run)
    assert provider.preflight()["available"]
    result = provider.search("Alpha")
    assert result.hits and (run.path / ".provider" / "kvk_observed_http.json").is_file()


def test_auto_fallback_and_provider_lock(run, monkeypatch: pytest.MonkeyPatch) -> None:
    auto = AutoProvider(run)
    monkeypatch.setattr(auto.http, "preflight", lambda: {"available": True})
    monkeypatch.setattr(auto.http, "search", lambda query: (_ for _ in ()).throw(KvkError("NETWORK_ERROR", "temporary")))
    monkeypatch.setattr(auto.browser, "search", lambda query, headed=False: ProviderResult(query, [], True, "public-browser", "x"))
    assert auto.search("Alpha").transport == "public-browser"
    monkeypatch.setattr(auto.http, "search", lambda query: (_ for _ in ()).throw(KvkError("RATE_LIMITED", "stop", 4)))
    with pytest.raises(KvkError):
        auto.search("Alpha")
    with ProviderLock(run):
        with pytest.raises(KvkError):
            with ProviderLock(run):
                pass


def test_resume_and_limit(run, monkeypatch: pytest.MonkeyPatch) -> None:
    _candidates(run, ["Alpha", "Beta"])
    monkeypatch.setattr("company_harvest.kvk._provider_for_run", lambda *_: FakeProvider())
    matches, unresolved = resolve(run, "auto", 1, False, False, False, 0)
    assert len(read_tsv(matches)) == 1
    assert read_tsv(unresolved)[0]["reason"] == "NOT_PROCESSED_LIMIT"
    matches2, _ = resolve(run, "auto", 1, True, False, False, 0)
    assert len(read_tsv(matches2)) >= 1


def test_incomplete_and_unknown_outcome_not_resent(run, monkeypatch: pytest.MonkeyPatch) -> None:
    _candidates(run, ["Alpha"])
    provider = FakeProvider()
    monkeypatch.setattr(provider, "search", lambda *args, **kwargs: ProviderResult("Alpha", [], False, "fake", "x"))
    monkeypatch.setattr("company_harvest.kvk._provider_for_run", lambda *_: provider)
    _, unresolved = resolve(run, "auto", None, False, False, False, 0)
    assert read_tsv(unresolved)[0]["reason"] == "TRUNCATED_RESULTS"
    with run.connect() as connection:
        connection.execute("UPDATE kvk_requests SET state='SENT_OUTCOME_UNKNOWN'")
    monkeypatch.setattr(provider, "search", lambda *args, **kwargs: pytest.fail("unknown request was resent"))
    _, unresolved2 = resolve(run, "auto", None, True, False, False, 0)
    assert read_tsv(unresolved2)[0]["reason"] == "SENT_OUTCOME_UNKNOWN"


def test_preflight_and_cli(tmp_path: Path, run, capsys: pytest.CaptureFixture[str]) -> None:
    assert host(tmp_path)["ready"]
    assert run_preflight(run)["workflow"] == "HARVEST"
    with pytest.raises(HarvestError):
        run_preflight(run, "MERGE_LISTS")
    assert cli.main(["--data-dir", str(tmp_path), "doctor"]) == 0
    assert cli.main(["--data-dir", str(tmp_path), "run", "init", "--target", "2", "--print-path"]) == 0
    created = Path(capsys.readouterr().out.strip().splitlines()[-1])
    assert created.is_dir()
    assert cli.main(["--data-dir", str(tmp_path), "run", "list"]) == 0
    assert cli.main(["run", "status", "--run-dir", str(created)]) == 0
    assert cli.main(["audit", "verify", "--run-dir", str(created)]) == 0
    assert cli.main(["run", "status", "--run-dir", str(tmp_path / "missing")]) == 3
