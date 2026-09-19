import csv
import gzip
import json
import re
import shutil
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from openpyxl import Workbook

from company_harvest import core
from company_harvest.core import (
    CSV_FIELD_SIZE_LIMIT,
    HTTP_USER_AGENT,
    HarvestError,
    atomic_write,
    data_root,
    normalize_name,
    open_run,
    read_tsv,
    redact,
    sha256,
    validate_kvk,
    write_tsv,
)
from company_harvest.sources import (
    _bounded_get,
    _enabled,
    _ind_source_date,
    _measurement_error,
    _parse_ind_html_with_stats,
    collect,
    discover,
    import_source,
    list_sources,
    measure_sources,
    parse_ind_html,
    parse_wikidata,
    read_catalog,
)


def test_core_roundtrip_and_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = tmp_path / "a.txt"
    atomic_write(text, "hello")
    assert text.read_text() == "hello"
    binary = tmp_path / "b.bin"
    atomic_write(binary, b"bytes")
    assert sha256(binary)
    table = tmp_path / "table.csv"
    write_tsv(table, ["a", "b"], [{"a": "tab\tquote\"line\n", "b": "001"}])
    assert read_tsv(table)[0]["a"] == "tab\tquote\"line\n"
    assert normalize_name("  CAFÉ\t BV ") == "café bv"
    assert redact("Authorization: abc token=secret") == "Authorization: [REDACTED] token=[REDACTED]"
    assert validate_kvk("01234567") == "01234567"
    assert validate_kvk(12345678) == "12345678"
    assert validate_kvk(12345678.0) == "12345678"
    for bad in (True, "123", "1234567²", 123.5, None):
        with pytest.raises(ValueError):
            validate_kvk(bad)
    monkeypatch.setenv("COMPANY_HARVEST_DATA_DIR", str(tmp_path))
    assert data_root() == tmp_path
    assert data_root(tmp_path / "x") == tmp_path / "x"


def test_csv_field_limit_keeps_large_evidence_and_rejects_oversized_field(tmp_path: Path) -> None:
    assert csv.field_size_limit() == CSV_FIELD_SIZE_LIMIT == 1024 * 1024
    accepted = "x" * 159_763
    path = tmp_path / "wide.tsv"
    write_tsv(path, ["source_payloads_json"], [{"source_payloads_json": accepted}])
    assert read_tsv(path) == [{"source_payloads_json": accepted}]
    write_tsv(path, ["source_payloads_json"],
              [{"source_payloads_json": "x" * (CSV_FIELD_SIZE_LIMIT + 1)}])
    with pytest.raises(csv.Error):
        read_tsv(path)


def test_timestamp_is_readable_utc_with_same_second_uniqueness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(core, "utc_now", lambda: datetime(2026, 9, 19, 10, 39, 17, tzinfo=UTC))
    suffixes = iter(("0123456789ab", "abcdef012345"))

    def next_suffix(byte_count: int) -> str:
        assert byte_count == 6
        return next(suffixes)

    monkeypatch.setattr(core.secrets, "token_hex", next_suffix)
    assert core.timestamp() == "2026.09.19_103917_0123456789ab"
    assert core.timestamp() == "2026.09.19_103917_abcdef012345"


