"""Volledig command-linecontract voor Company Harvest."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Never

from company_harvest import __version__
from company_harvest.audit import trace, verify
from company_harvest.console import active as console_active
from company_harvest.console import emit, error_text, phase
from company_harvest.console import result as console_result
from company_harvest.core import (
    CSV_FIELD_SIZE_LIMIT,
    HarvestError,
    Run,
    data_root,
    initialize_run,
    open_run,
)
from company_harvest.end_to_end import run_end_to_end
from company_harvest.gleif import collect_gleif
from company_harvest.kvk import preflight as kvk_preflight
from company_harvest.kvk import resolve
from company_harvest.matching import record_matching_review, run_matching_pilot
from company_harvest.merge_lists import InputOptions, merge_lists
from company_harvest.pre_kvk import build_pre_kvk_list
from company_harvest.pre_kvk_filter import build_pre_kvk_filter
from company_harvest.pre_kvk_kvk import resolve_pre_kvk, run_pre_kvk
from company_harvest.preflight import host, run_preflight
from company_harvest.prepare import prepare_pre_kvk
from company_harvest.public_registers import collect_public_register
from company_harvest.sampling import build_sample, record_sample_review
from company_harvest.sources import collect, discover, import_source, list_sources, measure_sources
from company_harvest.tenderned import collect_tenderned
from company_harvest.workflow import (
    active_only,
    consolidate,
    exclude_sole_proprietorships,
    export,
    merge_candidates,
    report,
)


def _run_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir", type=Path, required=True)


def _provider_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", choices=("auto", "public-http", "public-browser"), default="auto")


class _ConsoleParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        emit("FOUT", "Ongeldige opdracht of opties")
        self.print_usage(sys.stderr)
        option = re.search(r"--[a-z][a-z0-9-]*", message)
        known = option.group() if option and option.group() in self._option_string_actions else None
        detail = f" bij {known}" if known else ""
        self.exit(2, f"{self.prog}: fout: ongeldige opdracht of opties{detail}; gebruik --help\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _ConsoleParser(prog="company-harvest", description="Lokale, auditbare bedrijfsverzameling en offline lijstmerge")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--data-dir", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    run = commands.add_parser("run").add_subparsers(dest="run_command", required=True)
    init = run.add_parser("init"); init.add_argument("--target", type=int, default=10000); init.add_argument("--print-path", action="store_true")
    run.add_parser("list")
    for name in ("status", "preflight"):
        _run_arg(run.add_parser(name))
    execute = run.add_parser("execute"); _run_arg(execute); execute.add_argument("--kvk-provider", choices=("auto", "public-http", "public-browser"), default="auto"); execute.add_argument("--limit", type=int)
    e2e = run.add_parser("e2e")
    e2e.add_argument("--run-dir", type=Path)
    e2e_mode = e2e.add_mutually_exclusive_group(required=True)
    e2e_mode.add_argument("--limit-kvk-check", type=int)
    e2e_mode.add_argument("--all-kvk", action="store_true")
    e2e.add_argument("--interval", type=float, default=2.0)
    e2e.add_argument("--allow-partial", action="store_true")
    prepare = run.add_parser("prepare-pre-kvk"); _run_arg(prepare); prepare.add_argument("--refresh", action="store_true")
    sources = commands.add_parser("sources").add_subparsers(dest="sources_command", required=True)
    for name in ("discover", "list"):
        _run_arg(sources.add_parser(name))
    source_collect = sources.add_parser("collect"); _run_arg(source_collect); source_collect.add_argument("--only-source", action="append", default=[]); source_collect.add_argument("--skip-source", action="append", default=[]); source_collect.add_argument("--refresh", action="store_true"); source_collect.add_argument("--limit", type=int)
    source_measure = sources.add_parser("measure"); _run_arg(source_measure); source_measure.add_argument("--wikidata-limit", type=int, default=200)
    source_gleif = sources.add_parser("gleif"); _run_arg(source_gleif); source_gleif.add_argument("--archive", type=Path); source_gleif.add_argument("--limit", type=int); source_gleif.add_argument("--refresh", action="store_true")
    for command, source_id in (("anbi", "anbi_register"), ("duo", "duo_education_organisations")):
        source_register = sources.add_parser(command)
        _run_arg(source_register)
        source_register.add_argument("--archive", type=Path)
        source_register.add_argument("--limit", type=int)
        source_register.add_argument("--refresh", action="store_true")
        source_register.set_defaults(public_register_source_id=source_id)
    tenderned = sources.add_parser("tenderned")
    _run_arg(tenderned)
    tenderned.add_argument("--xlsx", type=Path)
    tenderned.add_argument("--json", type=Path)
    tenderned.add_argument("--refresh", action="store_true")
    source_import = sources.add_parser("import"); _run_arg(source_import); source_import.add_argument("--input", type=Path, required=True); source_import.add_argument("--source-id", required=True); source_import.add_argument("--name-column", required=True); source_import.add_argument("--kvk-column"); source_import.add_argument("--sheet")
    companies = commands.add_parser("companies").add_subparsers(dest="companies_command", required=True)
    for name in ("merge", "exclude-sole-proprietorships", "active-only"):
        _run_arg(companies.add_parser(name))
    _run_arg(companies.add_parser("pre-kvk-list"))
    _run_arg(companies.add_parser("pre-kvk-filter"))
    sample = companies.add_parser("sample"); _run_arg(sample); sample.add_argument("--size", type=int, default=500); sample.add_argument("--review-size", type=int, default=25); sample.add_argument("--pilot-size", type=int, default=50)
    sample_review = companies.add_parser("sample-review"); _run_arg(sample_review); sample_review.add_argument("--input", type=Path, required=True)
    merge = companies.add_parser("merge-lists"); merge.add_argument("--left", type=Path, required=True); merge.add_argument("--right", type=Path, required=True); merge.add_argument("--conflict-policy", choices=("exclude", "prefer-left", "prefer-right"), default="exclude"); merge.add_argument("--run-dir", type=Path)
    for side in ("left", "right"):
        merge.add_argument(f"--{side}-delimiter"); merge.add_argument(f"--{side}-encoding", default="utf-8-sig"); merge.add_argument(f"--{side}-sheet"); merge.add_argument(f"--{side}-name-column"); merge.add_argument(f"--{side}-kvk-column")
    kvk = commands.add_parser("kvk").add_subparsers(dest="kvk_command", required=True)
    kp = kvk.add_parser("preflight"); _run_arg(kp); _provider_arg(kp)
    kr = kvk.add_parser("resolve"); _run_arg(kr); _provider_arg(kr); kr.add_argument("--resume", action="store_true"); kr.add_argument("--refresh", action="store_true"); kr.add_argument("--headed", action="store_true"); kr.add_argument("--limit", type=int); kr.add_argument("--interval", type=float, default=2.0)
    kb = kvk.add_parser("pre-kvk-batch"); _run_arg(kb); kb.add_argument("--limit", type=int, default=10); kb.add_argument("--interval", type=float, default=2.0)
    kl = kvk.add_parser("pre-kvk-run"); _run_arg(kl); kl.add_argument("--interval", type=float, default=2.0)
    kl_mode = kl.add_mutually_exclusive_group(required=True)
    kl_mode.add_argument("--max-requests", type=int)
    kl_mode.add_argument("--until-complete", action="store_true")
    pilot = kvk.add_parser("pilot"); _run_arg(pilot); _provider_arg(pilot); pilot.add_argument("--refresh", action="store_true"); pilot.add_argument("--interval", type=float, default=2.0); pilot.add_argument("--review-size", type=int, default=20); pilot.add_argument("--max-live", type=int)
    pilot_review = kvk.add_parser("pilot-review"); _run_arg(pilot_review); pilot_review.add_argument("--input", type=Path, required=True)
    kc = kvk.add_parser("consolidate"); _run_arg(kc)
    exp = commands.add_parser("export"); _run_arg(exp); exp.add_argument("--allow-partial", action="store_true")
    rep = commands.add_parser("report"); _run_arg(rep)
    audit = commands.add_parser("audit").add_subparsers(dest="audit_command", required=True)
    av = audit.add_parser("verify"); _run_arg(av)
    at = audit.add_parser("trace"); _run_arg(at); at.add_argument("--kvk-number", required=True)
    return parser


def _options(args: argparse.Namespace, side: str) -> InputOptions:
    return InputOptions(getattr(args, f"{side}_delimiter"), getattr(args, f"{side}_encoding"), getattr(args, f"{side}_sheet"), getattr(args, f"{side}_name_column"), getattr(args, f"{side}_kvk_column"))


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    console_result(value)


def _dispatch_new_run(args: argparse.Namespace, root: Path) -> int:
    """Commando's die nog geen bestaande HARVEST-run nodig hebben."""
    if args.run_command == "init":
        run = initialize_run(root, args.target)
        print(run.path if args.print_path else json.dumps({"run_dir": str(run.path)}))
        console_result({"status": "CREATED"})
        return 0
    if args.run_command == "list":
        paths = sorted((root / "runs").glob("*")) if (root / "runs").exists() else []
        _print([str(path) for path in paths if (path / "run.json").is_file()])
        return 0
    if args.run_command == "e2e":
        if ((args.limit_kvk_check is not None and args.limit_kvk_check < 1)
                or not math.isfinite(args.interval) or args.interval < 2.0):
            raise HarvestError("E2E vereist een positieve KVK-limiet en minimaal 2 seconden KVK-interval")
        run = open_run(args.run_dir) if args.run_dir else initialize_run(
            root, args.limit_kvk_check if args.limit_kvk_check is not None else 10000
        )
        print(json.dumps({"run_dir": str(run.path), "phase": "STARTING"}), flush=True)
        emit("INFO", "Runmap aangemaakt of hervat")
        _print(run_end_to_end(run, args.limit_kvk_check, args.interval, args.allow_partial))
        return 0
    raise HarvestError("onbekend run-commando")


