"""Begrensde publieke broncatalogus en extractie."""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from company_harvest.core import HarvestError, Run, timestamp, validate_kvk, write_tsv

MAX_RESPONSE_BYTES = 20 * 1024 * 1024
ALLOWED_HOSTS = {"ind.nl", "www.wikidata.org", "query.wikidata.org"}


@dataclass(frozen=True)
class Source:
    source_id: str
    name: str
    owner: str
    url: str
    parser: str
    terms_url: str
    bias: str


CATALOG = (
    Source(
        "ind_arbeid",
        "Openbaar register Arbeid",
        "IND",
        "https://ind.nl/nl/openbaar-register-erkende-referenten/openbaar-register-arbeid",
        "ind_html_table_v1",
        "https://ind.nl/nl/copyright",
        "Erkende referenten voor arbeid; geen sectorbrede populatie.",
    ),
    Source(
        "wikidata_nl_companies",
        "Wikidata Nederlandse organisaties",
        "Wikimedia community",
        "https://query.wikidata.org/sparql",
        "wikidata_sparql_v1",
        "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use",
        "Vrijwillig samengestelde kennisbank; dekking en actualiteit variëren.",
    ),
)

SOURCE_HEADERS = [
    "source_id", "name", "owner", "url", "parser", "discovered_at", "terms_url",
    "status", "bias", "measured_count",
]
RAW_HEADERS = [
    "original_name", "country", "nl_evidence", "employees_raw", "employees_date",
    "employees_scope", "website", "sector", "source_kvk_hint", "source_id", "source_url",
    "fetched_at", "source_row", "evidence_reference",
]


def discover(run: Run) -> tuple[Path, Path]:
    now = datetime.now(UTC).isoformat()
    rows = [
        {
            "source_id": source.source_id, "name": source.name, "owner": source.owner,
            "url": source.url, "parser": source.parser, "discovered_at": now,
            "terms_url": source.terms_url, "status": "CONFIGURED_NOT_COLLECTED",
            "bias": source.bias, "measured_count": "",
        }
        for source in CATALOG
    ]
    csv_path = run.artifact_path("01", "sources_inventory", "csv")
    md_path = run.artifact_path("01", "sources_report", "md")
    write_tsv(csv_path, SOURCE_HEADERS, rows)
    report = "# Bronneninventaris\n\n" + "\n".join(
        f"- **{row['name']}** (`{row['source_id']}`): {row['status']}. Bias: {row['bias']}"
        for row in rows
    ) + "\n\nAantallen blijven onbekend totdat de bron werkelijk is verzameld.\n"
    md_path.write_text(report, encoding="utf-8")
    run.register_artifact(csv_path, "01", "sources_inventory")
    run.register_artifact(md_path, "01", "sources_report")
    run.log("INFO", "sources_discovered", count=len(rows))
    run.update_status("IN_PROGRESS", "01")
    return csv_path, md_path


def _bounded_get(client: httpx.Client, url: str) -> httpx.Response:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise HarvestError(f"bronhost niet toegestaan: {parsed.hostname}")
    response = client.get(url)
    response.raise_for_status()
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise HarvestError("bronresponse overschrijdt de maximale grootte")
    if response.url.host not in ALLOWED_HOSTS:
        raise HarvestError("bronredirect naar niet-toegestane host")
    return response


def parse_ind_html(content: str, source_url: str, limit: int | None = None) -> list[dict[str, str]]:
    text = re.sub(r"<[^>]+>", "\n", content)
    text = html.unescape(text)
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    rows: list[dict[str, str]] = []
    for index, line in enumerate(lines):
        inline = re.search(r"(.+?)\s+([0-9]{8})$", line)
        if inline:
            name, number = inline.groups()
        elif re.fullmatch(r"[0-9]{8}", line) and index:
            name, number = lines[index - 1], line
        else:
            continue
        try:
            kvk = validate_kvk(number)
        except ValueError:
            continue
        rows.append(_raw_row(name, kvk, "ind_arbeid", source_url, str(index + 1)))
        if limit and len(rows) >= limit:
            break
    if not rows:
        raise HarvestError("IND-parser vond onverwacht nul records", 5)
    return rows


