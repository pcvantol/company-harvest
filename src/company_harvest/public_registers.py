"""Streaming adapters for the public ANBI and DUO register snapshots."""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import time
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any
from urllib.parse import urljoin, urlparse

import httpx
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from company_harvest.core import (
    HTTP_USER_AGENT,
    HarvestError,
    Run,
    atomic_write,
    sha256,
    timestamp,
    validate_kvk,
)
from company_harvest.sources import RAW_HEADERS, SOURCE_HEADERS, read_catalog

MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_COMPRESSION_RATIO = 25.0
MIN_OUTPUT_RESERVE_BYTES = 64 * 1024 * 1024
MAX_DOWNLOAD_SECONDS = 10 * 60
MAX_REDIRECTS = 3
REPORT_SCHEMA_VERSION = 1
REJECTED_HEADERS = [
    "source_row",
    "original_name",
    "source_registration_raw",
    "registration_validation_status",
    "rejection_reason",
    "raw_record_json",
]
DUO_REQUIRED_COLUMNS = {
    "NAAM_VOLLEDIG",
    "NAAM_PLAATS_VEST",
    "INTERNET",
    "KVK_NR",
    "CODE_STAND_RECORD",
    "IND_OPGEHEVEN",
}


@dataclass(frozen=True)
class RegisterSpec:
    source_id: str
    name: str
    download_url: str
    terms_url: str
    allowed_hosts: frozenset[str]
    member_kind: str


ANBI = RegisterSpec(
    "anbi_register",
    "ANBI Open Data",
    "https://download.belastingdienst.nl/data/anbi/anbi.zip",
    "https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/themaoverstijgend/"
    "brochures_en_publicaties/open_data_anbi",
    frozenset({"download.belastingdienst.nl"}),
    "anbi_xml",
)
DUO = RegisterSpec(
    "duo_education_organisations",
    "DUO Basisgegevens instellingen",
    "https://duo.nl/open_onderwijsdata/images/basisgegevens-instellingen.zip",
    "https://duo.nl/open_onderwijsdata/onderwijs-algemeen/basisgegevens/"
    "basisgegevens-instellingen.jsp",
    frozenset({"duo.nl", "www.duo.nl"}),
    "duo_csv",
)
SPECS = {spec.source_id: spec for spec in (ANBI, DUO)}


def _member_for(spec: RegisterSpec, members: list[zipfile.ZipInfo]) -> zipfile.ZipInfo:
    if spec.member_kind == "anbi_xml":
        matches = [item for item in members if item.filename.casefold() == "anbi.xml"]
    else:
        matches = [
            item
            for item in members
            if item.filename.startswith("ORGANISATIES_") and item.filename.endswith(".csv")
        ]
    if len(matches) != 1:
        raise HarvestError(f"{spec.name}-ZIP bevat niet exact één verwacht databestand")
    return matches[0]


def _safe_archive(path: Path, spec: RegisterSpec) -> zipfile.ZipInfo:
    if not path.is_file():
        raise HarvestError(f"{spec.name}-archief ontbreekt")
    size = path.stat().st_size
    if size <= 0 or size > MAX_ARCHIVE_BYTES:
        raise HarvestError(f"{spec.name}-archief overschrijdt de groottegate")
    try:
        with zipfile.ZipFile(path) as bundle:
            members = [item for item in bundle.infolist() if not item.is_dir()]
    except zipfile.BadZipFile as exc:
        raise HarvestError(f"{spec.name}-archief is geen geldige ZIP") from exc
    if not members:
        raise HarvestError(f"{spec.name}-ZIP bevat geen bestanden")
    total = 0
    for member in members:
        if Path(member.filename).name != member.filename:
            raise HarvestError(f"{spec.name}-ZIP bevat een onveilig bestandspad")
        if member.flag_bits & 0x1:
            raise HarvestError(f"{spec.name}-ZIP mag niet versleuteld zijn")
        total += member.file_size
        if member.file_size / max(member.compress_size, 1) > MAX_COMPRESSION_RATIO:
            raise HarvestError(f"{spec.name}-ZIP overschrijdt de compressieratiogate")
    if total <= 0 or total > MAX_UNCOMPRESSED_BYTES:
        raise HarvestError(f"{spec.name}-ZIP overschrijdt de ongecomprimeerde groottegate")
    return _member_for(spec, members)


