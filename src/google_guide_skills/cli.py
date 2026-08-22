"""Command-line interface for generation, measurement, validation, and evaluation."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from .builder import assert_canonical_runtime, build
from .catalog import write_catalog
from .errors import GoogleGuideSkillsError, ManifestError
from .evals import (
    SUPPORTED_AGENTS,
    SUPPORTED_PROFILES,
    SUPPORTED_STAGES,
    load_cases,
    run_evaluation,
    select_cases,
)
from .installer import DEFAULT_AGENTS, install
from .manifest import find_project_root, load_manifest
from .metrics import write_metrics
from .sources import sync
from .validation import has_errors, validate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="google-guides",
        description="Generate portable Agent Skills from pinned, licensed Google guides.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Path to corpus.yaml (defaults to the nearest project root)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="Clone and checkout pinned repositories")
    sync_parser.add_argument("--repository", action="append", dest="repositories")

    build_parser = subparsers.add_parser("build", help="Build generated skills")
    build_parser.add_argument("--collection", action="append", dest="collections")
    build_parser.add_argument("--skill", action="append", dest="skills")
    build_parser.add_argument("--include-local", action="store_true")
    build_parser.add_argument("--no-sync", action="store_true")

    subparsers.add_parser("catalog", help="Regenerate catalog files and the index skill")
    metrics_parser = subparsers.add_parser("metrics", help="Measure every generated text file")
    metrics_parser.add_argument("--include-local", action="store_true")
    validate_parser = subparsers.add_parser("validate", help="Validate all skill invariants")
    validate_parser.add_argument("--include-local", action="store_true")
    validate_parser.add_argument("--json", action="store_true", dest="json_output")

    install_parser = subparsers.add_parser("install", help="Install skills through npx skills")
    install_parser.add_argument("--project", type=Path, default=Path.cwd())
    install_parser.add_argument("--agent", action="append", choices=DEFAULT_AGENTS)
    install_parser.add_argument("--skill", action="append", dest="skills")
    install_parser.add_argument("--copy", action="store_true")
    install_parser.add_argument("--dry-run", action="store_true")

    eval_parser = subparsers.add_parser(
        "eval", help="Run fresh-process skill discoverability and quality evaluations"
    )
    eval_subparsers = eval_parser.add_subparsers(dest="eval_mode", required=True)
    for mode in ("triggers", "quality"):
        mode_parser = eval_subparsers.add_parser(mode)
        mode_parser.add_argument("--agent", action="append", choices=SUPPORTED_AGENTS)
        mode_parser.add_argument("--profile", choices=SUPPORTED_PROFILES, default="all")
        mode_parser.add_argument(
            "--stage", action="append", dest="stages", choices=SUPPORTED_STAGES
        )
        mode_parser.add_argument(
            "--split", action="append", dest="splits", choices=("train", "validation")
        )
        mode_parser.add_argument("--case", action="append", dest="case_ids")
        mode_parser.add_argument("--repeat", type=int, default=1)
        mode_parser.add_argument("--limit", type=int)
        mode_parser.add_argument("--include-local", action="store_true")
        mode_parser.add_argument("--timeout", type=int, default=180)
        mode_parser.add_argument("--max-budget-usd", type=float)
        mode_parser.add_argument("--codex-model")
        mode_parser.add_argument("--claude-model")
        mode_parser.add_argument("--results-root", type=Path)
        mode_parser.add_argument(
            "--live", action="store_true", help="Execute model calls (default: plan only)"
        )
        mode_parser.add_argument(
            "--accept-cost", action="store_true", help="Acknowledge live model-call cost"
        )
        mode_parser.add_argument("--keep-raw", action="store_true")
        mode_parser.add_argument(
            "--accept-credential-risk",
            action="store_true",
            help="Confirm use of dedicated disposable provider API keys",
        )

    all_parser = subparsers.add_parser("all", help="Sync, build, catalog, measure, and validate")
    all_parser.add_argument("--include-local", action="store_true")
    return parser


def _manifest(path: Path | None):
    if path is None:
        return load_manifest(find_project_root() / "corpus.yaml")
    return load_manifest(path)


def _print_validation(issues, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps([issue.to_dict() for issue in issues], indent=2, sort_keys=True))
        return
    if not issues:
        print("Validation passed with no findings.")
        return
    for issue in issues:
        print(f"{issue.severity.upper()}: {issue.path}: {issue.message}")
    errors = sum(issue.severity == "error" for issue in issues)
    warnings = sum(issue.severity == "warning" for issue in issues)
    print(f"Validation finished: {errors} error(s), {warnings} warning(s).")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = _manifest(args.manifest)
        if args.command == "sync":
            paths = sync(manifest, args.repositories)
            for path in paths:
                print(path.relative_to(manifest.project_root))
            return 0
        if args.command == "build":
            built = build(
                manifest,
                collection_ids=args.collections,
                artifact_names=args.skills,
                include_local=args.include_local,
                sync_first=not args.no_sync,
            )
            write_catalog(manifest)
            write_metrics(manifest)
            if args.include_local:
                write_metrics(manifest, include_local=True)
            for skill in built:
                print(f"{skill.distribution}: {skill.path.relative_to(manifest.project_root)}")
            return 0
        if args.command == "catalog":
            for path in write_catalog(manifest):
                print(path.relative_to(manifest.project_root))
            return 0
        if args.command == "metrics":
            for path in write_metrics(manifest, include_local=args.include_local):
                print(path.relative_to(manifest.project_root))
            return 0
        if args.command == "validate":
            issues = validate(manifest, include_local=args.include_local)
            _print_validation(issues, as_json=args.json_output)
            return 1 if has_errors(issues) else 0
        if args.command == "install":
            commands = install(
                manifest,
                args.project,
                args.agent or list(DEFAULT_AGENTS),
                skills=args.skills,
                include_local=False,
                copy=args.copy,
                global_install=False,
                dry_run=args.dry_run,
            )
            if args.dry_run:
                for command in commands:
                    print(shlex.join(command))
            return 0
        if args.command == "eval":
            if args.live and not args.accept_cost:
                raise GoogleGuideSkillsError("Live evaluations require --accept-cost")
            if args.live and not args.accept_credential_risk:
                raise GoogleGuideSkillsError(
                    "Live evaluations require --accept-credential-risk and disposable API keys"
                )
            selected_agents = args.agent or list(SUPPORTED_AGENTS)
            if (
                args.live
                and "claude-code" in selected_agents
                and args.max_budget_usd is None
            ):
                raise GoogleGuideSkillsError(
                    "Live Claude evaluations require an explicit --max-budget-usd soft cap"
                )
            max_budget_usd = (
                0.25 if args.max_budget_usd is None else args.max_budget_usd
            )
            stages = args.stages or (
                ["smoke"] if args.eval_mode == "triggers" else ["representative"]
            )
            cases = select_cases(
                load_cases(manifest),
                stages=stages,
                splits=args.splits,
                case_ids=args.case_ids,
                require_rubric=args.eval_mode == "quality",
                limit=args.limit,
            )
            models = {
                key: value
                for key, value in {
                    "codex": args.codex_model,
                    "claude-code": args.claude_model,
                }.items()
                if value
            }
            if args.live:
                profile_count = (
                    2
                    if args.eval_mode == "quality" or args.profile == "index-ab"
                    else 1
                )
                processes = (
                    len(cases)
                    * len(args.agent or SUPPORTED_AGENTS)
                    * args.repeat
                    * profile_count
                )
                claude_calls = (
                    len(cases) * args.repeat * profile_count
                    if "claude-code" in (args.agent or SUPPORTED_AGENTS)
                    else 0
                )
                print(
                    f"Executing {processes} isolated process(es); Claude soft-cap sum "
                    f"${claude_calls * max_budget_usd:.2f} (individual calls may overshoot)."
                )
            report, output = run_evaluation(
                manifest,
                cases,
                mode=args.eval_mode,
                agents=args.agent or list(SUPPORTED_AGENTS),
                profile=args.profile,
                repeat=args.repeat,
                include_local=args.include_local,
                timeout=args.timeout,
                max_budget_usd=max_budget_usd,
                models=models,
                dry_run=not args.live,
                keep_raw=args.keep_raw,
                results_root=args.results_root,
                accept_credential_risk=args.accept_credential_risk,
            )
            print(json.dumps(report["summary"], indent=2, sort_keys=True))
            try:
                print(output.relative_to(manifest.project_root))
            except ValueError:
                print(output)
            summary = report["summary"]
            if args.live and (
                summary.get("failed_processes", 0)
                or summary.get("infrastructure_errors", 0)
            ):
                return 1
            return 0
        if args.command == "all":
            assert_canonical_runtime(manifest)
            sync(manifest)
            built = build(manifest, include_local=args.include_local, sync_first=False)
            write_catalog(manifest)
            write_metrics(manifest)
            if args.include_local:
                write_metrics(manifest, include_local=True)
            issues = validate(manifest, include_local=args.include_local)
            _print_validation(issues)
            print(f"Built {len(built)} skill(s).")
            return 1 if has_errors(issues) else 0
        raise AssertionError(f"Unhandled command: {args.command}")
    except (GoogleGuideSkillsError, ManifestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
