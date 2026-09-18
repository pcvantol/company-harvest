"""Deterministic, stratified R6 source and deduplication sampling."""

from __future__ import annotations

import hashlib
import heapq
import json
import time
import tracemalloc
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from company_harvest.core import (
    HarvestError,
    Run,
    atomic_write,
    normalize_name,
    read_tsv,
    sha256,
    validate_kvk,
    write_tsv,
)
from company_harvest.sources import RAW_HEADERS, read_catalog
from company_harvest.workflow import _deduplicate_rows, _missing_source_status

SAMPLE_SCHEMA_VERSION = 1
DEFAULT_SAMPLE_SIZE = 500
DEFAULT_REVIEW_SIZE = 25
DEFAULT_PILOT_SIZE = 50
CANDIDATE_HEADERS = [
    "candidate_id",
    "original_name",
    "normalized_name",
    "source_kvk_hint",
    "country",
    "city",
    "website",
    "sector",
    "source_relations",
]
DECISION_HEADERS = ["candidate_id", "decision", "input_count", "names"]
CONFLICT_HEADERS = ["original_name", "source_id", "reason", "source_kvk_hint"]
REVIEW_HEADERS = [
    "review_id",
    "review_category",
    "source_families",
    "identifier_stratum",
    "candidate_id",
    "names",
    "source_ids",
    "kvk_hints",
    "proposed_decision",
    "input_count",
    "review_verdict",
    "review_notes",
]
ASSESSMENT_HEADERS = ["queue_sha256", "review_id", "review_verdict", "review_notes"]
ALLOWED_VERDICTS = {"CONFIRMED", "FALSE_MERGE", "UNCERTAIN"}


def _latest_sources(run: Run) -> list[tuple[Path, str, str]]:
    with run.connect() as connection:
        rows = connection.execute(
            """
            SELECT path, kind, sha256 FROM artifacts
            WHERE id IN (
              SELECT MAX(id) FROM artifacts
              WHERE step='02' AND kind LIKE 'source_%' AND path LIKE '%.csv'
                AND status='COMPLETE'
              GROUP BY kind
            ) ORDER BY kind
            """
        ).fetchall()
    return [(run.path / row["path"], str(row["kind"]), str(row["sha256"])) for row in rows]


def _latest_catalog(run: Run) -> tuple[Path, str]:
    with run.connect() as connection:
        row = connection.execute(
            "SELECT path, sha256 FROM artifacts "
            "WHERE step='01' AND kind='sources_inventory' AND status='COMPLETE' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise HarvestError("geen broncatalogus; voer eerst sources discover uit")
    return run.path / row["path"], str(row["sha256"])


def _require_registered_integrity(run: Run, path: Path, step: str, kind: str) -> str:
    with run.connect() as connection:
        row = connection.execute(
            "SELECT sha256, size FROM artifacts "
            "WHERE path=? AND step=? AND kind=? AND status='COMPLETE'",
            (str(path.relative_to(run.path)), step, kind),
        ).fetchone()
    if (
        row is None
        or not path.is_file()
        or path.stat().st_size != row["size"]
        or sha256(path) != row["sha256"]
    ):
        raise HarvestError(f"geregistreerd artefact {kind} ontbreekt of wijkt af")
    return str(row["sha256"])


def _iter_rows(paths: list[tuple[Path, str, str]]) -> Iterator[dict[str, str]]:
    for path, _kind, _digest in paths:
        yield from read_tsv(path)


def _identifier_stratum(row: dict[str, str]) -> str:
    try:
        validate_kvk(row.get("source_kvk_hint"))
    except ValueError:
        return "WITHOUT_DIRECT"
    return "VALID_DIRECT"


def _even_allocation(capacities: dict[str, int], requested: int) -> dict[str, int]:
    """Allocate one item per sorted stratum per round, redistributing unused capacity."""
    allocation = {key: 0 for key in sorted(capacities)}
    remaining = min(requested, sum(capacities.values()))
    while remaining:
        eligible = [key for key in allocation if allocation[key] < capacities[key]]
        if not eligible:
            break
        for key in eligible:
            if not remaining:
                break
            allocation[key] += 1
            remaining -= 1
    return allocation


def _selection_hash(row: dict[str, str]) -> str:
    material = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode()).hexdigest()


