import json
import time
from pathlib import Path
from typing import Any

import pytest

import company_lookup.matching as matching
from company_lookup.cli import build_parser, dispatch
from company_lookup.core import HarvestError, read_tsv, sha256, write_tsv
from company_lookup.kvk import KvkError, ProviderLock, ProviderResult
from company_lookup.matching import (
    REVIEW_VERDICTS,
    _candidate_features,
    _offline_match,
    _public_match,
    _review_queue,
    _website_host,
    record_matching_review,
    run_matching_pilot,
)
from company_lookup.sampling import ASSESSMENT_HEADERS, build_sample, record_sample_review
from company_lookup.sources import CATALOG, RAW_HEADERS, discover


def _source_row(source_id: str, index: int, name: str, kvk: str = "") -> dict[str, str]:
    return {
        "original_name": name,
        "country": "Nederland",
        "nl_evidence": "fixture; plaats=Utrecht",
        "employees_raw": "",
        "employees_date": "",
        "employees_scope": "",
        "website": f"https://{source_id}-{index}.example.invalid",
        "sector": "",
        "source_kvk_hint": kvk,
        "source_id": source_id,
        "source_url": f"https://example.invalid/{source_id}",
        "fetched_at": "2026-09-18T00:00:00+00:00",
        "source_row": str(index),
        "evidence_reference": "fixture",
        "source_registration_raw": kvk,
        "registration_validation_status": "VALID" if kvk else "MISSING",
        "source_legal_form": "",
        "source_status": "",
        "candidate_layer": "raw",
    }


def _prepare_r6(run, pilot_size: int = 5) -> list[dict[str, str]]:
    discover(run)
    for source_index, source in enumerate(CATALOG):
        rows = [
            _source_row(
                source.source_id,
                1,
                f"{source.source_id} geregistreerd",
                f"{source_index + 1:08d}",
            ),
            _source_row(source.source_id, 2, f"{source.source_id} kandidaat alfa"),
            _source_row(source.source_id, 3, f"{source.source_id} kandidaat beta"),
            _source_row(source.source_id, 4, f"{source.source_id} kandidaat gamma"),
        ]
        path = run.artifact_path("02", f"source_{source.source_id}", "csv")
        write_tsv(path, RAW_HEADERS, rows)
        run.register_artifact(path, "02", f"source_{source.source_id}")
    paths = build_sample(run, size=20, review_size=10, pilot_size=pilot_size)
    queue = read_tsv(paths[4])
    assessment = run.path / "r6-assessment.tsv"
    write_tsv(
        assessment,
        ASSESSMENT_HEADERS,
        [
            {
                "queue_sha256": sha256(paths[4]),
                "review_id": row["review_id"],
                "review_verdict": "CONFIRMED",
                "review_notes": "fixture",
            }
            for row in queue
        ],
    )
    record_sample_review(run, assessment)
    return read_tsv(paths[5])


class FakeProvider:
    name = "fake-public"

    def __init__(self, run, modes: list[str]) -> None:
        self.run = run
        self.modes = modes
        self.calls: list[str] = []

    def preflight(self) -> dict[str, Any]:
        return {"available": True}

    def search(self, query: str, headed: bool = False) -> ProviderResult:
        del headed
        index = len(self.calls)
        self.calls.append(query)
        mode = self.modes[index]
        if mode == "BLOCK":
            raise KvkError("PUBLIC_ACCESS_BLOCKED", "fixture geblokkeerd")
        evidence = self.run.path / "evidence" / f"fake-{time.time_ns()}-{index}.json"
        evidence.write_text(json.dumps({"query": query, "mode": mode}), encoding="utf-8")
        hits: list[dict[str, Any]]
        if mode == "MATCH":
            hits = [{"naam": query, "kvkNummer": f"{70000000 + index}", "plaats": "Utrecht"}]
        elif mode == "AMBIGUOUS":
            hits = [{"naam": query, "kvkNummer": f"{70000000 + index}", "plaats": "Rotterdam"}]
        elif mode == "MULTIPLE":
            hits = [
                {"naam": query, "kvkNummer": "70000001", "plaats": "Utrecht"},
                {"naam": query, "kvkNummer": "70000002", "plaats": "Utrecht"},
            ]
        else:
            hits = [{"naam": "Andere organisatie", "kvkNummer": "70000009", "plaats": "Utrecht"}]
        return ProviderResult(
            query,
            hits,
            mode != "TRUNCATED",
            self.name,
            str(evidence.relative_to(self.run.path)),
        )


