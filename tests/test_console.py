"""Menselijke CLI-logregels zonder bedrijfsdata of stdout-vervuiling."""

import ctypes
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from company_harvest import cli, console
from company_harvest.core import HarvestError, Run


def test_console_color_and_no_color(monkeypatch: pytest.MonkeyPatch,
                                    capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    console.emit("INFO", "Buiten CLI")
    assert capsys.readouterr().err == ""
    with console.active():
        console.emit("START", "Bronnen verzamelen", count=2, total=5)
    colored = capsys.readouterr().err
    assert "\x1b[" in colored and "2/5" in colored and "Bronnen verzamelen" in colored
    monkeypatch.setenv("NO_COLOR", "")
    with console.active():
        console.emit("OK", "Gereed")
    assert "\x1b[" not in capsys.readouterr().err
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("FORCE_COLOR", "0")
    with console.active():
        console.emit("WARN", "Gepauzeerd")
    assert "\x1b[" not in capsys.readouterr().err


def test_windows_vt_is_enabled_or_falls_back_without_escape_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    modes: list[int] = []

    class Function:
        def __init__(self, operation: object) -> None:
            self.operation = operation
            self.argtypes: object = None
            self.restype: object = None

        def __call__(self, *args: object) -> object:
            return self.operation(*args)  # type: ignore[operator]

    def get_handle(number: int) -> int:
        assert number == -12
        return 0x123456789

    def get_mode(handle: int, pointer: object) -> int:
        assert handle == 0x123456789
        pointer._obj.value = 0x0001  # type: ignore[attr-defined]
        return 1

    def set_mode(handle: int, mode: int) -> int:
        assert handle == 0x123456789
        modes.append(mode)
        return 1

    kernel = SimpleNamespace(GetStdHandle=Function(get_handle),
                             GetConsoleMode=Function(get_mode),
                             SetConsoleMode=Function(set_mode))
    fake = SimpleNamespace(WinDLL=lambda *_args, **_kwargs: kernel,
                           c_uint=ctypes.c_uint, c_ulong=ctypes.c_ulong,
                           c_void_p=ctypes.c_void_p, c_int=ctypes.c_int,
                           POINTER=ctypes.POINTER, byref=ctypes.byref)
    monkeypatch.setattr(console, "ctypes", fake)
    assert console._enable_windows_vt()
    assert modes == [0x0005]
    assert kernel.GetStdHandle.restype is ctypes.c_void_p
    monkeypatch.setattr(fake, "WinDLL", lambda *_args, **_kwargs: None)
    assert not console._enable_windows_vt()


def test_phase_and_result_never_copy_record_data(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    with console.active():
        with console.phase("Pre-KVK-filter"):
            console.result({"status": "PARTIAL_EXPORTED", "delivery_rows": 3,
                            "audit_valid": True, "original_name": "GEHEIME BEDRIJFSNAAM",
                            "kvk_number": "12345678", "delivery_csv": "/private/naam.csv"})
        console.result([{"original_name": "GEHEIME BEDRIJFSNAAM"}])
        console.result(tmp_path / "uitvoer.csv")
        console.result({"status": "GEHEIM"})
        console.result("GEHEIME BEDRIJFSNAAM")
        with pytest.raises(HarvestError):
            with console.phase("Mislukte stap"):
                raise HarvestError("GEHEIME BEDRIJFSNAAM")
    output = capsys.readouterr().err
    assert "PARTIAL_EXPORTED" in output and "delivery_rows=3" in output
    assert "Resultaatitems" in output and "Resultaatbestand" in output
    assert "Mislukte stap gestopt" in output
    assert "GEHEIM" not in output and "12345678" not in output and "/private/" not in output


def test_only_known_audit_events_and_counts_are_mirrored(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with console.active():
        console.audit_event("INFO", "source_collect_completed",
                            {"count": 12, "query": "GEHEIME BEDRIJFSNAAM"})
        console.audit_event("WARNING", "audit_verify", {"checked_artifacts": 4,
                                                          "errors": ["GEHEIME BEDRIJFSNAAM"]})
        console.audit_event("INFO", "unlisted_event", {"count": 999})
        console.audit_event("INFO", "source_collect_started", {"source_id": "GEHEIM"})
    output = capsys.readouterr().err
    assert "Broninname afgerond" in output and "12" in output
    assert "Audit uitgevoerd" in output and "4" in output
    assert "GEHEIME" not in output and "999" not in output and "GEHEIM" not in output


@pytest.mark.parametrize(("command", "service"), [
    (["doctor"], "host"),
    (["run", "status"], "metadata"),
    (["sources", "discover"], "discover"),
    (["companies", "merge"], "merge_candidates"),
    (["kvk", "preflight"], "kvk_preflight"),
    (["export"], "export"),
    (["report"], "report"),
    (["audit", "verify"], "verify"),
])
def test_all_command_families_log_safe_progress(
    command: list[str], service: str, run: Run, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if service == "metadata":
        monkeypatch.setattr(Run, "metadata", lambda self: {"status": "IN_PROGRESS",
                                                      "original_name": "GEHEIME BEDRIJFSNAAM"})
    else:
        monkeypatch.setattr(cli, service, lambda *_args: {
            "status": "COMPLETE", "count": 2, "original_name": "GEHEIME BEDRIJFSNAAM"
        })
    args = [*command, "--run-dir", str(run.path)] if command != ["doctor"] else command
    assert cli.main(args) == 0
    output = capsys.readouterr()
    assert "GEHEIME BEDRIJFSNAAM" in output.out
    assert "GEHEIME BEDRIJFSNAAM" not in output.err
    assert "START" in output.err and "STEP" in output.err and "OK" in output.err
    assert "Resultaat:" in output.err


def test_cli_error_and_interrupt_are_formatted(
    run: Run, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "discover", lambda _run: (_ for _ in ()).throw(HarvestError("bronfout", 5)))
    args = ["sources", "discover", "--run-dir", str(run.path)]
    assert cli.main(args) == 5
    error = capsys.readouterr().err
    assert "FOUT" in error and "exitcode 5" in error and "Bron- of invoerprobleem" in error
    monkeypatch.setattr(cli, "discover", lambda _run: (_ for _ in ()).throw(KeyboardInterrupt))
    assert cli.main(args) == 130
    interrupted = capsys.readouterr().err
    assert "WARN" in interrupted and "ONDERBROKEN" in interrupted


def test_cli_invalid_options_and_unexpected_errors_are_safe(
    run: Run, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as parse_error:
        cli.main(["geen-commando"])
    assert parse_error.value.code == 2
    assert "FOUT" in capsys.readouterr().err
    with pytest.raises(SystemExit) as missing_option:
        cli.main(["run", "status"])
    assert missing_option.value.code == 2
    assert "bij --run-dir" in capsys.readouterr().err
    with pytest.raises(SystemExit) as invalid_value:
        cli.main(["run", "init", "--target", "GEHEIME BEDRIJFSNAAM"])
    assert invalid_value.value.code == 2
    parser_output = capsys.readouterr().err
    assert "bij --target" in parser_output and "GEHEIME BEDRIJFSNAAM" not in parser_output
    monkeypatch.setattr(cli, "discover", lambda _run: (_ for _ in ()).throw(ValueError("GEHEIME BEDRIJFSNAAM")))
    assert cli.main(["sources", "discover", "--run-dir", str(run.path)]) == 1
    output = capsys.readouterr().err
    assert "Onverwachte technische fout" in output and "ValueError" in output
    assert "GEHEIME BEDRIJFSNAAM" not in output


def test_cli_missing_trace_does_not_log_kvk_number(
    run: Run, capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["audit", "trace", "--run-dir", str(run.path),
                     "--kvk-number", "99999999"]) == 5
    output = capsys.readouterr().err
    assert "Geen trace gevonden" in output
    assert "opgegeven KVK-nummer" in output
    assert "99999999" not in output


def test_known_errors_never_echo_sheet_or_path_data(
    run: Run, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    args = ["companies", "merge-lists", "--left", "left.csv", "--right", "right.csv",
            "--run-dir", str(run.path)]
    for text in ("werkblad ontbreekt: GEHEIME BEDRIJFSNAAM",
                 "inputbestand ontbreekt: /private/GEHEIME BEDRIJFSNAAM.csv"):
        monkeypatch.setattr(cli, "merge_lists", lambda *_args, text=text: (
            _ for _ in ()).throw(HarvestError(text)))
        assert cli.main(args) == 3
        output = capsys.readouterr().err
        assert "Ongeldige invoer of runstatus" in output
        assert "GEHEIME BEDRIJFSNAAM" not in output


def test_unexpected_entrypoint_error_has_no_raw_traceback() -> None:
    script = ("from company_harvest import cli; "
              "cli.dispatch=lambda args: (_ for _ in ()).throw(ValueError('GEHEIME BEDRIJFSNAAM')); "
              "raise SystemExit(cli.main(['doctor']))")
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                               check=False)
    assert completed.returncode == 1
    assert "ValueError" in completed.stderr and "FOUT" in completed.stderr
    assert "GEHEIME BEDRIJFSNAAM" not in completed.stderr and "Traceback" not in completed.stderr
