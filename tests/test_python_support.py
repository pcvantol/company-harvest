"""De actuele distributie accepteert uitsluitend Python 3.14.x."""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from company_harvest.preflight import host

ROOT = Path(__file__).resolve().parents[1]


def test_package_contract_and_current_interpreter(tmp_path: Path) -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)
    assert config["project"]["requires-python"] == ">=3.14,<3.15"
    assert config["tool"]["ruff"]["target-version"] == "py314"
    assert config["tool"]["mypy"]["python_version"] == "3.14"
    assert sys.version_info[:2] == (3, 14)
    result = host(tmp_path)
    assert result["python_supported"] and result["ready"]


@pytest.mark.parametrize("minor", [11, 12, 13, 15])
def test_forced_import_rejects_other_python_minors(minor: int, monkeypatch: pytest.MonkeyPatch) -> None:
    source = ROOT / "src" / "company_harvest" / "__init__.py"
    # Voer de echte package-guard uit zonder de interpreter van pytest te wisselen.
    with monkeypatch.context() as patch:
        patch.setattr(sys, "version_info", (3, minor, 0))
        with pytest.raises(RuntimeError, match="Python 3.14.x"):
            runpy.run_path(str(source))


def test_posix_host_bootstrap_accepts_only_selected_314(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "host-preflight.sh"
    if os.name == "nt":
        pytest.skip("POSIX-wrapper draait alleen op macOS/POSIX")
    environment = os.environ.copy()
    environment["PYTHON_BIN"] = sys.executable
    accepted = subprocess.run(["sh", str(script)], env=environment, capture_output=True, text=True)
    assert accepted.returncode == 0 and "Python 3.14" in accepted.stdout
    wheel = tmp_path / "fake.whl"
    wheel.write_bytes(b"synthetic wheel for dry-run")
    install = ROOT / "scripts" / "install.sh"
    args = ["sh", str(install), str(wheel), str(tmp_path / "venv"), "--dry-run"]
    accepted_install = subprocess.run(args, env=environment, capture_output=True, text=True)
    assert accepted_install.returncode == 0 and "Dry-run geslaagd" in accepted_install.stdout
    environment["PYTHON_BIN"] = str(script.parent / "does-not-exist-python")
    rejected = subprocess.run(["sh", str(script)], env=environment, capture_output=True, text=True)
    assert rejected.returncode == 2 and "Python 3.14" in rejected.stderr
    rejected_install = subprocess.run(args, env=environment, capture_output=True, text=True)
    assert rejected_install.returncode == 2 and "Python 3.14" in rejected_install.stderr
    assert not (tmp_path / "venv").exists()
