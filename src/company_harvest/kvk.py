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

from company_harvest.core import HarvestError, Run, read_tsv, timestamp, write_tsv

KVK_HOSTS = {"www.kvk.nl", "kvk.nl", "web-api.kvk.nl"}
PUBLIC_SEARCH_ENDPOINT = "https://web-api.kvk.nl/zoeken/v3/search"
PUBLIC_PROFILE_ID = "5C10A89D-635E-49CC-94B8-042DD533B64A"
UNRESOLVED_HEADERS = ["candidate_id", "original_name", "reason", "detail", "resumable", "checked_at"]


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
    def __init__(self, reason: str, message: str, exit_code: int = 5) -> None:
        super().__init__(message, exit_code)
        self.reason = reason


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

    def __init__(self, run: Run, endpoint: str | None = None) -> None:
        self.run = run
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
        del headed
        if not self.endpoint or not self.query_parameter:
            raise KvkError("BROWSER_REQUIRED", "geen publieke HTTP-route waargenomen", 5)
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or parsed.hostname not in KVK_HOSTS:
            raise KvkError("CAPABILITY_MISSING", "waargenomen KVK-endpoint is niet toegestaan", 7)
        timeout = httpx.Timeout(20, connect=10, read=20, write=10, pool=10)
        headers = {"User-Agent": "company-harvest/0.1", "profileId": PUBLIC_PROFILE_ID}
        payloads: list[dict[str, Any]] = []
        hits: list[dict[str, Any]] = []
        start, total = 0, None
        with httpx.Client(timeout=timeout, follow_redirects=False, headers=headers) as client:
            for _page in range(20):
                params = {self.query_parameter: query, "language": "nl", "site": "kvk2014", "size": "10", "start": str(start)}
                response = self._get_with_retries(client, params)
                if response.status_code in {401, 403}:
                    raise KvkError("PUBLIC_ACCESS_BLOCKED", "publieke KVK-toegang geweigerd", 4)
                if response.status_code == 429:
                    self._cooldown(retry_after(response.headers.get("Retry-After")) or 300, "HTTP 429")
                    raise KvkError("RATE_LIMITED", "KVK-rate limit actief; hervat later", 4)
                if response.status_code >= 500:
                    raise KvkError("NETWORK_ERROR", f"tijdelijke KVK-serverfout {response.status_code}")
                try:
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    raise KvkError("PUBLIC_ACCESS_BLOCKED", f"KVK HTTP-fout: {exc}", 4) from exc
                if len(response.content) > 5 * 1024 * 1024:
                    raise KvkError("PARSING_ERROR", "KVK-response te groot")
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise KvkError("PARSING_ERROR", "KVK-response is geen geldige JSON") from exc
                if not isinstance(payload, dict):
                    raise KvkError("PARSING_ERROR", "onverwacht KVK-responseschema")
                payloads.append(payload)
                page_hits, page_total = _extract_public_search(payload)
                hits.extend(page_hits)
                total = page_total if total is None else total
                start += len(page_hits)
                if not page_hits or total is None or start >= total:
                    break
            else:
                raise KvkError("TRUNCATED_RESULTS", "KVK-paginabudget bereikt")
        evidence = self.run.path / "evidence" / f"{timestamp()}_04_kvk_http_response.json"
        evidence.write_text(json.dumps(payloads, ensure_ascii=False), encoding="utf-8")
        complete = total is not None and start >= total
        return ProviderResult(query, hits, complete, self.name, str(evidence.relative_to(self.run.path)))

    def _get_with_retries(self, client: httpx.Client, params: dict[str, str]) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = client.get(self.endpoint, params=params)
                if response.status_code < 500:
                    return response
                last_error = KvkError("NETWORK_ERROR", f"tijdelijke KVK-serverfout {response.status_code}")
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt < 2:
                time.sleep((2**attempt) + random.uniform(0, 0.25))
        raise KvkError("NETWORK_ERROR", f"KVK-netwerkfout na begrensde retries: {last_error}")

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
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright

        observed: list[dict[str, Any]] = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=not headed)
                context = browser.new_context()
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
            _check_cooldown(run)
            fingerprint = hashlib.sha256(f"{candidate_id}\0{candidate['original_name']}".encode()).hexdigest()
            with run.connect() as connection:
                connection.execute(
                    "INSERT INTO kvk_requests(candidate_id,query,state,attempt,request_fingerprint,provider) VALUES(?,?,'IN_FLIGHT',1,?,?) "
                    "ON CONFLICT(candidate_id) DO UPDATE SET state='IN_FLIGHT',attempt=attempt+1,request_fingerprint=excluded.request_fingerprint,provider=excluded.provider",
                    (candidate_id, candidate["original_name"], fingerprint, provider.name),
                )
            try:
                result = provider.search(candidate["original_name"], headed=headed)
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
    run.update_status("IN_PROGRESS", "04")
    return resolved_path, unresolved_path


def _check_cooldown(run: Run) -> None:
    with run.connect() as connection:
        row = connection.execute("SELECT until_epoch,reason FROM cooldowns WHERE provider='kvk'").fetchone()
    if row and row["until_epoch"] > time.time():
        raise HarvestError(f"KVK-cooldown actief tot {row['until_epoch']}: {row['reason']}", 4)


def _match(candidate: dict[str, str], result: ProviderResult) -> dict[str, Any] | None:
    from company_harvest.core import normalize_name, validate_kvk

    source_hint = candidate.get("source_kvk_hint", "")
    matches: list[tuple[dict[str, Any], str]] = []
    for hit in result.hits:
        number_raw = next((hit.get(key) for key in ("kvkNummer", "kvk_number", "kvk", "nummer") if hit.get(key)), None)
        name_raw = next((hit.get(key) for key in ("naam", "name", "handelsnaam") if hit.get(key)), None)
        try:
            number = validate_kvk(number_raw)
        except ValueError:
            continue
        name_matches = bool(name_raw) and normalize_name(str(name_raw)) == normalize_name(candidate["original_name"])
        if not name_matches:
            continue
        if source_hint and number != source_hint:
            continue
        matches.append((hit, "SOURCE_KVK_AND_NAME_CONFIRMED" if source_hint else "EXACT_NORMALIZED_NAME"))
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
    status_variant = next((item for item, _ in variants if item.get("status") or item.get("ondernemingsstatus")), hit)
    name = str(next((hit.get(key) for key in ("naam", "name", "handelsnaam") if hit.get(key)), candidate["original_name"]))
    legal_form = str(next((hit.get(key) for key in ("rechtsvorm", "legalForm") if hit.get(key) is not None), ""))
    status = str(next((status_variant.get(key) for key in ("status", "ondernemingsstatus") if status_variant.get(key) is not None), ""))
    city = str(next((location_variant.get(key) for key in ("plaats", "city") if location_variant.get(key) is not None), ""))
    country = str(next((location_variant.get(key) for key in ("land", "country") if location_variant.get(key) is not None), ""))
    if normalize_name(country) not in {"nederland", "netherlands"} or not city:
        return None
    return {"candidate_id": candidate["candidate_id"], "Bedrijfsnaam": name, "KVK-nummer": number, "raw_legal_form": legal_form, "raw_status": status, "city": city, "country": country, "match_method": method, "provider": result.transport, "checked_at": datetime.now(UTC).isoformat(), "response_json": json.dumps([item for item, _ in variants], ensure_ascii=False, separators=(",", ":")), "source_relations": candidate.get("source_relations", "")}


def _has_source_conflict(candidate: dict[str, str], result: ProviderResult) -> bool:
    from company_harvest.core import normalize_name, validate_kvk

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
