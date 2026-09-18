#!/usr/bin/env python3
"""Build, verify en veilige GitHub Release-publicatie van bestaande bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def scan_asset(path: Path) -> None:
    forbidden = {".env", "state.sqlite3", "storage-state.json"}
    names: list[str] = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    elif path.suffix == ".gz":
        import tarfile

        with tarfile.open(path) as archive:
            names = archive.getnames()
    if any(Path(name).name in forbidden or "runs/" in name or name.endswith((".har", ".log", ".jsonl", ".sqlite3")) for name in names):
        raise RuntimeError(f"verboden inhoud in distributieasset: {path.name}")


def qualify_wheel(wheel: Path) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="company-harvest-install-") as temporary:
        environment = Path(temporary) / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        cli = environment / ("Scripts/company-harvest.exe" if sys.platform == "win32" else "bin/company-harvest")
        subprocess.run([str(python), "-m", "pip", "install", str(wheel)], check=True)
        version = subprocess.run([str(cli), "--version"], check=True, capture_output=True, text=True).stdout.strip()
        subprocess.run([str(cli), "--help"], check=True, capture_output=True, text=True)
        location = subprocess.run([str(python), "-c", "import company_harvest; print(company_harvest.__file__)"], check=True, capture_output=True, text=True).stdout.strip()
    return {"version": version, "import_location": location, "status": "PASS"}


def build(root: Path, output_root: Path) -> Path:
    if git(root, "status", "--porcelain"):
        raise RuntimeError("releasebuild vereist een schone werkboom")
    version = _version(root)
    folder = output_root.resolve() / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}_{git(root, 'rev-parse', '--short=12', 'HEAD')}"
    folder.mkdir(parents=True, exist_ok=False)
    subprocess.run([sys.executable, "-m", "build", "--outdir", str(folder)], cwd=root, check=True)
    assets = sorted(path for path in folder.iterdir() if path.suffix in {".whl", ".gz"})
    bundle = folder / f"company-harvest-{version}-online-bundle.zip"
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary) / f"company-harvest-{version}"
        stage.mkdir()
        wheel = next(path for path in assets if path.suffix == ".whl")
        shutil.copy2(wheel, stage / wheel.name)
        for relative in ("scripts/host-preflight.sh", "scripts/host-preflight.ps1", "scripts/install.sh", "scripts/install.ps1", "scripts/run-preflight.sh", "scripts/run-preflight.ps1", "scripts/run.sh", "scripts/run.ps1", "README.md"):
            source = root / relative
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        shutil.make_archive(str(bundle.with_suffix("")), "zip", Path(temporary), stage.name)
    assets.append(bundle)
    for asset in assets:
        scan_asset(asset)
    wheel = next(path for path in assets if path.suffix == ".whl")
    installation = qualify_wheel(wheel)
    manifest: dict[str, Any] = {"schema": 1, "version": version, "tag": f"v{version}", "source_commit": git(root, "rev-parse", "HEAD"), "built_at": datetime.now(UTC).isoformat(), "clean_install": installation, "assets": [{"name": path.name, "path": str(path), "sha256": digest(path), "size": path.stat().st_size} for path in assets]}
    manifest_path = folder / "distribution-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    checksums = folder / "SHA256SUMS.txt"
    checksums.write_text("".join(f"{entry['sha256']}  {entry['name']}\n" for entry in manifest["assets"]), encoding="utf-8")
    manifest["assets"].extend([{"name": checksums.name, "path": str(checksums), "sha256": digest(checksums), "size": checksums.stat().st_size}])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _version(root: Path) -> str:
    import tomllib

    return str(tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])


def verify(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for asset in manifest["assets"]:
        path = Path(asset["path"])
        if not path.is_file() or path.stat().st_size != asset["size"] or digest(path) != asset["sha256"]:
            raise RuntimeError(f"assetverificatie mislukt: {asset['name']}")
        scan_asset(path)
    return manifest


def publish(root: Path, manifest_path: Path) -> None:
    manifest = verify(manifest_path)
    if git(root, "rev-parse", "HEAD") != manifest["source_commit"] or git(root, "status", "--porcelain"):
        raise RuntimeError("broncommit/werkboom wijkt af van manifest")
    tag = manifest["tag"]
    existing = subprocess.run(["gh", "release", "view", tag, "--json", "tagName"], cwd=root, capture_output=True, text=True)
    if existing.returncode == 0:
        raise RuntimeError("releaseversie bestaat al; assets worden niet overschreven")
    subprocess.run(["git", "tag", "-a", tag, "-m", f"Company Harvest {manifest['version']}"], cwd=root, check=True)
    subprocess.run(["git", "push", "origin", tag], cwd=root, check=True)
    assets = [entry["path"] for entry in manifest["assets"]] + [str(manifest_path)]
    subprocess.run(["gh", "release", "create", tag, *assets, "--verify-tag", "--title", f"Company Harvest {manifest['version']}", "--notes-file", str(root / "docs" / "releases" / f"v{manifest['version']}.md")], cwd=root, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build"); build_parser.add_argument("--output-root", type=Path, required=True); build_parser.add_argument("--print-manifest-path", action="store_true")
    verify_parser = sub.add_parser("verify"); verify_parser.add_argument("--manifest", type=Path, required=True)
    publish_parser = sub.add_parser("publish"); publish_parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "build":
            path = build(root, args.output_root)
            print(path if args.print_manifest_path else json.dumps(verify(path), indent=2))
        elif args.command == "verify":
            print(json.dumps(verify(args.manifest), indent=2))
        else:
            publish(root, args.manifest)
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"releasefout: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
