"""Runbeheer, logging, snapshots en gedeelde validatie."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUN_SCHEMA_VERSION = 1
HTTP_USER_AGENT = "company-lookup/0.1"
KVK_RE = re.compile(r"^[0-9]{8}$", re.ASCII)
SECRET_RE = re.compile(r"(?i)(authorization|cookie|token|secret|password)([=: ]+)([^\s,;]+)")
_RUN_LOCKS = threading.local()


class HarvestError(RuntimeError):
    """Gecontroleerde applicatiefout met een betekenisvolle exitcode."""

    def __init__(self, message: str, exit_code: int = 3) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def utc_now() -> datetime:
    return datetime.now(UTC)


def timestamp() -> str:
    now = utc_now()
    return f"{time.time_ns()}_{now:%Y%m%dT%H%M%S.%fZ}_{secrets.token_hex(3)}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def redact(value: str) -> str:
    return SECRET_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)


def normalize_name(value: str) -> str:
    import unicodedata

    return " ".join(unicodedata.normalize("NFC", value).strip().split()).casefold()


def validate_kvk(value: object) -> str:
    if isinstance(value, bool):
        raise ValueError("booleaanse waarde is geen KVK-nummer")
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, float) and value.is_integer():
        text = str(int(value))
    else:
        text = str(value or "").strip()
    if not KVK_RE.fullmatch(text):
        raise ValueError("KVK-nummer moet exact acht ASCII-cijfers bevatten")
    return text


def data_root(explicit: Path | None = None) -> Path:
    if explicit:
        return explicit.expanduser().resolve()
    configured = os.environ.get("COMPANY_HARVEST_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".local" / "share" / "company-harvest").resolve()


def atomic_write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    if isinstance(content, bytes):
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    else:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_tsv(path: Path, headers: Sequence[str], rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(headers), delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@dataclass(frozen=True)
class Run:
    path: Path

    @property
    def db_path(self) -> Path:
        return self.path / "state.sqlite3"

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def metadata(self) -> dict[str, Any]:
        value: dict[str, Any] = json.loads((self.path / "run.json").read_text(encoding="utf-8"))
        return value

    def update_status(self, status: str, step: str | None = None) -> None:
        metadata = self.metadata()
        metadata["status"] = status
        metadata["updated_at"] = utc_now().isoformat()
        if step:
            metadata["last_completed_step"] = step
        atomic_write(self.path / "run.json", json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

    def record_config(self, key: str, value: Any) -> None:
        metadata = self.metadata()
        runtime = metadata.setdefault("runtime_config", {})
        runtime[key] = value
        metadata["config_fingerprint"] = hashlib.sha256(json.dumps({"workflow": metadata["workflow"], "target": metadata["target"], "runtime_config": runtime}, sort_keys=True).encode()).hexdigest()
        atomic_write(self.path / "run.json", json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

    def invalidate_from(self, step: int, reason: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE artifacts SET status='STALE' WHERE CAST(step AS INTEGER)>=? AND status IN ('COMPLETE','PARTIAL')", (step,))
            if step <= 3:
                connection.execute("DELETE FROM kvk_requests")
        self.log("INFO", "downstream_invalidated", from_step=step, reason=reason)

    def artifact_path(self, step: str, description: str, suffix: str) -> Path:
        return self.path / "artifacts" / f"{timestamp()}_{step}_{description}.{suffix}"

    def register_artifact(self, path: Path, step: str, kind: str, status: str = "COMPLETE") -> None:
        self.register_artifact_set([(path, step, kind, status)])

    def register_artifact_set(self, entries: Sequence[tuple[Path, str, str, str]]) -> None:
        """Registreer een complete outputset in één databasetransactie."""
        with self.connect() as connection:
            connection.executemany(
                "INSERT INTO artifacts(path, step, kind, sha256, size, status, created_at) VALUES(?,?,?,?,?,?,?)",
                [(str(path.relative_to(self.path)), step, kind, sha256(path), path.stat().st_size, status, utc_now().isoformat()) for path, step, kind, status in entries],
            )

    def latest_artifact(self, step: str, kind: str) -> Path | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT path FROM artifacts WHERE step=? AND kind=? AND status='COMPLETE' ORDER BY id DESC LIMIT 1",
                (step, kind),
            ).fetchone()
        return self.path / row["path"] if row else None

    def log(self, level: str, event: str, **fields: Any) -> None:
        logs = self.path / "logs"
        logs.mkdir(exist_ok=True)
        safe_fields = {
            key: "[REDACTED]" if re.search(r"(?i)(authorization|cookie|token|secret|password)", key) else value
            for key, value in fields.items()
        }
        record = {"time": utc_now().isoformat(), "level": level, "event": event, **safe_fields}
        clean = json.loads(redact(json.dumps(record, ensure_ascii=False, default=str)))
        jsonl = logs / "events.jsonl"
        with jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(clean, ensure_ascii=False) + "\n")
            handle.flush()
        with (logs / "execution.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{clean['time']} {level} {event} {json.dumps(clean, ensure_ascii=False)}\n")

    @contextmanager
    def lock(self, wait_seconds: float = 0) -> Iterator[None]:
        lock_path = self.path / "run.lock"
        held: set[Path] = getattr(_RUN_LOCKS, "paths", set())
        if lock_path in held:
            yield
            return
        started = time.monotonic()
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(descriptor, json.dumps({"pid": os.getpid(), "created": utc_now().isoformat()}).encode())
            except FileExistsError as exc:
                if time.monotonic() - started >= wait_seconds:
                    raise HarvestError(f"run is vergrendeld: {lock_path}", 6) from exc
                time.sleep(0.1)
        try:
            held.add(lock_path)
            _RUN_LOCKS.paths = held
            yield
        finally:
            held.remove(lock_path)
            os.close(descriptor)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


def initialize_run(root: Path, target: int, workflow: str = "HARVEST") -> Run:
    if target < 1:
        raise HarvestError("target moet positief zijn")
    run_path = root / "runs" / timestamp()
    for directory in (run_path / "artifacts", run_path / "evidence", run_path / "logs", run_path / "snapshots"):
        directory.mkdir(parents=True, exist_ok=False)
    metadata = {
        "run_id": run_path.name,
        "workflow": workflow,
        "target": target,
        "schema_version": RUN_SCHEMA_VERSION,
        "created_at": utc_now().isoformat(),
        "status": "INITIALIZED",
        "python": sys.version.split()[0],
        "http_user_agent": HTTP_USER_AGENT,
        "runtime_config": {},
    }
    metadata["config_fingerprint"] = hashlib.sha256(
        json.dumps({"workflow": workflow, "target": target, "runtime_config": {}}, sort_keys=True).encode()
    ).hexdigest()
    atomic_write(run_path / "run.json", json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    run = Run(run_path)
    with run.connect() as connection:
        connection.executescript(
            """
            CREATE TABLE artifacts(id INTEGER PRIMARY KEY, path TEXT UNIQUE, step TEXT, kind TEXT,
              sha256 TEXT, size INTEGER, status TEXT, created_at TEXT);
            CREATE TABLE events(id INTEGER PRIMARY KEY, created_at TEXT, event TEXT, payload_json TEXT);
            CREATE TABLE kvk_requests(id INTEGER PRIMARY KEY, candidate_id TEXT UNIQUE, query TEXT,
              state TEXT, attempt INTEGER DEFAULT 0, request_fingerprint TEXT, provider TEXT,
              checked_at TEXT, result_json TEXT, evidence_path TEXT, error TEXT);
            CREATE TABLE cooldowns(provider TEXT PRIMARY KEY, until_epoch REAL, reason TEXT);
            """
        )
    metadata["storage_baseline"] = {
        "sqlite_bytes": sum(
            path.stat().st_size
            for path in (
                run.db_path,
                run.db_path.with_name(run.db_path.name + "-wal"),
                run.db_path.with_name(run.db_path.name + "-shm"),
            )
            if path.exists()
        ),
        "evidence_bytes": 0,
    }
    atomic_write(run_path / "run.json", json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    run.log("INFO", "run_initialized", workflow=workflow, target=target)
    return run


def open_run(path: Path) -> Run:
    resolved = path.expanduser().resolve()
    metadata_path = resolved / "run.json"
    if not metadata_path.is_file():
        raise HarvestError(f"geen geldige runmap: {resolved}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("schema_version") != RUN_SCHEMA_VERSION:
        raise HarvestError(
            f"incompatibele runschemaversie {metadata.get('schema_version')!r}; "
            "open de run met de oorspronkelijke programmaversie of start een nieuwe run",
            7,
        )
    run = Run(resolved)
    with run.connect() as connection:
        connection.execute("SELECT 1")
    return run


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))
