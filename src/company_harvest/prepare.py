"""Verzamel vier publieke bronfamilies tot één herleidbare pre-KVK-lijst."""

from __future__ import annotations

from pathlib import Path

from company_harvest.core import Run
from company_harvest.gleif import collect_gleif
from company_harvest.pre_kvk import build_pre_kvk_list
from company_harvest.pre_kvk_filter import build_pre_kvk_filter
from company_harvest.public_registers import collect_public_register
from company_harvest.sources import collect, discover


def prepare_pre_kvk(run: Run, refresh: bool = False) -> tuple[Path, Path, Path, Path, Path]:
    """Hervatbare volledige inname; nooit een KVK-verzoek of Wikidata-download."""
    with run.lock():
        if not run.latest_artifact("01", "sources_inventory"):
            discover(run)
        collect(run, only=("ind_arbeid",), limit=None, refresh=refresh)
        collect_gleif(run, limit=None, refresh=refresh)
        collect_public_register(run, "anbi_register", limit=None, refresh=refresh)
        collect_public_register(run, "duo_education_organisations", limit=None, refresh=refresh)
        master, report = build_pre_kvk_list(run)
        eligible, excluded, metadata = build_pre_kvk_filter(run)
        return master, report, eligible, excluded, metadata
