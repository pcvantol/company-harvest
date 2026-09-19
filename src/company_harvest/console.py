"""Veilige, menselijke CLI-voortgang; gestructureerde stdout blijft intact."""

from __future__ import annotations

import ctypes
import os
import sys
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any

_ACTIVE: ContextVar[bool] = ContextVar("company_harvest_console_active", default=False)
_COLORS = {"START": "36;1", "STEP": "34;1", "INFO": "36", "OK": "32;1",
           "WARN": "33;1", "FOUT": "31;1"}
_SAFE_SCALARS = ("status", "ready", "valid", "audit_valid", "delivery_rows",
                 "checked_kvk_candidates", "checked_artifacts", "remaining", "attempted",
                 "matched", "count")
_SAFE_STATUSES = {"CREATED", "INITIALIZED", "IN_PROGRESS", "COMPLETE", "PARTIAL",
                  "PARTIAL_EXPORTED", "EXPORT_COMPLETE", "COMPLETE_WITH_WARNINGS",
                  "BLOCKED", "FAILED", "PASS", "CHANGES_REQUIRED", "IMPLEMENTED",
                  "CAPABILITY_MISSING", "BROWSER_UNAVAILABLE",
                  "BROWSER_AVAILABLE_NOT_LIVE_PROVEN"}
_SOURCE_LABELS = {"ind_arbeid": "IND", "wikidata_nl_companies": "Wikidata"}
_SAFE_ERROR_TEXT = {
    "E2E-instellingen van deze run mogen bij hervatten niet wijzigen",
}
_ERROR_CATEGORIES = {
    3: "Ongeldige invoer of runstatus; controleer de opdracht en runvoorwaarden",
    4: "Publieke KVK-toegang geblokkeerd of niet beschikbaar; stop nieuwe verzoeken",
    5: "Bron- of invoerprobleem; controleer de lokale bestanden en evidence",
    6: "Run is vergrendeld; controleer de actieve uitvoering",
    7: "Integriteits- of controlefout; inspecteer de lokale runlogs",
}
_AUDIT_EVENTS = {
    "sources_discovered": ("Broncatalogus geregistreerd", "count"),
    "source_collect_started": ("Broninname gestart", None),
    "source_collect_completed": ("Broninname afgerond", "count"),
    "source_collect_reused": ("Bestaande bron hergebruikt", None),
    "source_import_completed": ("Import geregistreerd", "count"),
    "source_measurement_terminal_error": ("Bronmeting geblokkeerd of mislukt", None),
    "gleif_collect_completed": ("GLEIF-inname afgerond", "candidates"),
    "gleif_collect_reused": ("Bestaande GLEIF-bron hergebruikt", None),
    "anbi_register_collect_completed": ("ANBI-inname afgerond", "candidates"),
    "anbi_register_collect_reused": ("Bestaande ANBI-bron hergebruikt", None),
    "duo_education_organisations_collect_completed": ("DUO-inname afgerond", "candidates"),
    "duo_education_organisations_collect_reused": ("Bestaande DUO-bron hergebruikt", None),
    "audit_verify": ("Audit uitgevoerd", "checked_artifacts"),
}


def _use_color() -> bool:
    if "NO_COLOR" in os.environ:
        return False
    forced = os.environ.get("FORCE_COLOR")
    if forced is not None:
        return forced not in {"", "0", "false", "False"}
    return (sys.stderr.isatty() and os.environ.get("TERM") != "dumb"
            and (os.name != "nt" or _enable_windows_vt()))


def _enable_windows_vt() -> bool:
    """Activeer ANSI op klassieke Windows-consoles; kies anders kleurloos."""
    try:
        windows_ctypes: Any = ctypes
        kernel32 = windows_ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetStdHandle.argtypes = [ctypes.c_ulong]
        kernel32.GetStdHandle.restype = ctypes.c_void_p
        kernel32.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
        kernel32.GetConsoleMode.restype = ctypes.c_int
        kernel32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel32.SetConsoleMode.restype = ctypes.c_int
        handle = kernel32.GetStdHandle(-12)
        mode = ctypes.c_uint()
        return bool(kernel32.GetConsoleMode(handle, ctypes.byref(mode))
                    and kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except (AttributeError, OSError):
        return False


def emit(level: str, label: str, *, count: int | None = None,
         total: int | None = None) -> None:
    """Toon uitsluitend vaste labels en numerieke voortgang, nooit records."""
    if not _ACTIVE.get():
        return
    stamp = datetime.now().astimezone().strftime("%H:%M:%S")
    badge = f"{level:<5}"
    if _use_color():
        badge = f"\x1b[{_COLORS[level]}m{badge}\x1b[0m"
    suffix = f"  {count:,}" if count is not None else ""
    if total is not None:
        suffix += f"/{total:,}"
    print(f"{stamp}  {badge}  {label}{suffix}", file=sys.stderr, flush=True)


@contextmanager
def active() -> Iterator[None]:
    token = _ACTIVE.set(True)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


@contextmanager
def phase(label: str) -> Iterator[None]:
    if not _ACTIVE.get():
        yield
        return
    emit("STEP", label)
    started = time.monotonic()
    try:
        yield
    except BaseException:
        emit("FOUT", f"{label} gestopt")
        raise
    else:
        emit("OK", f"{label} gereed ({time.monotonic() - started:.1f}s)")


def result(value: object) -> None:
    """Vat resultaten samen zonder vrije tekst of recordinhoud over te nemen."""
    if isinstance(value, (list, tuple)):
        emit("INFO", "Resultaatitems", count=len(value))
    elif isinstance(value, Path):
        emit("INFO", "Resultaatbestand beschikbaar")
    elif isinstance(value, Mapping):
        parts: list[str] = []
        for key in _SAFE_SCALARS:
            item = value.get(key)
            if isinstance(item, bool):
                parts.append(f"{key}={'ja' if item else 'nee'}")
            elif type(item) is int:
                parts.append(f"{key}={item:,}")
            elif key == "status" and isinstance(item, str) and item in _SAFE_STATUSES:
                parts.append(f"status={item}")
        if parts:
            emit("INFO", "Resultaat: " + " · ".join(parts))
        else:
            emit("INFO", "Resultaat beschikbaar")
    else:
        emit("INFO", "Resultaat beschikbaar")


def error_text(message: str, exit_code: int) -> str:
    """Gebruik nooit vrije fouttekst: die kan een naam, pad of nummer bevatten."""
    if message in _SAFE_ERROR_TEXT:
        return message
    if message.startswith("geen trace gevonden voor KVK "):
        return "Geen trace gevonden voor het opgegeven KVK-nummer"
    return _ERROR_CATEGORIES.get(exit_code, "Opdracht mislukt; inspecteer de lokale runlogs")


def audit_event(level: str, event: str, fields: Mapping[str, Any]) -> None:
    """Spiegel alleen bekende runevents en vooraf gekozen aantallen naar stderr."""
    if not _ACTIVE.get() or event not in _AUDIT_EVENTS:
        return
    label, count_key = _AUDIT_EVENTS[event]
    if event.startswith("source_collect_") or event == "source_measurement_terminal_error":
        source_id = fields.get("source_id")
        source_label = _SOURCE_LABELS.get(source_id) if isinstance(source_id, str) else None
        if source_label:
            label += f" ({source_label})"
    count = fields.get(count_key) if count_key else None
    emit("WARN" if level in {"ERROR", "WARNING"} else "INFO", label,
         count=count if type(count) is int else None)