def _dispatch_run(args: argparse.Namespace, run: Run) -> int:
    """Bestaande run: status, preflight en expliciete voorbereidende stappen."""
    if args.run_command == "status":
        _print(run.metadata())
    elif args.run_command == "preflight":
        _print(run_preflight(run))
    elif args.run_command == "prepare-pre-kvk":
        _print(prepare_pre_kvk(run, args.refresh))
    elif args.run_command == "execute":
        if args.kvk_provider != "auto":
            raise HarvestError("run execute gebruikt alleen de publieke HTTP-route; gebruik kvk pre-kvk-batch")
        prepared_paths = prepare_pre_kvk(run)
        _print({"pre_kvk": prepared_paths, "kvk_batch": resolve_pre_kvk(run, args.limit) if args.limit else None})
    else:
        raise HarvestError("onbekend run-commando")
    return 0


def _dispatch_sources(args: argparse.Namespace, run: Run) -> int:
    """Broncommando's delen dezelfde bestaande run en uitvoerconventie."""
    if args.sources_command == "discover":
        _print(discover(run))
    elif args.sources_command == "list":
        _print(list_sources(run))
    elif args.sources_command == "collect":
        _print(collect(run, args.only_source, args.skip_source, args.limit, args.refresh))
    elif args.sources_command == "measure":
        _print(measure_sources(run, args.wikidata_limit))
    elif args.sources_command == "gleif":
        _print(collect_gleif(run, args.archive, args.limit, args.refresh))
    elif args.sources_command in {"anbi", "duo"}:
        _print(collect_public_register(run, args.public_register_source_id, args.archive, args.limit, args.refresh))
    elif args.sources_command == "tenderned":
        _print(collect_tenderned(run, args.xlsx, args.json, args.refresh))
    elif args.sources_command == "import":
        path = import_source(run, args.input, args.source_id, args.name_column, args.kvk_column, args.sheet)
        print(path)
        console_result(path)
    else:
        raise HarvestError("onbekend broncommando")
    return 0