def test_new_names_and_old_run_path_remain_usable(tmp_path: Path) -> None:
    fresh = core.initialize_run(tmp_path, 1)
    assert re.fullmatch(r"\d{4}\.\d{2}\.\d{2}_\d{6}_[0-9a-f]{12}", fresh.path.name)
    artifact = fresh.artifact_path("01", "demo", "txt")
    assert re.fullmatch(r"\d{4}\.\d{2}\.\d{2}_\d{6}_[0-9a-f]{12}_01_demo\.txt", artifact.name)
    artifact.write_text("bewaard", encoding="utf-8")
    fresh.register_artifact(artifact, "01", "demo")

    legacy = fresh.path.with_name("1789809357641683000_20260919T091557.641560Z_aa1cb6")
    # Windows kan een SQLite/WAL-runmap nog vergrendeld houden; een kopie
    # bewijst het openen van een legacy-pad zonder een live run te verplaatsen.
    shutil.copytree(fresh.path, legacy)
    metadata = json.loads((legacy / "run.json").read_text(encoding="utf-8"))
    metadata["run_id"] = legacy.name
    (legacy / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    reopened = open_run(legacy)
    assert reopened.metadata()["run_id"] == legacy.name
    preserved = reopened.latest_artifact("01", "demo")
    assert preserved is not None and preserved.read_text(encoding="utf-8") == "bewaard"
    continuation = reopened.artifact_path("02", "continued", "txt")
    assert re.fullmatch(r"\d{4}\.\d{2}\.\d{2}_\d{6}_[0-9a-f]{12}_02_continued\.txt", continuation.name)
    continuation.write_text("nieuw", encoding="utf-8")
    reopened.register_artifact(continuation, "02", "continued")
    assert reopened.latest_artifact("02", "continued") == continuation


def test_run_lock_artifacts_and_open(run, tmp_path: Path) -> None:
    assert run.metadata()["http_user_agent"] == HTTP_USER_AGENT == "company-lookup/0.1"
    assert run.metadata()["storage_baseline"]["evidence_bytes"] == 0
    artifact = run.artifact_path("01", "demo", "md")
    artifact.write_text("demo")
    run.register_artifact(artifact, "01", "demo")
    assert run.latest_artifact("01", "demo") == artifact
    run.log("INFO", "token_test", token="fake")
    assert "[REDACTED]" in (run.path / "logs" / "events.jsonl").read_text()
    with run.lock():
        with run.lock():
            assert (run.path / "run.lock").is_file()
    (run.path / "run.lock").write_text("other owner")
    with pytest.raises(HarvestError) as error:
        with run.lock():
            pass
    assert error.value.exit_code == 6
    (run.path / "run.lock").unlink()
    assert open_run(run.path).path == run.path
    with pytest.raises(HarvestError):
        open_run(tmp_path / "missing")
    metadata = json.loads((run.path / "run.json").read_text())
    metadata["schema_version"] = 999
    (run.path / "run.json").write_text(json.dumps(metadata))
    with pytest.raises(HarvestError, match="oorspronkelijke programmaversie"):
        open_run(run.path)


def test_run_lock_recovers_only_proven_dead_owner(run, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = run.path / "run.lock"
    lock.write_text(json.dumps({"pid": 456789, "created": "old"}))
    monkeypatch.setattr(core, "_process_alive", lambda _pid: True)
    with pytest.raises(HarvestError, match="vergrendeld"):
        with run.lock():
            pass
    assert lock.is_file()
    monkeypatch.setattr(core, "_process_alive", lambda _pid: False)
    with run.lock():
        assert json.loads(lock.read_text())["pid"] != 456789
    assert not lock.exists()


def test_sources_discovery_and_parsers(run) -> None:
    inventory, report = discover(run)
    assert inventory.is_file() and report.is_file()
    catalog = list_sources(run)
    assert len(catalog) == 6
    assert all(row["catalog_schema_version"] == "2" for row in catalog)
    assert {row["access_mode"] for row in catalog} == {"api", "bulk", "html"}
    assert {row["registration_number_type"] for row in catalog} == {
        "Fiscaal nummer (geen KVK-nummer)",
        "KVK",
        "KVK indien door de bron geleverd; ontbrekende waarden blijven kandidaten",
        "KVK via registratieautoriteit RA000463",
        "KVK-bronhint bij Nederlandse gegunde onderneming; niet onafhankelijk geverifieerd",
    }
    assert catalog[0]["terms_url"] == "https://ind.nl/nl/proclaimer"
    assert catalog[1]["terms_url"] == "https://www.wikidata.org/wiki/Wikidata:Data_access"
    rows = parse_ind_html("<tr><td>Voorbeeld B.V.</td><td>01234567</td></tr>", "https://ind.nl/x")
    assert rows[0]["source_kvk_hint"] == "01234567"
    with pytest.raises(HarvestError):
        parse_ind_html("geen tabel", "https://ind.nl/x")
    assert _ind_source_date(
        "<p>Het overzicht is <strong>bijgewerkt op 3 september 2026</strong>.</p>"
    ) == "3 september 2026"
    assert _ind_source_date("geen peildatum") is None
    parsed_ind, raw_ind, rejected_ind = _parse_ind_html_with_stats(
        "<table><tr><th>Naam</th><th>KvK nummer</th></tr>"
        "<tr><th>Goed B.V.</th><td>12345678</td></tr>"
        "<tr><th>Afgewezen B.V.</th><td>1234567</td></tr></table>",
        "https://ind.nl/x",
    )
    assert len(parsed_ind) == 1 and raw_ind == 2 and rejected_ind == 1
    payload = {"results": {"bindings": [{"orgLabel": {"value": "Demo"}, "kvk": {"value": "12345678"}}, {"orgLabel": {"value": "Bad"}, "kvk": {"value": "x"}}]}}
    parsed = parse_wikidata(payload, "https://query.wikidata.org")
    assert parsed[0]["original_name"] == "Demo"
    assert parsed[1]["registration_validation_status"] == "INVALID"
    assert parse_wikidata({}, "x") == []
    assert [item.source_id for item in _enabled(["ind_arbeid"], [])] == ["ind_arbeid"]
    assert {item.source_id for item in _enabled([], [])} == {"ind_arbeid"}
    assert {item.source_id for item in _enabled(["wikidata_nl_companies"], [])} == {"wikidata_nl_companies"}
    with pytest.raises(HarvestError, match="sources gleif"):
        _enabled(["gleif_golden_copy"], [])
    with pytest.raises(HarvestError):
        _enabled(["unknown"], [])


class FakeResponse:
    def __init__(self, content: bytes, url: str = "https://ind.nl/x") -> None:
        self.content = content
        self.text = content.decode()
        self.url = type("URL", (), {"host": "ind.nl", "__str__": lambda self: url})()
        self.status_code = 200
        self.headers = {"x-ratelimit-remaining": "99"}

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return json.loads(self.content)

    def iter_bytes(self, chunk_size=65536):
        yield from (self.content[index:index + chunk_size] for index in range(0, len(self.content), chunk_size))


class FakeClient:
    headers = {}

    def __init__(self, *args, **kwargs):
        type(self).headers = kwargs.get("headers", {})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get(self, url, **kwargs):
        if "wikidata" in url:
            return FakeResponse(b'{"results":{"bindings":[{"orgLabel":{"value":"Wiki BV"},"kvk":{"value":"23456789"}}]}}', "https://query.wikidata.org/sparql")
        return FakeResponse(b"<td>IND BV</td><td>12345678</td>")

    def stream(self, method, url, **kwargs):
        assert method == "GET" and kwargs.get("follow_redirects") is False
        return nullcontext(self.get(url, **kwargs))


def test_collect_and_bounds(run, monkeypatch: pytest.MonkeyPatch) -> None:
    discover(run)
    monkeypatch.setattr("company_harvest.sources.httpx.Client", FakeClient)
    outputs = collect(run, only=["ind_arbeid", "wikidata_nl_companies"], limit=1)
    assert len(outputs) == 2 and all(read_tsv(path) for path in outputs)
    assert FakeClient.headers["User-Agent"] == "company-lookup/0.1"
    assert "github" not in FakeClient.headers["User-Agent"].casefold()
    assert collect(run, only=["ind_arbeid", "wikidata_nl_companies"], limit=1) == outputs
    downstream = run.artifact_path("03", "downstream", "csv"); write_tsv(downstream, ["x"], [{"x": "1"}]); run.register_artifact(downstream, "03", "downstream")
    assert len(collect(run, only=["ind_arbeid"], limit=1, refresh=True)) == 1
    assert run.latest_artifact("03", "downstream") is None
    full_ind = collect(run, only=["ind_arbeid"], limit=None)
    assert len(full_ind) == 1 and full_ind[0] != outputs[0]
    assert run.metadata()["runtime_config"]["source_observations"]["ind_arbeid"]["collection_complete"] is True
    client = FakeClient()
    with pytest.raises(HarvestError):
        _bounded_get(client, "http://localhost/private")


def test_source_redirect_is_validated_before_next_request() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
                302,
                request=request,
                headers={"location": "https://not-allowed.example/private"},
            )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(HarvestError, match="niet toegestaan"):
            _bounded_get(client, "https://ind.nl/register")
    assert calls == ["https://ind.nl/register"]
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(HarvestError, match="ongeldig"):
            _bounded_get(client, "https://ind.nl:bad/register")
    assert calls == ["https://ind.nl/register"]

    def malformed_handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, request=request, headers={"location": "https://[invalid"})

    with httpx.Client(transport=httpx.MockTransport(malformed_handler)) as client:
        with pytest.raises(HarvestError, match="ongeldig"):
            _bounded_get(client, "https://ind.nl/register")
    assert calls == ["https://ind.nl/register", "https://ind.nl/register"]