def _sample_rows(
    paths: list[tuple[Path, str, str]],
    families: dict[str, str],
    size: int,
) -> tuple[list[dict[str, str]], dict[str, int], dict[str, int]]:
    group_capacities: Counter[str] = Counter()
    family_capacities: Counter[str] = Counter()
    for row in _iter_rows(paths):
        family = families.get(row.get("source_id", ""), "unclassified")
        stratum = f"{family}|{_identifier_stratum(row)}"
        group_capacities[stratum] += 1
        family_capacities[family] += 1
    if not group_capacities:
        raise HarvestError("geen bronrecords beschikbaar voor R6-sampling")
    if sum(group_capacities.values()) < size:
        raise HarvestError(
            f"R6 vereist {size} bronrecords; slechts {sum(group_capacities.values())} beschikbaar"
        )

    family_allocation = _even_allocation(dict(family_capacities), size)
    group_allocation: dict[str, int] = {}
    for family, family_size in family_allocation.items():
        capacities = {
            key: count for key, count in group_capacities.items() if key.startswith(f"{family}|")
        }
        group_allocation.update(_even_allocation(capacities, family_size))

    heaps: dict[str, list[tuple[int, str, int, dict[str, str]]]] = defaultdict(list)
    ordinal = 0
    for row in _iter_rows(paths):
        family = families.get(row.get("source_id", ""), "unclassified")
        stratum = f"{family}|{_identifier_stratum(row)}"
        quota = group_allocation.get(stratum, 0)
        if not quota:
            continue
        digest = _selection_hash(row)
        entry = (-int(digest, 16), digest, ordinal, row)
        ordinal += 1
        if len(heaps[stratum]) < quota:
            heapq.heappush(heaps[stratum], entry)
        elif entry > heaps[stratum][0]:
            heapq.heapreplace(heaps[stratum], entry)

    selected: list[dict[str, str]] = []
    for stratum in sorted(heaps):
        family, identifier = stratum.rsplit("|", 1)
        entries = sorted(heaps[stratum], key=lambda item: (item[1], item[2]))
        for _negative, digest, _ordinal, row in entries:
            selected.append(
                {
                    **{header: row.get(header, "") for header in RAW_HEADERS},
                    "sample_family": family,
                    "identifier_stratum": identifier,
                    "selection_hash": digest,
                }
            )
    selected.sort(
        key=lambda row: (row["sample_family"], row["identifier_stratum"], row["selection_hash"])
    )
    for index, row in enumerate(selected, 1):
        row["sample_rank"] = str(index)
    return selected, dict(group_capacities), group_allocation