def _require_space(destination: Path, required: int, name: str) -> None:
    free = shutil.disk_usage(destination).free
    if free < required:
        raise HarvestError(
            f"onvoldoende vrije schijfruimte voor {name}: vereist {required}, beschikbaar {free}"
        )


def _validate_url(url: str, spec: RegisterSpec) -> None:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise HarvestError(f"{spec.name}-redirect naar niet-toegestane host") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in spec.allowed_hosts
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise HarvestError(f"{spec.name}-redirect naar niet-toegestane host")


def _content_length(headers: Any, spec: RegisterSpec) -> int | None:
    value = headers.get("content-length")
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HarvestError(f"{spec.name}-download heeft een ongeldige Content-Length") from exc


def _download_evidence(run: Run, spec: RegisterSpec) -> tuple[Path, dict[str, object]]:
    _require_space(run.path, 2 * MAX_ARCHIVE_BYTES + MIN_OUTPUT_RESERVE_BYTES, spec.name)
    destination = run.path / "evidence" / f"{timestamp()}_02_{spec.source_id}.zip"
    temporary = destination.with_name(f".{destination.name}.tmp")
    downloaded = 0
    started = time.monotonic()
    metadata: dict[str, object] = {}
    timeout = httpx.Timeout(120, connect=15, read=120, write=15, pool=15)
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": HTTP_USER_AGENT},
        ) as client:
            current_url = spec.download_url
            for redirect_count in range(MAX_REDIRECTS + 1):
                _validate_url(current_url, spec)
                with client.stream("GET", current_url) as response:
                    response_url = str(response.url)
                    _validate_url(response_url, spec)
                    if 300 <= response.status_code < 400:
                        location = response.headers.get("location")
                        if not location or redirect_count >= MAX_REDIRECTS:
                            raise HarvestError(f"{spec.name}-download overschrijdt de redirectgate")
                        current_url = urljoin(response_url, location)
                        _validate_url(current_url, spec)
                        continue
                    length = _content_length(response.headers, spec)
                    if length is not None and length > MAX_ARCHIVE_BYTES:
                        raise HarvestError(f"{spec.name}-download overschrijdt de groottegate")
                    metadata = {
                        "http_status": response.status_code,
                        "final_url": response_url,
                        "redirect_count": redirect_count,
                        "content_length": length,
                        "last_modified": response.headers.get("last-modified"),
                        "user_agent": HTTP_USER_AGENT,
                    }
                    response.raise_for_status()
                    with temporary.open("wb") as handle:
                        for chunk in response.iter_bytes(1024 * 1024):
                            if time.monotonic() - started > MAX_DOWNLOAD_SECONDS:
                                raise HarvestError(f"{spec.name}-download overschrijdt de tijdgate")
                            downloaded += len(chunk)
                            if downloaded > MAX_ARCHIVE_BYTES:
                                raise HarvestError(f"{spec.name}-download overschrijdt de groottegate")
                            handle.write(chunk)
                        handle.flush()
                        os.fsync(handle.fileno())
                    break
        os.replace(temporary, destination)
    except httpx.HTTPStatusError as exc:
        raise HarvestError(
            f"{spec.name}-download stopte met HTTP {exc.response.status_code}; "
            "geen fallback uitgevoerd"
        ) from exc
    except httpx.HTTPError as exc:
        raise HarvestError(f"{spec.name}-download mislukt: {type(exc).__name__}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    metadata["downloaded_bytes"] = downloaded
    return destination, metadata


def _copy_evidence(run: Run, source: Path, spec: RegisterSpec, expected_hash: str) -> Path:
    source = source.expanduser().resolve()
    _safe_archive(source, spec)
    _require_space(
        run.path,
        source.stat().st_size + MAX_UNCOMPRESSED_BYTES + MIN_OUTPUT_RESERVE_BYTES,
        spec.name,
    )
    destination = run.path / "evidence" / f"{timestamp()}_02_{spec.source_id}.zip"
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        shutil.copyfile(source, temporary)
        if sha256(temporary) != expected_hash:
            raise HarvestError(f"{spec.name}-evidencekopie heeft een afwijkende SHA-256")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _anbi_rows(binary: IO[bytes]) -> Iterator[tuple[int, dict[str, str]]]:
    row_number = 0
    for _event, element in ET.iterparse(binary, events=("end",)):
        if _local_tag(element.tag) != "beschikking":
            continue
        row_number += 1
        yield row_number, {
            _local_tag(child.tag): (child.text or "").strip() for child in element
        }
        element.clear()


def _duo_rows(binary: IO[bytes]) -> Iterator[tuple[int, dict[str, str]]]:
    text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
    reader = csv.DictReader(text)
    missing = DUO_REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise HarvestError("DUO-CSV mist verplichte kolommen: " + ", ".join(sorted(missing)))
    for row_number, row in enumerate(reader, 2):
        yield row_number, {key: value or "" for key, value in row.items()}


def _candidate(
    spec: RegisterSpec,
    row: dict[str, str],
    row_number: int,
    evidence_name: str,
    fetched_at: str,
) -> tuple[dict[str, str] | None, dict[str, str] | None, str, bool]:
    if spec is ANBI:
        name = row.get("naam", "").strip()
        registration = row.get("fiscaalNummer", "").strip()
        reasons = [
            "NON_KVK_FISCAL_IDENTIFIER"
            if registration
            else "MISSING_DIRECT_REGISTRATION_IDENTIFIER"
        ]
        current = True
        number = ""
        validation = "MISSING"
        website = row.get("webSite", "").strip()
        place = row.get("vestigingsPlaats", "").strip()
        # De publicatie bevat een ingangsdatum, maar geen expliciete actuele status.
        # Die datum blijft in het ruwe evidence-record en wordt niet als status vermomd.
        source_status = ""
        nl_evidence = "Belastingdienst ANBI-register" + (f"; plaats={place}" if place else "")
        sector = "algemeen nut beogende instelling"
    else:
        name = row.get("NAAM_VOLLEDIG", "").strip()
        registration = row.get("KVK_NR", "").strip()
        current = row.get("CODE_STAND_RECORD", "").strip() == "A"
        reasons = [] if current else ["NON_CURRENT_SOURCE_RECORD"]
        number = ""
        if registration:
            try:
                number = validate_kvk(registration)
                validation = "VALID"
            except ValueError:
                validation = "INVALID"
                if current:
                    reasons.append("INVALID_KVK")
        else:
            validation = "MISSING"
            if current:
                reasons.append("MISSING_KVK")
        website = row.get("INTERNET", "").strip()
        place = row.get("NAAM_PLAATS_VEST", "").strip()
        source_status = (
            f"record={row.get('CODE_STAND_RECORD', '').strip()};"
            f"opgeheven={row.get('IND_OPGEHEVEN', '').strip()}"
        )
        nl_evidence = "DUO Basisgegevens instellingen" + (f"; plaats={place}" if place else "")
        sector = "onderwijs"
    if not name:
        reasons.append("MISSING_LEGAL_NAME")
    rejected = None
    if reasons:
        rejected = {
            "source_row": str(row_number),
            "original_name": name,
            "source_registration_raw": registration,
            "registration_validation_status": validation,
            "rejection_reason": "|".join(reasons),
            "raw_record_json": json.dumps(row, ensure_ascii=False, separators=(",", ":")),
        }
    if not name or not current:
        return None, rejected, validation, current
    return (
        {
            "original_name": name,
            "country": "Nederland" if spec is DUO else "",
            "nl_evidence": nl_evidence,
            "employees_raw": "",
            "employees_date": "",
            "employees_scope": "",
            "website": website,
            "sector": sector,
            "source_kvk_hint": number,
            "source_id": spec.source_id,
            "source_url": spec.download_url,
            "fetched_at": fetched_at,
            "source_row": str(row_number),
            "evidence_reference": evidence_name,
            "source_registration_raw": registration,
            "registration_validation_status": validation,
            "source_legal_form": "",
            "source_status": source_status,
            "candidate_layer": "raw",
        },
        rejected,
        validation,
        current,
    )


def _parse_archive(
    run: Run,
    evidence: Path,
    evidence_hash: str,
    spec: RegisterSpec,
    limit: int | None,
) -> tuple[Path, Path, dict[str, object]]:
    if limit is not None and limit < 1:
        raise HarvestError(f"{spec.name}-limiet moet positief zijn")
    member = _safe_archive(evidence, spec)
    candidate_path = run.artifact_path("02", f"source_{spec.source_id}_companies", "csv")
    rejected_path = run.artifact_path("02", f"source_{spec.source_id}_rejected", "csv")
    candidate_temp = candidate_path.with_name(f".{candidate_path.name}.tmp")
    rejected_temp = rejected_path.with_name(f".{rejected_path.name}.tmp")
    fetched_at = datetime.now(UTC).isoformat()
    started = time.monotonic()
    counts = {
        "all_records_seen": 0,
        "current_records": 0,
        "non_current_records": 0,
        "candidate_records": 0,
        "missing_name_records": 0,
        "valid_kvk_records": 0,
        "missing_kvk_records": 0,
        "invalid_kvk_records": 0,
        "review_records": 0,
        "records_with_source_identifier": 0,
        "records_without_source_identifier": 0,
    }
    unique_kvk: set[str] = set()
    try:
        with (
            candidate_temp.open("w", encoding="utf-8", newline="") as candidate_handle,
            rejected_temp.open("w", encoding="utf-8", newline="") as rejected_handle,
            zipfile.ZipFile(evidence) as bundle,
            bundle.open(member) as binary,
        ):
            candidate_writer = csv.DictWriter(
                candidate_handle, fieldnames=RAW_HEADERS, delimiter="\t", extrasaction="ignore"
            )
            rejected_writer = csv.DictWriter(
                rejected_handle,
                fieldnames=REJECTED_HEADERS,
                delimiter="\t",
                extrasaction="ignore",
            )
            candidate_writer.writeheader()
            rejected_writer.writeheader()
            rows = _anbi_rows(binary) if spec is ANBI else _duo_rows(binary)
            for row_number, row in rows:
                if limit is not None and counts["current_records"] >= limit:
                    break
                counts["all_records_seen"] += 1
                candidate, rejected, validation, current = _candidate(
                    spec, row, row_number, evidence.name, fetched_at
                )
                if current:
                    counts["current_records"] += 1
                    registration_key = "fiscaalNummer" if spec is ANBI else "KVK_NR"
                    if row.get(registration_key, "").strip():
                        counts["records_with_source_identifier"] += 1
                    else:
                        counts["records_without_source_identifier"] += 1
                    counts[f"{validation.casefold()}_kvk_records"] += 1
                    if validation == "VALID":
                        registration_key = "fiscaalNummer" if spec is ANBI else "KVK_NR"
                        unique_kvk.add(validate_kvk(row.get(registration_key, "")))
                    if candidate:
                        candidate_writer.writerow(candidate)
                        counts["candidate_records"] += 1
                    else:
                        counts["missing_name_records"] += 1
                else:
                    counts["non_current_records"] += 1
                if rejected:
                    rejected_writer.writerow(rejected)
                    counts["review_records"] += 1
            candidate_handle.flush()
            os.fsync(candidate_handle.fileno())
            rejected_handle.flush()
            os.fsync(rejected_handle.fileno())
        os.replace(candidate_temp, candidate_path)
        os.replace(rejected_temp, rejected_path)
    finally:
        candidate_temp.unlink(missing_ok=True)
        rejected_temp.unlink(missing_ok=True)
    counts["unique_valid_kvk"] = len(unique_kvk)
    counts["duplicate_valid_kvk_records"] = counts["valid_kvk_records"] - len(unique_kvk)
    report: dict[str, object] = {
        "public_register_ingest_report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_id": spec.source_id,
        "source_url": spec.download_url,
        "terms_url": spec.terms_url,
        "evidence_file": evidence.name,
        "evidence_sha256": evidence_hash,
        "archive_bytes": evidence.stat().st_size,
        "uncompressed_data_bytes": member.file_size,
        "configured_limit": limit,
        "scope": "FULL_ARCHIVE" if limit is None else "BOUNDED_CURRENT_SAMPLE",
        "duration_seconds": round(time.monotonic() - started, 6),
        "counts": counts,
        "count_closure": {
            "seen_to_current_or_non_current": (
                "CLOSED"
                if counts["all_records_seen"]
                == counts["current_records"] + counts["non_current_records"]
                else "OPEN"
            ),
            "current_to_candidate_or_name_rejected": (
                "CLOSED"
                if counts["current_records"]
                == counts["candidate_records"] + counts["missing_name_records"]
                else "OPEN"
            ),
            "current_identifier_partition": (
                "CLOSED"
                if counts["current_records"]
                == counts["valid_kvk_records"]
                + counts["missing_kvk_records"]
                + counts["invalid_kvk_records"]
                else "OPEN"
            ),
        },
        "status_semantics": "SOURCE_DATA_NOT_KVK_VERIFICATION",
    }
    return candidate_path, rejected_path, report


def _update_inventory(run: Run, spec: RegisterSpec, report: dict[str, object]) -> None:
    rows = read_catalog(run, migrate=True)
    counts = report["counts"]
    assert isinstance(counts, dict)
    for row in rows:
        if row["source_id"] == spec.source_id:
            row["status"] = "COLLECTED"
            row["live_measurement_status"] = "MEASURED_LIVE_EVIDENCE"
            row["measured_count"] = str(counts["candidate_records"])
    path = run.artifact_path("01", f"sources_inventory_{spec.source_id}_measured", "csv")
    from company_harvest.core import write_tsv

    write_tsv(path, SOURCE_HEADERS, rows)
    run.register_artifact(path, "01", "sources_inventory")


def _outputs_are_reusable(
    run: Run,
    prior: dict[str, Path | None],
    kinds: dict[str, str],
    config: object,
) -> bool:
    """Require the exact configured output set and its registered hashes to remain intact."""
    if not isinstance(config, dict):
        return False
    expected_paths = config.get("output_paths")
    expected_hashes = config.get("output_sha256")
    if not isinstance(expected_paths, dict) or not isinstance(expected_hashes, dict):
        return False
    with run.connect() as connection:
        for key, kind in kinds.items():
            path = prior.get(key)
            if path is None or not path.is_file():
                return False
            relative = str(path.relative_to(run.path))
            row = connection.execute(
                "SELECT sha256, size FROM artifacts "
                "WHERE path=? AND step='02' AND kind=? AND status='COMPLETE'",
                (relative, kind),
            ).fetchone()
            if row is None or expected_paths.get(key) != relative:
                return False
            digest = sha256(path)
            if (
                expected_hashes.get(key) != digest
                or row["sha256"] != digest
                or row["size"] != path.stat().st_size
            ):
                return False
    return True


def collect_public_register(
    run: Run,
    source_id: str,
    archive: Path | None = None,
    limit: int | None = None,
    refresh: bool = False,
) -> tuple[Path, Path, Path, Path]:
    with run.lock():
        return _collect_public_register_unlocked(run, source_id, archive, limit, refresh)


def _collect_public_register_unlocked(
    run: Run,
    source_id: str,
    archive: Path | None,
    limit: int | None,
    refresh: bool,
) -> tuple[Path, Path, Path, Path]:
    """Download or import one public register snapshot and preserve every selected candidate."""
    try:
        spec = SPECS[source_id]
    except KeyError as exc:
        raise HarvestError(f"onbekend publiek register: {source_id}") from exc
    if limit is not None and limit < 1:
        raise HarvestError(f"{spec.name}-limiet moet positief zijn")
    if not run.latest_artifact("01", "sources_inventory"):
        from company_harvest.sources import discover

        discover(run)
    kinds = {
        "source": f"source_{source_id}",
        "rejected": f"{source_id}_rejected",
        "json": f"{source_id}_ingest_report",
        "md": f"{source_id}_ingest_report_md",
        "evidence": f"evidence_{source_id}",
    }
    prior = {key: run.latest_artifact("02", kind) for key, kind in kinds.items()}
    config_key = f"{source_id}_collect"
    config = run.metadata().get("runtime_config", {}).get(config_key, {})
    archive_path = archive.expanduser().resolve() if archive else None
    if archive_path is not None and not archive_path.is_file():
        raise HarvestError(f"{spec.name}-archief ontbreekt")
    archive_hash = sha256(archive_path) if archive_path else None
    same_input = (
        isinstance(config, dict)
        and archive_hash is not None
        and config.get("mode") == "local-archive"
        and config.get("input_sha256") == archive_hash
    )
    if (
        not refresh
        and _outputs_are_reusable(run, prior, kinds, config)
        and ((archive is None and config.get("mode") == "download") or same_input)
        and config.get("limit") == limit
    ):
        run.log("INFO", f"{source_id}_collect_reused", evidence_sha256=config.get("evidence_sha256"))
        return prior["source"], prior["rejected"], prior["json"], prior["md"]  # type: ignore[return-value]

    response_metadata: dict[str, object] | None = None
    if archive is None:
        evidence, response_metadata = _download_evidence(run, spec)
        evidence_hash = sha256(evidence)
        mode = "download"
    else:
        assert archive_hash is not None
        evidence = _copy_evidence(run, archive, spec, archive_hash)
        evidence_hash = archive_hash
        mode = "local-archive"
    try:
        candidate_path, rejected_path, report = _parse_archive(
            run, evidence, evidence_hash, spec, limit
        )
    except HarvestError:
        raise
    except (
        csv.Error,
        ET.ParseError,
        DefusedXmlException,
        UnicodeError,
        OSError,
        RuntimeError,
        zipfile.BadZipFile,
    ) as exc:
        raise HarvestError(f"{spec.name}-verwerking mislukt: {type(exc).__name__}") from exc
    run.invalidate_from(3, f"{source_id}_collection_changed")
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
    json_path = run.artifact_path("02", f"{source_id}_ingest_report", "json")
    atomic_write(json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    counts = report["counts"]
    assert isinstance(counts, dict)
    md_path = run.artifact_path("02", f"{source_id}_ingest_report", "md")
    atomic_write(
        md_path,
        "\n".join(
            [
                f"# {spec.name}-inname",
                "",
                f"- Scope: `{report['scope']}`",
                f"- Evidence SHA-256: `{evidence_hash}`",
                f"- Bronrecords gezien: {counts['all_records_seen']}",
                f"- Huidige records: {counts['current_records']}",
                f"- Kandidaten: {counts['candidate_records']}",
                f"- Geldig/uniek KVK: {counts['valid_kvk_records']} / {counts['unique_valid_kvk']}",
                f"- Ontbrekend/ongeldig KVK: {counts['missing_kvk_records']} / {counts['invalid_kvk_records']}",
                f"- Reviewrecords: {counts['review_records']}",
                "",
                "Bronstatus blijft brondata en is geen actuele KVK-verificatie.",
                "",
            ]
        ),
    )
    run.register_artifact_set(
        [
            (evidence, "02", kinds["evidence"], "COMPLETE"),
            (candidate_path, "02", kinds["source"], "COMPLETE"),
            (rejected_path, "02", kinds["rejected"], "COMPLETE"),
            (json_path, "02", kinds["json"], "COMPLETE"),
            (md_path, "02", kinds["md"], "COMPLETE"),
        ]
    )
    _update_inventory(run, spec, report)
    output_paths = {
        "source": candidate_path,
        "rejected": rejected_path,
        "json": json_path,
        "md": md_path,
        "evidence": evidence,
    }
    run.record_config(
        config_key,
        {
            "mode": mode,
            "input_sha256": archive_hash,
            "evidence_sha256": evidence_hash,
            "limit": limit,
            "report_schema": REPORT_SCHEMA_VERSION,
            "download": response_metadata,
            "output_paths": {
                key: str(path.relative_to(run.path)) for key, path in output_paths.items()
            },
            "output_sha256": {key: sha256(path) for key, path in output_paths.items()},
        },
    )
    run.log(
        "INFO",
        f"{source_id}_collect_completed",
        candidates=counts["candidate_records"],
        rejected=counts["review_records"],
        evidence_sha256=evidence_hash,
    )
    run.update_status("IN_PROGRESS", "02")
    return candidate_path, rejected_path, json_path, md_path
