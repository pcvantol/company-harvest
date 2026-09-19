"""Offline CLI-ketenproef voor de expliciete macOS-/Windows-CI-poort."""

from __future__ import annotations

import ipaddress
import json
import socket
from pathlib import Path

import pytest
from test_pre_kvk import _full_sources, _raw

from company_harvest import cli, pre_kvk_kvk, prepare
from company_harvest.audit import verify
from company_harvest.core import Run, open_run, read_tsv, sha256, write_tsv
from company_harvest.kvk import ProviderResult, PublicHttpProvider
from company_harvest.sources import RAW_HEADERS


def _local_ipc(family: int, address: object) -> bool:
    if family == getattr(socket, "AF_UNIX", None):
        return True
    if family not in {socket.AF_INET, socket.AF_INET6} or not isinstance(address, tuple):
        return False
    try:
        return ipaddress.ip_address(address[0]).is_loopback
    except (ValueError, TypeError, IndexError):
        return False


def test_network_guard_rejects_nonlocal_connections() -> None:
    assert _local_ipc(socket.AF_INET, ("127.0.0.1", 1))
    assert _local_ipc(socket.AF_INET6, ("::1", 1))
    assert not _local_ipc(socket.AF_INET, ("8.8.8.8", 443))
    assert not _local_ipc(socket.AF_INET, ("example.org", 443))
    assert not _local_ipc(socket.AF_INET, "malformed")


def test_offline_cli_e2e_from_sources_to_audited_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eén lege run, drie KVK-mocks, eenmanszaak eruit, audit en veilig hervatten."""

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded_connect(sock: socket.socket, address: object) -> None:
        if not _local_ipc(sock.family, address):
            pytest.fail("de CI-E2E-proef mag geen externe netwerkverbinding openen")
        original_connect(sock, address)

    def guarded_connect_ex(sock: socket.socket, address: object) -> int:
        if not _local_ipc(sock.family, address):
            pytest.fail("de CI-E2E-proef mag geen externe netwerkverbinding openen")
        return original_connect_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    sources: list[str] = []
    monkeypatch.setattr(prepare, "discover", lambda _run: sources.append("discover"))

    def collect_ind(run: Run, **_kwargs: object) -> None:
        sources.append("ind_arbeid")
        _full_sources(run)
        old = run.latest_artifact("02", "source_ind_arbeid")
        assert old is not None
        updated = run.artifact_path("02", "source_ind_arbeid_ci", "csv")
        write_tsv(
            updated, RAW_HEADERS,
            read_tsv(old) + [_raw("ind_arbeid", 4, "Aard Klusbedrijf", "45678901")],
        )
        run.register_artifact(updated, "02", "source_ind_arbeid")
        observations = run.metadata()["runtime_config"]["source_observations"]
        observations["ind_arbeid"]["source_artifact"] = {
            "path": str(updated.relative_to(run.path)),
            "sha256": sha256(updated),
            "size": updated.stat().st_size,
        }
        run.record_config("source_observations", observations)

    monkeypatch.setattr(prepare, "collect", collect_ind)
    monkeypatch.setattr(
        prepare, "collect_gleif", lambda _run, **_kwargs: sources.append("gleif_golden_copy")
    )
    monkeypatch.setattr(
        prepare, "collect_public_register",
        lambda _run, source, **_kwargs: sources.append(source),
    )
    requests: list[str] = []
    numbers = {
        "Aard Klusbedrijf": "45678901",
        "Delta B.V.": "34567890",
        "Gamma B.V.": "23456789",
    }

    def mock_kvk_search(provider: PublicHttpProvider, query: str, headed: bool = False) -> ProviderResult:
        assert not headed and query in numbers
        requests.append(query)
        response = {
            "naam": query,
            "kvkNummer": numbers[query],
            "plaats": "Utrecht",
            "land": "Nederland",
            "rechtsvorm": "Eenmanszaak" if query == "Aard Klusbedrijf" else "Besloten vennootschap",
            "status": "Actief",
        }
        evidence = provider.run.path / "evidence" / f"ci-kvk-mock-{len(requests)}.json"
        evidence.write_text(json.dumps(response), encoding="utf-8")
        return ProviderResult(query, [response], True, "public-http", str(evidence.relative_to(provider.run.path)))

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", mock_kvk_search)
    command = ["--data-dir", str(tmp_path), "run", "e2e", "--limit-kvk-check", "3"]
    assert cli.main(command) == 0
    run_path = Path(json.loads(capsys.readouterr().out.splitlines()[0])["run_dir"])
    run = open_run(run_path)
    assert sources == [
        "discover", "ind_arbeid", "gleif_golden_copy",
        "anbi_register", "duo_education_organisations",
    ]
    assert set(requests) == set(numbers) and len(requests) == 3
    assert run.metadata()["status"] == "EXPORT_COMPLETE"
    with run.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM kvk_requests").fetchone()[0] == 3
    sole = run.latest_artifact("06", "sole_excluded")
    assert sole is not None
    assert [row["KVK-nummer"] for row in read_tsv(sole)] == ["45678901"]
    manifest = run.latest_artifact("08", "outputset_manifest")
    assert manifest is not None
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["status"] == "COMPLETE" and len(payload["files"]) == 5
    assert payload["kvk_scope"]["selected_rows"] == 3
    assert payload["kvk_scope"]["not_checked_rows"] == 0
    delivery = manifest.parent / "companies_delivery.csv"
    assert {row["KVK-nummer"] for row in read_tsv(delivery)} == {"23456789", "34567890"}
    assert verify(run)["valid"]

    resumed = ["--data-dir", str(tmp_path), "run", "e2e", "--run-dir", str(run_path), "--limit-kvk-check", "3"]
    assert cli.main(resumed) == 0
    capsys.readouterr()
    assert len(requests) == 3
    assert verify(run)["valid"]
