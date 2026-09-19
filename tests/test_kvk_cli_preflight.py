import json
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
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

    def __init__(self):
        self.calls = 0

    def preflight(self):
        return {"available": True}

    def search(self, query, headed=False):
        assert query == "01234567"
        self.calls += 1
        if self.calls == 2:
            raise KvkError("PUBLIC_ACCESS_BLOCKED", "blocked", 4)
        return ProviderResult(query, [{"naam": "Andere handelsnaam", "kvkNummer": "01234567", "rechtsvorm": "BV", "status": "actief", "plaats": "Utrecht", "land": "Nederland"}], True, "fake", "evidence.txt")


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
    assert _match({**candidate, "source_kvk_hint": ""}, result) is None
    renamed = ProviderResult("01234567", [{"naam": "Nieuwe handelsnaam B.V.", "kvkNummer": "01234567",
                                          "plaats": "Utrecht", "land": "Nederland"}], True, "mock", "x")
    assert _match(candidate, renamed)["match_method"] == "SOURCE_KVK_NUMBER_CONFIRMED"
    assert _match(candidate, ProviderResult("01234567", [{"naam": "Alpha", "kvkNummer": "99999999",
                                                        "plaats": "Utrecht", "land": "Nederland"}], True, "mock", "x")) is None
    conflicting = ProviderResult("01234567", [
        {"naam": "Nieuwe naam", "kvkNummer": "01234567", "plaats": "Utrecht", "land": "Nederland",
         "rechtsvorm": "BV", "status": "Actief"},
        {"naam": "Andere vestiging", "kvkNummer": "01234567", "plaats": "Utrecht", "land": "Nederland",
         "rechtsvorm": "Vereniging", "status": "Inactief"},
    ], True, "mock", "x")
    assert _match(candidate, conflicting) is None
    status_conflict = ProviderResult("01234567", [
        {"naam": "Alpha", "kvkNummer": "01234567", "plaats": "Utrecht", "land": "Nederland",
         "rechtsvorm": "BV", "status": "Actief"},
        {"naam": "Nieuwe naam", "kvkNummer": "01234567", "plaats": "Utrecht", "land": "Nederland",
         "rechtsvorm": "BV", "status": "Inactief"},
    ], True, "mock", "x")
    assert _match(candidate, status_conflict) is None
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
    with run.connect() as connection:
        assert {row[0] for row in connection.execute("SELECT query FROM kvk_requests")} == {"01234567"}
    assert preflight(run, "public-http").is_file()
    with pytest.raises(HarvestError):
        preflight(run, "bad")


def test_generic_resolve_never_searches_by_name_without_hint(run, monkeypatch: pytest.MonkeyPatch) -> None:
    _candidates(run, ["No Hint"])
    path = run.latest_artifact("03", "candidates")
    assert path is not None
    rows = read_tsv(path)
    rows[0]["source_kvk_hint"] = ""
    replacement = run.artifact_path("03", "candidates_no_hint", "csv")
    write_tsv(replacement, list(rows[0]), rows)
    run.register_artifact(replacement, "03", "candidates")
    provider = FakeProvider()
    monkeypatch.setattr(provider, "search", lambda *_args, **_kwargs: pytest.fail("naamquery verstuurd"))
    monkeypatch.setattr("company_harvest.kvk._provider_for_run", lambda *_: provider)
    matches, unresolved = resolve(run, "auto", None, False, False, False, 0)
    assert read_tsv(matches) == []
    assert read_tsv(unresolved)[0]["reason"] == "NO_DIRECT_KVK_HINT"
    with run.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM kvk_requests").fetchone()[0] == 0


class HttpResponse:
    status_code = 200
    content = b'{"data":{"numberOfHits":1,"items":[{"naam":"Alpha","kvkNummer":"01234567","rechtsvormOmschrijving":"Besloten Vennootschap","actief":true,"bezoeklocatie":{"plaats":"Utrecht"}}]}}'
    headers = {"content-type": "application/json"}
    request = httpx.Request("GET", "https://www.kvk.nl/public-search")

    def iter_bytes(self, chunk_size=65536):
        yield self.content

    def raise_for_status(self):
        return None

    def json(self):
        return json.loads(self.content)


class HttpClient:
    headers = {}
    request_params = {}

    def __init__(self, *args, **kwargs):
        type(self).headers = kwargs.get("headers", {})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    @contextmanager
    def stream(self, *args, **kwargs):
        type(self).request_params = kwargs.get("params", {})
        yield HttpResponse()


