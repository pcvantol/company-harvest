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
from company_harvest.gleif import (
    DOWNLOAD_URL,
    REQUIRED_COLUMNS,
    _content_length,
    _download_evidence,
    _raw_candidate,
    _safe_archive,
    collect_gleif,
)
from company_harvest.sources import list_sources
from company_harvest.workflow import merge_candidates, outcome_metrics

HEADERS = sorted(REQUIRED_COLUMNS)


def _row(
    lei: str,
    name: str,
    country: str = "NL",
    authority: str = "RA000463",
    registration: str = "12345678",
    legal_form: str = "54M6",
    entity_status: str = "ACTIVE",
    registration_status: str = "ISSUED",
) -> dict[str, str]:
    return {
        "LEI": lei,
        "Entity.LegalName": name,
        "Entity.LegalAddress.Country": country,
        "Entity.RegistrationAuthority.RegistrationAuthorityID": authority,
        "Entity.RegistrationAuthority.RegistrationAuthorityEntityID": registration,
        "Entity.LegalForm.EntityLegalFormCode": legal_form,
        "Entity.EntityStatus": entity_status,
        "Registration.RegistrationStatus": registration_status,
    }


def _archive(path: Path, rows: list[dict[str, str]], headers: list[str] | None = None) -> Path:
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=headers or HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as bundle:
        bundle.writestr("lei2.csv", text.getvalue())
    return path


def _representative_archive(tmp_path: Path) -> Path:
    return _archive(
        tmp_path / "gleif.zip",
        [
            _row("LEI-1", "Voorbeeld Een", registration="12345678"),
            _row("LEI-2", "Voorbeeld Twee", registration="12345678"),
            _row("LEI-3", "Zonder Nummer", registration=""),
            _row("LEI-4", "Ongeldig Nummer", registration="ABC"),
            _row(
                "LEI-5",
                "Andere Autoriteit",
                authority="RA999999",
                registration="87654321",
                legal_form=" ",
                registration_status="",
            ),
            _row("LEI-6", "", registration="23456789"),
            _row("LEI-7", "Buitenland", country="BE", registration="34567890"),
        ],
    )


def test_gleif_vertical_slice_preserves_candidates_and_closes_counts(run, tmp_path: Path) -> None:
    source = _representative_archive(tmp_path)
    source_hash = sha256(source)

    candidate_path, rejected_path, json_path, md_path = collect_gleif(run, source)

    candidates = read_tsv(candidate_path)
    rejected = read_tsv(rejected_path)
    report = json.loads(json_path.read_text(encoding="utf-8"))
    counts = report["counts"]
    assert len(candidates) == 5
    assert len(rejected) == 4
    assert counts == {
        "all_records_seen": 7,
        "non_nl_records": 1,
        "nl_records": 6,
        "candidate_records": 5,
        "missing_name_records": 1,
        "valid_kvk_records": 3,
        "missing_kvk_records": 2,
        "invalid_kvk_records": 1,
        "identifier_review_records": 4,
        "missing_legal_form_records": 1,
        "missing_status_records": 1,
        "unique_valid_kvk": 2,
        "duplicate_valid_kvk_records": 1,
    }
    assert set(report["count_closure"].values()) == {"CLOSED"}
    assert report["evidence_sha256"] == source_hash
    assert report["status_semantics"] == "GLEIF_SOURCE_DATA_NOT_KVK_VERIFICATION"
    assert md_path.is_file()

    by_name = {row["original_name"]: row for row in candidates}
    assert by_name["Andere Autoriteit"]["source_kvk_hint"] == ""
    assert by_name["Andere Autoriteit"]["source_registration_raw"] == "87654321"
    assert by_name["Andere Autoriteit"]["registration_validation_status"] == "MISSING"
    assert by_name["Voorbeeld Een"]["source_legal_form"] == "54M6"
    assert by_name["Voorbeeld Een"]["source_status"] == "entity=ACTIVE;registration=ISSUED"
    assert {row["rejection_reason"] for row in rejected} == {
        "MISSING_KVK",
        "INVALID_KVK",
        "NON_KVK_REGISTRATION_AUTHORITY",
        "MISSING_LEGAL_NAME",
    }
    assert all(json.loads(row["raw_record_json"])["LEI"].startswith("LEI-") for row in rejected)

    evidence = run.latest_artifact("02", "evidence_gleif_golden_copy")
    assert evidence and evidence != source and evidence.is_file() and sha256(evidence) == source_hash
    inventory = {row["source_id"]: row for row in list_sources(run)}
    assert inventory["gleif_golden_copy"]["measured_count"] == "5"

    merge_candidates(run)
    metrics = outcome_metrics(run)
    gleif = next(item for item in metrics["sources"] if item["source_id"] == "gleif_golden_copy")
    assert gleif["raw_records"] == 5
    assert gleif["valid_registration_numbers"] == 2
    assert gleif["missing_registration_numbers"] == 2
    assert gleif["invalid_registration_numbers"] == 1
    assert gleif["missing_legal_form"] == 1
    assert gleif["missing_status"] == 1
    assert gleif["source_family"] == "wereldwijd-entiteitenregister"


