"""Volledig command-linecontract voor Company Harvest."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from company_harvest import __version__
from company_harvest.audit import trace, verify
from company_harvest.core import HarvestError, data_root, initialize_run, open_run
from company_harvest.gleif import collect_gleif
from company_harvest.kvk import preflight as kvk_preflight
from company_harvest.kvk import resolve
from company_harvest.merge_lists import InputOptions, merge_lists
from company_harvest.preflight import host, run_preflight
from company_harvest.public_registers import collect_public_register
from company_harvest.sources import collect, discover, import_source, list_sources, measure_sources
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="company-harvest", description="Lokale, auditbare bedrijfsverzameling en offline lijstmerge")
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
    source_import = sources.add_parser("import"); _run_arg(source_import); source_import.add_argument("--input", type=Path, required=True); source_import.add_argument("--source-id", required=True); source_import.add_argument("--name-column", required=True); source_import.add_argument("--kvk-column"); source_import.add_argument("--sheet")
    companies = commands.add_parser("companies").add_subparsers(dest="companies_command", required=True)
    for name in ("merge", "exclude-sole-proprietorships", "active-only"):
        _run_arg(companies.add_parser(name))
    merge = companies.add_parser("merge-lists"); merge.add_argument("--left", type=Path, required=True); merge.add_argument("--right", type=Path, required=True); merge.add_argument("--conflict-policy", choices=("exclude", "prefer-left", "prefer-right"), default="exclude"); merge.add_argument("--run-dir", type=Path)
    for side in ("left", "right"):
        merge.add_argument(f"--{side}-delimiter"); merge.add_argument(f"--{side}-encoding", default="utf-8-sig"); merge.add_argument(f"--{side}-sheet"); merge.add_argument(f"--{side}-name-column"); merge.add_argument(f"--{side}-kvk-column")
    kvk = commands.add_parser("kvk").add_subparsers(dest="kvk_command", required=True)
    kp = kvk.add_parser("preflight"); _run_arg(kp); _provider_arg(kp)
    kr = kvk.add_parser("resolve"); _run_arg(kr); _provider_arg(kr); kr.add_argument("--resume", action="store_true"); kr.add_argument("--refresh", action="store_true"); kr.add_argument("--headed", action="store_true"); kr.add_argument("--limit", type=int); kr.add_argument("--interval", type=float, default=2.0)
    kc = kvk.add_parser("consolidate"); _run_arg(kc)
    exp = commands.add_parser("export"); _run_arg(exp); exp.add_argument("--limit", type=int, default=10000); exp.add_argument("--allow-partial", action="store_true")
    rep = commands.add_parser("report"); _run_arg(rep)
    audit = commands.add_parser("audit").add_subparsers(dest="audit_command", required=True)
    av = audit.add_parser("verify"); _run_arg(av)
    at = audit.add_parser("trace"); _run_arg(at); at.add_argument("--kvk-number", required=True)
    return parser


def _options(args: argparse.Namespace, side: str) -> InputOptions:
    return InputOptions(getattr(args, f"{side}_delimiter"), getattr(args, f"{side}_encoding"), getattr(args, f"{side}_sheet"), getattr(args, f"{side}_name_column"), getattr(args, f"{side}_kvk_column"))


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def dispatch(args: argparse.Namespace) -> int:
    root = data_root(args.data_dir)
    if args.command == "doctor": _print(host(root)); return 0
    if args.command == "run" and args.run_command == "init":
        run = initialize_run(root, args.target)
        print(run.path if args.print_path else json.dumps({"run_dir": str(run.path)}))
        return 0
    if args.command == "run" and args.run_command == "list":
        _print([str(path) for path in sorted((root / "runs").glob("*")) if (path / "run.json").is_file()] if (root / "runs").exists() else []); return 0
    if args.command == "companies" and args.companies_command == "merge-lists":
        run = open_run(args.run_dir) if args.run_dir else initialize_run(root, 1, "MERGE_LISTS")
        paths = merge_lists(run, args.left, args.right, args.conflict_policy, _options(args, "left"), _options(args, "right")); _print([str(path) for path in paths]); return 0
    run = open_run(args.run_dir)
    if args.command == "run" and args.run_command == "status": _print(run.metadata()); return 0
    if args.command == "run" and args.run_command == "preflight": _print(run_preflight(run)); return 0
    if args.command == "sources" and args.sources_command == "discover": _print(discover(run)); return 0
    if args.command == "sources" and args.sources_command == "list": _print(list_sources(run)); return 0
    if args.command == "sources" and args.sources_command == "collect": _print(collect(run, args.only_source, args.skip_source, args.limit, args.refresh)); return 0
    if args.command == "sources" and args.sources_command == "measure": _print(measure_sources(run, args.wikidata_limit)); return 0
    if args.command == "sources" and args.sources_command == "gleif": _print(collect_gleif(run, args.archive, args.limit, args.refresh)); return 0
    if args.command == "sources" and args.sources_command in {"anbi", "duo"}: _print(collect_public_register(run, args.public_register_source_id, args.archive, args.limit, args.refresh)); return 0
    if args.command == "sources" and args.sources_command == "import": print(import_source(run, args.input, args.source_id, args.name_column, args.kvk_column, args.sheet)); return 0
    if args.command == "companies" and args.companies_command == "merge": _print(merge_candidates(run)); return 0
    if args.command == "kvk" and args.kvk_command == "preflight": print(kvk_preflight(run, args.provider)); return 0
    if args.command == "kvk" and args.kvk_command == "resolve": _print(resolve(run, args.provider, args.limit, args.resume, args.refresh, args.headed, args.interval)); return 0
    if args.command == "kvk" and args.kvk_command == "consolidate": print(consolidate(run)); return 0
    if args.command == "companies" and args.companies_command == "exclude-sole-proprietorships": _print(exclude_sole_proprietorships(run)); return 0
    if args.command == "companies" and args.companies_command == "active-only": _print(active_only(run)); return 0
    if args.command == "export": _print(export(run, args.limit, args.allow_partial)); return 0
    if args.command == "report": print(report(run)); return 0
    if args.command == "audit" and args.audit_command == "verify": _print(verify(run)); return 0
    if args.command == "audit" and args.audit_command == "trace": _print(trace(run, args.kvk_number)); return 0
    if args.command == "run" and args.run_command == "execute":
        discover(run); collect(run); merge_candidates(run); kvk_preflight(run, args.kvk_provider); resolve(run, args.kvk_provider, args.limit, True, False, False); consolidate(run); exclude_sole_proprietorships(run); active_only(run); export(run, run.metadata()["target"]); report(run); return 0
    raise HarvestError("onbekend commando")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return dispatch(build_parser().parse_args(argv))
    except HarvestError as exc:
        print(f"FOUT: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("ONDERBROKEN: voortgang is gecheckpoint; hervat de bestaande run", file=sys.stderr)
        return 130