def test_http_search_observed(run, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = run.path / ".provider"; folder.mkdir()
    (folder / "kvk_observed_http.json").write_text(
        '{"endpoint":"https://www.kvk.nl/public-search","query_parameter":"q"}'
    )
    monkeypatch.setattr("company_harvest.kvk.httpx.Client", HttpClient)
    provider = PublicHttpProvider(run)
    assert provider.preflight()["available"]
    result = provider.search("01234567")
    assert result.hits and Path(run.path / result.evidence).is_file()
    assert HttpClient.request_params["q"] == "01234567"
    assert HttpClient.headers["User-Agent"] == "company-lookup/0.1"
    assert "github" not in HttpClient.headers["User-Agent"].casefold()
    for invalid in ("Alpha", "1234567", ""):
        with pytest.raises(KvkError, match="achtcijferig bronnummer"):
            provider.search(invalid)
        with pytest.raises(KvkError, match="achtcijferig bronnummer"):
            PublicBrowserProvider(run).search(invalid)
        with pytest.raises(KvkError, match="achtcijferig bronnummer"):
            AutoProvider(run).search(invalid)
    provider._cooldown(1, "test")
    assert _choose_provider(run, "auto").name == "public-http"
    assert _choose_provider(run, "public-browser").name == "public-browser"
    with pytest.raises(HarvestError):
        _choose_provider(run, "bad")


def test_http_single_page_is_partial_and_bounded(run, monkeypatch: pytest.MonkeyPatch) -> None:
    class PartialResponse(HttpResponse):
        content = b'{"data":{"numberOfHits":20,"items":[{"naam":"Alpha","kvkNummer":"01234567","bezoeklocatie":{"plaats":"Utrecht"}}]}}'

    class PartialClient(HttpClient):
        calls = 0

        @contextmanager
        def stream(self, *args, **kwargs):
            type(self).calls += 1
            yield PartialResponse()

    monkeypatch.setattr("company_harvest.kvk.httpx.Client", PartialClient)
    result = PublicHttpProvider(run, max_pages=1, max_attempts=1).search("01234567")
    assert result.complete is False and len(result.hits) == 1
    assert (run.path / result.evidence).is_file()
    assert PartialClient.calls == 1


def test_http_error_and_oversize_keep_local_evidence(run, monkeypatch: pytest.MonkeyPatch) -> None:
    class BlockedResponse(HttpResponse):
        status_code = 403
        content = b"access denied"

    class BlockedClient(HttpClient):
        calls = 0

        @contextmanager
        def stream(self, *args, **kwargs):
            type(self).calls += 1
            yield BlockedResponse()

    monkeypatch.setattr("company_harvest.kvk.httpx.Client", BlockedClient)
    with pytest.raises(KvkError) as blocked:
        PublicHttpProvider(run, max_pages=1, max_attempts=1).search("01234567")
    assert blocked.value.reason == "PUBLIC_ACCESS_BLOCKED"
    assert blocked.value.evidence and (run.path / blocked.value.evidence).is_file()
    assert BlockedClient.calls == 1

    class ServerErrorResponse(HttpResponse):
        status_code = 500
        content = b"temporary"

    class ServerErrorClient(HttpClient):
        calls = 0

        @contextmanager
        def stream(self, *args, **kwargs):
            type(self).calls += 1
            yield ServerErrorResponse()

    monkeypatch.setattr("company_harvest.kvk.httpx.Client", ServerErrorClient)
    with pytest.raises(KvkError) as server_error:
        PublicHttpProvider(run, max_pages=1, max_attempts=1).search("01234567")
    assert server_error.value.reason == "NETWORK_ERROR"
    assert ServerErrorClient.calls == 1

    class OversizeResponse(HttpResponse):
        def iter_bytes(self, chunk_size=65536):
            for _ in range(81):
                yield b"x" * chunk_size

    class OversizeClient(HttpClient):
        @contextmanager
        def stream(self, *args, **kwargs):
            yield OversizeResponse()

    monkeypatch.setattr("company_harvest.kvk.httpx.Client", OversizeClient)
    with pytest.raises(KvkError) as oversize:
        PublicHttpProvider(run, max_pages=1, max_attempts=1).search("01234567")
    assert oversize.value.reason == "PARSING_ERROR"
    assert oversize.value.evidence and (run.path / oversize.value.evidence).is_file()


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
            url="https://www.kvk.nl/public-search?q=01234567",
            headers={"content-type": "application/json"},
            status=200,
            json=lambda: {"results": [{"naam": "Alpha", "kvkNummer": "01234567", "plaats": "Utrecht"}]},
        )
        self.handler(response)