def test_gleif_limit_reuse_refresh_and_downstream_invalidation(run, tmp_path: Path) -> None:
    source = _representative_archive(tmp_path)
    first = collect_gleif(run, source, limit=2)
    report = json.loads(first[2].read_text(encoding="utf-8"))
    assert report["counts"]["nl_records"] == 2
    assert report["scope"] == "BOUNDED_NL_SAMPLE"
    assert collect_gleif(run, source, limit=2) == first

    downstream = run.artifact_path("03", "downstream", "csv")
    write_tsv(downstream, ["x"], [{"x": "1"}])
    run.register_artifact(downstream, "03", "downstream")
    refreshed = collect_gleif(run, source, limit=2, refresh=True)
    assert refreshed != first
    assert run.latest_artifact("03", "downstream") is None

    run.record_config(
        "gleif_collect",
        {"mode": "download", "input_sha256": None, "limit": 2},
    )
    with pytest.raises(HarvestError, match="archief ontbreekt"):
        collect_gleif(run, tmp_path / "missing.zip", limit=2)


def test_gleif_archive_and_row_safety_gates(run, tmp_path: Path, monkeypatch) -> None:
    missing = tmp_path / "missing.zip"
    with pytest.raises(HarvestError, match="ontbreekt"):
        _safe_archive(missing)

    empty = tmp_path / "empty.zip"
    empty.write_bytes(b"")
    with pytest.raises(HarvestError, match="groottegate"):
        _safe_archive(empty)

    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not-a-zip")
    with pytest.raises(HarvestError, match="geldige ZIP"):
        _safe_archive(bad)

    multiple = tmp_path / "multiple.zip"
    with zipfile.ZipFile(multiple, "w") as bundle:
        bundle.writestr("one.csv", "x")
        bundle.writestr("two.csv", "x")
    with pytest.raises(HarvestError, match="exact één"):
        _safe_archive(multiple)

    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as bundle:
        bundle.writestr("../one.csv", "x")
    with pytest.raises(HarvestError, match="onveilig"):
        _safe_archive(unsafe)

    source = _representative_archive(tmp_path)
    monkeypatch.setattr("company_harvest.gleif.MAX_UNCOMPRESSED_BYTES", 1)
    with pytest.raises(HarvestError, match="ongecomprimeerde"):
        _safe_archive(source)

    row = _row("LEI-X", "Naam", authority="RA999999", registration="87654321")
    candidate, rejected, status = _raw_candidate(row, 2, "evidence.zip", "now")
    assert candidate and rejected and status == "MISSING"
    assert candidate["source_registration_raw"] == "87654321"
    _, combined_rejection, combined_status = _raw_candidate(
        _row("LEI-Y", "", registration="bad"), 3, "evidence.zip", "now"
    )
    assert combined_status == "INVALID"
    assert combined_rejection and combined_rejection["rejection_reason"] == (
        "INVALID_KVK|MISSING_LEGAL_NAME"
    )

    assert _content_length({}) is None
    assert _content_length({"content-length": "12"}) == 12
    with pytest.raises(HarvestError, match="Content-Length"):
        _content_length({"content-length": "unknown"})


def test_gleif_rejects_invalid_limit_columns_space_and_ratio(run, tmp_path: Path, monkeypatch) -> None:
    source = _representative_archive(tmp_path)
    with pytest.raises(HarvestError, match="positief"):
        collect_gleif(run, source, limit=0)

    incomplete = _archive(tmp_path / "incomplete.zip", [{"LEI": "X"}], ["LEI"])
    downstream = run.artifact_path("03", "preserved_on_failed_refresh", "csv")
    write_tsv(downstream, ["x"], [{"x": "1"}])
    run.register_artifact(downstream, "03", "preserved_on_failed_refresh")
    with pytest.raises(HarvestError, match="mist verplichte kolommen"):
        collect_gleif(run, incomplete, refresh=True)
    assert run.latest_artifact("03", "preserved_on_failed_refresh") == downstream

    monkeypatch.setattr("company_harvest.gleif.MAX_COMPRESSION_RATIO", 0.5)
    with pytest.raises(HarvestError, match="compressieratio"):
        _safe_archive(source)
    monkeypatch.setattr("company_harvest.gleif.MAX_COMPRESSION_RATIO", 15.0)

    monkeypatch.setattr(
        "company_harvest.gleif.shutil.disk_usage",
        lambda _path: type("Usage", (), {"free": 0})(),
    )
    with pytest.raises(HarvestError, match="onvoldoende vrije schijfruimte"):
        collect_gleif(run, source, refresh=True)


