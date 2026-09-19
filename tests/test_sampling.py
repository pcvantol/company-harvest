import json
from pathlib import Path

import pytest

import company_harvest.sampling as sampling
from company_harvest.cli import build_parser, dispatch
from company_harvest.core import HarvestError, read_tsv, sha256, write_tsv
from company_harvest.sampling import (
    ASSESSMENT_HEADERS,
    _even_allocation,
    build_sample,
    record_sample_review,
)
from company_harvest.sources import CATALOG, RAW_HEADERS, discover


def _row(source_id: str, index: int, name: str, kvk: str = "") -> dict[str, str]:
    return {
        "original_name": name,
        "country": "Nederland",
        "nl_evidence": "fixture",
        "employees_raw": "",
        "employees_date": "",
        "employees_scope": "",
        "website": "",
        "sector": "",
        "source_kvk_hint": kvk,
        "source_id": source_id,
        "source_url": f"https://example.invalid/{source_id}",
        "fetched_at": "2026-09-18T00:00:00+00:00",
        "source_row": str(index),
        "evidence_reference": "fixture",
        "source_registration_raw": kvk,
        "registration_validation_status": "VALID" if kvk else "MISSING",
        "source_legal_form": "Stichting" if index % 2 else "",
        "source_status": "active" if index % 2 else "",
        "candidate_layer": "raw",
    }


def _register_sources(run) -> None:
    discover(run)
    for source_index, source in enumerate(CATALOG):
        rows = [
            _row(source.source_id, 1, f"{source.name} geldig", f"{source_index + 1:08d}"),
            _row(source.source_id, 2, f"{source.name} geldig twee", f"{source_index + 11:08d}"),
            _row(source.source_id, 3, f"{source.name} zonder"),
            _row(source.source_id, 4, f"{source.name} zonder twee"),
        ]
        path = run.artifact_path("02", f"source_{source.source_id}", "csv")
        write_tsv(path, RAW_HEADERS, rows)
        run.register_artifact(path, "02", f"source_{source.source_id}")


def test_r6_sample_is_stratified_deterministic_and_closed(run, tmp_path: Path) -> None:
    _register_sources(run)
    paths = build_sample(run, size=24, review_size=12, pilot_size=6)
    sample = read_tsv(paths[0])
    candidates = read_tsv(paths[1])
    review = read_tsv(paths[4])
    pilot = read_tsv(paths[5])
    report = json.loads(paths[6].read_text(encoding="utf-8"))

    assert len(sample) == 24
    assert len({row["sample_family"] for row in sample}) == 6
    assert {
        (row["sample_family"], row["identifier_stratum"]) for row in sample
    } == {
        (source.source_family, stratum)
        for source in CATALOG
        for stratum in ("VALID_DIRECT", "WITHOUT_DIRECT")
    }
    assert all(
        sum(row["sample_family"] == source.source_family for row in sample) == 4
        for source in CATALOG
    )
    assert report["counts"]["sample_records"] == 24
    assert report["counts"]["valid_direct_registration_numbers"] == 12
    assert report["counts"]["without_direct_registration_number"] == 12
    assert report["count_closure"] == {
        "status": "CLOSED",
        "input": 24,
        "decision_inputs": 24,
        "conflict_inputs": 0,
        "output": 24,
        "delta": 0,
    }
    assert report["review"]["status"] == "PENDING"
    assert len(review) == 12 and len(pilot) == 6
    assert len({row["source_families"] for row in review}) == 6
    assert {row["identifier_stratum"] for row in review} == {
        "VALID_DIRECT",
        "WITHOUT_DIRECT",
    }
    assert all(not row["source_kvk_hint"] for row in pilot)
    assert report["resources"]["evidence_growth_bytes"] == 0
    assert report["r8_metrics_contract"]["threshold_policy"].startswith("set only")

    repeated = build_sample(run, size=24, review_size=12, pilot_size=6)
    assert read_tsv(repeated[0]) == sample
    assert read_tsv(repeated[1]) == candidates
    assert read_tsv(repeated[4]) == review
    assert read_tsv(repeated[5]) == pilot

    assessment = tmp_path / "assessment.tsv"
    queue_hash = sha256(paths[4])
    write_tsv(
        assessment,
        ASSESSMENT_HEADERS,
        [
            {
                "queue_sha256": queue_hash,
                "review_id": row["review_id"],
                "review_verdict": "CONFIRMED",
                "review_notes": "fixture gecontroleerd",
            }
            for row in review
        ],
    )
    assessment_paths = record_sample_review(run, assessment)
    review_report = json.loads(assessment_paths[1].read_text(encoding="utf-8"))
    assert review_report["status"] == "PASS"
    assert review_report["closure"] == "CLOSED"
    assert review_report["reviewed_records"] == 12

    build_sample(run, size=20, review_size=10, pilot_size=5)
    assert run.latest_artifact("03", "r6_review_report") is None
    assert run.metadata()["runtime_config"]["r6_review"]["status"] == "PENDING"


