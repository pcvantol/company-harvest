from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest

from company_harvest.cli import build_parser, dispatch
from company_harvest.core import HTTP_USER_AGENT, HarvestError, read_tsv, sha256, write_tsv
from company_harvest.public_registers import (
    ANBI,
    DUO,
    _candidate,
    _content_length,
    _download_evidence,
    _safe_archive,
    collect_public_register,
)
from company_harvest.sources import list_sources
from company_harvest.workflow import merge_candidates, outcome_metrics


def _anbi_archive(path: Path, rows: list[dict[str, str]]) -> Path:
    parts = ["<?xml version='1.0' encoding='UTF-8'?><publicatieAnbiInstellingen>"]
    for row in rows:
        parts.append("<beschikking>")
        parts.extend(f"<{key}>{value}</{key}>" for key, value in row.items())
        parts.append("</beschikking>")
    parts.append("</publicatieAnbiInstellingen>")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as bundle:
        bundle.writestr("anbi.xml", "".join(parts))
        bundle.writestr("README.txt", "CC0")
    return path


def _duo_archive(path: Path, rows: list[dict[str, str]], *, complete: bool = True) -> Path:
    headers = [
        "NAAM_VOLLEDIG",
        "NAAM_PLAATS_VEST",
        "INTERNET",
        "KVK_NR",
        "CODE_STAND_RECORD",
        "IND_OPGEHEVEN",
    ]
    if not complete:
        headers = ["NAAM_VOLLEDIG"]
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as bundle:
        bundle.writestr("ORGANISATIES_20260918.csv", text.getvalue())
        bundle.writestr("Beschrijving.txt", "test")
    return path


def _duo_row(
    name: str,
    kvk: str,
    stand: str = "A",
    closed: str = "N",
) -> dict[str, str]:
    return {
        "NAAM_VOLLEDIG": name,
        "NAAM_PLAATS_VEST": "Testplaats",
        "INTERNET": "https://example.invalid",
        "KVK_NR": kvk,
        "CODE_STAND_RECORD": stand,
        "IND_OPGEHEVEN": closed,
    }


def test_anbi_vertical_slice_keeps_candidates_without_kvk(run, tmp_path: Path) -> None:
    source = _anbi_archive(
        tmp_path / "anbi.zip",
        [
            {
                "fiscaalNummer": "123456789",
                "naam": "Stichting Voorbeeld",
                "vestigingsPlaats": "Testplaats",
                "webSite": "https://example.invalid",
                "ingangsDatum": "20200101",
            },
            {"naam": "Zonder fiscaal nummer", "ingangsDatum": "20210101"},
            {"fiscaalNummer": "987654321", "naam": ""},
        ],
    )
    paths = collect_public_register(run, ANBI.source_id, source)
    candidates, rejected = read_tsv(paths[0]), read_tsv(paths[1])
    report = json.loads(paths[2].read_text(encoding="utf-8"))

    assert len(candidates) == 2 and len(rejected) == 3
    assert report["counts"] == {
        "all_records_seen": 3,
        "current_records": 3,
        "non_current_records": 0,
        "candidate_records": 2,
        "missing_name_records": 1,
        "valid_kvk_records": 0,
        "missing_kvk_records": 3,
        "invalid_kvk_records": 0,
        "review_records": 3,
        "records_with_source_identifier": 2,
        "records_without_source_identifier": 1,
        "unique_valid_kvk": 0,
        "duplicate_valid_kvk_records": 0,
    }
    assert set(report["count_closure"].values()) == {"CLOSED"}
    assert report["evidence_sha256"] == sha256(source)
    assert all(row["source_kvk_hint"] == "" for row in candidates)
    assert all(row["registration_validation_status"] == "MISSING" for row in candidates)
    assert candidates[0]["source_registration_raw"] == "123456789"
    assert candidates[0]["country"] == ""
    assert candidates[0]["source_status"] == ""
    assert "Belastingdienst ANBI-register" in candidates[0]["nl_evidence"]
    assert {row["rejection_reason"] for row in rejected} == {
        "NON_KVK_FISCAL_IDENTIFIER",
        "MISSING_DIRECT_REGISTRATION_IDENTIFIER",
        "NON_KVK_FISCAL_IDENTIFIER|MISSING_LEGAL_NAME",
    }
    assert run.latest_artifact("02", "evidence_anbi_register") is not None
    assert {row["source_id"]: row for row in list_sources(run)}[ANBI.source_id][
        "measured_count"
    ] == "2"

    merge_candidates(run)
    source_metrics = next(
        row for row in outcome_metrics(run)["sources"] if row["source_id"] == ANBI.source_id
    )
    assert source_metrics["raw_records"] == 2
    assert source_metrics["missing_registration_numbers"] == 2
    assert source_metrics["source_family"] == "fiscale-erkenningen"