def _review_queue(
    candidates: list[dict[str, str]],
    decisions: list[dict[str, str]],
    conflicts: list[dict[str, str]],
    families: dict[str, str],
    size: int,
) -> list[dict[str, str]]:
    by_candidate = {row["candidate_id"]: row for row in candidates}
    items: list[dict[str, str]] = []
    for decision in decisions:
        candidate = by_candidate[decision["candidate_id"]]
        relations = json.loads(candidate["source_relations"])
        source_ids = sorted({str(relation["source_id"]) for relation in relations})
        category = decision["decision"]
        item = {
            "review_category": category,
            "source_families": "+".join(
                sorted({families.get(source_id, "unclassified") for source_id in source_ids})
            ),
            "identifier_stratum": (
                "VALID_DIRECT" if candidate["source_kvk_hint"] else "WITHOUT_DIRECT"
            ),
            "candidate_id": decision["candidate_id"],
            "names": decision["names"],
            "source_ids": json.dumps(source_ids, ensure_ascii=False),
            "kvk_hints": json.dumps(
                sorted({candidate["source_kvk_hint"]} - {""}), ensure_ascii=False
            ),
            "proposed_decision": decision["decision"],
            "input_count": decision["input_count"],
            "review_verdict": "",
            "review_notes": "",
        }
        item["review_id"] = hashlib.sha256(
            ("decision\0" + decision["candidate_id"]).encode()
        ).hexdigest()[:20]
        items.append(item)

    grouped_conflicts: dict[str, list[dict[str, str]]] = defaultdict(list)
    for conflict in conflicts:
        grouped_conflicts[normalize_name(conflict["original_name"])].append(conflict)
    for normalized, rows in grouped_conflicts.items():
        source_ids = sorted({row["source_id"] for row in rows})
        item = {
            "review_category": "CONFLICT_EXCLUDED",
            "source_families": "+".join(
                sorted({families.get(source_id, "unclassified") for source_id in source_ids})
            ),
            "identifier_stratum": "VALID_DIRECT",
            "candidate_id": "",
            "names": json.dumps(sorted({row["original_name"] for row in rows}), ensure_ascii=False),
            "source_ids": json.dumps(source_ids, ensure_ascii=False),
            "kvk_hints": json.dumps(
                sorted({row["source_kvk_hint"] for row in rows if row["source_kvk_hint"]}),
                ensure_ascii=False,
            ),
            "proposed_decision": "CONFLICT_EXCLUDED",
            "input_count": str(len(rows)),
            "review_verdict": "",
            "review_notes": "",
        }
        item["review_id"] = hashlib.sha256(("conflict\0" + normalized).encode()).hexdigest()[:20]
        items.append(item)

    significant = [item for item in items if item["review_category"] != "KEPT_SINGLE"]
    singles = [item for item in items if item["review_category"] == "KEPT_SINGLE"]
    significant.sort(key=lambda item: item["review_id"])
    singles.sort(key=lambda item: item["review_id"])

    def stratified(items: list[dict[str, str]], requested: int) -> list[dict[str, str]]:
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for item in items:
            key = "|".join(
                (
                    item["review_category"],
                    item["source_families"],
                    item["identifier_stratum"],
                )
            )
            groups[key].append(item)
        allocation = _even_allocation({key: len(rows) for key, rows in groups.items()}, requested)
        return [
            item
            for key in sorted(groups)
            for item in groups[key][: allocation.get(key, 0)]
        ]

    if len(significant) >= size:
        chosen = stratified(significant, size)
    else:
        chosen = significant + stratified(singles, size - len(significant))
    return sorted(
        chosen,
        key=lambda item: (
            item["review_category"],
            item["source_families"],
            item["identifier_stratum"],
            item["review_id"],
        ),
    )


def _pilot_pool(
    candidates: list[dict[str, str]], families: dict[str, str], size: int
) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for candidate in candidates:
        if candidate["source_kvk_hint"]:
            continue
        relations = json.loads(candidate["source_relations"])
        candidate_families = sorted(
            {families.get(str(relation["source_id"]), "unclassified") for relation in relations}
        )
        group = "+".join(candidate_families)
        groups[group].append(candidate)
    allocation = _even_allocation({key: len(rows) for key, rows in groups.items()}, size)
    selected: list[dict[str, str]] = []
    for group in sorted(groups):
        rows = sorted(
            groups[group],
            key=lambda row: hashlib.sha256(("r8\0" + row["candidate_id"]).encode()).hexdigest(),
        )[: allocation[group]]
        for row in rows:
            selected.append(
                {
                    **row,
                    "source_families": group,
                    "pilot_hash": hashlib.sha256(
                        ("r8\0" + row["candidate_id"]).encode()
                    ).hexdigest(),
                }
            )
    selected.sort(key=lambda row: (row["source_families"], row["pilot_hash"]))
    for index, row in enumerate(selected, 1):
        row["pilot_rank"] = str(index)
    return selected