def _dispatch_companies(args: argparse.Namespace, run: Run) -> int:
    """Bedrijvenstappen gebruiken hun bestaande gedeelde services."""
    if args.companies_command == "sample":
        _print(build_sample(run, args.size, args.review_size, args.pilot_size))
    elif args.companies_command == "sample-review":
        _print(record_sample_review(run, args.input))
    elif args.companies_command == "merge":
        _print(merge_candidates(run))
    elif args.companies_command == "pre-kvk-list":
        _print(build_pre_kvk_list(run))
    elif args.companies_command == "pre-kvk-filter":
        _print(build_pre_kvk_filter(run))
    elif args.companies_command == "exclude-sole-proprietorships":
        _print(exclude_sole_proprietorships(run))
    elif args.companies_command == "active-only":
        _print(active_only(run))
    else:
        raise HarvestError("onbekend bedrijvencommando")
    return 0


def _dispatch_kvk(args: argparse.Namespace, run: Run) -> int:
    """KVK-transport en vervolgverwerking blijven expliciet gescheiden."""
    if args.kvk_command == "preflight":
        value = kvk_preflight(run, args.provider)
        print(value)
        console_result(value)
    elif args.kvk_command == "pilot":
        _print(run_matching_pilot(run, args.provider, args.interval, args.refresh, args.review_size, args.max_live))
    elif args.kvk_command == "pilot-review":
        _print(record_matching_review(run, args.input))
    elif args.kvk_command == "resolve":
        _print(resolve(run, args.provider, args.limit, args.resume, args.refresh, args.headed, args.interval))
    elif args.kvk_command == "pre-kvk-batch":
        _print(resolve_pre_kvk(run, args.limit, args.interval))
    elif args.kvk_command == "pre-kvk-run":
        _print(run_pre_kvk(run, args.interval, args.max_requests))
    elif args.kvk_command == "consolidate":
        value = consolidate(run)
        print(value)
        console_result(value)
    else:
        raise HarvestError("onbekend KVK-commando")
    return 0