class NeverCalledProvider(FakeProvider):
    def search(self, query: str, headed: bool = False) -> ProviderResult:
        raise AssertionError(f"journalresultaat had hergebruikt moeten worden voor {query}")


def _r8_assessment(run, verdict: str = "CONFIRMED") -> Path:
    queue_path = run.latest_artifact("04", "r8_review_queue")
    assert queue_path is not None
    assessment = run.path / "r8-assessment.tsv"
    write_tsv(
        assessment,
        ["queue_sha256", "review_id", "review_verdict", "review_seconds", "review_notes"],
        [
            {
                "queue_sha256": sha256(queue_path),
                "review_id": row["review_id"],
                "review_verdict": verdict,
                "review_seconds": "1.5",
                "review_notes": "evidence bekeken",
            }
            for row in read_tsv(queue_path)
        ],
    )
    return assessment


def test_strong_field_matching_and_ambiguity() -> None:
    candidate = {
        "candidate_id": "candidate-1",
        "original_name": "Voorbeeld B.V.",
        "source_families": "fixture",
        "source_relations": "[]",
    }
    features = ({"voorbeeld.nl"}, {"utrecht"})
    complete = ProviderResult(
        "Voorbeeld B.V.",
        [{"naam": "Voorbeeld B.V.", "kvkNummer": "12345678", "plaats": "Utrecht", "status": "Actief"}],
        True,
        "fixture",
        "evidence.json",
    )
    matched = _public_match(candidate, features, complete)
    assert matched["terminal_outcome"] == "MATCHED"
    assert matched["provisional_kvk"] == "12345678"
    assert matched["verification_status"].startswith("PROVISIONAL")
    assert matched["observed_status"] == "Actief"

    name_only = _public_match(candidate, (set(), set()), complete)
    assert name_only["terminal_outcome"] == "AMBIGUOUS"
    assert not name_only["provisional_kvk"]
    no_match = _public_match(
        candidate,
        features,
        ProviderResult("x", [{"naam": "Anders", "kvkNummer": "12345678"}], True, "fixture", "x"),
    )
    assert no_match["terminal_outcome"] == "NO_MATCH"
    truncated = _public_match(candidate, features, ProviderResult("x", [], False, "fixture", "x"))
    assert truncated["terminal_outcome"] == "TECHNICAL_ERROR"
    multiple = _public_match(
        candidate,
        features,
        ProviderResult(
            "x",
            [
                {"naam": "Voorbeeld B.V.", "kvkNummer": "12345678", "plaats": "Utrecht"},
                {"naam": "Voorbeeld B.V.", "kvkNummer": "87654321", "plaats": "Utrecht"},
            ],
            True,
            "fixture",
            "x",
        ),
    )
    assert multiple["terminal_outcome"] == "AMBIGUOUS"
    assert multiple["reason"] == "MULTIPLE_PUBLIC_KVK_CANDIDATES"


def test_offline_matching_features_and_source_conflict() -> None:
    candidate = {
        "candidate_id": "candidate-1",
        "original_name": "Zelfde Naam",
        "source_families": "fixture",
        "source_relations": json.dumps([{"source_id": "a", "row": "1"}]),
    }
    sample = {
        ("a", "1"): {
            "website": "https://www.example.nl/pad",
            "nl_evidence": "bron; plaats=Utrecht",
        }
    }
    assert _website_host("https://www.Example.nl/x") == "example.nl"
    features = _candidate_features(candidate, sample)
    assert features == ({"example.nl"}, {"utrecht"})
    first_row = _source_row("a", 1, "Zelfde Naam", "12345678")
    first_row.update(
        _artifact_path="artifacts/a.csv",
        _artifact_kind="source_a",
        _artifact_sha256="a" * 64,
        _artifact_size="100",
    )
    indexed = {
        "zelfde naam": [first_row]
    }
    indexed["zelfde naam"][0]["website"] = "https://example.nl"
    matched = _offline_match(candidate, features, indexed)
    assert matched and matched["terminal_outcome"] == "MATCHED"
    matched_references = json.loads(matched["evidence_reference"])
    assert len(matched_references) == 1
    assert matched_references[0]["artifact_sha256"] == "a" * 64
    second_row = _source_row("b", 2, "Zelfde Naam", "87654321")
    second_row.update(
        _artifact_path="artifacts/b.csv",
        _artifact_kind="source_b",
        _artifact_sha256="b" * 64,
        _artifact_size="200",
    )
    indexed["zelfde naam"].append(second_row)
    conflict = _offline_match(candidate, features, indexed)
    assert conflict and conflict["terminal_outcome"] == "SOURCE_CONFLICT"
    conflict_references = json.loads(conflict["evidence_reference"])
    assert set(conflict_references) == {"12345678", "87654321"}
    assert conflict_references["87654321"][0]["artifact_path"] == "artifacts/b.csv"
    assert _offline_match(candidate, (set(), set()), indexed) is None


