"""Exact token and file-size metrics for generated skill trees."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import tiktoken
import yaml

from .errors import GoogleGuideSkillsError
from .models import Manifest
from .path_policy import require_safe_project_path

TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}
CODEX_FALLBACK_METADATA_CHARS = 8000
MIN_SUPPORTED_INSTALL_ROOT_CHARS = 48
REFERENCE_INSTALL_ROOT = "/workspace/google-guide-skills/.agents/skills"


def _kind(path: Path) -> str:
    if path.name == "SKILL.md":
        return "skill"
    if path.name.startswith("LICENSE") and path.suffix == ".txt":
        return "license"
    if path.name == "source.json":
        return "provenance"
    if "references" in path.parts:
        return "reference"
    return "other"


def _metadata_text(skill_text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", skill_text, flags=re.DOTALL)
    return match.group(1) if match else ""


def metadata_budget(
    skill_dirs: list[Path], *, install_root: str = REFERENCE_INSTALL_ROOT
) -> dict[str, object]:
    """Measure startup metadata using a stable documented Codex list rendering."""

    encoding = tiktoken.get_encoding("o200k_base")
    records: list[tuple[str, str]] = []
    for skill_dir in sorted(skill_dirs):
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        metadata = yaml.safe_load(_metadata_text(text))
        if not isinstance(metadata, dict):
            continue
        name = metadata.get("name")
        description = metadata.get("description")
        if isinstance(name, str) and isinstance(description, str):
            records.append((name, " ".join(description.split())))
    rendered = "".join(
        f"- {name}: {description} "
        f"(file: {install_root}/{name}/SKILL.md)\n"
        for name, description in records
    )
    path_independent_chars = len(rendered) - len(records) * len(install_root)
    maximum_root_chars = (
        (CODEX_FALLBACK_METADATA_CHARS - path_independent_chars) // len(records)
        if records
        else CODEX_FALLBACK_METADATA_CHARS
    )
    description_text = "\n".join(description for _name, description in records)
    return {
        "skills": len(records),
        "description_chars": sum(len(description) for _name, description in records),
        "description_tokens_o200k_base": len(encoding.encode(description_text)),
        "reference_install_root": install_root,
        "codex_list_chars": len(rendered),
        "path_independent_list_chars": path_independent_chars,
        "maximum_install_root_chars": maximum_root_chars,
        "codex_fallback_limit_chars": CODEX_FALLBACK_METADATA_CHARS,
        "headroom_chars": CODEX_FALLBACK_METADATA_CHARS - len(rendered),
    }


def collect_metrics(manifest: Manifest, include_local: bool = False) -> dict[str, object]:
    encoding = tiktoken.get_encoding("o200k_base")
    roots = [manifest.root_for("committed")]
    if include_local:
        roots.append(manifest.root_for("local-only"))
    files: list[dict[str, object]] = []
    skills: list[dict[str, object]] = []
    measured_skill_dirs: list[Path] = []

    for root in roots:
        if not root.is_dir():
            continue
        for skill_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            measured_skill_dirs.append(skill_dir)
            skill_files: list[dict[str, object]] = []
            for path in sorted(skill_dir.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                text = path.read_text(encoding="utf-8")
                record = {
                    "path": path.relative_to(manifest.project_root).as_posix(),
                    "skill": skill_dir.name,
                    "kind": _kind(path),
                    "bytes": len(text.encode("utf-8")),
                    "lines": len(text.splitlines()),
                    "words": len(re.findall(r"\S+", text)),
                    "tokens_o200k_base": len(encoding.encode(text)),
                }
                files.append(record)
                skill_files.append(record)
            skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            skill_record = next(
                (record for record in skill_files if record["kind"] == "skill"), None
            )
            skills.append(
                {
                    "skill": skill_dir.name,
                    "distribution": "local-only"
                    if root == manifest.root_for("local-only")
                    else "committed",
                    "metadata_tokens_o200k_base": len(encoding.encode(_metadata_text(skill_text))),
                    "skill_md_tokens_o200k_base": skill_record["tokens_o200k_base"]
                    if skill_record
                    else 0,
                    "reference_tokens_o200k_base": sum(
                        int(record["tokens_o200k_base"])
                        for record in skill_files
                        if record["kind"] == "reference"
                    ),
                    "license_tokens_o200k_base": sum(
                        int(record["tokens_o200k_base"])
                        for record in skill_files
                        if record["kind"] == "license"
                    ),
                    "total_tokens_o200k_base": sum(
                        int(record["tokens_o200k_base"]) for record in skill_files
                    ),
                    "files": len(skill_files),
                }
            )
    return {
        "schema_version": 1,
        "encoding": "o200k_base",
        "includes_local_only": include_local,
        "summary": {
            "skills": len(skills),
            "files": len(files),
            "tokens_o200k_base": sum(int(record["tokens_o200k_base"]) for record in files),
        },
        "metadata_budget": metadata_budget(measured_skill_dirs),
        "skills": skills,
        "files": files,
    }


def write_metrics(manifest: Manifest, include_local: bool = False) -> tuple[Path, Path]:
    metrics = collect_metrics(manifest, include_local=include_local)
    output_dir = (
        manifest.project_root / ".generated" / "metrics"
        if include_local
        else manifest.project_root / "catalog"
    )
    output_dir = require_safe_project_path(
        manifest.project_root,
        output_dir,
        context="Metrics output",
        error_type=GoogleGuideSkillsError,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "tokens.json"
    csv_path = output_dir / "tokens.csv"
    for path in (json_path, csv_path):
        require_safe_project_path(
            manifest.project_root,
            path,
            context="Metrics output",
            error_type=GoogleGuideSkillsError,
        )
    json_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    fields = ["path", "skill", "kind", "bytes", "lines", "words", "tokens_o200k_base"]
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(metrics["files"])
    return json_path, csv_path