def _dispatch_audit(args: argparse.Namespace, run: Run) -> int:
    if args.audit_command == "verify":
        _print(verify(run))
    elif args.audit_command == "trace":
        _print(trace(run, args.kvk_number))
    else:
        raise HarvestError("onbekend auditcommando")
    return 0


def dispatch(args: argparse.Namespace) -> int:
    """Routeer op workflow en commandofamilie zonder zijpaden in de keten."""
    root = data_root(args.data_dir)
    if args.command == "doctor":
        _print(host(root))
        return 0
    if args.command == "run" and args.run_command in {"init", "list", "e2e"}:
        return _dispatch_new_run(args, root)
    if args.command == "companies" and args.companies_command == "merge-lists":
        run = open_run(args.run_dir) if args.run_dir else initialize_run(root, 1, "MERGE_LISTS")
        paths = merge_lists(run, args.left, args.right, args.conflict_policy, _options(args, "left"), _options(args, "right"))
        _print([str(path) for path in paths])
        return 0
    run = open_run(args.run_dir)
    if args.command == "run":
        return _dispatch_run(args, run)
    if args.command == "sources":
        return _dispatch_sources(args, run)
    if args.command == "companies":
        return _dispatch_companies(args, run)
    if args.command == "kvk":
        return _dispatch_kvk(args, run)
    if args.command == "export":
        _print(export(run, args.allow_partial))
        return 0
    if args.command == "report":
        value = report(run)
        print(value)
        console_result(value)
        return 0
    if args.command == "audit":
        return _dispatch_audit(args, run)
    raise HarvestError("onbekend commando")


def main(argv: Sequence[str] | None = None) -> int:
    with console_active():
        args = build_parser().parse_args(argv)
        command = " ".join(str(part) for part in (
            args.command, getattr(args, f"{args.command}_command", None)
        ) if part is not None)
        emit("START", command)
        try:
            with phase(command):
                return dispatch(args)
        except HarvestError as exc:
            emit("FOUT", f"Commando gestopt (exitcode {exc.exit_code})")
            print(f"FOUT: {error_text(str(exc), exc.exit_code)}", file=sys.stderr)
            return exc.exit_code
        except KeyboardInterrupt:
            emit("WARN", "Onderbroken; voortgang is gecheckpoint")
            print("ONDERBROKEN: voortgang is gecheckpoint; hervat de bestaande run", file=sys.stderr)
            return 130
        except csv.Error:
            emit("FOUT", "CSV/TSV-invoer ongeldig of boven de veldlimiet")
            print(f"FOUT: CSV/TSV-invoer ongeldig of veld groter dan {CSV_FIELD_SIZE_LIMIT} tekens", file=sys.stderr)
            return 3
        except Exception as exc:
            emit("FOUT", "Onverwachte technische fout")
            print(f"FOUT: onverwachte technische fout ({type(exc).__name__})", file=sys.stderr)
            return 1