def test_matching_pilot_resume_review_and_cli(run, capsys) -> None:
    pilot = _prepare_r6(run)
    provider = FakeProvider(run, ["MATCH", "AMBIGUOUS", "NO_MATCH", "MATCH", "AMBIGUOUS"])
    paths = run_matching_pilot(
        run,
        provider_name="fake-public",
        interval=0,
        review_size=5,
        provider_override=provider,
    )
    results = read_tsv(paths[0])
    report = json.loads(paths[2].read_text(encoding="utf-8"))
    assert len(results) == len(pilot) == 5
    assert report["metrics"]["terminal_outcome_closure"] is True
    assert report["metrics"]["terminal_counts"] == {
        "AMBIGUOUS": 0,
        "MATCHED": 0,
        "NO_MATCH": 0,
        "SOURCE_CONFLICT": 0,
        "TECHNICAL_ERROR": 5,
    }
    assert report["resources"]["evidence_bytes"] == 0
    assert report["live_calls"] == 0 and provider.calls == []
    assert {row["reason"] for row in results} == {"NO_DIRECT_KVK_HINT"}
    assert all(not row["provisional_kvk"] for row in results if row["terminal_outcome"] != "MATCHED")

    resumed = run_matching_pilot(
        run,
        provider_name="fake-public",
        interval=0,
        review_size=5,
        provider_override=NeverCalledProvider(run, []),
    )
    assert read_tsv(resumed[0]) == results
    resumed_report = json.loads(resumed[2].read_text(encoding="utf-8"))
    assert resumed_report["resources"]["evidence_bytes"] == report["resources"]["evidence_bytes"]

    review_paths = record_matching_review(run, _r8_assessment(run))
    review_report = json.loads(review_paths[1].read_text(encoding="utf-8"))
    assert review_report["status"] == "CHANGES_REQUIRED"
    assert review_report["pilot_decision"] != "GO_R9_METRICS"
    assert review_report["r9_thresholds"]["status"] == "NOT_SET_UNSUCCESSFUL_PILOT"
    assert review_report["review_seconds_total"] == 7.5
    assert REVIEW_VERDICTS == {"CONFIRMED", "FALSE_MATCH", "UNCERTAIN"}

    run_matching_pilot(
        run,
        provider_name="fake-public",
        interval=0,
        review_size=5,
        provider_override=NeverCalledProvider(run, []),
    )
    assert run.latest_artifact("04", "r8_review_report") is None
    assert run.metadata()["runtime_config"]["r8_review"]["status"] == "PENDING"
    with run.connect() as connection:
        current_counts = dict(
            connection.execute(
                "SELECT kind,count(*) FROM artifacts WHERE step='04' AND status='COMPLETE' "
                "AND kind LIKE 'r8_%' GROUP BY kind"
            ).fetchall()
        )
    assert set(current_counts.values()) == {1}

    args = build_parser().parse_args(
        ["kvk", "pilot-review", "--run-dir", str(run.path), "--input", str(_r8_assessment(run))]
    )
    assert dispatch(args) == 0
    assert "r8_review_report" in capsys.readouterr().out