def test_r6_review_prioritizes_merges_and_conflicts(run) -> None:
    _register_sources(run)
    source_paths = []
    with run.connect() as connection:
        source_paths = connection.execute(
            "SELECT path, kind FROM artifacts WHERE step='02' AND kind LIKE 'source_%'"
        ).fetchall()
    first_path = run.path / source_paths[0]["path"]
    second_path = run.path / source_paths[1]["path"]
    first = read_tsv(first_path)
    second = read_tsv(second_path)
    first[0]["original_name"] = "Exact gedeeld"
    first[0]["source_kvk_hint"] = "12345678"
    first[0]["source_registration_raw"] = "12345678"
    second[0]["original_name"] = "Exact gedeeld"
    second[0]["source_kvk_hint"] = "12345678"
    second[0]["source_registration_raw"] = "12345678"
    first[1]["original_name"] = "Conflict naam"
    first[1]["source_kvk_hint"] = "87654321"
    second[1]["original_name"] = " Conflict   naam "
    second[1]["source_kvk_hint"] = "99999999"
    write_tsv(first_path, RAW_HEADERS, first)
    write_tsv(second_path, RAW_HEADERS, second)
    with run.connect() as connection:
        for path in (first_path, second_path):
            connection.execute(
                "UPDATE artifacts SET sha256=?, size=? WHERE path=?",
                (
                    __import__("company_harvest.core", fromlist=["sha256"]).sha256(path),
                    path.stat().st_size,
                    str(path.relative_to(run.path)),
                ),
            )

    paths = build_sample(run, size=20, review_size=5, pilot_size=5)
    report = json.loads(paths[6].read_text(encoding="utf-8"))
    categories = {row["review_category"] for row in read_tsv(paths[4])}
    conflict_reviews = [
        row for row in read_tsv(paths[4]) if row["review_category"] == "CONFLICT_EXCLUDED"
    ]
    assert report["counts"]["identical_merges"] == 1
    assert report["counts"]["conflict_records"] == 2
    assert report["count_closure"]["status"] == "CLOSED"
    assert {"MERGED_IDENTICAL", "CONFLICT_EXCLUDED"} <= categories
    assert len(conflict_reviews) == 1 and conflict_reviews[0]["input_count"] == "2"


