import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from company_harvest.core import (
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
    collect,
    discover,
    import_source,
    list_sources,
    parse_ind_html,
    parse_wikidata,
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


def test_run_lock_artifacts_and_open(run, tmp_path: Path) -> None:
    artifact = run.artifact_path("01", "demo", "md")
    artifact.write_text("demo")
    run.register_artifact(artifact, "01", "demo")
    assert run.latest_artifact("01", "demo") == artifact
    run.log("INFO", "token_test", token="fake")
    assert "[REDACTED]" in (run.path / "logs" / "events.jsonl").read_text()
    with run.lock():
        with pytest.raises(HarvestError) as error:
            with run.lock():
                pass
        assert error.value.exit_code == 6
    assert open_run(run.path).path == run.path
    with pytest.raises(HarvestError):
        open_run(tmp_path / "missing")
    metadata = json.loads((run.path / "run.json").read_text())
    metadata["schema_version"] = 999
    (run.path / "run.json").write_text(json.dumps(metadata))
    with pytest.raises(HarvestError):
        open_run(run.path)


def test_sources_discovery_and_parsers(run) -> None:
    inventory, report = discover(run)
    assert inventory.is_file() and report.is_file()
    assert len(list_sources(run)) == 2
    rows = parse_ind_html("<tr><td>Voorbeeld B.V.</td><td>01234567</td></tr>", "https://ind.nl/x")
    assert rows[0]["source_kvk_hint"] == "01234567"
    with pytest.raises(HarvestError):
        parse_ind_html("geen tabel", "https://ind.nl/x")
    payload = {"results": {"bindings": [{"orgLabel": {"value": "Demo"}, "kvk": {"value": "12345678"}}, {"orgLabel": {"value": "Bad"}, "kvk": {"value": "x"}}]}}
    assert parse_wikidata(payload, "https://query.wikidata.org")[0]["original_name"] == "Demo"
    assert parse_wikidata({}, "x") == []
    assert [item.source_id for item in _enabled(["ind_arbeid"], [])] == ["ind_arbeid"]
    with pytest.raises(HarvestError):
        _enabled(["unknown"], [])


class FakeResponse:
    def __init__(self, content: bytes, url: str = "https://ind.nl/x") -> None:
        self.content = content
        self.text = content.decode()
        self.url = type("URL", (), {"host": "ind.nl", "__str__": lambda self: url})()

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return json.loads(self.content)


class FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get(self, url, **kwargs):
        if "wikidata" in url:
            return FakeResponse(b'{"results":{"bindings":[{"orgLabel":{"value":"Wiki BV"},"kvk":{"value":"23456789"}}]}}', "https://query.wikidata.org/sparql")
        return FakeResponse(b"<td>IND BV</td><td>12345678</td>")


def test_collect_and_bounds(run, monkeypatch: pytest.MonkeyPatch) -> None:
    discover(run)
    monkeypatch.setattr("company_harvest.sources.httpx.Client", FakeClient)
    outputs = collect(run, limit=1)
    assert len(outputs) == 2 and all(read_tsv(path) for path in outputs)
    assert collect(run, limit=1) == outputs
    client = FakeClient()
    with pytest.raises(HarvestError):
        _bounded_get(client, "http://localhost/private")


def test_generic_source_import_adapters(run, tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("Naam;KVK\nAlpha BV;01234567\n", encoding="utf-8")
    assert read_tsv(import_source(run, csv_path, "csv_input", "Naam", "KVK"))[0]["original_name"] == "Alpha BV"
    html_path = tmp_path / "input.html"
    html_path.write_text("<table><tr><th>Naam</th><th>KVK</th></tr><tr><td>Beta &amp; Co</td><td>12345678</td></tr></table>", encoding="utf-8")
    assert read_tsv(import_source(run, html_path, "html_input", "Naam", "KVK"))[0]["original_name"] == "Beta & Co"
    xlsx_path = tmp_path / "input.xlsx"
    workbook = Workbook(); sheet = workbook.active; sheet.append(["Naam", "KVK"]); sheet.append(["Gamma BV", "23456789"]); workbook.save(xlsx_path)
    assert read_tsv(import_source(run, xlsx_path, "xlsx_input", "Naam", "KVK"))[0]["source_kvk_hint"] == "23456789"
    with pytest.raises(HarvestError):
        import_source(run, csv_path, "BAD", "Naam", "KVK")