def test_matching_pilot_stops_after_block_and_rejects_bad_review(run, tmp_path: Path) -> None:
    _prepare_r6(run)
    provider = FakeProvider(run, ["BLOCK"])
    paths = run_matching_pilot(
        run,
        provider_name="fake-public",
        interval=0,
        review_size=5,
        provider_override=provider,
    )
    report = json.loads(paths[2].read_text(encoding="utf-8"))
    assert len(provider.calls) == 0
    assert report["metrics"]["terminal_counts"]["TECHNICAL_ERROR"] == 5
    assert {row["reason"] for row in read_tsv(paths[0])} == {"NO_DIRECT_KVK_HINT"}
    review_report = json.loads(record_matching_review(run, _r8_assessment(run))[1].read_text())
    assert review_report["status"] == "CHANGES_REQUIRED"
    assert review_report["r9_thresholds"]["status"] == "NOT_SET_UNSUCCESSFUL_PILOT"

    resumed_provider = FakeProvider(run, ["NO_MATCH"] * 5)
    resumed_paths = run_matching_pilot(
        run,
        provider_name="fake-public",
        interval=0,
        review_size=5,
        provider_override=resumed_provider,
    )
    assert len(resumed_provider.calls) == 0
    assert {
        row["terminal_outcome"] for row in read_tsv(resumed_paths[0])
    } == {"TECHNICAL_ERROR"}
    assert run.latest_artifact("04", "r8_review_report") is None

    queue_path = run.latest_artifact("04", "r8_review_queue")
    assert queue_path is not None
    queue = read_tsv(queue_path)
    bad = tmp_path / "bad.tsv"
    write_tsv(
        bad,
        ["queue_sha256", "review_id", "review_verdict", "review_seconds", "review_notes"],
        [{
            "queue_sha256": "wrong",
            "review_id": queue[0]["review_id"],
            "review_verdict": "CONFIRMED",
            "review_seconds": "1",
            "review_notes": "",
        }],
    )
    with pytest.raises(HarvestError, match="actuele queue"):
        record_matching_review(run, bad)
    with pytest.raises(HarvestError, match="livelimieten"):
        run_matching_pilot(run, interval=-1)


def test_source_fingerprint_invalidates_journal_and_binds_offline_evidence(run) -> None:
    pilot = _prepare_r6(run)
    first_provider = FakeProvider(run, ["NO_MATCH"] * 5)
    first_paths = run_matching_pilot(
        run,
        provider_name="fake-public",
        interval=0,
        review_size=5,
        provider_override=first_provider,
    )
    first_report = json.loads(first_paths[2].read_text(encoding="utf-8"))

    source_kind = "source_ind_arbeid"
    old_source = run.latest_artifact("02", source_kind)
    assert old_source is not None
    new_rows = read_tsv(old_source)
    new_rows.append(_source_row("ind_arbeid", 99, pilot[0]["original_name"], "81234567"))
    new_source = run.artifact_path("02", source_kind, "csv")
    write_tsv(new_source, RAW_HEADERS, new_rows)
    run.register_artifact(new_source, "02", source_kind)

    second_provider = FakeProvider(run, ["NO_MATCH"] * 4)
    second_paths = run_matching_pilot(
        run,
        provider_name="fake-public",
        interval=0,
        review_size=5,
        provider_override=second_provider,
    )
    second_report = json.loads(second_paths[2].read_text(encoding="utf-8"))
    assert len(second_provider.calls) == 0
    assert second_report["source_artifacts_fingerprint"] != first_report[
        "source_artifacts_fingerprint"
    ]
    assert run.metadata()["runtime_config"]["r8_matching"][
        "source_artifacts_fingerprint"
    ] == second_report["source_artifacts_fingerprint"]
    offline = [
        row for row in read_tsv(second_paths[0]) if row["provider"] == "collected-sources"
    ]
    assert len(offline) == 1 and offline[0]["provisional_kvk"] == "81234567"
    reference = json.loads(offline[0]["evidence_reference"])[0]
    assert reference == {
        "artifact_kind": source_kind,
        "artifact_path": str(new_source.relative_to(run.path)),
        "artifact_sha256": sha256(new_source),
        "artifact_size": new_source.stat().st_size,
        "source_id": "ind_arbeid",
        "source_row": "99",
    }


def test_live_limit_queue_allocation_and_prerequisite_checks(run) -> None:
    with pytest.raises(HarvestError, match="complete en beoordeelde"):
        run_matching_pilot(run, provider_override=FakeProvider(run, []), interval=0)
    _prepare_r6(run)
    paths = run_matching_pilot(
        run,
        provider_name="fake-public",
        interval=0,
        max_live=0,
        review_size=3,
        provider_override=FakeProvider(run, []),
    )
    rows = read_tsv(paths[0])
    assert len(rows) == 5
    assert {row["reason"] for row in rows} == {"NO_DIRECT_KVK_HINT"}
    assert len(read_tsv(paths[1])) == 3
    assert len(_review_queue(rows, 2)) == 2


