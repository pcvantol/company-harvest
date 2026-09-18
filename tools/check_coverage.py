#!/usr/bin/env python3
"""Strikte per-file statementcoveragegate voor alle eigen Pythonlogica."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any


def executable_files(root: Path) -> list[Path]:
    files = sorted((root / "src").rglob("*.py")) + sorted((root / "tools").glob("*.py"))
    return [path for path in files if path.name != "check_coverage.py" or path.is_file()]


def has_statements(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(isinstance(node, ast.stmt) for node in ast.walk(tree))


def evaluate(root: Path, report: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    report_files = report.get("files")
    if not isinstance(report_files, dict):
        raise ValueError("coverage JSON mist files")
    rows: list[dict[str, Any]] = []
    passed = True
    for path in executable_files(root):
        relative = str(path.relative_to(root))
        if not has_statements(path):
            rows.append({"file": relative, "statements": 0, "covered": 0, "status": "N/A"})
            continue
        entry = report_files.get(relative)
        if not isinstance(entry, dict):
            rows.append({"file": relative, "statements": None, "covered": None, "status": "MISSING"})
            passed = False
            continue
        summary = entry.get("summary", {})
        total = int(summary.get("num_statements", 0))
        covered = int(summary.get("covered_lines", 0))
        branches = int(summary.get("num_branches", 0))
        covered_branches = int(summary.get("covered_branches", 0))
        ok = total > 0 and 5 * covered > 4 * total
        rows.append({"file": relative, "statements": total, "covered": covered, "branches": branches, "covered_branches": covered_branches, "status": "PASS" if ok else "FAIL"})
        passed = passed and ok
    return rows, passed


def markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["# Coverage per bestand", "", "| Bestand | Statements | Gedekt | Branches | Gedekte branches | Status |", "|---|---:|---:|---:|---:|---|"]
    lines.extend(f"| `{row['file']}` | {row['statements']} | {row['covered']} | {row.get('branches', 0)} | {row.get('covered_branches', 0)} | {row['status']} |" for row in rows)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    arguments = argv or sys.argv[1:]
    if len(arguments) != 2:
        print("gebruik: check_coverage.py ROOT COVERAGE_JSON", file=sys.stderr)
        return 2
    root, report_path = Path(arguments[0]).resolve(), Path(arguments[1]).resolve()
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        rows, passed = evaluate(root, report)
    except (OSError, ValueError, SyntaxError, json.JSONDecodeError) as exc:
        print(f"coveragegate ongeldig: {exc}", file=sys.stderr)
        return 2
    output = root / ".local" / "quality"
    output.mkdir(parents=True, exist_ok=True)
    (output / "coverage-per-file.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (output / "coverage-per-file.md").write_text(markdown(rows), encoding="utf-8")
    for row in rows:
        print(f"{row['status']:7} {row['file']} {row['covered']}/{row['statements']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
