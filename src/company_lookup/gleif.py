"""Streaming GLEIF Level 1 Golden Copy-adapter."""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import sqlite3
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from company_lookup.core import (
    HTTP_USER_AGENT,
    HarvestError,
    Run,
    atomic_write,
    sha256,
    timestamp,
    validate_kvk,
    write_tsv,
)
from company_lookup.sources import (
    RAW_HEADERS,
    SOURCE_HEADERS,
    read_catalog,
)

SOURCE_ID = "gleif_golden_copy"
DOWNLOAD_URL = "https://goldencopy.gleif.org/api/v2/golden-copies/publishes/lei2/latest.csv"
TERMS_URL = "https://www.gleif.org/en/meta/lei-data-terms-of-use"
ALLOWED_HOSTS = {"goldencopy.gleif.org"}
MAX_ARCHIVE_BYTES = 600 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 6 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 15.0
MIN_OUTPUT_RESERVE_BYTES = 64 * 1024 * 1024
MAX_DOWNLOAD_SECONDS = 30 * 60
MAX_REDIRECTS = 3
REPORT_SCHEMA_VERSION = 1
REQUIRED_COLUMNS = {
    "LEI",
    "Entity.LegalName",
    "Entity.LegalAddress.Country",
    "Entity.RegistrationAuthority.RegistrationAuthorityID",
    "Entity.RegistrationAuthority.RegistrationAuthorityEntityID",
    "Entity.LegalForm.EntityLegalFormCode",
    "Entity.EntityStatus",
    "Registration.RegistrationStatus",
}
REJECTED_HEADERS = [
    "source_row",
    "source_lei",
    "original_name",
    "registration_authority",
    "source_registration_raw",
    "registration_validation_status",
    "rejection_reason",
    "raw_record_json",
]


def _safe_archive(path: Path) -> zipfile.ZipInfo:
    if not path.is_file():
        raise HarvestError("GLEIF-archief ontbreekt")
    size = path.stat().st_size
    if size <= 0 or size > MAX_ARCHIVE_BYTES:
        raise HarvestError("GLEIF-archief overschrijdt de geconfigureerde groottegate")
    try:
        with zipfile.ZipFile(path) as bundle:
            members = [item for item in bundle.infolist() if not item.is_dir()]
    except zipfile.BadZipFile as exc:
        raise HarvestError("GLEIF-archief is geen geldige ZIP") from exc
    if len(members) != 1:
        raise HarvestError("GLEIF-archief moet exact één CSV-bestand bevatten")
    member = members[0]
    if Path(member.filename).name != member.filename or not member.filename.lower().endswith(".csv"):
        raise HarvestError("GLEIF-ZIP bevat een onveilig of onverwacht bestandspad")
    if member.flag_bits & 0x1:
        raise HarvestError("GLEIF-ZIP mag niet versleuteld zijn")
    if member.file_size <= 0 or member.file_size > MAX_UNCOMPRESSED_BYTES:
        raise HarvestError("GLEIF-CSV overschrijdt de ongecomprimeerde groottegate")
    ratio = member.file_size / max(member.compress_size, 1)
    if ratio > MAX_COMPRESSION_RATIO:
        raise HarvestError("GLEIF-ZIP overschrijdt de compressieratiogate")
    return member


def _require_space(destination: Path, required: int) -> None:
    free = shutil.disk_usage(destination).free
    if free < required:
        raise HarvestError(
            f"onvoldoende vrije schijfruimte voor GLEIF: vereist {required}, beschikbaar {free}"
        )


def _copy_evidence(run: Run, source: Path, expected_hash: str) -> Path:
    source = source.expanduser().resolve()
    member = _safe_archive(source)
    _require_space(
        run.path,
        source.stat().st_size + min(member.file_size, MAX_ARCHIVE_BYTES) + MIN_OUTPUT_RESERVE_BYTES,
    )
    destination = run.path / "evidence" / f"{timestamp()}_02_gleif_golden_copy.csv.zip"
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        shutil.copyfile(source, temporary)
        if sha256(temporary) != expected_hash:
            raise HarvestError("GLEIF-evidencekopie heeft een afwijkende SHA-256")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _content_length(headers: Any) -> int | None:
    value = headers.get("content-length")
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HarvestError("GLEIF-download heeft een ongeldige Content-Length") from exc


