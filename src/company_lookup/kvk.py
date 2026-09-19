"""Publieke KVK-providercontracten met gedeelde cooldown en herstelstate."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

import httpx

from company_lookup.core import (
    HTTP_USER_AGENT,
    HarvestError,
    Run,
    read_tsv,
    redact,
    timestamp,
    validate_kvk,
    write_tsv,
)

KVK_HOSTS = {"www.kvk.nl", "kvk.nl", "web-api.kvk.nl"}
PUBLIC_SEARCH_ENDPOINT = "https://web-api.kvk.nl/zoeken/v3/search"
PUBLIC_PROFILE_ID = "5C10A89D-635E-49CC-94B8-042DD533B64A"
UNRESOLVED_HEADERS = ["candidate_id", "original_name", "reason", "detail", "resumable", "checked_at"]


def _require_number_query(query: str) -> str:
    try:
        return validate_kvk(query)
    except ValueError as exc:
        raise KvkError("INVALID_KVK_QUERY", "publieke KVK-zoekopdracht vereist een achtcijferig bronnummer", 3) from exc


@dataclass(frozen=True)
class ProviderResult:
    query: str
    hits: list[dict[str, Any]]
    complete: bool
    transport: str
    evidence: str


class Provider(Protocol):
    name: str

    def preflight(self) -> dict[str, Any]: ...
    def search(self, query: str, headed: bool = False) -> ProviderResult: ...


class KvkError(HarvestError):
    def __init__(self, reason: str, message: str, exit_code: int = 5,
                 evidence: str | None = None) -> None:
        super().__init__(message, exit_code)
        self.reason = reason
        self.evidence = evidence


def retry_after(value: str | None, now: datetime | None = None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            reference = now or datetime.now(UTC)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return max(0.0, (parsed - reference).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class PublicHttpProvider:
    name = "public-http"

    def __init__(self, run: Run, endpoint: str | None = None,
                 max_pages: int = 20, page_interval: float = 0.0,
                 max_attempts: int = 3) -> None:
        self.run = run
        self.max_pages = max_pages
        self.page_interval = page_interval
        self.max_attempts = max_attempts
        self.last_error_evidence: str | None = None
        observed_endpoint, observed_parameter = self._observed_route()
        self.endpoint = endpoint or observed_endpoint or PUBLIC_SEARCH_ENDPOINT
        self.query_parameter = "q" if endpoint else observed_parameter or "q"

    def _observed_route(self) -> tuple[str | None, str | None]:
        capability = self.run.path / ".provider" / "kvk_observed_http.json"
        if capability.is_file():
            payload = json.loads(capability.read_text(encoding="utf-8"))
            endpoint, parameter = payload.get("endpoint"), payload.get("query_parameter")
            return (str(endpoint), str(parameter)) if endpoint and parameter else (None, None)
        return None, None

    def preflight(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "available": bool(self.endpoint and self.query_parameter),
            "endpoint": self.endpoint or "UNKNOWN_NOT_OBSERVED",
            "status": "IMPLEMENTED" if self.endpoint else "CAPABILITY_MISSING",
            "semantics": "Route en publieke profileId zijn op 2026-09-18 tijdens gewone frontendinteractie waargenomen.",
        }

    def search(self, query: str, headed: bool = False) -> ProviderResult:
        query = _require_number_query(query)
        del headed
        self.last_error_evidence = None
        if not self.endpoint or not self.query_parameter:
            raise KvkError("BROWSER_REQUIRED", "geen publieke HTTP-route waargenomen", 5)
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or parsed.hostname not in KVK_HOSTS:
            raise KvkError("CAPABILITY_MISSING", "waargenomen KVK-endpoint is niet toegestaan", 7)
        timeout = httpx.Timeout(20, connect=10, read=20, write=10, pool=10)
        headers = {"User-Agent": HTTP_USER_AGENT, "profileId": PUBLIC_PROFILE_ID}
        payloads: list[dict[str, Any]] = []
        hits: list[dict[str, Any]] = []
        start, total = 0, None
        with httpx.Client(timeout=timeout, follow_redirects=False, headers=headers) as client:
            for page in range(self.max_pages):
                if page and self.page_interval:
                    time.sleep(self.page_interval)
                params = {self.query_parameter: query, "language": "nl", "site": "kvk2014", "size": "10", "start": str(start)}
                response = self._get_with_retries(client, params)
                if response.status_code in {401, 403}:
                    raise KvkError("PUBLIC_ACCESS_BLOCKED", "publieke KVK-toegang geweigerd", 4, self.last_error_evidence)
                if response.status_code == 429:
                    self._cooldown(retry_after(response.headers.get("Retry-After")) or 300, "HTTP 429")
                    raise KvkError("RATE_LIMITED", "KVK-rate limit actief; hervat later", 4, self.last_error_evidence)
                if response.status_code >= 500:
                    raise KvkError("NETWORK_ERROR", f"tijdelijke KVK-serverfout {response.status_code}")
                try:
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    raise KvkError("PUBLIC_ACCESS_BLOCKED", f"KVK HTTP-fout: {exc}", 4, self.last_error_evidence) from exc
                try:
                    payload = response.json()
                except ValueError as exc:
                    self._save_error_evidence(response.status_code, response.content, response.headers)
                    raise KvkError("PARSING_ERROR", "KVK-response is geen geldige JSON", evidence=self.last_error_evidence) from exc
                if not isinstance(payload, dict):
                    self._save_error_evidence(response.status_code, response.content, response.headers)
                    raise KvkError("PARSING_ERROR", "onverwacht KVK-responseschema", evidence=self.last_error_evidence)
                payloads.append(payload)
                page_hits, page_total = _extract_public_search(payload)
                hits.extend(page_hits)
                total = page_total if total is None else total
                start += len(page_hits)
                if not page_hits or total is None or start >= total:
                    break
            # De bewaarde response toont bij een bereikt paginabudget expliciet
            # dat de zoekactie onvolledig is; geen automatische match volgt.
        evidence = self.run.path / "evidence" / f"{timestamp()}_04_kvk_http_response.json"
        evidence.write_text(json.dumps(payloads, ensure_ascii=False), encoding="utf-8")
        complete = total is not None and start >= total
        return ProviderResult(query, hits, complete, self.name, str(evidence.relative_to(self.run.path)))

    def _get_with_retries(self, client: httpx.Client, params: dict[str, str]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                with client.stream("GET", self.endpoint, params=params) as streamed:
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in streamed.iter_bytes(chunk_size=64 * 1024):
                        size += len(chunk)
                        if size > 5 * 1024 * 1024:
                            self._save_error_evidence(streamed.status_code, b"".join(chunks), streamed.headers, truncated=True)
                            raise KvkError("PARSING_ERROR", "KVK-response te groot", evidence=self.last_error_evidence)
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    response = httpx.Response(streamed.status_code, headers=streamed.headers,
                                              content=body, request=streamed.request)
                if response.status_code >= 400:
                    self._save_error_evidence(response.status_code, body, response.headers)
                if response.status_code < 500:
                    return response
                last_error = KvkError("NETWORK_ERROR", f"tijdelijke KVK-serverfout {response.status_code}")
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt < self.max_attempts - 1:
                time.sleep((2**attempt) + random.uniform(0, 0.25))
        raise KvkError("NETWORK_ERROR", f"KVK-netwerkfout na begrensde retries: {last_error}", evidence=self.last_error_evidence)

    def _save_error_evidence(self, status: int, body: bytes, headers: Any,
                             truncated: bool = False) -> None:
        evidence = self.run.path / "evidence" / f"{timestamp()}_04_kvk_http_error.json"
        payload = {"status": status, "body_sha256": hashlib.sha256(body).hexdigest(),
                   "captured_bytes": len(body), "truncated": truncated,
                   "body_preview": redact(body[:4096].decode("utf-8", errors="replace")),
                   "retry_after": headers.get("Retry-After")}
        evidence.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        self.run.register_artifact(evidence, "04", "evidence_public-http-error")
        self.last_error_evidence = str(evidence.relative_to(self.run.path))

    def _cooldown(self, seconds: float, reason: str) -> None:
        with self.run.connect() as connection:
            connection.execute(
                "INSERT INTO cooldowns(provider,until_epoch,reason) VALUES('kvk',?,?) "
                "ON CONFLICT(provider) DO UPDATE SET until_epoch=excluded.until_epoch,reason=excluded.reason",
                (time.time() + seconds, reason),
            )


class PublicBrowserProvider:
    name = "public-browser"

    def __init__(self, run: Run) -> None:
        self.run = run

    def preflight(self) -> dict[str, Any]:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                executable = playwright.chromium.executable_path
            available = Path(executable).exists()
        except Exception as exc:  # dependency of browser runtime can fail in multiple ways
            return {"provider": self.name, "available": False, "status": "BROWSER_UNAVAILABLE", "detail": str(exc)}
        return {"provider": self.name, "available": available, "status": "BROWSER_AVAILABLE_NOT_LIVE_PROVEN" if available else "BROWSER_UNAVAILABLE", "executable": executable}

    def search(self, query: str, headed: bool = False) -> ProviderResult:
        query = _require_number_query(query)
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright

        observed: list[dict[str, Any]] = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=not headed)
                context = browser.new_context(user_agent=HTTP_USER_AGENT)
                page = context.new_page()

                def capture(response: Any) -> None:
                    if response.request.resource_type in {"xhr", "fetch"} and "kvk.nl" in response.url:
                        try:
                            if "json" in response.headers.get("content-type", ""):
                                observed.append({"url": response.url, "status": response.status, "json": response.json()})
                        except Exception:
                            return

                page.on("response", capture)
                page.goto("https://www.kvk.nl/zoeken/", wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_load_state("networkidle", timeout=30_000)
                cookie_button = page.get_by_role("button", name="Alleen standaard cookies")
                if cookie_button.count() and cookie_button.first.is_visible():
                    cookie_button.first.click()
                field = page.locator("input[type='search']").first
                field.wait_for(state="visible", timeout=15_000)
                if field.count() == 0:
                    raise KvkError("PARSING_ERROR", "KVK-zoekveld niet gevonden; frontend gewijzigd")
                field.fill(query)
                page.get_by_role("button", name="Zoeken", exact=True).last.click()
                page.wait_for_load_state("networkidle", timeout=30_000)
                body = page.locator("body").inner_text(timeout=10_000)
                if "captcha" in body.casefold() or "robot" in body.casefold():
                    raise KvkError("PUBLIC_ACCESS_BLOCKED", "KVK-challenge gedetecteerd; geen omzeiling", 4)
                evidence = self.run.path / "evidence" / f"{timestamp()}_04_kvk_browser_dom.txt"
                evidence.write_text(body[:2_000_000], encoding="utf-8")
                browser.close()
        except KvkError:
            raise
        except PlaywrightError as exc:
            raise KvkError("BROWSER_UNAVAILABLE", f"browserfout: {exc}") from exc
        hits: list[dict[str, Any]] = []
        for item in observed:
            hits.extend(_extract_hits(item.get("json")))
        if not hits:
            hits = _extract_dom_hits(body)
        self._persist_observed_endpoint(observed, query)
        return ProviderResult(query, hits, True, self.name, str(evidence.relative_to(self.run.path)))

    def _persist_observed_endpoint(self, observed: list[dict[str, Any]], query: str) -> None:
        candidate = next((item["url"] for item in observed if _extract_hits(item.get("json"))), None)
        if not candidate:
            return
        parsed = urlparse(candidate)
        parameters = parse_qs(parsed.query)
        query_parameter = next((key for key, values in parameters.items() if query in values), None)
        if not query_parameter:
            return
        endpoint = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        folder = self.run.path / ".provider"
        folder.mkdir(exist_ok=True)
        (folder / "kvk_observed_http.json").write_text(
            json.dumps(
                {
                    "endpoint": endpoint,
                    "query_parameter": query_parameter,
                    "observed_at": datetime.now(UTC).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def _extract_hits(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = next((payload[key] for key in ("resultaten", "results", "items", "data") if isinstance(payload.get(key), list)), [])
    else:
        candidates = []
    return [dict(item) for item in candidates if isinstance(item, dict)]


def _extract_public_search(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int | None]:
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return [], None
    hits: list[dict[str, Any]] = []
    for item in data["items"]:
        if not isinstance(item, dict):
            continue
        raw_location = item.get("bezoeklocatie")
        location: dict[str, Any] = raw_location if isinstance(raw_location, dict) else {}
        hits.append({
            **item,
            "rechtsvorm": item.get("rechtsvormOmschrijving", ""),
            "status": "Actief" if item.get("actief") is True else "Inactief" if item.get("actief") is False else "",
            "plaats": location.get("plaats", ""),
            "land": "Nederland" if location.get("plaats") else "",
        })
    total = data.get("numberOfHits")
    return hits, int(total) if isinstance(total, int) else None


def _extract_dom_hits(body: str) -> list[dict[str, Any]]:
    """Lees uitsluitend expliciet zichtbare velden uit de gewone resultatenpagina."""
    hits: list[dict[str, Any]] = []
    for match in re.finditer(r"(?m)^([^\n]+)\nKVK-nummer: ([0-9]{8})\n([^\n]+)$", body):
        name, number, legal_form = match.groups()
        tail = body[match.end() : match.end() + 1000]
        city_match = re.search(r"\b[0-9]{4}[A-Z]{2}\s+([^\n]+)", tail)
        hits.append(
            {
                "naam": name.strip(),
                "kvkNummer": number,
                "rechtsvorm": legal_form.strip(),
                "plaats": city_match.group(1).strip() if city_match else "",
                "land": "Nederland" if city_match else "",
                "status": "",
                "public_dom_fields": True,
            }
        )
    return hits


def preflight(run: Run, provider_name: str) -> Path:
    providers: list[Provider] = [PublicHttpProvider(run), PublicBrowserProvider(run)]
    selected = providers if provider_name == "auto" else [p for p in providers if p.name == provider_name]
    if not selected:
        raise HarvestError(f"onbekende KVK-provider: {provider_name}")
    results = [provider.preflight() for provider in selected]
    path = run.artifact_path("04", "kvk_capability_preflight", "md")
    lines = ["# KVK capabilitypreflight", "", f"Tijd: {datetime.now(UTC).isoformat()}", ""]
    for result in results:
        lines.append(f"- `{result['provider']}`: **{result['status']}** — `{json.dumps(result, ensure_ascii=False)}`")
    lines.extend(["", "Onbekende velden worden niet afgeleid. Een succesvolle paginalaadtest bewijst geen bulktoestemming.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    run.register_artifact(path, "04", "kvk_preflight")
    return path


def _choose_provider(run: Run, name: str) -> Provider:
    if name == "public-http":
        return PublicHttpProvider(run)
    if name == "public-browser":
        return PublicBrowserProvider(run)
    if name != "auto":
        raise HarvestError(f"onbekende KVK-provider: {name}")
    http = PublicHttpProvider(run)
    if http.preflight()["available"]:
        return http
    browser = PublicBrowserProvider(run)
    if browser.preflight()["available"]:
        return browser
    raise HarvestError("geen publieke KVK-transportweg beschikbaar", 4)


class AutoProvider:
    name = "auto"

    def __init__(self, run: Run) -> None:
        self.http = PublicHttpProvider(run)
        self.browser = PublicBrowserProvider(run)

    def preflight(self) -> dict[str, Any]:
        return {"provider": "auto", "http": self.http.preflight(), "browser": self.browser.preflight()}

    def search(self, query: str, headed: bool = False) -> ProviderResult:
        query = _require_number_query(query)
        if self.http.preflight()["available"]:
            try:
                return self.http.search(query)
            except KvkError as exc:
                if exc.reason not in {"NETWORK_ERROR", "PARSING_ERROR", "BROWSER_REQUIRED"}:
                    raise
        return self.browser.search(query, headed=headed)


def _provider_for_run(run: Run, name: str) -> Provider:
    return AutoProvider(run) if name == "auto" else _choose_provider(run, name)


class ProviderLock:
    def __init__(self, run: Run) -> None:
        self.path = run.path.parent.parent / ".local" / "kvk-provider.lock"
        self.descriptor: int | None = None

    def __enter__(self) -> ProviderLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                owner = json.loads(self.path.read_text(encoding="utf-8"))
                pid = int(owner["pid"])
                if os.name == "nt":
                    windows_ctypes: Any = ctypes
                    kernel32 = windows_ctypes.WinDLL("kernel32", use_last_error=True)
                    handle = kernel32.OpenProcess(0x1000, False, pid)
                    if handle:
                        kernel32.CloseHandle(handle)
                    elif windows_ctypes.get_last_error() != 5:
                        raise ProcessLookupError(pid)
                else:
                    os.kill(pid, 0)
            except ProcessLookupError:
                self.path.unlink(missing_ok=True)
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                pass
        try:
            self.descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(self.descriptor, json.dumps({"pid": os.getpid(), "time": time.time()}).encode())
        except FileExistsError as exc:
            raise KvkError("PROVIDER_LOCKED", f"KVK-provider is lokaal vergrendeld: {self.path}", 6) from exc
        return self

    def __exit__(self, *_: object) -> None:
        if self.descriptor is not None:
            os.close(self.descriptor)
        self.path.unlink(missing_ok=True)


def resolve(run: Run, provider_name: str, limit: int | None, resume: bool, refresh: bool, headed: bool, interval: float = 2.0) -> tuple[Path, Path]:
    candidates_path = run.latest_artifact("03", "candidates")
    if not candidates_path:
        raise HarvestError("voer eerst companies merge uit")
    candidates = read_tsv(candidates_path)
    if refresh:
        run.invalidate_from(5, "kvk_refresh")
    provider = _provider_for_run(run, provider_name)
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, str]] = []
    processed = 0
    with run.lock(), ProviderLock(run):
        with run.connect() as connection:
            connection.execute("UPDATE kvk_requests SET state='SENT_OUTCOME_UNKNOWN',error='INTERRUPTED_BEFORE_DURABLE_OUTCOME' WHERE state='IN_FLIGHT'")
        for candidate in candidates:
            candidate_id = candidate["candidate_id"]
            with run.connect() as connection:
                prior = connection.execute("SELECT state,result_json FROM kvk_requests WHERE candidate_id=?", (candidate_id,)).fetchone()
            if prior and prior["state"] == "SUCCEEDED" and resume and not refresh:
                resolved.append(json.loads(prior["result_json"]))
                continue
            if prior and prior["state"] == "SENT_OUTCOME_UNKNOWN" and not refresh:
                unresolved.append({"candidate_id": candidate_id, "original_name": candidate["original_name"], "reason": "SENT_OUTCOME_UNKNOWN", "detail": "expliciete --refresh vereist voor veilige herhaling", "resumable": "true", "checked_at": ""})
                continue
            if limit is not None and processed >= limit:
                unresolved.append({"candidate_id": candidate_id, "original_name": candidate["original_name"], "reason": "NOT_PROCESSED_LIMIT", "detail": "kandidaatlimiet bereikt", "resumable": "true", "checked_at": ""})
                continue
            try:
                query = validate_kvk(candidate.get("source_kvk_hint", ""))
            except ValueError:
                unresolved.append({"candidate_id": candidate_id, "original_name": candidate["original_name"],
                                   "reason": "NO_DIRECT_KVK_HINT", "detail": "geen geldig direct bron-KVK-nummer",
                                   "resumable": "false", "checked_at": ""})
                continue
            _check_cooldown(run)
            fingerprint = hashlib.sha256(f"{candidate_id}\0{query}".encode()).hexdigest()
            with run.connect() as connection:
                connection.execute(
                    "INSERT INTO kvk_requests(candidate_id,query,state,attempt,request_fingerprint,provider) VALUES(?,?,'IN_FLIGHT',1,?,?) "
                    "ON CONFLICT(candidate_id) DO UPDATE SET state='IN_FLIGHT',attempt=attempt+1,request_fingerprint=excluded.request_fingerprint,provider=excluded.provider",
                    (candidate_id, query, fingerprint, provider.name),
                )
            try:
                result = provider.search(query, headed=headed)
                evidence_path = run.path / result.evidence
                if evidence_path.is_file():
                    run.register_artifact(evidence_path, "04", f"evidence_{result.transport}")
                record = _match(candidate, result) if result.complete else None
                if record:
                    resolved.append(record)
                    state, error = "SUCCEEDED", None
                else:
                    if not result.complete:
                        reason, detail, resumable = "TRUNCATED_RESULTS", "zoekresultaat niet aantoonbaar volledig", "true"
                    elif _has_source_conflict(candidate, result):
                        reason, detail, resumable = "SOURCE_CONFLICT", "exacte naam met ander KVK-nummer dan bronhint", "false"
                    else:
                        reason, detail, resumable = "NOT_FOUND", "voltooide zoekactie zonder onderbouwde unieke match", "false"
                    unresolved.append({"candidate_id": candidate_id, "original_name": candidate["original_name"], "reason": reason, "detail": detail, "resumable": resumable, "checked_at": datetime.now(UTC).isoformat()})
                    state, error = "UNRESOLVED", reason
                with run.connect() as connection:
                    connection.execute("UPDATE kvk_requests SET state=?,checked_at=?,result_json=?,evidence_path=?,error=? WHERE candidate_id=?", (state, datetime.now(UTC).isoformat(), json.dumps(record) if record else None, result.evidence, error, candidate_id))
            except KvkError as exc:
                reason = exc.reason
                unresolved.append({"candidate_id": candidate_id, "original_name": candidate["original_name"], "reason": reason, "detail": str(exc), "resumable": "true", "checked_at": datetime.now(UTC).isoformat()})
                with run.connect() as connection:
                    connection.execute("UPDATE kvk_requests SET state='FAILED',error=? WHERE candidate_id=?", (reason, candidate_id))
                if reason in {"PUBLIC_ACCESS_BLOCKED", "RATE_LIMITED", "PROVIDER_LOCKED"}:
                    for remaining in candidates[candidates.index(candidate) + 1 :]:
                        unresolved.append({"candidate_id": remaining["candidate_id"], "original_name": remaining["original_name"], "reason": "NOT_PROCESSED_INTERRUPTED", "detail": reason, "resumable": "true", "checked_at": ""})
                    break
            except KeyboardInterrupt:
                with run.connect() as connection:
                    connection.execute("UPDATE kvk_requests SET state='SENT_OUTCOME_UNKNOWN',error='INTERRUPTED' WHERE candidate_id=?", (candidate_id,))
                raise
            processed += 1
            if interval > 0:
                time.sleep(interval + random.uniform(0, min(0.25, interval / 4)))
    resolved_path = run.artifact_path("04", "kvk_matches", "csv")
    unresolved_path = run.artifact_path("05", "kvk_unresolved_companies", "csv")
    headers = ["candidate_id", "Bedrijfsnaam", "KVK-nummer", "raw_legal_form", "raw_status", "city", "country", "match_method", "provider", "checked_at", "response_json", "source_relations"]
    write_tsv(resolved_path, headers, resolved)
    write_tsv(unresolved_path, UNRESOLVED_HEADERS, unresolved)
    run.register_artifact(resolved_path, "04", "kvk_matches")
    run.register_artifact(unresolved_path, "05", "kvk_unresolved")
    run.record_config("kvk_resolve", {"provider": provider_name, "limit": limit, "resume": resume, "refresh": refresh, "headed": headed, "interval": interval})
    run.update_status("IN_PROGRESS", "04")
    return resolved_path, unresolved_path


def _check_cooldown(run: Run) -> None:
    with run.connect() as connection:
        row = connection.execute("SELECT until_epoch,reason FROM cooldowns WHERE provider='kvk'").fetchone()
    if row and row["until_epoch"] > time.time():
        raise HarvestError(f"KVK-cooldown actief tot {row['until_epoch']}: {row['reason']}", 4)


def _match(candidate: dict[str, str], result: ProviderResult) -> dict[str, Any] | None:
    from company_lookup.core import normalize_name, validate_kvk

    source_hint = candidate.get("source_kvk_hint", "")
    if not source_hint:
        return None
    matches: list[tuple[dict[str, Any], str]] = []
    for hit in result.hits:
        number_raw = next((hit.get(key) for key in ("kvkNummer", "kvk_number", "kvk", "nummer") if hit.get(key)), None)
        try:
            number = validate_kvk(number_raw)
        except ValueError:
            continue
        if number == source_hint:
            matches.append((hit, "SOURCE_KVK_NUMBER_CONFIRMED"))
    unique: dict[str, list[tuple[dict[str, Any], str]]] = {}
    for hit, method in matches:
        number = validate_kvk(
            next(hit.get(key) for key in ("kvkNummer", "kvk_number", "kvk", "nummer") if hit.get(key))
        )
        unique.setdefault(number, []).append((hit, method))
    if len(unique) != 1:
        return None
    number, variants = next(iter(unique.items()))
    hit, method = variants[0]
    location_variant = next((item for item, _ in variants if item.get("city") or item.get("plaats")), hit)

    def consistent_field(keys: tuple[str, ...]) -> str | None:
        values = [str(next((item.get(key) for key in keys if item.get(key)), "")) for item, _ in variants]
        populated = [value for value in values if value]
        if len({normalize_name(value) for value in populated}) > 1:
            return None
        return populated[0] if populated else ""

    legal_form = consistent_field(("rechtsvorm", "legalForm"))
    status = consistent_field(("status", "ondernemingsstatus"))
    if legal_form is None or status is None:
        return None
    name = str(next((hit.get(key) for key in ("naam", "name", "handelsnaam") if hit.get(key)), candidate["original_name"]))
    city = str(next((location_variant.get(key) for key in ("plaats", "city") if location_variant.get(key) is not None), ""))
    country = str(next((location_variant.get(key) for key in ("land", "country") if location_variant.get(key) is not None), ""))
    if normalize_name(country) not in {"nederland", "netherlands"} or not city:
        return None
    return {"candidate_id": candidate["candidate_id"], "Bedrijfsnaam": name, "KVK-nummer": number, "raw_legal_form": legal_form, "raw_status": status, "city": city, "country": country, "match_method": method, "provider": result.transport, "checked_at": datetime.now(UTC).isoformat(), "response_json": json.dumps([item for item, _ in variants], ensure_ascii=False, separators=(",", ":")), "source_relations": candidate.get("source_relations", "")}


def _has_source_conflict(candidate: dict[str, str], result: ProviderResult) -> bool:
    from company_lookup.core import normalize_name, validate_kvk

    hint = candidate.get("source_kvk_hint", "")
    if not hint:
        return False
    for hit in result.hits:
        name = next((hit.get(key) for key in ("naam", "name", "handelsnaam") if hit.get(key)), None)
        number = next((hit.get(key) for key in ("kvkNummer", "kvk_number", "kvk", "nummer") if hit.get(key)), None)
        try:
            if name and normalize_name(str(name)) == normalize_name(candidate["original_name"]) and validate_kvk(number) != hint:
                return True
        except ValueError:
            continue
    return False
