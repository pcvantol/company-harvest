"""Expliciete, hervatbare keten van publieke bronnen tot geaudite eindlijst."""

from __future__ import annotations

import json
import math
from typing import Any

from company_lookup.audit import verify
from company_lookup.console import emit, phase
from company_lookup.core import HarvestError, Run, read_tsv
from company_lookup.kvk import PublicHttpProvider
from company_lookup.kvk import preflight as kvk_preflight
from company_lookup.kvk_scope import bind_kvk_scope, scope_details
from company_lookup.pre_kvk_kvk import check_access_blocks, run_pre_kvk
from company_lookup.preflight import host as host_preflight
from company_lookup.prepare import prepare_pre_kvk
from company_lookup.workflow import (
    active_only,
    consolidate,
    exclude_sole_proprietorships,
    export,
    report,
)


def run_end_to_end(run: Run, limit_kvk_check: int | None, interval: float = 2.0,
                   allow_partial: bool = False) -> dict[str, Any]:
    """Voer één expliciet gekozen KVK-scope uit; hervat zonder scopeverruiming."""
    if ((limit_kvk_check is not None and (type(limit_kvk_check) is not int or limit_kvk_check < 1))
            or not math.isfinite(interval) or interval < 2.0):
        raise HarvestError("E2E vereist een positieve KVK-limiet en minimaal 2 seconden KVK-interval")
    requested = {
        "limit_kvk_check": limit_kvk_check,
        "interval": interval,
        "provider": "public-http",
    }
    with run.lock():
        with phase("Host, run en hervatinstellingen controleren"):
            if run.metadata().get("workflow") != "HARVEST" or not host_preflight(run.path)["ready"]:
                raise HarvestError("host/run-preflight is niet gereed; controleer run en opslag")
            metadata = run.metadata()
            config = metadata.get("runtime_config", {}).get("end_to_end")
            if config is not None and config != requested:
                legacy_limit = config.get("export_limit") if isinstance(config, dict) else None
                legacy_matches = (
                    type(legacy_limit) is int and legacy_limit > 0
                    and {key: value for key, value in config.items() if key != "export_limit"} == requested
                ) if isinstance(config, dict) else False
                if not legacy_matches:
                    raise HarvestError("E2E-instellingen van deze run mogen bij hervatten niet wijzigen")
                if metadata["status"] not in {"EXPORT_COMPLETE", "PARTIAL_EXPORTED"}:
                    if (limit_kvk_check is None or not isinstance(legacy_limit, int)
                            or legacy_limit < limit_kvk_check):
                        raise HarvestError(
                            "oude E2E-run heeft een mogelijk bindende exportlimiet; "
                            "rond die af met de oorspronkelijke toolversie of start bewust een nieuwe run"
                        )
                    run.record_config("end_to_end", requested)
            if config is None:
                with run.connect() as connection:
                    if connection.execute("SELECT 1 FROM kvk_requests LIMIT 1").fetchone():
                        raise HarvestError("bestaand KVK-journal vereist een eigen besluit; start hier geen nieuwe E2E-scope")
                run.record_config("end_to_end", requested)
        if run.metadata()["status"] in {"EXPORT_COMPLETE", "PARTIAL_EXPORTED"}:
            emit("INFO", "Bestaande export wordt gecontroleerd; geen KVK-verzoeken")
            with phase("Rapport en eindlijst controleren"):
                _ensure_report(run)
                audit = verify(run)
            return _finished(run, audit)
        with phase("Bekende KVK-blokkades controleren"):
            check_access_blocks(run)
        with phase("Publieke bronnen voorbereiden"):
            prepare_pre_kvk(run)
        with phase("KVK-cohort binden"):
            scope = bind_kvk_scope(run, limit_kvk_check) if limit_kvk_check is not None else None
            if scope is not None and scope_details(run) != scope:
                raise HarvestError("KVK-cohortbinding is gewijzigd")
        if scope is not None:
            emit("INFO", "KVK-kandidaten geselecteerd", count=int(scope["selected_rows"]),
                 total=int(scope["full_eligible_rows"]))
        with phase("Publieke KVK-route controleren"):
            kvk_preflight(run, "public-http")
            if not PublicHttpProvider(run).preflight()["available"]:
                raise HarvestError("publieke KVK-frontendroute is niet beschikbaar; geen verzoek verstuurd")
        with phase("KVK-kandidaten controleren"):
            _, _, progress_path = run_pre_kvk(run, interval=interval)
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
            emit("INFO", "KVK-checkpoint bijgewerkt", count=int(progress["journal_rows"]),
                 total=int(progress["eligible_rows"]))
            if progress["status"] != "COMPLETE":
                raise HarvestError(
                    f"KVK-check stopte met status {progress['status']}; hervat uitsluitend deze run na beoordeling",
                    4 if progress["status"] == "BLOCKED" else 7,
                )
        with phase("KVK-resultaten auditen en consolideren"):
            verify(run)
            if not run.latest_artifact("05", "canonical"):
                consolidate(run)
        with phase("Eenmanszaken uitsluiten"):
            if not run.latest_artifact("06", "non_sole"):
                exclude_sole_proprietorships(run)
        with phase("Actieve bedrijven selecteren"):
            if not run.latest_artifact("07", "active"):
                active_only(run)
        unresolved = run.latest_artifact("05", "kvk_unresolved")
        unresolved_count = len(read_tsv(unresolved)) if unresolved else 0
        skipped = int(scope["not_checked_rows"]) if scope is not None else 0
        if unresolved_count and not allow_partial:
            raise HarvestError("onopgeloste KVK-kandidaten vereisen expliciet --allow-partial voor export")
        partial = allow_partial or skipped > 0
        with phase("Definitieve eindlijst exporteren"):
            export(run, allow_partial=partial)
        with phase("Rapport en eindaudit afronden"):
            _ensure_report(run)
            audit = verify(run)
        return _finished(run, audit)