def _validate_download_url(url: str) -> None:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise HarvestError("GLEIF-redirect naar niet-toegestane host") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise HarvestError("GLEIF-redirect naar niet-toegestane host")


def _download_evidence(run: Run) -> tuple[Path, dict[str, object]]:
    _require_space(run.path, 2 * MAX_ARCHIVE_BYTES + MIN_OUTPUT_RESERVE_BYTES)
    destination = run.path / "evidence" / f"{timestamp()}_02_gleif_golden_copy.csv.zip"
    temporary = destination.with_name(f".{destination.name}.tmp")
    response_metadata: dict[str, object] = {}
    downloaded = 0
    started = time.monotonic()
    timeout = httpx.Timeout(120, connect=15, read=120, write=15, pool=15)
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": HTTP_USER_AGENT},
        ) as client:
            current_url = DOWNLOAD_URL
            for redirect_count in range(MAX_REDIRECTS + 1):
                _validate_download_url(current_url)
                with client.stream("GET", current_url) as response:
                    response_url = str(response.url)
                    _validate_download_url(response_url)
                    if 300 <= response.status_code < 400:
                        location = response.headers.get("location")
                        if not location or redirect_count >= MAX_REDIRECTS:
                            raise HarvestError("GLEIF-download overschrijdt de redirectgate")
                        next_url = urljoin(response_url, location)
                        _validate_download_url(next_url)
                        current_url = next_url
                        continue
                    content_length = _content_length(response.headers)
                    if content_length is not None and content_length > MAX_ARCHIVE_BYTES:
                        raise HarvestError("GLEIF-download overschrijdt de groottegate")
                    response_metadata = {
                        "http_status": response.status_code,
                        "final_url": response_url,
                        "redirect_count": redirect_count,
                        "publish_date": response.headers.get("x-gleif-publish-date"),
                        "content_length": content_length,
                        "user_agent": HTTP_USER_AGENT,
                    }
                    response.raise_for_status()
                    with temporary.open("wb") as handle:
                        for chunk in response.iter_bytes(1024 * 1024):
                            if time.monotonic() - started > MAX_DOWNLOAD_SECONDS:
                                raise HarvestError("GLEIF-download overschrijdt de tijdgate")
                            downloaded += len(chunk)
                            if downloaded > MAX_ARCHIVE_BYTES:
                                raise HarvestError("GLEIF-download overschrijdt de groottegate")
                            handle.write(chunk)
                        handle.flush()
                        os.fsync(handle.fileno())
                    break
        os.replace(temporary, destination)
    except httpx.HTTPStatusError as exc:
        raise HarvestError(
            f"GLEIF-download stopte met HTTP {exc.response.status_code}; geen fallback uitgevoerd"
        ) from exc
    except httpx.HTTPError as exc:
        raise HarvestError(f"GLEIF-download mislukt: {type(exc).__name__}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    response_metadata["downloaded_bytes"] = downloaded
    return destination, response_metadata


def _raw_candidate(
    row: dict[str, str],
    row_number: int,
    evidence_name: str,
    fetched_at: str,
) -> tuple[dict[str, str] | None, dict[str, str] | None, str]:
    name = (row.get("Entity.LegalName") or "").strip()
    authority = (
        row.get("Entity.RegistrationAuthority.RegistrationAuthorityID") or ""
    ).strip()
    registration = (
        row.get("Entity.RegistrationAuthority.RegistrationAuthorityEntityID") or ""
    ).strip()
    status: str
    reasons: list[str] = []
    number = ""
    if authority != "RA000463":
        status = "MISSING"
        reasons.append("NON_KVK_REGISTRATION_AUTHORITY")
    else:
        try:
            number = validate_kvk(registration)
            status = "VALID"
        except ValueError:
            status = "INVALID" if registration else "MISSING"
            reasons.append("INVALID_KVK" if registration else "MISSING_KVK")
    if not name:
        reasons.append("MISSING_LEGAL_NAME")
    reason = "|".join(reasons)
    rejected = None
    if reason:
        rejected = {
            "source_row": str(row_number),
            "source_lei": row.get("LEI") or "",
            "original_name": name,
            "registration_authority": authority,
            "source_registration_raw": registration,
            "registration_validation_status": status,
            "rejection_reason": reason,
            "raw_record_json": json.dumps(row, ensure_ascii=False, separators=(",", ":")),
        }
    if not name:
        return None, rejected, status
    candidate = {
        "original_name": name,
        "country": "Nederland",
        "nl_evidence": "GLEIF Entity.LegalAddress.Country=NL",
        "employees_raw": "",
        "employees_date": "",
        "employees_scope": "",
        "website": "",
        "sector": "",
        "source_kvk_hint": number,
        "source_id": SOURCE_ID,
        "source_url": DOWNLOAD_URL,
        "fetched_at": fetched_at,
        "source_row": str(row_number),
        "evidence_reference": evidence_name,
        "source_registration_raw": registration,
        "registration_validation_status": status,
        "source_legal_form": row.get("Entity.LegalForm.EntityLegalFormCode") or "",
        "source_status": (
            f"entity={row.get('Entity.EntityStatus') or ''};"
            f"registration={row.get('Registration.RegistrationStatus') or ''}"
        ),
        "candidate_layer": "raw",
    }
    return candidate, rejected, status


def _parse_archive(
    run: Run, evidence: Path, evidence_hash: str, limit: int | None
) -> tuple[Path, Path, dict[str, object]]:
    if limit is not None and limit < 1:
        raise HarvestError("GLEIF-limiet moet positief zijn")
    member = _safe_archive(evidence)
    candidate_path = run.artifact_path("02", "source_gleif_golden_copy_companies", "csv")
    rejected_path = run.artifact_path("02", "source_gleif_golden_copy_rejected", "csv")
    candidate_temp = candidate_path.with_name(f".{candidate_path.name}.tmp")
    rejected_temp = rejected_path.with_name(f".{rejected_path.name}.tmp")
    unique_db = run.path / f".{timestamp()}_gleif_unique.sqlite"
    fetched_at = datetime.now(UTC).isoformat()
    started = time.monotonic()
    counts: dict[str, int] = {
        "all_records_seen": 0,
        "non_nl_records": 0,
        "nl_records": 0,
        "candidate_records": 0,
        "missing_name_records": 0,
        "valid_kvk_records": 0,
        "missing_kvk_records": 0,
        "invalid_kvk_records": 0,
        "identifier_review_records": 0,
        "missing_legal_form_records": 0,
        "missing_status_records": 0,
    }
    connection = sqlite3.connect(unique_db)
    connection.execute("CREATE TABLE kvk (number TEXT PRIMARY KEY) WITHOUT ROWID")
    try:
        with (
            candidate_temp.open("w", encoding="utf-8", newline="") as candidate_handle,
            rejected_temp.open("w", encoding="utf-8", newline="") as rejected_handle,
        ):
            candidate_writer = csv.DictWriter(
                candidate_handle,
                fieldnames=RAW_HEADERS,
                delimiter="\t",
                extrasaction="ignore",
            )
            rejected_writer = csv.DictWriter(
                rejected_handle,
                fieldnames=REJECTED_HEADERS,
                delimiter="\t",
                extrasaction="ignore",
            )
            candidate_writer.writeheader()
            rejected_writer.writeheader()
            with zipfile.ZipFile(evidence) as bundle, bundle.open(member) as binary:
                text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
                reader = csv.DictReader(text)
                headers = set(reader.fieldnames or [])
                missing_columns = REQUIRED_COLUMNS - headers
                if missing_columns:
                    raise HarvestError(
                        "GLEIF-CSV mist verplichte kolommen: " + ", ".join(sorted(missing_columns))
                    )
                for row_number, row in enumerate(reader, 2):
                    if limit is not None and counts["nl_records"] >= limit:
                        break
                    counts["all_records_seen"] += 1
                    if (row.get("Entity.LegalAddress.Country") or "").strip() != "NL":
                        counts["non_nl_records"] += 1
                        continue
                    counts["nl_records"] += 1
                    candidate, rejected, status = _raw_candidate(
                        row, row_number, evidence.name, fetched_at
                    )
                    if candidate is None:
                        counts["missing_name_records"] += 1
                    else:
                        candidate_writer.writerow(candidate)
                        counts["candidate_records"] += 1
                        if not candidate["source_legal_form"].strip():
                            counts["missing_legal_form_records"] += 1
                        if not (row.get("Entity.EntityStatus") or "").strip() or not (
                            row.get("Registration.RegistrationStatus") or ""
                        ).strip():
                            counts["missing_status_records"] += 1
                    if status == "VALID":
                        counts["valid_kvk_records"] += 1
                        number = candidate["source_kvk_hint"] if candidate else validate_kvk(
                            row["Entity.RegistrationAuthority.RegistrationAuthorityEntityID"]
                            or ""
                        )
                        connection.execute("INSERT OR IGNORE INTO kvk VALUES (?)", (number,))
                    elif status == "INVALID":
                        counts["invalid_kvk_records"] += 1
                    else:
                        counts["missing_kvk_records"] += 1
                    if rejected:
                        rejected_writer.writerow(rejected)
                        counts["identifier_review_records"] += 1
            candidate_handle.flush()
            os.fsync(candidate_handle.fileno())
            rejected_handle.flush()
            os.fsync(rejected_handle.fileno())
        connection.commit()
        unique_count = int(connection.execute("SELECT COUNT(*) FROM kvk").fetchone()[0])
        os.replace(candidate_temp, candidate_path)
        os.replace(rejected_temp, rejected_path)
    finally:
        connection.close()
        unique_db.unlink(missing_ok=True)
        candidate_temp.unlink(missing_ok=True)
        rejected_temp.unlink(missing_ok=True)
    counts["unique_valid_kvk"] = unique_count
    counts["duplicate_valid_kvk_records"] = counts["valid_kvk_records"] - unique_count
    report: dict[str, object] = {
        "gleif_ingest_report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_id": SOURCE_ID,
        "source_url": DOWNLOAD_URL,
        "terms_url": TERMS_URL,
        "evidence_file": evidence.name,
        "evidence_sha256": evidence_hash,
        "archive_bytes": evidence.stat().st_size,
        "uncompressed_csv_bytes": member.file_size,
        "configured_limit": limit,
        "scope": "FULL_ARCHIVE" if limit is None else "BOUNDED_NL_SAMPLE",
        "duration_seconds": round(time.monotonic() - started, 6),
        "counts": counts,
        "count_closure": {
            "nl_to_candidate_or_name_rejected": (
                "CLOSED"
                if counts["nl_records"]
                == counts["candidate_records"] + counts["missing_name_records"]
                else "OPEN"
            ),
            "nl_identifier_partition": (
                "CLOSED"
                if counts["nl_records"]
                == counts["valid_kvk_records"]
                + counts["missing_kvk_records"]
                + counts["invalid_kvk_records"]
                else "OPEN"
            ),
        },
        "status_semantics": "GLEIF_SOURCE_DATA_NOT_KVK_VERIFICATION",
    }
    return candidate_path, rejected_path, report


def _update_inventory(run: Run, report: dict[str, object]) -> None:
    rows = read_catalog(run, migrate=True)
    counts = report["counts"]
    assert isinstance(counts, dict)
    for row in rows:
        if row["source_id"] == SOURCE_ID:
            row["status"] = "COLLECTED"
            row["live_measurement_status"] = "MEASURED_LIVE_EVIDENCE"
            row["measured_count"] = str(counts["candidate_records"])
    updated = run.artifact_path("01", "sources_inventory_gleif_measured", "csv")
    write_tsv(updated, SOURCE_HEADERS, rows)
    run.register_artifact(updated, "01", "sources_inventory")


def collect_gleif(
    run: Run,
    archive: Path | None = None,
    limit: int | None = None,
    refresh: bool = False,
) -> tuple[Path, Path, Path, Path]:
    with run.lock():
        return _collect_gleif_unlocked(run, archive, limit, refresh)


def _collect_gleif_unlocked(
    run: Run,
    archive: Path | None,
    limit: int | None,
    refresh: bool,
) -> tuple[Path, Path, Path, Path]:
    """Download of importeer GLEIF evidence en verwerk die streaming."""
    if limit is not None and limit < 1:
        raise HarvestError("GLEIF-limiet moet positief zijn")
    if not run.latest_artifact("01", "sources_inventory"):
        from company_lookup.sources import discover

        discover(run)
    prior_source = run.latest_artifact("02", f"source_{SOURCE_ID}")
    prior_rejected = run.latest_artifact("02", "gleif_rejected")
    prior_json = run.latest_artifact("02", "gleif_ingest_report")
    prior_md = run.latest_artifact("02", "gleif_ingest_report_md")
    prior_evidence = run.latest_artifact("02", f"evidence_{SOURCE_ID}")
    config = run.metadata().get("runtime_config", {}).get("gleif_collect", {})
    archive_path = archive.expanduser().resolve() if archive else None
    if archive_path is not None and not archive_path.is_file():
        raise HarvestError("GLEIF-archief ontbreekt")
    archive_hash = sha256(archive_path) if archive_path else None
    same_input = (
        isinstance(config, dict)
        and archive_hash is not None
        and config.get("mode") == "local-archive"
        and config.get("input_sha256") == archive_hash
    )
    if (
        not refresh
        and all((prior_source, prior_rejected, prior_json, prior_md, prior_evidence))
        and prior_evidence is not None
        and prior_evidence.is_file()
        and ((archive is None and config.get("mode") == "download") or same_input)
        and config.get("limit") == limit
    ):
        assert prior_source and prior_rejected and prior_json and prior_md
        run.log("INFO", "gleif_collect_reused", evidence_sha256=config.get("evidence_sha256"))
        return prior_source, prior_rejected, prior_json, prior_md

    response_metadata: dict[str, object] | None = None
    if archive is None:
        evidence, response_metadata = _download_evidence(run)
        evidence_hash = sha256(evidence)
        mode = "download"
    else:
        if archive_hash is None:
            raise HarvestError("GLEIF-archief ontbreekt")
        evidence = _copy_evidence(run, archive, archive_hash)
        evidence_hash = archive_hash
        mode = "local-archive"
    run.register_artifact(evidence, "02", f"evidence_{SOURCE_ID}")
    try:
        candidate_path, rejected_path, report = _parse_archive(
            run, evidence, evidence_hash, limit
        )
    except HarvestError:
        raise
    except (csv.Error, UnicodeError, OSError, RuntimeError, sqlite3.Error, zipfile.BadZipFile) as exc:
        raise HarvestError(f"GLEIF-verwerking mislukt: {type(exc).__name__}") from exc
    run.invalidate_from(3, "gleif_collection_changed")
    report["acquisition"] = response_metadata or {
        "mode": "local-archive",
        "input_sha256": archive_hash,
        "user_agent": None,
    }
    report["candidate_artifact"] = {
        "path": str(candidate_path.relative_to(run.path)),
        "sha256": sha256(candidate_path),
        "size": candidate_path.stat().st_size,
    }
    json_path = run.artifact_path("02", "gleif_ingest_report", "json")
    atomic_write(json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    counts = report["counts"]
    assert isinstance(counts, dict)
    lines = [
        "# GLEIF-inname",
        "",
        f"- Scope: `{report['scope']}`",
        f"- Evidence SHA-256: `{evidence_hash}`",
        f"- Nederlandse records: {counts['nl_records']}",
        f"- Kandidaten: {counts['candidate_records']}",
        f"- Geldig/uniek KVK: {counts['valid_kvk_records']} / {counts['unique_valid_kvk']}",
        f"- Ontbrekend/ongeldig KVK: {counts['missing_kvk_records']} / {counts['invalid_kvk_records']}",
        f"- Reviewrecords: {counts['identifier_review_records']}",
        "",
        "GLEIF-rechtsvorm en -status blijven brondata en zijn geen actuele KVK-verificatie.",
        "",
    ]
    md_path = run.artifact_path("02", "gleif_ingest_report", "md")
    atomic_write(md_path, "\n".join(lines))
    run.register_artifact_set(
        [
            (candidate_path, "02", f"source_{SOURCE_ID}", "COMPLETE"),
            (rejected_path, "02", "gleif_rejected", "COMPLETE"),
            (json_path, "02", "gleif_ingest_report", "COMPLETE"),
            (md_path, "02", "gleif_ingest_report_md", "COMPLETE"),
        ]
    )
    run.record_config(
        "gleif_collect",
        {
            "mode": mode,
            "input_sha256": archive_hash,
            "evidence_sha256": evidence_hash,
            "limit": limit,
            "report_schema": REPORT_SCHEMA_VERSION,
            "download": response_metadata,
        },
    )
    _update_inventory(run, report)
    run.log(
        "INFO",
        "gleif_collect_completed",
        candidates=counts["candidate_records"],
        rejected=counts["identifier_review_records"],
        evidence_sha256=evidence_hash,
    )
    run.update_status("IN_PROGRESS", "02")
    return candidate_path, rejected_path, json_path, md_path