def test_duo_vertical_slice_partitions_history_and_identifiers(run, tmp_path: Path) -> None:
    source = _duo_archive(
        tmp_path / "duo.zip",
        [
            _duo_row("Historisch", "87654321", "H", "J"),
            _duo_row("Geldig een", "12345678"),
            _duo_row("Geldig twee", "12345678"),
            _duo_row("Zonder KVK", ""),
            _duo_row("Ongeldig KVK", "ABC"),
            _duo_row("", "23456789"),
            _duo_row("Transitie", "", "T"),
        ],
    )
    paths = collect_public_register(run, DUO.source_id, source)
    candidates, rejected = read_tsv(paths[0]), read_tsv(paths[1])
    report = json.loads(paths[2].read_text(encoding="utf-8"))
    counts = report["counts"]

    assert len(candidates) == 4 and len(rejected) == 5
    assert counts == {
        "all_records_seen": 7,
        "current_records": 5,
        "non_current_records": 2,
        "candidate_records": 4,
        "missing_name_records": 1,
        "valid_kvk_records": 3,
        "missing_kvk_records": 1,
        "invalid_kvk_records": 1,
        "review_records": 5,
        "records_with_source_identifier": 4,
        "records_without_source_identifier": 1,
        "unique_valid_kvk": 2,
        "duplicate_valid_kvk_records": 1,
    }
    assert set(report["count_closure"].values()) == {"CLOSED"}
    assert {row["original_name"] for row in candidates} == {
        "Geldig een",
        "Geldig twee",
        "Zonder KVK",
        "Ongeldig KVK",
    }
    assert all(row["country"] == "Nederland" for row in candidates)
    assert all(row["source_status"].startswith("record=A;") for row in candidates)
    reasons = {row["rejection_reason"] for row in rejected}
    assert reasons == {
        "NON_CURRENT_SOURCE_RECORD",
        "MISSING_KVK",
        "INVALID_KVK",
        "MISSING_LEGAL_NAME",
    }
    no_kvk = next(row for row in candidates if row["original_name"] == "Zonder KVK")
    assert no_kvk["registration_validation_status"] == "MISSING"
    invalid = next(row for row in candidates if row["original_name"] == "Ongeldig KVK")
    assert invalid["registration_validation_status"] == "INVALID"