class _StreamResponse:
    def __init__(
        self,
        content: bytes,
        *,
        url: str = DOWNLOAD_URL,
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
            request = httpx.Request("GET", DOWNLOAD_URL)
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("download failed", request=request, response=response)


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


def test_gleif_download_is_bounded_and_uses_neutral_user_agent(
    run, tmp_path: Path, monkeypatch
) -> None:
    source = _representative_archive(tmp_path)
    _StreamClient.response = _StreamResponse(source.read_bytes())
    monkeypatch.setattr("company_harvest.gleif.httpx.Client", _StreamClient)
    evidence, metadata = _download_evidence(run)
    assert evidence.is_file() and sha256(evidence) == sha256(source)
    assert metadata["downloaded_bytes"] == source.stat().st_size
    assert _StreamClient.headers == {"User-Agent": HTTP_USER_AGENT}
    assert _StreamClient.options["follow_redirects"] is False
    assert HTTP_USER_AGENT == "company-lookup/0.1" and "github" not in HTTP_USER_AGENT

    _StreamClient.response = _StreamResponse(source.read_bytes(), url="https://example.org/x")
    with pytest.raises(HarvestError, match="niet-toegestane host"):
        _download_evidence(run)

    _StreamClient.response = _StreamResponse(
        source.read_bytes(), url="http://goldencopy.gleif.org/x"
    )
    with pytest.raises(HarvestError, match="niet-toegestane host"):
        _download_evidence(run)

    _StreamClient.response = _StreamResponse(
        b"", status=302, headers={"location": "https://example.org/private"}
    )
    with pytest.raises(HarvestError, match="niet-toegestane host"):
        _download_evidence(run)
    assert _StreamClient.urls == [DOWNLOAD_URL]

    for location in (
        "https://goldencopy.gleif.org:bad/private",
        "https://goldencopy.gleif.org:99999/private",
    ):
        _StreamClient.response = _StreamResponse(
            b"", status=302, headers={"location": location}
        )
        with pytest.raises(HarvestError, match="niet-toegestane host"):
            _download_evidence(run)
        assert _StreamClient.urls == [DOWNLOAD_URL]

    redirected_url = "https://goldencopy.gleif.org/approved.csv"
    _StreamClient.response = [
        _StreamResponse(b"", status=302, headers={"location": "/approved.csv"}),
        _StreamResponse(source.read_bytes(), url=redirected_url),
    ]
    redirected, redirected_metadata = _download_evidence(run)
    assert redirected.is_file()
    assert _StreamClient.urls == [DOWNLOAD_URL, redirected_url]
    assert redirected_metadata["redirect_count"] == 1

    _StreamClient.response = _StreamResponse(
        source.read_bytes(), headers={"content-length": str(700 * 1024 * 1024)}
    )
    with pytest.raises(HarvestError, match="groottegate"):
        _download_evidence(run)

    _StreamClient.response = _StreamResponse(source.read_bytes(), status=429)
    with pytest.raises(HarvestError, match="HTTP 429; geen fallback"):
        _download_evidence(run)

    _StreamClient.response = _StreamResponse(source.read_bytes())
    with monkeypatch.context() as scoped:
        moments = iter((0.0, 1801.0))
        scoped.setattr("company_harvest.gleif.time.monotonic", lambda: next(moments))
        with pytest.raises(HarvestError, match="tijdgate"):
            _download_evidence(run)

    class TimeoutClient(_StreamClient):
        def stream(self, method: str, url: str):
            raise httpx.ReadTimeout("timeout", request=httpx.Request(method, url))

    monkeypatch.setattr("company_harvest.gleif.httpx.Client", TimeoutClient)
    with pytest.raises(HarvestError, match="ReadTimeout"):
        _download_evidence(run)


def test_gleif_cli_and_catalog_contract(run, tmp_path: Path, capsys) -> None:
    source = _representative_archive(tmp_path)
    args = build_parser().parse_args(
        ["sources", "gleif", "--run-dir", str(run.path), "--archive", str(source), "--limit", "1"]
    )
    assert dispatch(args) == 0
    assert "gleif_ingest_report" in capsys.readouterr().out
    catalog = {row["source_id"]: row for row in list_sources(run)}
    gleif = catalog["gleif_golden_copy"]
    assert gleif["access_mode"] == "bulk"
    assert gleif["provides_legal_form"] == "true"
    assert gleif["provides_status"] == "true"
    assert gleif["registration_number_type"] == "KVK via registratieautoriteit RA000463"
