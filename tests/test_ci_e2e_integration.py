"""Offline CLI-ketenproef voor de expliciete macOS-/Windows-CI-poort."""

from __future__ import annotations

import ipaddress
import json
import socket
from pathlib import Path

import pytest
from openpyxl import load_workbook
from test_pre_kvk import _full_sources, _raw
from test_tenderned import mock_official_download, snapshots

from company_lookup import cli, pre_kvk_kvk, prepare, tenderned
from company_lookup.audit import verify
from company_lookup.core import Run, open_run, read_tsv, sha256, write_tsv
from company_lookup.kvk import ProviderResult, PublicHttpProvider
from company_lookup.sources import RAW_HEADERS
from company_lookup.tenderned import collect_tenderned


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


def _block_nonlocal_connections(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_offline_cli_e2e_from_sources_to_audited_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eén lege run, drie KVK-mocks, eenmanszaak eruit, audit en veilig hervatten."""

    _block_nonlocal_connections(monkeypatch)
    tenderned_xlsx, tenderned_json = snapshots(tmp_path)
    mock_official_download(monkeypatch, tenderned_xlsx, tenderned_json)
    sources: list[str] = []
    monkeypatch.setattr(prepare, "discover", lambda _run: sources.append("discover"))

    def collect_ind(run: Run, **_kwargs: object) -> None:
        sources.append("ind_arbeid")
        _full_sources(run, legacy_scope=False)
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
    def collect_tenderned_fixture(run: Run, **_kwargs: object) -> None:
        sources.append("tenderned_awards")
        collect_tenderned(run)

    monkeypatch.setattr(prepare, "collect_tenderned", collect_tenderned_fixture)
    requests: list[str] = []
    numbers = {
        "45678901": "Aard Klusbedrijf",
        "34567890": "Delta B.V.",
        "56789012": "Tweede Gunning B.V.",
    }

    def mock_kvk_search(provider: PublicHttpProvider, query: str, headed: bool = False) -> ProviderResult:
        assert not headed and query in numbers
        requests.append(query)
        response = {
            "naam": numbers[query],
            "kvkNummer": query,
            "plaats": "Utrecht",
            "land": "Nederland",
            "rechtsvorm": "Eenmanszaak" if query == "45678901" else "Besloten vennootschap",
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
    source_report = run.latest_artifact("03", "pre_kvk_report")
    assert source_report is not None
    assert json.loads(source_report.read_text())["scope"] == [
        "ind_arbeid", "gleif_golden_copy", "anbi_register",
        "duo_education_organisations", "tenderned_awards",
    ]
    assert sources == [
        "discover", "ind_arbeid", "gleif_golden_copy",
        "anbi_register", "duo_education_organisations",
        "tenderned_awards",
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
    assert payload["status"] == "COMPLETE" and payload["schema"] == 2
    assert len(payload["files"]) == 7
    assert payload["kvk_scope"]["selected_rows"] == 3
    assert payload["kvk_scope"]["not_checked_rows"] == 0
    delivery = manifest.parent / "companies_delivery.csv"
    assert {row["KVK-nummer"] for row in read_tsv(delivery)} == {"56789012", "34567890"}
    light = manifest.parent / "companies_delivery_light.csv"
    light_rows = read_tsv(light)
    assert {row["KVK-nummer"] for row in light_rows} == {"56789012", "34567890"}
    assert all(row["Rechtsvorm (KVK)"] == "Besloten vennootschap" and row["Status (KVK)"] == "Actief" for row in light_rows)
    assert all("response_json" not in row and "source_relations" not in row for row in light_rows)
    sheet = load_workbook(manifest.parent / "companies_delivery_light.xlsx")["Bedrijven"]
    assert sheet["B2"].value in {"56789012", "34567890"}
    assert verify(run)["valid"]

    resumed = ["--data-dir", str(tmp_path), "run", "e2e", "--run-dir", str(run_path), "--limit-kvk-check", "3"]
    assert cli.main(resumed) == 0
    capsys.readouterr()
    assert len(requests) == 3
    assert len(sources) == 6  # Afgeronde export bezoekt bronfasen niet opnieuw.
    assert verify(run)["valid"]


def test_cli_e2e_resume_reuses_completed_sources_and_kvk_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Onderbreking na broninname: geen tweede download of dubbel KVK-verzoek."""
    _block_nonlocal_connections(monkeypatch)
    xlsx, json_file = snapshots(tmp_path)
    mock_official_download(monkeypatch, xlsx, json_file)
    original_download = tenderned._download
    downloads: list[str] = []

    def counted_download(url: str, destination: Path, maximum: int) -> dict[str, object]:
        downloads.append(url)
        return original_download(url, destination, maximum)

    monkeypatch.setattr(tenderned, "_download", counted_download)
    source_visits: list[str] = []

    def collect_ind(check_run: Run, **_kwargs: object) -> None:
        source_visits.append("ind")
        if check_run.latest_artifact("02", "source_ind_arbeid") is None:
            _full_sources(check_run, legacy_scope=False)
            original = check_run.latest_artifact("02", "source_ind_arbeid")
            assert original is not None
            expanded = check_run.artifact_path("02", "source_ind_resume", "csv")
            write_tsv(
                expanded, RAW_HEADERS,
                read_tsv(original) + [_raw("ind_arbeid", 4, "Aard Klusbedrijf", "45678901")],
            )
            check_run.register_artifact(expanded, "02", "source_ind_arbeid")
            observations = check_run.metadata()["runtime_config"]["source_observations"]
            observations["ind_arbeid"]["source_artifact"] = {
                "path": str(expanded.relative_to(check_run.path)),
                "sha256": sha256(expanded), "size": expanded.stat().st_size,
            }
            check_run.record_config("source_observations", observations)

    def check_existing(check_run: Run, source_id: str) -> None:
        source_visits.append(source_id)
        assert check_run.latest_artifact("02", f"source_{source_id}") is not None

    monkeypatch.setattr(prepare, "collect", collect_ind)
    monkeypatch.setattr(
        prepare, "collect_gleif",
        lambda check_run, **_kw: check_existing(check_run, "gleif_golden_copy"),
    )
    monkeypatch.setattr(
        prepare, "collect_public_register",
        lambda check_run, source_id, **_kw: check_existing(check_run, source_id),
    )
    requests: list[str] = []

    def search(provider: PublicHttpProvider, query: str) -> ProviderResult:
        requests.append(query)
        if len(requests) == 2:
            raise KeyboardInterrupt
        numbers = {
            "45678901": "Aard Klusbedrijf", "34567890": "Delta B.V.",
            "23456789": "Gamma B.V.", "56789012": "Tweede Gunning B.V.",
            "12345678": "Oude Leverancier B.V.",
        }
        response = {
            "naam": numbers.get(query, "Andere handelsnaam"), "kvkNummer": query,
            "plaats": "Utrecht", "land": "Nederland",
            "rechtsvorm": "Besloten vennootschap", "status": "Actief",
        }
        evidence = provider.run.path / "evidence" / f"resume-{len(requests)}.json"
        evidence.write_text(json.dumps(response), encoding="utf-8")
        return ProviderResult(query, [response], True, "public-http", str(evidence.relative_to(provider.run.path)))

    monkeypatch.setattr(pre_kvk_kvk.PublicHttpProvider, "search", search)
    monkeypatch.setattr(pre_kvk_kvk, "_pace_request", lambda _run, _interval: None)
    command = ["--data-dir", str(tmp_path), "run", "e2e", "--limit-kvk-check", "3", "--interval", "2"]
    assert cli.main(command) == 130
    first_output = capsys.readouterr()
    run_path = Path(json.loads(first_output.out.splitlines()[0])["run_dir"])
    run = open_run(run_path)
    assert len(downloads) == 3 and len(requests) == 2
    source_before = run.latest_artifact("02", "source_tenderned_awards")
    master_before = run.latest_artifact("03", "pre_kvk_master")
    eligible_before = run.latest_artifact("03", "pre_kvk_eligible")
    assert source_before and master_before and eligible_before
    with run.connect() as connection:
        states = connection.execute("SELECT state FROM kvk_requests ORDER BY id").fetchall()
    assert [row["state"] for row in states] == ["SUCCEEDED", "SENT_OUTCOME_UNKNOWN"]

    resumed = [*command[:4], "--run-dir", str(run_path), *command[4:]]
    assert cli.main(resumed) == 3
    capsys.readouterr()
    assert run.latest_artifact("08", "outputset_manifest") is None
    assert len(downloads) == 3
    assert len(source_visits) == 8  # Bronfasen worden gecontroleerd, niet blind overgeslagen.
    assert run.latest_artifact("02", "source_tenderned_awards") == source_before
    assert run.latest_artifact("03", "pre_kvk_master") == master_before
    assert run.latest_artifact("03", "pre_kvk_eligible") == eligible_before
    assert len(requests) == 3 and len(set(requests)) == 3

    resumed_partial = [*resumed, "--allow-partial"]
    assert cli.main(resumed_partial) == 0
    capsys.readouterr()
    assert len(downloads) == 3 and len(requests) == 3 and len(source_visits) == 12
    assert run.metadata()["status"] == "PARTIAL_EXPORTED"
    assert verify(run)["valid"]
    with run.connect() as connection:
        states = connection.execute("SELECT state FROM kvk_requests ORDER BY id").fetchall()
    assert len(states) == 3 and sum(row["state"] == "SENT_OUTCOME_UNKNOWN" for row in states) == 1

    assert cli.main(resumed_partial) == 0
    capsys.readouterr()
    assert len(downloads) == 3 and len(requests) == 3 and len(source_visits) == 12