def test_public_register_limit_reuse_refresh_and_failures(
    run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _duo_archive(
        tmp_path / "duo.zip",
        [_duo_row("Historisch", "", "H"), _duo_row("Een", ""), _duo_row("Twee", "")],
    )
    first = collect_public_register(run, DUO.source_id, source, limit=1)
    report = json.loads(first[2].read_text(encoding="utf-8"))
    assert report["counts"]["all_records_seen"] == 2
    assert report["counts"]["current_records"] == 1
    assert report["scope"] == "BOUNDED_CURRENT_SAMPLE"
    assert collect_public_register(run, DUO.source_id, source, limit=1) == first

    first[0].write_text("corrupt", encoding="utf-8")
    repaired = collect_public_register(run, DUO.source_id, source, limit=1)
    assert repaired != first
    assert [row["original_name"] for row in read_tsv(repaired[0])] == ["Een"]

    original_update = __import__(
        "company_harvest.public_registers", fromlist=["_update_inventory"]
    )._update_inventory
    config_before_failure = run.metadata()["runtime_config"][f"{DUO.source_id}_collect"]

    def fail_inventory(*_args) -> None:
        raise RuntimeError("inventory update failed")

    monkeypatch.setattr("company_harvest.public_registers._update_inventory", fail_inventory)
    with pytest.raises(RuntimeError, match="inventory update failed"):
        collect_public_register(run, DUO.source_id, source, limit=1, refresh=True)
    assert run.metadata()["runtime_config"][f"{DUO.source_id}_collect"] == config_before_failure
    failed_candidate = run.latest_artifact("02", f"source_{DUO.source_id}")
    monkeypatch.setattr("company_harvest.public_registers._update_inventory", original_update)
    recovered = collect_public_register(run, DUO.source_id, source, limit=1)
    assert recovered[0] != failed_candidate

    downstream = run.artifact_path("03", "downstream", "csv")
    write_tsv(downstream, ["x"], [{"x": "1"}])
    run.register_artifact(downstream, "03", "downstream")
    refreshed = collect_public_register(run, DUO.source_id, source, limit=1, refresh=True)
    assert refreshed != first and run.latest_artifact("03", "downstream") is None

    with pytest.raises(HarvestError, match="onbekend publiek register"):
        collect_public_register(run, "unknown", source)
    with pytest.raises(HarvestError, match="positief"):
        collect_public_register(run, DUO.source_id, source, limit=0)
    with pytest.raises(HarvestError, match="ontbreekt"):
        collect_public_register(run, DUO.source_id, tmp_path / "missing.zip")

    incomplete = _duo_archive(tmp_path / "incomplete.zip", [{"NAAM_VOLLEDIG": "X"}], complete=False)
    preserved = run.artifact_path("03", "preserved", "csv")
    write_tsv(preserved, ["x"], [{"x": "1"}])
    run.register_artifact(preserved, "03", "preserved")
    with pytest.raises(HarvestError, match="mist verplichte kolommen"):
        collect_public_register(run, DUO.source_id, incomplete, refresh=True)
    assert run.latest_artifact("03", "preserved") == preserved

    broken_xml = tmp_path / "broken-anbi.zip"
    with zipfile.ZipFile(broken_xml, "w") as bundle:
        bundle.writestr("anbi.xml", "<broken>")
    with pytest.raises(HarvestError, match="ParseError"):
        collect_public_register(run, ANBI.source_id, broken_xml, refresh=True)

    entity_xml = tmp_path / "entity-anbi.zip"
    with zipfile.ZipFile(entity_xml, "w") as bundle:
        bundle.writestr(
            "anbi.xml",
            '<!DOCTYPE x [<!ENTITY unsafe "expanded">]>'
            "<publicatieAnbiInstellingen><beschikking><naam>&unsafe;</naam>"
            "</beschikking></publicatieAnbiInstellingen>",
        )
    with pytest.raises(HarvestError, match="EntitiesForbidden"):
        collect_public_register(run, ANBI.source_id, entity_xml, refresh=True)


def test_public_register_archive_and_candidate_gates(run, tmp_path: Path, monkeypatch) -> None:
    with pytest.raises(HarvestError, match="ontbreekt"):
        _safe_archive(tmp_path / "missing.zip", ANBI)
    empty = tmp_path / "empty.zip"
    empty.write_bytes(b"")
    with pytest.raises(HarvestError, match="groottegate"):
        _safe_archive(empty, ANBI)
    invalid = tmp_path / "invalid.zip"
    invalid.write_bytes(b"no zip")
    with pytest.raises(HarvestError, match="geldige ZIP"):
        _safe_archive(invalid, ANBI)
    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as bundle:
        bundle.writestr("../anbi.xml", "x")
    with pytest.raises(HarvestError, match="onveilig"):
        _safe_archive(unsafe, ANBI)
    wrong_member = tmp_path / "wrong.zip"
    with zipfile.ZipFile(wrong_member, "w") as bundle:
        bundle.writestr("other.xml", "x")
    with pytest.raises(HarvestError, match="exact één"):
        _safe_archive(wrong_member, ANBI)

    source = _anbi_archive(tmp_path / "anbi.zip", [{"naam": "X"}])
    monkeypatch.setattr("company_harvest.public_registers.MAX_COMPRESSION_RATIO", 0.5)
    with pytest.raises(HarvestError, match="compressieratio"):
        _safe_archive(source, ANBI)
    monkeypatch.setattr("company_harvest.public_registers.MAX_COMPRESSION_RATIO", 25.0)
    monkeypatch.setattr(
        "company_harvest.public_registers.shutil.disk_usage",
        lambda _path: type("Usage", (), {"free": 0})(),
    )
    with pytest.raises(HarvestError, match="onvoldoende vrije schijfruimte"):
        collect_public_register(run, ANBI.source_id, source)

    candidate, rejected, status, current = _candidate(
        ANBI, {"naam": "Naam", "fiscaalNummer": "123"}, 1, "e.zip", "now"
    )
    assert candidate and rejected and status == "MISSING" and current
    historic, historic_rejected, valid_status, current = _candidate(
        DUO, _duo_row("Oud", "12345678", "H"), 2, "e.zip", "now"
    )
    assert historic is None and historic_rejected and valid_status == "VALID" and not current
    assert _content_length({}, ANBI) is None
    assert _content_length({"content-length": "10"}, ANBI) == 10
    with pytest.raises(HarvestError, match="Content-Length"):
        _content_length({"content-length": "nope"}, ANBI)


class _StreamResponse:
    def __init__(
        self,
        content: bytes,
        *,
        url: str = ANBI.download_url,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.content = content
        self.url = url
        self.status_code = status
        self.headers = headers or {"content-length": str(len(content))}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def iter_bytes(self, _size: int):
        yield self.content

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", ANBI.download_url)
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("failed", request=request, response=response)


class _StreamClient:
    headers: dict[str, str] = {}
    options: dict[str, object] = {}
    urls: list[str] = []
    response: _StreamResponse | list[_StreamResponse]

    def __init__(self, *args, **kwargs) -> None:
        type(self).headers = kwargs["headers"]
        type(self).options = kwargs
        type(self).urls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def stream(self, method: str, url: str):
        assert method == "GET"
        type(self).urls.append(url)
        response = type(self).response
        return response.pop(0) if isinstance(response, list) else response


def test_public_register_download_bounds_redirects_and_user_agent(
    run, tmp_path: Path, monkeypatch
) -> None:
    source = _anbi_archive(tmp_path / "anbi.zip", [{"naam": "X"}])
    _StreamClient.response = _StreamResponse(source.read_bytes())
    monkeypatch.setattr("company_harvest.public_registers.httpx.Client", _StreamClient)
    evidence, metadata = _download_evidence(run, ANBI)
    assert sha256(evidence) == sha256(source)
    assert metadata["downloaded_bytes"] == source.stat().st_size
    assert _StreamClient.headers == {"User-Agent": HTTP_USER_AGENT}
    assert _StreamClient.options["follow_redirects"] is False

    redirected_url = "https://download.belastingdienst.nl/data/anbi/current.zip"
    _StreamClient.response = [
        _StreamResponse(b"", status=302, headers={"location": "/data/anbi/current.zip"}),
        _StreamResponse(source.read_bytes(), url=redirected_url),
    ]
    _, redirected_metadata = _download_evidence(run, ANBI)
    assert _StreamClient.urls == [ANBI.download_url, redirected_url]
    assert redirected_metadata["redirect_count"] == 1

    for location in (
        "https://example.org/private.zip",
        "https://download.belastingdienst.nl:bad/private.zip",
    ):
        _StreamClient.response = _StreamResponse(b"", status=302, headers={"location": location})
        with pytest.raises(HarvestError, match="niet-toegestane host"):
            _download_evidence(run, ANBI)
        assert _StreamClient.urls == [ANBI.download_url]

    for url in (
        "https://example.org/private.zip",
        "http://download.belastingdienst.nl/private.zip",
        "https://download.belastingdienst.nl:bad/private.zip",
    ):
        _StreamClient.response = _StreamResponse(source.read_bytes(), url=url)
        with pytest.raises(HarvestError, match="niet-toegestane host"):
            _download_evidence(run, ANBI)

    _StreamClient.response = _StreamResponse(
        source.read_bytes(), headers={"content-length": str(30 * 1024 * 1024)}
    )
    with pytest.raises(HarvestError, match="groottegate"):
        _download_evidence(run, ANBI)
    _StreamClient.response = _StreamResponse(source.read_bytes(), status=429)
    with pytest.raises(HarvestError, match="HTTP 429"):
        _download_evidence(run, ANBI)

    class TimeoutClient(_StreamClient):
        def stream(self, method: str, url: str):
            raise httpx.ReadTimeout("timeout", request=httpx.Request(method, url))

    monkeypatch.setattr("company_harvest.public_registers.httpx.Client", TimeoutClient)
    with pytest.raises(HarvestError, match="ReadTimeout"):
        _download_evidence(run, ANBI)


@pytest.mark.parametrize(
    ("command", "source_id", "factory"),
    [
        ("anbi", ANBI.source_id, lambda path: _anbi_archive(path, [{"naam": "X"}])),
        ("duo", DUO.source_id, lambda path: _duo_archive(path, [_duo_row("X", "")])),
    ],
)
def test_public_register_cli_and_catalog_contract(
    run, tmp_path: Path, capsys, command: str, source_id: str, factory
) -> None:
    source = factory(tmp_path / f"{command}.zip")
    args = build_parser().parse_args(
        ["sources", command, "--run-dir", str(run.path), "--archive", str(source), "--limit", "1"]
    )
    assert dispatch(args) == 0
    assert "ingest_report" in capsys.readouterr().out
    catalog = {row["source_id"]: row for row in list_sources(run)}
    assert len(catalog) == 6
    assert catalog[source_id]["access_mode"] == "bulk"
    assert catalog[source_id]["candidate_layer"] == "raw"