def _raw_row(name: str, kvk: str, source_id: str, url: str, row: str) -> dict[str, str]:
    clean_name = re.sub(r'""([^\n]+?)""', r'"\1"', name.strip())
    return {
        "original_name": clean_name, "country": "Nederland",
        "nl_evidence": "Publiek Nederlands register", "employees_raw": "",
        "employees_date": "", "employees_scope": "", "website": "", "sector": "",
        "source_kvk_hint": kvk, "source_id": source_id, "source_url": url,
        "fetched_at": datetime.now(UTC).isoformat(), "source_row": row,
        "evidence_reference": url,
    }


def parse_wikidata(payload: dict[str, object], source_url: str, limit: int | None = None) -> list[dict[str, str]]:
    results = payload.get("results")
    bindings = results.get("bindings", []) if isinstance(results, dict) else []
    rows: list[dict[str, str]] = []
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            continue
        label = binding.get("orgLabel", {})
        kvk_cell = binding.get("kvk", {})
        name = label.get("value", "") if isinstance(label, dict) else ""
        kvk = kvk_cell.get("value", "") if isinstance(kvk_cell, dict) else ""
        try:
            number = validate_kvk(kvk)
        except ValueError:
            continue
        rows.append(_raw_row(str(name), number, "wikidata_nl_companies", source_url, str(index + 1)))
        if limit and len(rows) >= limit:
            break
    return rows


def _enabled(only: Iterable[str], skip: Iterable[str]) -> list[Source]:
    only_set, skip_set = set(only), set(skip)
    known = {source.source_id for source in CATALOG}
    unknown = (only_set | skip_set) - known
    if unknown:
        raise HarvestError(f"onbekende source-id(s): {', '.join(sorted(unknown))}")
    return [source for source in CATALOG if (not only_set or source.source_id in only_set) and source.source_id not in skip_set]


def collect(run: Run, only: Iterable[str] = (), skip: Iterable[str] = (), limit: int | None = None) -> list[Path]:
    outputs: list[Path] = []
    timeout = httpx.Timeout(20, connect=10, read=20, write=10, pool=10)
    headers = {"User-Agent": "company-harvest/0.1 (+local audited collection)"}
    with httpx.Client(timeout=timeout, follow_redirects=True, max_redirects=3, headers=headers) as client:
        for source in _enabled(only, skip):
            run.log("INFO", "source_collect_started", source_id=source.source_id)
            if source.source_id == "ind_arbeid":
                response = _bounded_get(client, source.url)
                snapshot = run.path / "evidence" / f"{timestamp()}_02_ind_arbeid_source.html"
                snapshot.write_bytes(response.content)
                rows = parse_ind_html(response.text, str(response.url), limit)
            else:
                query = "SELECT ?org ?orgLabel ?kvk WHERE {?org wdt:P31/wdt:P279* wd:Q4830453; wdt:P17 wd:Q55; wdt:P3821 ?kvk. SERVICE wikibase:label { bd:serviceParam wikibase:language 'nl,en'. }} ORDER BY ?orgLabel LIMIT 100"
                response = client.get(source.url, params={"query": query, "format": "json"})
                response.raise_for_status()
                if len(response.content) > MAX_RESPONSE_BYTES:
                    raise HarvestError("Wikidata-response overschrijdt de maximale grootte")
                snapshot = run.path / "evidence" / f"{timestamp()}_02_wikidata_source.json"
                snapshot.write_bytes(response.content)
                rows = parse_wikidata(response.json(), str(response.url), limit)
            path = run.artifact_path("02", f"source_{source.source_id}_companies", "csv")
            rows.sort(key=lambda row: (row["original_name"].casefold(), row["source_kvk_hint"]))
            write_tsv(path, RAW_HEADERS, rows)
            run.register_artifact(path, "02", f"source_{source.source_id}")
            run.log("INFO", "source_collect_completed", source_id=source.source_id, count=len(rows), evidence_sha256=_hash(snapshot))
            outputs.append(path)
    run.update_status("IN_PROGRESS", "02")
    return outputs


def _hash(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def list_sources(run: Run) -> list[dict[str, str]]:
    path = run.latest_artifact("01", "sources_inventory")
    if not path:
        raise HarvestError("voer eerst sources discover uit")
    from company_harvest.core import read_tsv

    return read_tsv(path)