class Browser:
    context_options = {}
    def new_context(self, **kwargs):
        type(self).context_options = kwargs
        return self
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
    result = provider.search("01234567")
    assert result.hits and (run.path / ".provider" / "kvk_observed_http.json").is_file()
    assert Browser.context_options == {"user_agent": "company-lookup/0.1"}


def test_auto_fallback_and_provider_lock(run, monkeypatch: pytest.MonkeyPatch) -> None:
    auto = AutoProvider(run)
    monkeypatch.setattr(auto.http, "preflight", lambda: {"available": True})
    monkeypatch.setattr(auto.http, "search", lambda query: (_ for _ in ()).throw(KvkError("NETWORK_ERROR", "temporary")))
    monkeypatch.setattr(auto.browser, "search", lambda query, headed=False: ProviderResult(query, [], True, "public-browser", "x"))
    assert auto.search("01234567").transport == "public-browser"
    monkeypatch.setattr(auto.http, "search", lambda query: (_ for _ in ()).throw(KvkError("RATE_LIMITED", "stop", 4)))
    with pytest.raises(KvkError):
        auto.search("01234567")
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
    downstream = run.artifact_path("05", "canonical", "csv")
    write_tsv(downstream, ["KVK-nummer"], [{"KVK-nummer": "01234567"}]); run.register_artifact(downstream, "05", "canonical")
    resolve(run, "auto", 1, False, True, False, 0)
    assert run.latest_artifact("05", "canonical") is None


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


def test_sources_measure_cli(run, monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    def fake_measure(selected_run, limit):
        called.update(run=selected_run.path, limit=limit)
        return run.path / "capability.json", run.path / "capability.md"

    monkeypatch.setattr(cli, "measure_sources", fake_measure)
    assert cli.main([
        "sources", "measure", "--run-dir", str(run.path),
        "--wikidata-limit", "25",
    ]) == 0
    assert called == {"run": run.path, "limit": 25}


def test_r1_vertical_cli_slice_accepts_name_only_source(run, tmp_path: Path) -> None:
    source = tmp_path / "organisaties.csv"
    source.write_text("Naam\nVoorbeeld Zonder Nummer\n", encoding="utf-8")
    assert cli.main([
        "sources", "import", "--run-dir", str(run.path), "--input", str(source),
        "--source-id", "name_only", "--name-column", "Naam",
    ]) == 0
    first = tmp_path / "eerste.csv"
    first.write_text(
        "Naam,KVK\nNaamgenoot,\nOngeldig,abc\nConflict,11111111\n",
        encoding="utf-8",
    )
    second = tmp_path / "tweede.csv"
    second.write_text(
        "Naam,KVK\nNaamgenoot,\nOngeldig,xyz\nConflict,22222222\n",
        encoding="utf-8",
    )
    for path, source_id in ((first, "family_a"), (second, "family_b")):
        assert cli.main([
            "sources", "import", "--run-dir", str(run.path), "--input", str(path),
            "--source-id", source_id, "--name-column", "Naam", "--kvk-column", "KVK",
        ]) == 0
    inventory = run.latest_artifact("01", "sources_inventory")
    assert inventory is not None
    catalog = read_tsv(inventory)
    for row in catalog:
        if row["source_id"] in {"family_a", "family_b"}:
            row["source_family"] = row["source_id"]
    catalog_path = run.artifact_path("01", "sources_inventory_two_families", "csv")
    write_tsv(catalog_path, list(catalog[0]), catalog)
    run.register_artifact(catalog_path, "01", "sources_inventory")
    assert cli.main(["companies", "merge", "--run-dir", str(run.path)]) == 0
    assert cli.main(["report", "--run-dir", str(run.path)]) == 0
    outcome_path = run.latest_artifact("08", "outcome_report")
    assert outcome_path is not None
    outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
    assert outcome["counts"]["raw_records"] == 7
    assert outcome["counts"]["without_direct_registration_number"] == 5
    assert outcome["counts"]["unique_candidates_after_deduplication"] == 5
    assert outcome["counts"]["conflict_records"] == 2
    assert outcome["source_diversity"]["source_family_count"] == 3
    assert outcome["count_closure"]["status"] == "PARTIAL_CLOSED"
    assert outcome["count_closure"]["transitions"]["raw_to_dedup"]["status"] == "CLOSED"
    assert outcome["http_user_agent"] == "company-lookup/0.1"