@pytest.mark.parametrize("invalid_interval", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_interval_is_rejected_before_provider_call(run, invalid_interval: float) -> None:
    provider = FakeProvider(run, ["MATCH"])
    with pytest.raises(HarvestError, match="livelimieten"):
        run_matching_pilot(run, interval=invalid_interval, provider_override=provider)
    assert provider.calls == []


def test_real_provider_interval_cannot_disable_rate_limit(run) -> None:
    with pytest.raises(HarvestError, match="livelimieten"):
        run_matching_pilot(run, interval=0)


def test_pilot_publication_rolls_back_as_a_set(run, monkeypatch: pytest.MonkeyPatch) -> None:
    old = run.artifact_path("04", "r8_matching_report", "json")
    old.write_text("{}", encoding="utf-8")
    run.register_artifact(old, "04", "r8_matching_report")
    first = run.artifact_path("04", "r8_matching_results", "csv")
    second = run.artifact_path("04", "r8_review_queue", "csv")
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    real_sha256 = matching.sha256

    def fail_second(path: Path) -> str:
        if path == second:
            raise OSError("publication fixture")
        return real_sha256(path)

    monkeypatch.setattr(matching, "sha256", fail_second)
    with pytest.raises(OSError, match="publication fixture"):
        matching._publish_pilot_outputset(
            run,
            [
                (first, "04", "r8_matching_results", "COMPLETE"),
                (second, "04", "r8_review_queue", "COMPLETE"),
            ],
        )
    assert run.latest_artifact("04", "r8_matching_report") == old
    assert run.latest_artifact("04", "r8_matching_results") is None


def test_refresh_lock_failure_preserves_journal(run) -> None:
    _prepare_r6(run)
    run_matching_pilot(
        run,
        provider_name="fake-public",
        interval=0,
        max_live=0,
        review_size=5,
        provider_override=FakeProvider(run, []),
    )
    with run.connect() as connection:
        before = connection.execute(
            "SELECT candidate_id,state,result_json FROM kvk_requests "
            "WHERE candidate_id LIKE 'r8:%' ORDER BY candidate_id"
        ).fetchall()
    with ProviderLock(run):
        with pytest.raises(KvkError, match="vergrendeld"):
            run_matching_pilot(
                run,
                provider_name="fake-public",
                interval=0,
                refresh=True,
                review_size=5,
                provider_override=FakeProvider(run, []),
            )
    with run.connect() as connection:
        after = connection.execute(
            "SELECT candidate_id,state,result_json FROM kvk_requests "
            "WHERE candidate_id LIKE 'r8:%' ORDER BY candidate_id"
        ).fetchall()
    assert [tuple(row) for row in after] == [tuple(row) for row in before]


def test_active_cooldown_makes_no_provider_calls_and_closes(run) -> None:
    _prepare_r6(run)
    provider = FakeProvider(run, ["MATCH"] * 5)
    with run.connect() as connection:
        connection.execute(
            "INSERT INTO cooldowns(provider,until_epoch,reason) VALUES('kvk',?,?)",
            (time.time() + 60, "fixture cooldown"),
        )
    paths = run_matching_pilot(
        run,
        provider_name="fake-public",
        interval=0,
        review_size=5,
        provider_override=provider,
    )
    assert provider.calls == []
    rows = read_tsv(paths[0])
    assert len(rows) == 5
    assert {row["terminal_outcome"] for row in rows} == {"TECHNICAL_ERROR"}
    assert {row["reason"] for row in rows} == {"NO_DIRECT_KVK_HINT"}


@pytest.mark.parametrize("invalid_seconds", ["nan", "inf", "-inf"])
def test_review_rejects_non_finite_seconds(run, tmp_path: Path, invalid_seconds: str) -> None:
    _prepare_r6(run)
    run_matching_pilot(
        run,
        provider_name="fake-public",
        interval=0,
        max_live=0,
        review_size=5,
        provider_override=FakeProvider(run, []),
    )
    queue_path = run.latest_artifact("04", "r8_review_queue")
    assert queue_path is not None
    queue = read_tsv(queue_path)
    assessment = tmp_path / f"non-finite-{invalid_seconds}.tsv"
    write_tsv(
        assessment,
        ["queue_sha256", "review_id", "review_verdict", "review_seconds", "review_notes"],
        [
            {
                "queue_sha256": sha256(queue_path),
                "review_id": row["review_id"],
                "review_verdict": "CONFIRMED",
                "review_seconds": invalid_seconds if index == 0 else "1",
                "review_notes": "fixture",
            }
            for index, row in enumerate(queue)
        ],
    )
    with pytest.raises(HarvestError, match="ongeldige tijd"):
        record_matching_review(run, assessment)
