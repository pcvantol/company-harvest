"""Reproduceerbare, verliesvrije toelatingsfilter vóór de publieke KVK-check."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from company_harvest.core import HarvestError, Run, atomic_write, sha256
from company_harvest.pre_kvk import MASTER_HEADERS, SOURCE_IDS, _registered, validated_master

RULE_VERSION = "pre-kvk-eligibility-7"
RULES = {
    "ANBI_SOURCE": "Bronrelatie met ANBI-register: algemeen nut beogende instelling.",
    "EDUCATION_SOURCE": "Bronrelatie met DUO Basisgegevens instellingen: onderwijsinstelling.",
    "NO_DIRECT_KVK_HINT": "Geen geldig direct KVK-nummer in de verzamelde brondata; geen bewijs dat inschrijving ontbreekt.",
    "SOURCE_CONFLICT_REVIEW": "Bronidentiteit heeft een conflict en vereist afzonderlijke review.",
    "HOLDING_OR_MANAGEMENT": "Naam bevat holding, beheer(s)maatschappij of Beheer B.V./N.V.; generiek beheer telt niet.",
    "FOUNDATION_OR_ASSOCIATION": "Naam noemt stichting of vereniging, ook als Nederlands samengesteld eindwoord.",
    "SCHOOL_OR_UNIVERSITY": "Naam noemt school (ook als samengesteld eindwoord), onderwijs, universiteit of lyceum.",
    "BANK": "Naam noemt zelfstandig bank/banken/bankiers/banking of een specifiek banktype zoals spaarbank/hypotheekbank; geen willekeurig -bank-eindwoord.",
    "PENSION_FUND": "Naam noemt pensioenfonds (ook als samengesteld eindwoord) of pension fund/scheme.",
    "FUND_OR_EQUITY_NAME": "Naam bevat fonds/fund/equity (ook samengesteld) of beleggingsmodel/-instelling; dit naamsignaal bewijst geen beleggingsfonds.",
    "RELIGIOUS_ORGANISATION": "Naam noemt kerk/kerken als los woord, een herkenbaar kerktype, kerkgenootschap, diaconie, parochie, moskee of Jehova's getuigen; plaatsnamen op -kerk tellen niet.",
    "POLITICAL_PARTY": "Naam noemt expliciet een politieke partij of een herkenbare partijnaam.",
}
EXCLUDED_HEADERS = [
    "candidate_id", "original_name", "source_kvk_hint", "source_ids_json",
    "kvk_queue_status", "primary_reason", "all_reasons_json",
]
PATTERNS = {
    "HOLDING_OR_MANAGEMENT": re.compile(r"\b(?:holding|holdings|holdingmaatschappij|beheers?maatschappij)\b|\bbeheer\s+(?:b\.?v\.?|n\.?v\.?)\b", re.I),
    "FOUNDATION_OR_ASSOCIATION": re.compile(r"\b[\w-]*(?:stichting|vereniging)\b", re.I),
    "SCHOOL_OR_UNIVERSITY": re.compile(r"\b[\w-]*school(?:en)?\b|\b(?:universiteit|onderwijs|lyceum)\b", re.I),
    "BANK": re.compile(r"\b(?:bank|banken|bankiers|banking|spaarbank|hypotheekbank|kredietbank|investeringsbank|beleggingsbank|handelsbank|zakenbank|depositobank|volksbank|rabobank|regiobank)\b", re.I),
    "PENSION_FUND": re.compile(r"\b[\w-]*pensioenfonds(?:en)?\b|\bpension(?: fund| scheme)\b", re.I),
    "FUND_OR_EQUITY_NAME": re.compile(r"\b[\w-]*fonds(?:en)?\b|\b(?:fund|funds|equity|equities|beleggingsmodel|beleggingsinstelling)\b", re.I),
    "RELIGIOUS_ORGANISATION": re.compile(r"\b(?:kerk|kerken|kerkgenootschap|dorpskerk|stadskerk|wijkkerk|parochiekerk|baptistenkerk|pinksterkerk|hervormdekerk|gereformeerdekerk|diaconie|parochie|moskee|protestantse gemeente|christelijke gemeente|jehovah'?s getuigen)\b", re.I),
    "POLITICAL_PARTY": re.compile(r"\b(?:politieke partij|christenunie|groenlinks|partij van de arbeid|partij voor de dieren|forum voor democratie|volkspartij voor vrijheid en democratie|democraten 66)\b", re.I),
}
PATTERN_METADATA = {
    reason: {"regex": pattern.pattern, "case_insensitive": bool(pattern.flags & re.IGNORECASE)}
    for reason, pattern in PATTERNS.items()
}


def _reasons(row: dict[str, str]) -> tuple[list[str], list[str]]:
    try:
        relations = json.loads(row["source_relations"])
        sources = sorted({relation["source_id"] for relation in relations})
    except (ValueError, TypeError, KeyError) as exc:
        raise HarvestError("pre-KVK-master bevat ongeldige bronrelaties") from exc
    if not sources or any(source not in SOURCE_IDS for source in sources):
        raise HarvestError("pre-KVK-master bevat onbekende bronrelaties")
    reasons = []
    if "anbi_register" in sources or row["sector"].casefold() == "algemeen nut beogende instelling":
        reasons.append("ANBI_SOURCE")
    if "duo_education_organisations" in sources:
        reasons.append("EDUCATION_SOURCE")
    if not row["source_kvk_hint"]:
        reasons.append("NO_DIRECT_KVK_HINT")
    if row["kvk_queue_status"] == "REVIEW_REQUIRED":
        reasons.append("SOURCE_CONFLICT_REVIEW")
    elif row["kvk_queue_status"] not in {"READY_FOR_KVK_VERIFICATION", "READY_FOR_KVK_MATCHING"}:
        raise HarvestError("pre-KVK-master bevat ongeldige wachtrijstatus")
    for reason, pattern in PATTERNS.items():
        if pattern.search(row["original_name"]):
            reasons.append(reason)
    return reasons, sources


def validated_filter(run: Run, master_sha256: str) -> tuple[Path, str, Path, str, Path]:
    """Fail-closed: alleen de actuele, byte- en regelgebonden filterset is KVK-input."""
    eligible, eligible_hash = _registered(run, "03", "pre_kvk_eligible")
    excluded, excluded_hash = _registered(run, "03", "pre_kvk_excluded")
    metadata_path, _ = _registered(run, "03", "pre_kvk_filter_metadata")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HarvestError("pre-KVK-filtermetadata is ongeldig") from exc
    counts = metadata.get("counts")
    primary = metadata.get("primary_reason_counts")
    master = run.latest_artifact("03", "pre_kvk_master")
    if (not isinstance(counts, dict) or not isinstance(primary, dict)
            or not {"master_rows", "eligible_rows", "excluded_rows"}.issubset(counts)
            or any(type(value) is not int or value < 0 for value in counts.values())
            or any(type(value) is not int or value < 0 for value in primary.values())
            or counts["master_rows"] != counts["eligible_rows"] + counts["excluded_rows"]
            or sum(primary.values()) != counts["excluded_rows"]):
        raise HarvestError("pre-KVK-filter heeft geen gesloten aantallen")
    if (master is None or metadata.get("rule_version") != RULE_VERSION
            or metadata.get("rules") != RULES
            or metadata.get("patterns") != PATTERN_METADATA
            or metadata.get("master_sha256") != master_sha256
            or metadata.get("master_path") != str(master.relative_to(run.path))
            or metadata.get("eligible_path") != str(eligible.relative_to(run.path))
            or metadata.get("excluded_path") != str(excluded.relative_to(run.path))
            or metadata.get("eligible_sha256") != eligible_hash
            or metadata.get("excluded_sha256") != excluded_hash
            or metadata.get("eligible_bytes") != eligible.stat().st_size
            or metadata.get("excluded_bytes") != excluded.stat().st_size
            or metadata.get("count_closure") != "CLOSED"):
        raise HarvestError("pre-KVK-filter is niet actueel of niet gesloten")
    return eligible, eligible_hash, excluded, excluded_hash, metadata_path


def build_pre_kvk_filter(run: Run) -> tuple[Path, Path, Path]:
    """Scheid actuele master offline in KVK-kandidaten en een auditbare uitsluitlijst."""
    with run.lock():
        master, master_hash = validated_master(run)
        try:
            eligible, _hash, excluded, _excluded_hash, prior_metadata = validated_filter(run, master_hash)
            return eligible, excluded, prior_metadata
        except HarvestError:
            pass
        with run.connect() as connection:
            if connection.execute("SELECT 1 FROM kvk_requests LIMIT 1").fetchone():
                raise HarvestError("bestaande KVK-journal vereist eerst een expliciet migratiebesluit")
        required_space = 2 * master.stat().st_size + 64 * 1024 * 1024
        if shutil.disk_usage(run.path).free < required_space:
            raise HarvestError("onvoldoende vrije ruimte voor pre-KVK-filter")
        eligible = run.artifact_path("03", "pre_kvk_eligible", "tsv")
        excluded = run.artifact_path("03", "pre_kvk_excluded", "tsv")
        metadata_path = run.artifact_path("03", "pre_kvk_filter_metadata", "json")
        eligible_tmp = eligible.with_name(f".{eligible.name}.tmp")
        excluded_tmp = excluded.with_name(f".{excluded.name}.tmp")
        counts: Counter[str] = Counter()
        primary: Counter[str] = Counter()
        all_reasons: Counter[str] = Counter()
        source_eligible: Counter[str] = Counter()
        source_excluded: Counter[str] = Counter()
        seen_ids: set[str] = set()
        try:
            with (master.open(encoding="utf-8-sig", newline="") as source,
                  eligible_tmp.open("w", encoding="utf-8", newline="") as keep,
                  excluded_tmp.open("w", encoding="utf-8", newline="") as drop):
                reader = csv.DictReader(source, delimiter="\t")
                if reader.fieldnames != MASTER_HEADERS:
                    raise HarvestError("pre-KVK-master mist het verwachte kolomcontract")
                keep_writer = csv.DictWriter(keep, fieldnames=MASTER_HEADERS, delimiter="\t")
                drop_writer = csv.DictWriter(drop, fieldnames=EXCLUDED_HEADERS, delimiter="\t")
                keep_writer.writeheader()
                drop_writer.writeheader()
                for row in reader:
                    candidate_id = row["candidate_id"]
                    if not candidate_id or candidate_id in seen_ids:
                        raise HarvestError("pre-KVK-master bevat ontbrekende of dubbele kandidaat-ID")
                    seen_ids.add(candidate_id)
                    reasons, sources = _reasons(row)
                    counts["master_rows"] += 1
                    if reasons:
                        drop_writer.writerow({
                            "candidate_id": candidate_id,
                            "original_name": row["original_name"],
                            "source_kvk_hint": row["source_kvk_hint"],
                            "source_ids_json": json.dumps(sources, ensure_ascii=False),
                            "kvk_queue_status": row["kvk_queue_status"],
                            "primary_reason": reasons[0],
                            "all_reasons_json": json.dumps(reasons, ensure_ascii=False),
                        })
                        counts["excluded_rows"] += 1
                        primary[reasons[0]] += 1
                        all_reasons.update(reasons)
                        source_excluded.update(sources)
                    else:
                        keep_writer.writerow(row)
                        counts["eligible_rows"] += 1
                        source_eligible.update(sources)
                for handle in (keep, drop):
                    handle.flush()
                    os.fsync(handle.fileno())
            if counts["master_rows"] != counts["eligible_rows"] + counts["excluded_rows"]:
                raise HarvestError("pre-KVK-filter sluit niet op masterlijst")
            if validated_master(run) != (master, master_hash) or sha256(master) != master_hash:
                raise HarvestError("pre-KVK-master veranderde tijdens filtering")
            os.replace(eligible_tmp, eligible)
            os.replace(excluded_tmp, excluded)
            metadata: dict[str, Any] = {
                "schema_version": 1,
                "rule_version": RULE_VERSION,
                "rules": RULES,
                "patterns": PATTERN_METADATA,
                "master_path": str(master.relative_to(run.path)),
                "master_sha256": master_hash,
                "eligible_path": str(eligible.relative_to(run.path)),
                "eligible_sha256": sha256(eligible),
                "eligible_bytes": eligible.stat().st_size,
                "excluded_path": str(excluded.relative_to(run.path)),
                "excluded_sha256": sha256(excluded),
                "excluded_bytes": excluded.stat().st_size,
                "counts": dict(counts),
                "primary_reason_counts": dict(primary),
                "all_reason_counts": dict(all_reasons),
                "eligible_source_relations": dict(source_eligible),
                "excluded_source_relations": dict(source_excluded),
                "count_closure": "CLOSED",
                "kvk_requests": 0,
            }
            atomic_write(metadata_path, json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
            run.register_artifact_set([
                (eligible, "03", "pre_kvk_eligible", "COMPLETE"),
                (excluded, "03", "pre_kvk_excluded", "COMPLETE"),
                (metadata_path, "03", "pre_kvk_filter_metadata", "COMPLETE"),
            ])
            run.record_config("pre_kvk_filter", {
                "rule_version": RULE_VERSION, "master_sha256": master_hash,
                "eligible_sha256": metadata["eligible_sha256"],
            })
            return eligible, excluded, metadata_path
        finally:
            eligible_tmp.unlink(missing_ok=True)
            excluded_tmp.unlink(missing_ok=True)