def test_source_safe_redirect_and_redirect_limit() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if str(request.url).endswith("/final"):
            return httpx.Response(200, request=request, content=b"ok")
        return httpx.Response(302, request=request, headers={"location": "/final"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert _bounded_get(client, "https://ind.nl/start").content == b"ok"
    assert calls == ["https://ind.nl/start", "https://ind.nl/final"]

    looping = 0

    def loop_handler(request: httpx.Request) -> httpx.Response:
        nonlocal looping
        looping += 1
        return httpx.Response(302, request=request, headers={"location": "/loop"})

    with httpx.Client(transport=httpx.MockTransport(loop_handler)) as client:
        with pytest.raises(HarvestError, match="redirectgate"):
            _bounded_get(client, "https://ind.nl/loop")
    assert looping == 4


def test_source_body_limit_stops_stream_before_full_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("company_harvest.sources.MAX_RESPONSE_BYTES", 70000)
    emitted = 0

    def body():
        nonlocal emitted
        for _ in range(4):
            emitted += 1
            yield b"x" * 65536

    class TrackingStream(httpx.SyncByteStream):
        def __iter__(self):
            return body()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, stream=TrackingStream())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(HarvestError, match="grootte"):
            _bounded_get(client, "https://ind.nl/start")
    assert emitted < 4


def test_source_gzip_is_decoded_once() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"content-encoding": "gzip", "content-length": "25"},
            content=gzip.compress(b"<table>goed</table>"),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = _bounded_get(client, "https://ind.nl/register")
    assert response.content == b"<table>goed</table>"
    assert "content-encoding" not in response.headers