def _ensure_report(run: Run) -> None:
    """Een export is pas E2E-afgerond als beide rapporten ná het manifest bestaan."""
    with run.connect() as connection:
        rows = connection.execute(
            "SELECT kind,MAX(id) AS id FROM artifacts WHERE step='08' "
            "AND kind IN ('outputset_manifest','outcome_report','run_report') "
            "AND status IN ('COMPLETE','PARTIAL') GROUP BY kind"
        ).fetchall()
    ids = {row["kind"]: row["id"] for row in rows}
    manifest_id = ids.get("outputset_manifest")
    if manifest_id is None:
        raise HarvestError("E2E-outputsetmanifest ontbreekt")
    if any(ids.get(kind, 0) <= manifest_id for kind in ("outcome_report", "run_report")):
        report(run)


def _finished(run: Run, audit: dict[str, Any]) -> dict[str, Any]:
    scope = scope_details(run)
    with run.connect() as connection:
        row = connection.execute(
            "SELECT path FROM artifacts WHERE step='08' AND kind='outputset_manifest' "
            "AND status IN ('COMPLETE','PARTIAL') ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise HarvestError("E2E-outputsetmanifest ontbreekt")
    manifest = run.path / row["path"]
    delivery = manifest.parent / "companies_delivery.csv"
    if not delivery.is_file():
        raise HarvestError("E2E-eindlijst ontbreekt")
    rows = len(read_tsv(delivery))
    if scope is not None and rows > int(scope["limit_kvk_check"]):
        raise HarvestError("E2E-eindlijst overschrijdt --limit-kvk-check")
    return {
        "run_dir": str(run.path),
        "status": run.metadata()["status"],
        "scope": scope,
        "checked_kvk_candidates": (int(scope["selected_rows"]) if scope else None),
        "delivery_rows": rows,
        "delivery_csv": str(delivery),
        "outputset_manifest": str(manifest),
        "audit_valid": audit["valid"],
    }