def _file_bytes(paths: list[Path]) -> int:
    return sum(path.stat().st_size for path in paths)


def _sqlite_allocated_bytes(run: Run) -> int:
    with run.connect() as connection:
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
    return page_count * page_size


def _publish_sample_outputset(
    run: Run,
    entries: list[tuple[Path, str, str, str]],
    report_path: Path,
    report: dict[str, Any],
    sqlite_before: int,
) -> None:
    """Publish outputs, review invalidation and downstream invalidation in one transaction."""
    created_at = datetime.now(UTC).isoformat()
    with run.connect() as connection:
        connection.executemany(
            "UPDATE artifacts SET status='STALE' "
            "WHERE step=? AND kind=? AND status IN ('COMPLETE','PARTIAL')",
            [
                ("03", "r6_review_assessment"),
                ("03", "r6_review_report"),
                ("03", "r6_review_report_md"),
            ],
        )
        connection.execute(
            "UPDATE artifacts SET status='STALE' "
            "WHERE CAST(step AS INTEGER)>=4 AND status IN ('COMPLETE','PARTIAL')"
        )
        connection.execute("DELETE FROM kvk_requests")
        connection.executemany(
            "INSERT INTO artifacts(path, step, kind, sha256, size, status, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            [
                (
                    str(path.relative_to(run.path)),
                    step,
                    kind,
                    sha256(path),
                    path.stat().st_size,
                    status,
                    created_at,
                )
                for path, step, kind, status in entries
            ],
        )
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        sqlite_after = page_count * page_size
        resources = report["resources"]
        assert isinstance(resources, dict)
        resources["sqlite_bytes_after_publication"] = sqlite_after
        resources["sqlite_growth_bytes"] = sqlite_after - sqlite_before
        atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        connection.execute(
            "UPDATE artifacts SET sha256=?, size=? WHERE path=?",
            (
                sha256(report_path),
                report_path.stat().st_size,
                str(report_path.relative_to(run.path)),
            ),
        )


