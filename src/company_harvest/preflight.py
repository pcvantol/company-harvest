"""Host- en runpreflight zonder ongevraagde bulkacties."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from company_harvest import __version__
from company_harvest.core import HarvestError, Run


def host(data_dir: Path) -> dict[str, Any]:
    data_dir.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(data_dir)
    supported = sys.version_info[:2] == (3, 14)
    writable = os.access(data_dir, os.W_OK)
    risks = []
    text = str(data_dir).casefold()
    if any(marker in text for marker in ("dropbox", "onedrive", "icloud", "network")):
        risks.append("sync- of netwerkopslag kan SQLite/locks verstoren")
    playwright_installed = importlib.util.find_spec("playwright") is not None
    browser_installed = False
    if playwright_installed:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser_installed = Path(playwright.chromium.executable_path).is_file()
        except Exception:
            browser_installed = False
    return {"version": __version__, "python": platform.python_version(), "python_supported": supported, "os": platform.system(), "architecture": platform.machine(), "data_dir": str(data_dir), "writable": writable, "free_bytes": usage.free, "venv_active": sys.prefix != sys.base_prefix, "pip_available": importlib.util.find_spec("pip") is not None, "sqlite_version": __import__("sqlite3").sqlite_version, "playwright_installed": playwright_installed, "browser_installed": browser_installed, "risks": risks, "ready": supported and writable and usage.free > 100 * 1024 * 1024}


def run_preflight(run: Run, workflow: str | None = None) -> dict[str, Any]:
    metadata = run.metadata()
    if workflow and metadata["workflow"] != workflow:
        raise HarvestError(f"runworkflow is {metadata['workflow']}, verwacht {workflow}")
    result = host(run.path)
    result.update({"run_id": metadata["run_id"], "workflow": metadata["workflow"], "schema_version": metadata["schema_version"], "locked": (run.path / "run.lock").exists()})
    result["ready"] = bool(result["ready"] and not result["locked"])
    return result