def test_live_capability_measurement_is_bounded_and_reconcilable(
    run, monkeypatch: pytest.MonkeyPatch
) -> None:
    discover(run)
    monkeypatch.setattr("company_harvest.sources.httpx.Client", FakeClient)
    json_path, md_path = measure_sources(run, wikidata_limit=1)
    report = json.loads(json_path.read_text())
    assert md_path.is_file() and report["all_sources_terminal"]
    assert report["http_user_agent"] == "company-lookup/0.1"
    by_source = {item["source_id"]: item for item in report["sources"]}
    assert by_source["ind_arbeid"]["measurement_scope"] == "FULL_SOURCE_PAGE"
    assert by_source["ind_arbeid"]["collection_complete"] is True
    assert by_source["wikidata_nl_companies"]["measurement_scope"] == "BOUNDED_SAMPLE"
    assert by_source["wikidata_nl_companies"]["collection_complete"] is False
    assert all(item["count_closure"] == "CLOSED" for item in by_source.values())
    assert all(item["rate_limit_observation"] == "HEADERS_OBSERVED" for item in by_source.values())
    catalog = {item["source_id"]: item for item in list_sources(run)}
    assert {
        catalog[source_id]["live_measurement_status"]
        for source_id in ("ind_arbeid", "wikidata_nl_companies")
    } == {"LIVE_MEASURED"}
    assert catalog["gleif_golden_copy"]["live_measurement_status"] == "NOT_MEASURED"


def test_measurement_error_classifies_rate_limit_as_blocked() -> None:
    request = httpx.Request("GET", "https://query.wikidata.org/sparql")
    response = httpx.Response(429, request=request, headers={"retry-after": "60"})
    exc = httpx.HTTPStatusError("rate limited", request=request, response=response)
    status, evidence = _measurement_error(exc)
    assert status == "BLOCKED"
    assert evidence == {
        "error_type": "HTTPStatusError",
        "http_status": 429,
        "retry_after": "60",
    }


def test_capability_report_preserves_terminal_source_failure(
    run, monkeypatch: pytest.MonkeyPatch
) -> None:
    class PartialClient(FakeClient):
        def get(self, url, **kwargs):
            if "wikidata" in url:
                request = httpx.Request("GET", url)
                raise httpx.ReadTimeout("bounded timeout", request=request)
            return super().get(url, **kwargs)

    monkeypatch.setattr("company_harvest.sources.httpx.Client", PartialClient)
    json_path, _ = measure_sources(run, wikidata_limit=1)
    report = json.loads(json_path.read_text())
    by_source = {item["source_id"]: item for item in report["sources"]}
    assert by_source["ind_arbeid"]["measurement_status"] == "LIVE_MEASURED"
    assert by_source["wikidata_nl_companies"]["measurement_status"] == "FAILED"
    assert by_source["wikidata_nl_companies"]["configured_limit"] == 1
    assert by_source["wikidata_nl_companies"]["count_closure"] == "NOT_AVAILABLE"
    assert report["exact_registration_overlap"]["status"] == "NOT_AVAILABLE"
    assert report["exact_registration_overlap"]["shared_valid_registration_numbers"] is None