def build_sample(
    run: Run,
    size: int = DEFAULT_SAMPLE_SIZE,
    review_size: int = DEFAULT_REVIEW_SIZE,
    pilot_size: int = DEFAULT_PILOT_SIZE,
) -> tuple[Path, ...]:
    """Build the deterministic R6 sample, preliminary dedup outputs and R8 pilot pool."""
    if min(size, review_size, pilot_size) < 1:
        raise HarvestError("sample-, review- en pilotomvang moeten positief zijn")
    sources = _latest_sources(run)
    if not sources:
        raise HarvestError("geen verzamelde bronlijsten; voer eerst broninname uit")
    for path, kind, expected_hash in sources:
        if not path.is_file() or sha256(path) != expected_hash:
            raise HarvestError(f"bronartefact voor {kind} ontbreekt of wijkt af van de registratie")
    catalog_path, catalog_hash = _latest_catalog(run)
    if not catalog_path.is_file() or sha256(catalog_path) != catalog_hash:
        raise HarvestError("broncatalogus ontbreekt of wijkt af van de registratie")
    catalog = read_catalog(run)
    families = {row["source_id"]: row["source_family"] or "unclassified" for row in catalog}
    started = time.monotonic()
    tracemalloc.start()
    tracemalloc.reset_peak()
    sqlite_before = _sqlite_allocated_bytes(run)

    sample, capacities, allocation = _sample_rows(sources, families, size)
    candidates, decisions, conflicts = _deduplicate_rows(sample)
    review = _review_queue(candidates, decisions, conflicts, families, min(review_size, size))
    pilot = _pilot_pool(candidates, families, pilot_size)
    if len(review) != min(review_size, size):
        raise HarvestError("onvoldoende dedupbeslissingen voor de gevraagde R6-reviewomvang")
    if len(pilot) != pilot_size:
        raise HarvestError("onvoldoende kandidaten zonder direct KVK voor de gevraagde R8-pilot")

    sample_path = run.artifact_path("03", "r6_source_sample", "csv")
    candidate_path = run.artifact_path("03", "r6_candidates", "csv")
    decision_path = run.artifact_path("03", "r6_dedup_decisions", "csv")
    conflict_path = run.artifact_path("03", "r6_dedup_conflicts", "csv")
    review_path = run.artifact_path("03", "r6_review_queue", "csv")
    pilot_path = run.artifact_path("03", "r8_pilot_selection", "csv")
    write_tsv(
        sample_path,
        RAW_HEADERS
        + ["sample_family", "identifier_stratum", "selection_hash", "sample_rank"],
        sample,
    )
    write_tsv(candidate_path, CANDIDATE_HEADERS, candidates)
    write_tsv(decision_path, DECISION_HEADERS, decisions)
    write_tsv(conflict_path, CONFLICT_HEADERS, conflicts)
    write_tsv(review_path, REVIEW_HEADERS, review)
    write_tsv(
        pilot_path,
        CANDIDATE_HEADERS + ["source_families", "pilot_hash", "pilot_rank"],
        pilot,
    )
    data_paths = [
        sample_path,
        candidate_path,
        decision_path,
        conflict_path,
        review_path,
        pilot_path,
    ]
    _current, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    decision_inputs = sum(int(row["input_count"]) for row in decisions)
    closure_output = decision_inputs + len(conflicts)
    per_source: list[dict[str, Any]] = []
    for source_id in sorted({row["source_id"] for row in sample}):
        rows = [row for row in sample if row["source_id"] == source_id]
        per_source.append(
            {
                "source_id": source_id,
                "source_family": families.get(source_id, "unclassified"),
                "sample_records": len(rows),
                "valid_direct_registration_numbers": sum(
                    _identifier_stratum(row) == "VALID_DIRECT" for row in rows
                ),
                "without_direct_registration_number": sum(
                    _identifier_stratum(row) == "WITHOUT_DIRECT" for row in rows
                ),
                "legal_form_coverage": sum(bool(row.get("source_legal_form", "").strip()) for row in rows),
                "source_status_coverage": sum(
                    not _missing_source_status(row.get("source_status")) for row in rows
                ),
            }
        )
    source_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "catalog_sha256": catalog_hash,
                "families": dict(sorted(families.items())),
                "sources": [
                    {"kind": kind, "sha256": digest} for _path, kind, digest in sources
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    report: dict[str, Any] = {
        "r6_sample_report_schema_version": SAMPLE_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_artifact_fingerprint": source_fingerprint,
        "catalog_sha256": catalog_hash,
        "definition": {
            "requested_records": size,
            "family_allocation": "equal round-robin with capacity redistribution",
            "identifier_allocation": "equal round-robin across VALID_DIRECT and WITHOUT_DIRECT per family",
            "selection": "lowest SHA-256 of canonical full source row per stratum",
            "deduplication": "canonical preliminary exact normalized-name/KVK-hint rules",
            "review_selection": "all merges/conflicts when capacity permits, then deterministic singles",
            "r8_pilot_selection": "equal family allocation from candidates without direct KVK, lowest candidate SHA-256",
        },
        "strata": {
            key: {"available": capacities[key], "selected": allocation.get(key, 0)}
            for key in sorted(capacities)
        },
        "counts": {
            "sample_records": len(sample),
            "valid_direct_registration_numbers": sum(
                _identifier_stratum(row) == "VALID_DIRECT" for row in sample
            ),
            "without_direct_registration_number": sum(
                _identifier_stratum(row) == "WITHOUT_DIRECT" for row in sample
            ),
            "unique_candidates": len(candidates),
            "identical_merges": sum(
                max(int(row["input_count"]) - 1, 0)
                for row in decisions
                if row["decision"] == "MERGED_IDENTICAL"
            ),
            "conflict_records": len(conflicts),
            "review_queue_records": len(review),
            "r8_pilot_records": len(pilot),
        },
        "ratios": {
            "duplicate_ratio": (
                sum(
                    max(int(row["input_count"]) - 1, 0)
                    for row in decisions
                    if row["decision"] == "MERGED_IDENTICAL"
                )
                / len(sample)
            ),
            "conflict_ratio": len(conflicts) / len(sample),
        },
        "per_source": per_source,
        "count_closure": {
            "status": "CLOSED" if closure_output == len(sample) else "OPEN",
            "input": len(sample),
            "decision_inputs": decision_inputs,
            "conflict_inputs": len(conflicts),
            "output": closure_output,
            "delta": len(sample) - closure_output,
        },
        "review": {
            "status": "PENDING",
            "queue_sha256": sha256(review_path),
            "required_verdicts": sorted(ALLOWED_VERDICTS),
        },
        "r8_metrics_contract": {
            "terminal_outcomes": [
                "MATCHED",
                "NO_MATCH",
                "AMBIGUOUS",
                "SOURCE_CONFLICT",
                "TECHNICAL_ERROR",
            ],
            "required_metrics": [
                "terminal_outcome_closure",
                "match_rate_per_source_family",
                "ambiguous_rate",
                "review_rate",
                "technical_error_rate",
                "seconds_per_candidate",
                "evidence_bytes_per_candidate",
            ],
            "threshold_policy": "set only after measured R8 pilot and manual review",
        },
        "resources": {
            "duration_seconds": round(time.monotonic() - started, 6),
            "python_peak_allocated_bytes": peak_memory,
            "sqlite_bytes_before_publication": sqlite_before,
            "sqlite_bytes_after_publication": None,
            "sqlite_growth_bytes": None,
            "data_output_bytes": _file_bytes(data_paths),
            "evidence_growth_bytes": 0,
        },
    }
    if report["count_closure"]["status"] != "CLOSED":
        raise HarvestError("R6 count-closure is niet gesloten")
    report_path = run.artifact_path("03", "r6_sample_report", "json")
    md_path = run.artifact_path("03", "r6_sample_report", "md")
    atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    atomic_write(
        md_path,
        "\n".join(
            [
                "# R6 bron- en deduplicatiesample",
                "",
                f"- Bronrecords: {len(sample)}",
                f"- Geldig direct KVK / zonder direct KVK: {report['counts']['valid_direct_registration_numbers']} / {report['counts']['without_direct_registration_number']}",
                f"- Kandidaten: {len(candidates)}",
                f"- Identieke merges / conflictrecords: {report['counts']['identical_merges']} / {len(conflicts)}",
                f"- Reviewqueue / R8-pilot: {len(review)} / {len(pilot)}",
                f"- Count-closure: {report['count_closure']['status']}",
                "- Handmatige review: PENDING",
                "",
                "Deze sample doet geen KVK-frontendcalls en bronstatus is geen KVK-verificatie.",
                "",
            ]
        ),
    )
    outputset = [
        (sample_path, "03", "r6_source_sample", "COMPLETE"),
        (candidate_path, "03", "r6_candidates", "COMPLETE"),
        (decision_path, "03", "r6_dedup_decisions", "COMPLETE"),
        (conflict_path, "03", "r6_dedup_conflicts", "COMPLETE"),
        (review_path, "03", "r6_review_queue", "COMPLETE"),
        (pilot_path, "03", "r8_pilot_selection", "COMPLETE"),
        (report_path, "03", "r6_sample_report", "COMPLETE"),
        (md_path, "03", "r6_sample_report_md", "COMPLETE"),
    ]
    config = {
        "source_artifact_fingerprint": source_fingerprint,
        "size": size,
        "review_size": review_size,
        "pilot_size": pilot_size,
        "schema": SAMPLE_SCHEMA_VERSION,
    }
    run.record_config("r6_sample", {**config, "status": "PUBLISHING"})
    run.record_config(
        "r6_review",
        {"status": "PENDING", "queue_sha256": sha256(review_path)},
    )
    _publish_sample_outputset(run, outputset, report_path, report, sqlite_before)
    run.log("INFO", "downstream_invalidated", from_step=4, reason="r6_sample_changed")
    run.record_config(
        "r6_sample",
        {**config, "status": "COMPLETE", "report_sha256": sha256(report_path)},
    )
    run.update_status("IN_PROGRESS", "03")
    return (*data_paths, report_path, md_path)


def record_sample_review(run: Run, assessment: Path) -> tuple[Path, Path, Path]:
    """Validate and preserve a complete manual assessment of the current R6 review queue."""
    queue_path = run.latest_artifact("03", "r6_review_queue")
    if not queue_path:
        raise HarvestError("geen R6-reviewqueue; voer eerst companies sample uit")
    queue_hash = _require_registered_integrity(run, queue_path, "03", "r6_review_queue")
    source = assessment.expanduser().resolve()
    if not source.is_file():
        raise HarvestError("R6-reviewassessment ontbreekt")
    queue = read_tsv(queue_path)
    supplied = read_tsv(source)
    if not supplied or not set(ASSESSMENT_HEADERS).issubset(supplied[0]):
        raise HarvestError("R6-reviewassessment mist verplichte kolommen")
    by_id: dict[str, dict[str, str]] = {}
    for row in supplied:
        review_id = row["review_id"].strip()
        verdict = row["review_verdict"].strip().upper()
        if row["queue_sha256"].strip() != queue_hash:
            raise HarvestError("R6-reviewassessment hoort niet bij de actuele reviewqueue")
        if not review_id or review_id in by_id:
            raise HarvestError("R6-reviewassessment bevat lege of dubbele review_id")
        if verdict not in ALLOWED_VERDICTS:
            raise HarvestError("R6-reviewassessment bevat een onbekend verdict")
        by_id[review_id] = {
            "queue_sha256": queue_hash,
            "review_id": review_id,
            "review_verdict": verdict,
            "review_notes": row["review_notes"].strip(),
        }
    expected = {row["review_id"] for row in queue}
    if set(by_id) != expected:
        raise HarvestError("R6-reviewassessment sluit niet exact op de actuele reviewqueue")
    rows = [by_id[review_id] for review_id in sorted(by_id)]
    counts = Counter(row["review_verdict"] for row in rows)
    status = "PASS" if not counts["FALSE_MERGE"] and not counts["UNCERTAIN"] else "CHANGES_REQUIRED"
    output = run.artifact_path("03", "r6_review_assessment", "csv")
    report_path = run.artifact_path("03", "r6_review_report", "json")
    md_path = run.artifact_path("03", "r6_review_report", "md")
    write_tsv(output, ASSESSMENT_HEADERS, rows)
    report = {
        "r6_review_report_schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "queue_sha256": queue_hash,
        "assessment_input_sha256": sha256(source),
        "reviewed_records": len(rows),
        "verdict_counts": dict(sorted(counts.items())),
        "closure": "CLOSED" if len(rows) == len(queue) else "OPEN",
        "status": status,
    }
    atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    atomic_write(
        md_path,
        "\n".join(
            [
                "# R6 handmatige deduplicatiereview",
                "",
                f"- Beoordeeld: {len(rows)} / {len(queue)}",
                f"- Confirmed: {counts['CONFIRMED']}",
                f"- False merge: {counts['FALSE_MERGE']}",
                f"- Uncertain: {counts['UNCERTAIN']}",
                f"- Status: **{status}**",
                "",
            ]
        ),
    )
    run.register_artifact_set(
        [
            (output, "03", "r6_review_assessment", "COMPLETE"),
            (report_path, "03", "r6_review_report", "COMPLETE"),
            (md_path, "03", "r6_review_report_md", "COMPLETE"),
        ]
    )
    run.record_config(
        "r6_review",
        {
            "queue_sha256": queue_hash,
            "assessment_sha256": sha256(output),
            "status": status,
        },
    )
    return output, report_path, md_path
