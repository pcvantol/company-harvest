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
    supported = (3, 11) <= sys.version_info[:2] < (3, 15)
    writable = os.access(data_dir, os.W_OK)
    risks = []
    text = str(data_dir).casefold()
    if any(marker in text for marker in ("dropbox", "onedrive", "icloud", "network")):
        risks.append("sync- of netwerkopslag kan SQLite/locks verstoren")
    return {"version": __version__, "python": platform.python_version(), "python_supported": supported, "os": platform.system(), "architecture": platform.machine(), "data_dir": str(data_dir), "writable": writable, "free_bytes": usage.free, "playwright_installed": importlib.util.find_spec("playwright") is not None, "risks": risks, "ready": supported and writable and usage.free > 100 * 1024 * 1024}


def run_preflight(run: Run, workflow: str | None = None) -> dict[str, Any]:
    metadata = run.metadata()
    if workflow and metadata["workflow"] != workflow:
        raise HarvestError(f"runworkflow is {metadata['workflow']}, verwacht {workflow}")
    result = host(run.path)
    result.update({"run_id": metadata["run_id"], "workflow": metadata["workflow"], "schema_version": metadata["schema_version"], "locked": (run.path / "run.lock").exists()})
    result["ready"] = bool(result["ready"] and not result["locked"])
    return result

