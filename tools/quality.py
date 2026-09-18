#!/usr/bin/env python3
"""Eén vaste quality-opdracht voor tests, coverage, lint, types en publicatiescan."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path


def run(command: list[str], root: Path, environment: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, cwd=root, env=environment, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def scan(root: Path) -> None:
    forbidden_names = {"state.sqlite3", "storage-state.json", ".env"}
    forbidden_suffixes = {".har", ".log", ".jsonl"}
    tracked = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    paths = [root / line for line in tracked.stdout.splitlines() if line]
    violations = [str(path.relative_to(root)) for path in paths if path.name in forbidden_names or path.suffix in forbidden_suffixes or "runs" in path.parts]
    secret_patterns = (
        re.compile(rb"gh[pousr]_[A-Za-z0-9_]{20,}"),
        re.compile(rb"AKIA[0-9A-Z]{16}"),
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    )
    for path in paths:
        if not path.is_file() or path.stat().st_size > 25 * 1024 * 1024:
            continue
        blobs: list[tuple[str, bytes]] = []
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if info.file_size <= 5 * 1024 * 1024:
                        blobs.append((f"{path}!{info.filename}", archive.read(info)))
        else:
            blobs.append((str(path), path.read_bytes()))
        for label, content in blobs:
            if any(pattern.search(content) for pattern in secret_patterns):
                violations.append(f"secretpatroon:{label}")
    if violations:
        raise SystemExit(f"verboden publicatiebestanden: {violations}")


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    if args != ["check"]:
        print("gebruik: quality.py check", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    local = root / ".local" / "quality"
    local.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["COVERAGE_FILE"] = str(local / ".coverage")
    python = sys.executable
    run([python, "-m", "coverage", "erase"], root, environment)
    run([python, "-m", "coverage", "run", "-m", "pytest"], root, environment)
    run([python, "-m", "coverage", "json", "-o", str(local / "coverage.json")], root, environment)
    run([python, str(root / "tools" / "check_coverage.py"), str(root), str(local / "coverage.json")], root, environment)
    run([python, "-m", "ruff", "check", "src", "tests", "tools"], root)
    run([python, "-m", "mypy", "src"], root)
    scan(root)
    print("QUALITY PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
