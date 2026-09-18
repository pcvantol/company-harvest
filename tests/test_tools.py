import importlib.util
import json
import runpy
import subprocess
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_coverage_gate(tmp_path: Path) -> None:
    module = load("check_coverage")
    (tmp_path / "src").mkdir(); (tmp_path / "tools").mkdir()
    file = tmp_path / "src" / "x.py"; file.write_text("a=1\nb=2\nc=3\nd=4\ne=5\n")
    report = {"files": {"src/x.py": {"summary": {"num_statements": 5, "covered_lines": 5, "percent_covered_display": "100"}}}}
    rows, passed = module.evaluate(tmp_path, report)
    assert passed and rows[0]["status"] == "PASS" and "Coverage" in module.markdown(rows)
    report["files"]["src/x.py"]["summary"]["covered_lines"] = 4
    assert not module.evaluate(tmp_path, report)[1]
    report["files"]["src\\x.py"] = report["files"].pop("src/x.py")
    assert not module.evaluate(tmp_path, report)[1]
    with pytest.raises(ValueError):
        module.evaluate(tmp_path, {})
    report_path = tmp_path / "coverage.json"; report_path.write_text(json.dumps(report))
    assert module.main([str(tmp_path), str(report_path)]) == 1
    assert module.main([]) == 2


def test_release_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load("release")
    assert Path(module.git(ROOT, "rev-parse", "--show-toplevel")).resolve() == ROOT.resolve()
    with pytest.raises(RuntimeError):
        module.git(ROOT, "rev-parse", "--verify", "refs/tags/does-not-exist")
    file = tmp_path / "asset.whl"; file.write_bytes(b"wheel")
    manifest_path = tmp_path / "manifest.json"
    manifest = {"assets": [{"name": file.name, "path": str(file), "sha256": module.digest(file), "size": 5}]}
    manifest_path.write_text(json.dumps(manifest))
    assert module.verify(manifest_path) == manifest
    file.write_bytes(b"bad")
    with pytest.raises(RuntimeError):
        module.verify(manifest_path)
    assert module._version(ROOT) == "0.1.0"
    monkeypatch.setattr(module, "verify", lambda _: {"source_commit": "x", "tag": "v1", "assets": [], "version": "1"})
    monkeypatch.setattr(module, "git", lambda *_: "dirty")
    with pytest.raises(RuntimeError):
        module.publish(ROOT, manifest_path)
    with pytest.raises(RuntimeError):
        module.build(ROOT, tmp_path / "dirty-build")
    monkeypatch.setattr(module, "git", lambda root, *args: "x" if args[:2] == ("rev-parse", "HEAD") else ("" if args[0] == "status" else "different"))
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0))
    with pytest.raises(RuntimeError):
        module.publish(ROOT, manifest_path)
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 1 if args[0][0] == "gh" else 0))
    with pytest.raises(RuntimeError):
        module.publish(ROOT, manifest_path)
    monkeypatch.undo()
    module = load("release")
    assert module.main(["verify", "--manifest", str(tmp_path / "missing")]) == 1


def test_release_build_publish_and_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    module = load("release")
    monkeypatch.setattr(module, "git", lambda root, *args: "" if args[0] == "status" else ("abc123" if "short=12" in " ".join(args) else "a" * 40))

    def fake_run(command, cwd=None, **kwargs):
        if "build" in command:
            out = Path(command[command.index("--outdir") + 1])
            (out / "company_harvest-0.1.0-py3-none-any.whl").write_bytes(b"wheel")
            source = out / "source.txt"
            source.write_text("sdist")
            with tarfile.open(out / "company_harvest-0.1.0.tar.gz", "w:gz") as archive:
                archive.add(source, arcname="company_harvest-0.1.0/source.txt")
            source.unlink()
        missing = command[:3] == ["gh", "release", "view"] or command[:3] == ["git", "rev-parse", "--verify"]
        return subprocess.CompletedProcess(command, 1 if missing else 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "qualify_wheel", lambda wheel, root: {"version": "0.1.0", "import_scope": "isolated-site-packages", "status": "PASS"})
    manifest_path = module.build(ROOT, tmp_path)
    manifest = module.verify(manifest_path)
    assert len(manifest["assets"]) == 4
    monkeypatch.setattr(module, "verify", lambda _: {"source_commit": "x", "tag": "v0.1.0", "assets": [], "version": "0.1.0"})
    monkeypatch.setattr(module, "git", lambda root, *args: "x" if args[0] == "rev-parse" else "")
    module.publish(ROOT, manifest_path)
    monkeypatch.setattr(module, "build", lambda *_: manifest_path)
    monkeypatch.setattr(module, "verify", lambda *_: {"ok": True})
    assert module.main(["build", "--output-root", str(tmp_path), "--print-manifest-path"]) == 0
    assert str(manifest_path) in capsys.readouterr().out


def test_release_scan_asset(tmp_path: Path) -> None:
    module = load("release")
    safe = tmp_path / "safe.zip"
    unsafe = tmp_path / "unsafe.zip"
    import zipfile

    with zipfile.ZipFile(safe, "w") as archive:
        archive.writestr("README.md", "safe")
    module.scan_asset(safe)
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("runs/data.csv", "bad")
    with pytest.raises(RuntimeError):
        module.scan_asset(unsafe)
    secret = tmp_path / "secret.zip"
    with zipfile.ZipFile(secret, "w") as archive:
        archive.writestr("config.txt", "ghp_" + "A" * 30)
    with pytest.raises(RuntimeError):
        module.scan_asset(secret)


def test_package_main(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("company_harvest.cli.main", lambda: 0)
    with pytest.raises(SystemExit) as result:
        runpy.run_module("company_harvest.__main__", run_name="__main__")
    assert result.value.code == 0


def test_quality_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load("quality")
    ok = subprocess.CompletedProcess([], 0)
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: ok)
    module.run(["ok"], tmp_path)
    failed = subprocess.CompletedProcess([], 2)
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: failed)
    with pytest.raises(SystemExit):
        module.run(["bad"], tmp_path)
    assert module.main([]) == 2


def test_quality_scan_and_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load("quality")
    completed = subprocess.CompletedProcess([], 0, stdout="safe.py\n")
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: completed)
    module.scan(tmp_path)
    completed.stdout = "runs/data.csv\n"
    with pytest.raises(SystemExit):
        module.scan(tmp_path)
    calls = []
    monkeypatch.setattr(module, "run", lambda command, root, environment=None: calls.append(command))
    monkeypatch.setattr(module, "scan", lambda root: calls.append(["scan"]))
    assert module.main(["check"]) == 0
    assert len(calls) == 7


def test_quality_scan_detects_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load("quality")
    (tmp_path / "unsafe.txt").write_text("ghp_" + "A" * 30)
    completed = subprocess.CompletedProcess([], 0, stdout="unsafe.txt\n")
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: completed)
    with pytest.raises(SystemExit):
        module.scan(tmp_path)
