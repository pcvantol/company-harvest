"""Duurzame, controleerbare KVK-cohort voor een begrensde end-to-end-run."""

from __future__ import annotations

import csv
import json
import os
from typing import cast

from company_harvest.core import HarvestError, Run, atomic_write, sha256
from company_harvest.pre_kvk import MASTER_HEADERS, _registered, validated_master
from company_harvest.pre_kvk_filter import validated_filter


def scope_details(run: Run) -> dict[str, int | str] | None:
    """Valideer de vastgelegde cohort tegen de actuele volledige filteroutput."""
    config = run.metadata().get("runtime_config", {}).get("kvk_scope")
    if config is None:
        return None
    if not isinstance(config, dict):
        raise HarvestError("KVK-cohortconfiguratie is ongeldig")
    _, master_hash = validated_master(run)
    full, full_hash, _, _, filter_meta_path = validated_filter(run, master_hash)
    filter_meta = json.loads(filter_meta_path.read_text(encoding="utf-8"))
    full_count = filter_meta["counts"]["eligible_rows"]
    scoped, scoped_hash = _registered(run, "03", "kvk_scope_eligible")
    metadata_path, metadata_hash = _registered(run, "03", "kvk_scope_metadata")
    try:
        details = json.loads(metadata_path.read_text(encoding="utf-8"))
        limit = details["limit_kvk_check"]
        selected = details["selected_rows"]
        skipped = details["not_checked_rows"]
        if (type(limit) is not int or limit < 1 or type(selected) is not int
                or type(skipped) is not int or selected != min(limit, full_count)
                or skipped != full_count - selected):
            raise ValueError("cohortaantallen")
        expected = {
            "schema_version": 1,
            "limit_kvk_check": limit,
            "full_eligible_path": str(full.relative_to(run.path)),
            "full_eligible_sha256": full_hash,
            "full_eligible_rows": full_count,
            "scoped_path": str(scoped.relative_to(run.path)),
            "scoped_sha256": scoped_hash,
            "selected_rows": selected,
            "not_checked_rows": skipped,
        }
        if details != expected or config != {"limit_kvk_check": limit, "metadata_sha256": metadata_hash}:
            raise ValueError("cohortbinding")
        with (full.open(encoding="utf-8-sig", newline="") as source,
              scoped.open(encoding="utf-8-sig", newline="") as subset):
            source_rows = csv.DictReader(source, delimiter="\t")
            subset_rows = csv.DictReader(subset, delimiter="\t")
            if source_rows.fieldnames != MASTER_HEADERS or subset_rows.fieldnames != MASTER_HEADERS:
                raise ValueError("cohortkolommen")
            seen: set[str] = set()
            for index, row in enumerate(subset_rows, start=1):
                if index > selected or row != next(source_rows, None):
                    raise ValueError("cohort is geen prefix van de filterlijst")
                candidate_id = row["candidate_id"]
                if not candidate_id or candidate_id in seen:
                    raise ValueError("dubbele kandidaat in cohort")
                seen.add(candidate_id)
            if len(seen) != selected:
                raise ValueError("cohortlengte")
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        raise HarvestError("KVK-cohort is gewijzigd of niet gesloten") from exc
    return cast("dict[str, int | str]", details)


def bind_kvk_scope(run: Run, limit: int) -> dict[str, int | str]:
    """Kies de eerste N stabiele filterkandidaten vóór de eerste publieke GET."""
    if type(limit) is not int or limit < 1:
        raise HarvestError("--limit-kvk-check moet positief zijn")
    with run.lock():
        existing = scope_details(run)
        if existing is not None:
            if existing["limit_kvk_check"] != limit:
                raise HarvestError("KVK-cohortlimiet van deze run mag niet wijzigen")
            return existing
        with run.connect() as connection:
            if connection.execute("SELECT 1 FROM kvk_requests LIMIT 1").fetchone():
                raise HarvestError("bestaand KVK-journal kan niet achteraf worden begrensd")
        _, master_hash = validated_master(run)
        full, full_hash, _, _, filter_meta_path = validated_filter(run, master_hash)
        full_count = json.loads(filter_meta_path.read_text(encoding="utf-8"))["counts"]["eligible_rows"]
        selected = min(limit, full_count)
        scoped = run.artifact_path("03", "kvk_scope_eligible", "tsv")
        staged = scoped.with_name(f".{scoped.name}.tmp")
        try:
            with (full.open(encoding="utf-8-sig", newline="") as source,
                  staged.open("w", encoding="utf-8", newline="") as destination):
                reader = csv.DictReader(source, delimiter="\t")
                if reader.fieldnames != MASTER_HEADERS:
                    raise HarvestError("KVK-filterlijst heeft ongeldige kolommen")
                writer = csv.DictWriter(destination, fieldnames=MASTER_HEADERS, delimiter="\t")
                writer.writeheader()
                for index, row in enumerate(reader):
                    if index == selected:
                        break
                    writer.writerow(row)
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(staged, scoped)
        finally:
            staged.unlink(missing_ok=True)
        details: dict[str, int | str] = {
            "schema_version": 1,
            "limit_kvk_check": limit,
            "full_eligible_path": str(full.relative_to(run.path)),
            "full_eligible_sha256": full_hash,
            "full_eligible_rows": full_count,
            "scoped_path": str(scoped.relative_to(run.path)),
            "scoped_sha256": sha256(scoped),
            "selected_rows": selected,
            "not_checked_rows": full_count - selected,
        }
        metadata_path = run.artifact_path("03", "kvk_scope_metadata", "json")
        atomic_write(metadata_path, json.dumps(details, ensure_ascii=False, indent=2) + "\n")
        run.register_artifact_set([
            (scoped, "03", "kvk_scope_eligible", "COMPLETE"),
            (metadata_path, "03", "kvk_scope_metadata", "COMPLETE"),
        ])
        run.record_config("kvk_scope", {
            "limit_kvk_check": limit, "metadata_sha256": sha256(metadata_path),
        })
        return details