def test_r6_validation_and_cli(run, tmp_path: Path, capsys) -> None:
    with pytest.raises(HarvestError, match="geen verzamelde"):
        build_sample(run, 5)
    _register_sources(run)
    assert _even_allocation({"a": 1, "b": 5}, 5) == {"a": 1, "b": 4}
    with pytest.raises(HarvestError, match="positief"):
        build_sample(run, 0)
    with pytest.raises(HarvestError, match="slechts"):
        build_sample(run, 25)
    with pytest.raises(HarvestError, match="R8-pilot"):
        build_sample(run, 20, review_size=5, pilot_size=11)

    args = build_parser().parse_args(
        [
            "companies",
            "sample",
            "--run-dir",
            str(run.path),
            "--size",
            "20",
            "--review-size",
            "5",
            "--pilot-size",
            "5",
        ]
    )
    assert dispatch(args) == 0
    assert "r6_sample_report" in capsys.readouterr().out

    queue = read_tsv(run.latest_artifact("03", "r6_review_queue"))
    incomplete = tmp_path / "incomplete.tsv"
    write_tsv(incomplete, ASSESSMENT_HEADERS, [])
    with pytest.raises(HarvestError, match="mist verplichte"):
        record_sample_review(run, incomplete)
    bad = tmp_path / "bad.tsv"
    queue_hash = sha256(run.latest_artifact("03", "r6_review_queue"))
    write_tsv(
        bad,
        ASSESSMENT_HEADERS,
        [{
            "queue_sha256": queue_hash,
            "review_id": queue[0]["review_id"],
            "review_verdict": "NOPE",
            "review_notes": "",
        }],
    )
    with pytest.raises(HarvestError, match="onbekend verdict"):
        record_sample_review(run, bad)

    false_merge = tmp_path / "false.tsv"
    write_tsv(
        false_merge,
        ASSESSMENT_HEADERS,
        [
            {
                "queue_sha256": queue_hash,
                "review_id": row["review_id"],
                "review_verdict": "FALSE_MERGE" if index == 0 else "CONFIRMED",
                "review_notes": "handmatig",
            }
            for index, row in enumerate(queue)
        ],
    )
    review_args = build_parser().parse_args(
        ["companies", "sample-review", "--run-dir", str(run.path), "--input", str(false_merge)]
    )
    assert dispatch(review_args) == 0
    assert "r6_review_report" in capsys.readouterr().out
    review_report = json.loads(
        run.latest_artifact("03", "r6_review_report").read_text(encoding="utf-8")
    )
    assert review_report["status"] == "CHANGES_REQUIRED"

    queue_path = run.latest_artifact("03", "r6_review_queue")
    queue_path.write_text(queue_path.read_text(encoding="utf-8") + "beschadigd", encoding="utf-8")
    with pytest.raises(HarvestError, match="review_queue"):
        record_sample_review(run, false_merge)

    damaged = run.latest_artifact("02", f"source_{CATALOG[0].source_id}")
    damaged.write_text("beschadigd", encoding="utf-8")
    with pytest.raises(HarvestError, match="wijkt af"):
        build_sample(run, 20)


def test_r6_fingerprint_binds_catalog_family_mapping(run) -> None:
    _register_sources(run)
    first = build_sample(run, 20, review_size=5, pilot_size=5)
    first_report = json.loads(first[6].read_text(encoding="utf-8"))
    catalog_path = run.latest_artifact("01", "sources_inventory")
    rows = read_tsv(catalog_path)
    rows[0]["source_family"] = "gewijzigde-familie"
    write_tsv(catalog_path, list(rows[0]), rows)
    with run.connect() as connection:
        connection.execute(
            "UPDATE artifacts SET sha256=?, size=? WHERE path=?",
            (
                sha256(catalog_path),
                catalog_path.stat().st_size,
                str(catalog_path.relative_to(run.path)),
            ),
        )
    second = build_sample(run, 20, review_size=5, pilot_size=5)
    second_report = json.loads(second[6].read_text(encoding="utf-8"))
    assert first_report["source_artifact_fingerprint"] != second_report[
        "source_artifact_fingerprint"
    ]
    assert second_report["catalog_sha256"] == sha256(catalog_path)


def test_r6_outputset_publication_is_atomic(run, monkeypatch: pytest.MonkeyPatch) -> None:
    _register_sources(run)
    original = sampling.atomic_write
    calls = 0

    def fail_during_publication(path: Path, content: str | bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("publication failed")
        original(path, content)

    monkeypatch.setattr(sampling, "atomic_write", fail_during_publication)
    with pytest.raises(OSError, match="publication failed"):
        build_sample(run, 20, review_size=5, pilot_size=5)
    for kind in (
        "r6_source_sample",
        "r6_candidates",
        "r6_review_queue",
        "r6_sample_report",
    ):
        assert run.latest_artifact("03", kind) is None
    assert run.metadata()["runtime_config"]["r6_sample"]["status"] == "PUBLISHING"
