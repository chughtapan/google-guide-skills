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
from .installer import (
    DEFAULT_AGENTS,
    SWE_BOOK_COLLECTION_ID,
    InstallLinkAction,
    install,
    install_links,
    require_swe_book_license_acceptance,
    selected_install_skills,
    swe_book_license_notice,
)
from .manifest import find_project_root, load_manifest
from .metrics import write_metrics
from .models import Manifest, ValidationIssue
from .sources import sync
from .validation import has_errors, validate


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="google-guides",
        description=(
            "Convert licensed Google guides into Agent Skills, install them, and test selection."
        ),
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
    build_parser.add_argument("--include-swe-book", action="store_true", dest="include_local")
    build_parser.add_argument("--no-sync", action="store_true")

    subparsers.add_parser("catalog", help="Regenerate catalog files")
    metrics_parser = subparsers.add_parser("metrics", help="Measure every generated text file")
    metrics_parser.add_argument("--include-swe-book", action="store_true", dest="include_local")
    validate_parser = subparsers.add_parser("validate", help="Validate all skill invariants")
    validate_parser.add_argument("--include-swe-book", action="store_true", dest="include_local")
    validate_parser.add_argument("--json", action="store_true", dest="json_output")

    install_parser = subparsers.add_parser(
        "install",
        help="Install for the current user (recommended) or an explicit project",
    )
    install_parser.add_argument("--project", type=Path)
    install_parser.add_argument("--agent", action="append", choices=DEFAULT_AGENTS)
    install_parser.add_argument("--skill", action="append", dest="skills")
    install_parser.add_argument("--copy", action="store_true")
    install_parser.add_argument(
        "--include-swe-book",
        action="store_true",
        help="Generate and link the Software Engineering at Google skills",
    )
    install_parser.add_argument(
        "--accept-swe-book-license",
        action="store_true",
        help="Accept the SWE-book CC BY-NC-ND 4.0 license without an interactive prompt",
    )
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
        mode_parser.add_argument("--include-swe-book", action="store_true", dest="include_local")
        mode_parser.add_argument("--timeout", type=int, default=180)
        mode_parser.add_argument(
            "--model",
            action="append",
            metavar="AGENT=MODEL",
            help="Override one client's configured/default model",
        )
        mode_parser.add_argument("--results-root", type=Path)
        mode_parser.add_argument(
            "--live",
            action="store_true",
            help="Run with the selected clients' existing logins (default: plan only)",
        )
        mode_parser.add_argument("--keep-raw", action="store_true")

    all_parser = subparsers.add_parser("all", help="Sync, build, catalog, measure, and validate")
    all_parser.add_argument("--include-swe-book", action="store_true", dest="include_local")
    return parser


def _manifest(path: Path | None) -> Manifest:
    if path is None:
        return load_manifest(find_project_root() / "corpus.yaml")
    return load_manifest(path)


def _print_validation(issues: list[ValidationIssue], as_json: bool = False) -> None:
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


def _run_sync(args: argparse.Namespace, manifest: Manifest) -> int:
    for path in sync(manifest, args.repositories):
        print(path.relative_to(manifest.project_root))
    return 0


def _run_build(args: argparse.Namespace, manifest: Manifest) -> int:
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


def _run_catalog(_args: argparse.Namespace, manifest: Manifest) -> int:
    for path in write_catalog(manifest):
        print(path.relative_to(manifest.project_root))
    return 0


def _run_metrics(args: argparse.Namespace, manifest: Manifest) -> int:
    for path in write_metrics(manifest, include_local=args.include_local):
        print(path.relative_to(manifest.project_root))
    return 0


def _run_validate(args: argparse.Namespace, manifest: Manifest) -> int:
    issues = validate(manifest, include_local=args.include_local)
    _print_validation(issues, as_json=args.json_output)
    return 1 if has_errors(issues) else 0


def _prepare_swe_book_install(
    args: argparse.Namespace,
    manifest: Manifest,
    local_skills: list[str],
) -> None:
    if not local_skills:
        return
    if args.dry_run:
        print(f"license acceptance required: {swe_book_license_notice(manifest)}")
        return
    notice = require_swe_book_license_acceptance(
        manifest,
        accepted=args.accept_swe_book_license,
    )
    print(f"license accepted: {notice}")
    built = build(
        manifest,
        collection_ids=[SWE_BOOK_COLLECTION_ID],
        include_local=True,
    )
    write_metrics(manifest, include_local=True)
    print(f"Generated {len(built)} SWE-book skill(s).")