def test_capability_report_preserves_malformed_json_as_terminal_failure(
    run, monkeypatch: pytest.MonkeyPatch
) -> None:
    class MalformedJsonClient(FakeClient):
        def get(self, url, **kwargs):
            if "wikidata" in url:
                return FakeResponse(b"not-json", "https://query.wikidata.org/sparql")
            return super().get(url, **kwargs)

    monkeypatch.setattr("company_harvest.sources.httpx.Client", MalformedJsonClient)
    json_path, _ = measure_sources(run, wikidata_limit=1)
    report = json.loads(json_path.read_text())
    by_source = {item["source_id"]: item for item in report["sources"]}
    assert by_source["wikidata_nl_companies"]["measurement_status"] == "FAILED"
    assert by_source["wikidata_nl_companies"]["error"]["error_type"] == "HarvestError"
    assert by_source["wikidata_nl_companies"]["response_count"] == 1
    assert run.latest_artifact("02", "evidence_wikidata_nl_companies") is not None


def test_failed_refresh_does_not_reuse_prior_attempt_observations(
    run, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("company_harvest.sources.httpx.Client", FakeClient)
    measure_sources(run, wikidata_limit=1)

    class TimeoutClient(FakeClient):
        def get(self, url, **kwargs):
            raise httpx.ReadTimeout("new attempt failed", request=httpx.Request("GET", url))

    monkeypatch.setattr("company_harvest.sources.httpx.Client", TimeoutClient)
    json_path, _ = measure_sources(run, wikidata_limit=1)
    report = json.loads(json_path.read_text())
    for item in report["sources"]:
        assert item["measurement_status"] == "FAILED"
        assert item["response_count"] is None
        assert item["response_bytes"] is None
        assert item["http_statuses"] == []


def test_http_block_records_current_response_metrics_headers_and_evidence(
    run, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BlockedClient(FakeClient):
        def get(self, url, **kwargs):
            request = httpx.Request("GET", url)
            return httpx.Response(
                429,
                request=request,
                content=b"rate limited",
                headers={"retry-after": "60", "x-ratelimit-remaining": "0"},
            )

    monkeypatch.setattr("company_harvest.sources.httpx.Client", BlockedClient)
    json_path, _ = measure_sources(run, wikidata_limit=1)
    report = json.loads(json_path.read_text())
    for item in report["sources"]:
        assert item["measurement_status"] == "BLOCKED"
        assert item["response_count"] == 1
        assert item["response_bytes"] == 12
        assert item["http_statuses"] == [429]
        assert item["rate_limit_headers"] == {
            "retry-after": "60",
            "x-ratelimit-remaining": "0",
        }
        assert run.latest_artifact("02", f"evidence_{item['source_id']}") is not None


def test_ind_invalid_only_failure_keeps_parser_rejection_count(
    run, monkeypatch: pytest.MonkeyPatch
) -> None:
    class InvalidIndClient(FakeClient):
        def get(self, url, **kwargs):
            if "ind.nl" in url:
                return FakeResponse(
                    b"<table><tr><th>Naam</th><th>KvK nummer</th></tr>"
                    b"<tr><th>Ongeldig B.V.</th><td>1234567</td></tr></table>"
                )
            return super().get(url, **kwargs)

    monkeypatch.setattr("company_harvest.sources.httpx.Client", InvalidIndClient)
    json_path, _ = measure_sources(run, wikidata_limit=1)
    report = json.loads(json_path.read_text())
    ind = next(item for item in report["sources"] if item["source_id"] == "ind_arbeid")
    assert ind["measurement_status"] == "FAILED"
    assert ind["parser_rejections"] == 1
    assert ind["response_count"] == 1


def test_wikidata_paginates_on_raw_binding_count(run, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    pauses = []
    monkeypatch.setattr("company_harvest.sources.time.sleep", pauses.append)

    class PagingClient(FakeClient):
        def get(self, url, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                bindings = [{"orgLabel": {"value": f"Org {index}"}, "kvk": {"value": f"{index:08d}"}} for index in range(100)]
                bindings[0]["kvk"]["value"] = "invalid"
            else:
                bindings = []
            return FakeResponse(json.dumps({"results": {"bindings": bindings}}).encode(), "https://query.wikidata.org/sparql")

    discover(run)
    monkeypatch.setattr("company_harvest.sources.httpx.Client", PagingClient)
    output = collect(run, only=["wikidata_nl_companies"])[0]
    assert len(calls) == 2 and len(read_tsv(output)) == 100
    assert pauses == [3.0]
    assert "wdt:P3220" in calls[0]["params"]["query"]
    assert "wdt:P3821" not in calls[0]["params"]["query"]
    assert read_tsv(output)[0]["registration_validation_status"] == "INVALID"


def test_wikidata_429_stops_without_next_page(run, monkeypatch: pytest.MonkeyPatch) -> None:
    class RateLimitedClient(FakeClient):
        calls = 0

        def get(self, url, **kwargs):
            type(self).calls += 1
            return httpx.Response(
                429,
                request=httpx.Request("GET", url),
                headers={"retry-after": "60"},
                content=b"rate limited",
            )

    discover(run)
    monkeypatch.setattr("company_harvest.sources.httpx.Client", RateLimitedClient)
    with pytest.raises(httpx.HTTPStatusError):
        collect(run, only=["wikidata_nl_companies"])
    assert RateLimitedClient.calls == 1
    assert run.latest_artifact("02", "source_wikidata_nl_companies") is None


def test_generic_source_import_adapters(run, tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("Naam;KVK\nAlpha BV;01234567\n", encoding="utf-8")
    assert read_tsv(import_source(run, csv_path, "csv_input", "Naam", "KVK"))[0]["original_name"] == "Alpha BV"
    downstream = run.artifact_path("03", "after_import", "csv"); write_tsv(downstream, ["x"], [{"x": "1"}]); run.register_artifact(downstream, "03", "after_import")
    html_path = tmp_path / "input.html"
    html_path.write_text("<table><tr><th>Naam</th><th>KVK</th></tr><tr><td>Beta &amp; Co</td><td>12345678</td></tr></table>", encoding="utf-8")
    assert read_tsv(import_source(run, html_path, "html_input", "Naam", "KVK"))[0]["original_name"] == "Beta & Co"
    assert run.latest_artifact("03", "after_import") is None
    xlsx_path = tmp_path / "input.xlsx"
    workbook = Workbook(); sheet = workbook.active; sheet.append(["Naam", "KVK"]); sheet.append(["Gamma BV", "23456789"]); workbook.save(xlsx_path)
    assert read_tsv(import_source(run, xlsx_path, "xlsx_input", "Naam", "KVK"))[0]["source_kvk_hint"] == "23456789"
    names_path = tmp_path / "names.csv"
    names_path.write_text("Naam\nZonder Nummer BV\n", encoding="utf-8")
    name_only = read_tsv(import_source(run, names_path, "name_only", "Naam"))
    assert name_only[0]["source_kvk_hint"] == ""
    assert name_only[0]["registration_validation_status"] == "MISSING"
    profile = next(row for row in list_sources(run) if row["source_id"] == "name_only")
    assert profile["has_registration_number"] == "false"
    with pytest.raises(HarvestError):
        import_source(run, csv_path, "BAD", "Naam", "KVK")


def test_legacy_source_catalog_is_migrated_losslessly(run) -> None:
    legacy = run.artifact_path("01", "legacy_inventory", "csv")
    headers = [
        "source_id", "name", "owner", "url", "parser", "discovered_at", "terms_url",
        "status", "bias", "measured_count",
    ]
    write_tsv(
        legacy,
        headers,
        [{
            "source_id": "ind_arbeid", "name": "Legacy naam", "owner": "IND",
            "url": "https://ind.nl/legacy", "parser": "legacy", "discovered_at": "then",
            "terms_url": "https://ind.nl/nl/copyright", "status": "COLLECTED",
            "bias": "bewaard", "measured_count": "7",
        }],
    )
    run.register_artifact(legacy, "01", "sources_inventory")
    historical = read_catalog(run)
    assert [row["source_id"] for row in historical] == ["ind_arbeid"]
    assert run.latest_artifact("01", "sources_inventory") == legacy
    migrated = list_sources(run)[0]
    assert migrated["catalog_schema_version"] == "2"
    assert migrated["name"] == "Legacy naam" and migrated["measured_count"] == "7"
    assert migrated["source_family"] == "overheidsregister"
    assert run.latest_artifact("01", "sources_inventory") != legacy