def _validate_install(manifest: Manifest, *, include_swe_book: bool) -> None:
    issues = validate(manifest, include_local=include_swe_book)
    if has_errors(issues):
        option = " --include-swe-book" if include_swe_book else ""
        raise GoogleGuideSkillsError(
            f"Generated skills failed validation; run `google-guides validate{option}` for details"
        )


def _print_link_actions(actions: list[InstallLinkAction]) -> None:
    for action in actions:
        source_kind = "SWE-book" if action.distribution == "local-only" else "public"
        print(f"{action.status}: {action.destination} -> {action.source} [{source_kind}]")


def _run_install(args: argparse.Namespace, manifest: Manifest) -> int:
    agents = args.agent or list(DEFAULT_AGENTS)
    committed_skills, local_skills = selected_install_skills(
        manifest,
        args.skills,
        include_local=args.include_swe_book,
    )
    project = args.project
    if project is not None and not project.is_dir():
        raise GoogleGuideSkillsError(f"Install project does not exist: {project}")
    if project is None and args.copy:
        raise GoogleGuideSkillsError("User installation uses symlinks; --copy requires --project")
    _prepare_swe_book_install(args, manifest, local_skills)
    _validate_install(
        manifest,
        include_swe_book=bool(local_skills) and not args.dry_run,
    )
    commands = []
    if project is not None and committed_skills:
        commands = install(
            manifest,
            project,
            agents,
            skills=committed_skills,
            copy=args.copy,
            dry_run=args.dry_run,
        )
    if args.dry_run:
        for command in commands:
            print(shlex.join(command))
    if args.copy and local_skills:
        print("--copy applies to public skills; SWE-book skills are linked.")
    link_skills = local_skills if project is not None else committed_skills + local_skills
    if link_skills:
        actions = install_links(
            manifest,
            agents,
            skills=link_skills,
            include_local=bool(local_skills),
            dry_run=args.dry_run,
            project=project,
        )
        _print_link_actions(actions)
    return 0


def _evaluation_models(args: argparse.Namespace) -> dict[str, str]:
    models: dict[str, str] = {}
    for value in args.model or []:
        agent, separator, model = value.partition("=")
        if not separator or agent not in SUPPORTED_AGENTS or not model:
            raise GoogleGuideSkillsError("--model must use AGENT=MODEL with a supported agent name")
        if agent in models:
            raise GoogleGuideSkillsError(f"Model specified more than once for {agent}")
        models[agent] = model
    return models


def _print_evaluation_plan(
    args: argparse.Namespace,
    agents: list[str],
    case_count: int,
) -> None:
    if not args.live:
        return
    profile_count = 2 if args.eval_mode == "quality" else 1
    processes = case_count * len(agents) * args.repeat * profile_count
    print(f"Executing {processes} isolated process(es) with existing client login(s).")


def _run_eval(args: argparse.Namespace, manifest: Manifest) -> int:
    agents = args.agent or list(SUPPORTED_AGENTS)
    stages = args.stages or (["smoke"] if args.eval_mode == "triggers" else ["representative"])
    cases = select_cases(
        load_cases(manifest),
        stages=stages,
        splits=args.splits,
        case_ids=args.case_ids,
        require_rubric=args.eval_mode == "quality",
        limit=args.limit,
    )
    _print_evaluation_plan(args, agents, len(cases))
    report, output = run_evaluation(
        manifest,
        cases,
        mode=args.eval_mode,
        agents=agents,
        profile=args.profile,
        repeat=args.repeat,
        include_local=args.include_local,
        timeout=args.timeout,
        models=_evaluation_models(args),
        dry_run=not args.live,
        keep_raw=args.keep_raw,
        results_root=args.results_root,
    )
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    try:
        print(output.relative_to(manifest.project_root))
    except ValueError:
        print(output)
    summary = report["summary"]
    failed = summary.get("failed_processes", 0) or summary.get("infrastructure_errors", 0)
    return 1 if args.live and failed else 0


def _run_all(args: argparse.Namespace, manifest: Manifest) -> int:
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


COMMAND_HANDLERS = {
    "sync": _run_sync,
    "build": _run_build,
    "catalog": _run_catalog,
    "metrics": _run_metrics,
    "validate": _run_validate,
    "install": _run_install,
    "eval": _run_eval,
    "all": _run_all,
}


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface and convert expected errors to exit status 2."""
    args = _parser().parse_args(argv)
    try:
        return COMMAND_HANDLERS[args.command](args, _manifest(args.manifest))
    except (GoogleGuideSkillsError, ManifestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
