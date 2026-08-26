"""Build deterministic Agent Skill directories from manifest artifacts."""

from __future__ import annotations

import fnmatch
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .convert import (
    MARKDOWN_IMAGE_RE,
    MARKDOWN_LINK_RE,
    markdown_fenced_segments,
    markdown_inline_segments,
    next_markdown_fence,
    source_to_markdown,
)
from .errors import BuildError
from .git_safe import command as git_command
from .git_safe import environment as git_environment
from .git_safe import git_dir_is_safe, repository_config_problem
from .models import Artifact, BuiltSkill, Collection, LicenseInfo, Manifest, Repository
from .path_policy import require_safe_project_path
from .project_license import (
    PROJECT_LICENSE_SHA256,
    WRAPPER_LICENSE_FILENAME,
    verified_project_license,
    wrapper_license_metadata,
)
from .sources import checkout_path, sync

GLOB_CHARS = frozenset("*?[")
ALLOWED_SUPPLEMENTAL_LICENSES = {("Apache-2.0", "LICENSE"): PROJECT_LICENSE_SHA256}
MANDATORY_SOURCE_PATH_RULES = {
    "resources/swe-book/html/**": (
        "local-only",
        "Software Engineering at Google is generated only into ignored local output.",
    ),
    "Rguide.md": (
        "catalog-only",
        "The R guide has composite upstream licensing pending a redistribution audit.",
    ),
}


@dataclass(frozen=True)
class _PreparedSources:
    running_python: str
    repository: Repository
    checkout: Path
    inputs: tuple[Path, ...]
    license_info: LicenseInfo
    matched_path_policies: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class _SelectedExcerpt:
    """Source-authored blocks selected for one rendered section."""

    source_title: str
    heading: str
    blocks: tuple[str, ...]


def assert_canonical_runtime(manifest: Manifest) -> str:
    """Reject non-canonical generation before source sync or output mutation."""
    running_python = platform.python_version()
    if running_python != manifest.canonical_python:
        raise BuildError(
            f"Canonical generation requires Python {manifest.canonical_python}; "
            f"running {running_python}"
        )
    return running_python


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _frontmatter(name: str, description: str) -> str:
    wrapped = textwrap.wrap(
        " ".join(description.split()),
        width=94,
        break_long_words=False,
        break_on_hyphens=False,
    )
    description_lines = "\n".join(f"  {line}" for line in wrapped)
    return f"---\nname: {name}\ndescription: >-\n{description_lines}\n---\n"


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _assert_safe_output_root(manifest: Manifest, distribution: str) -> Path:
    """Reject symlinked or physically overlapping generated roots before writing."""
    output_root = require_safe_project_path(
        manifest.project_root,
        manifest.root_for(distribution),
        context="Generated output path",
        error_type=BuildError,
    )
    other_distribution = "local-only" if distribution == "committed" else "committed"
    other_root = manifest.root_for(other_distribution)
    if output_root.resolve() == other_root.resolve():
        raise BuildError("Committed and local-only generated roots resolve to the same directory")
    return output_root


def _evidence_file(path: Path, checkout: Path, context: str) -> Path:
    if not path.is_file():
        raise BuildError(f"Missing license evidence file: {path}")
    if not _is_within(path, checkout):
        raise BuildError(f"{context}: license evidence escapes the pinned checkout: {path}")
    return path


def _assert_matches_revision(path: Path, checkout: Path, revision: str, context: str) -> None:
    """Require bytes to come from a tracked regular file at the pinned commit."""
    try:
        relative = path.relative_to(checkout).as_posix()
    except ValueError as exc:
        raise BuildError(f"{context}: source escapes the pinned checkout: {path}") from exc
    completed = subprocess.run(
        git_command("show", f"{revision}:{relative}"),
        cwd=checkout,
        env=git_environment(checkout),
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise BuildError(f"{context}: source is not tracked at the pinned revision: {relative}")
    if completed.stdout != path.read_bytes():
        raise BuildError(f"{context}: source differs from the pinned revision: {relative}")


def _project_license_file(
    manifest: Manifest, spdx: str, relative: str, expected_sha256: str, context: str
) -> Path:
    path = manifest.project_root / relative
    if path.is_symlink() or not path.is_file() or not _is_within(path, manifest.project_root):
        raise BuildError(f"{context}: invalid supplemental license file: {relative}")
    allowlisted_hash = ALLOWED_SUPPLEMENTAL_LICENSES.get((spdx, relative))
    if allowlisted_hash is None or expected_sha256 != allowlisted_hash:
        raise BuildError(f"{context}: supplemental license asset is not allowlisted")
    if _sha256(path) != expected_sha256:
        raise BuildError(f"{context}: supplemental license asset hash does not match")
    return path


def _expand_inputs(checkout: Path, artifact: Artifact) -> list[Path]:
    found: dict[str, Path] = {}
    for pattern in artifact.inputs:
        matches = sorted(checkout.glob(pattern))
        if not any(char in pattern for char in GLOB_CHARS):
            exact = checkout / pattern
            matches = [exact] if exact.is_file() else []
        matches = [path for path in matches if path.is_file() and _is_within(path, checkout)]
        if not matches:
            raise BuildError(f"{artifact.name}: input pattern matched no files: {pattern}")
        for match in matches:
            relative = match.relative_to(checkout).as_posix()
            found.setdefault(relative, match)
    return list(found.values())


def _matches_policy(relative: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        return relative.startswith(pattern[:-3].rstrip("/") + "/")
    return fnmatch.fnmatchcase(relative, pattern)


def _enforce_source_path_policies(
    manifest: Manifest,
    collection: Collection,
    inputs: list[Path],
    checkout: Path,
) -> list[dict[str, str]]:
    matched: list[dict[str, str]] = []
    for source_path in inputs:
        relative = source_path.relative_to(checkout).as_posix()
        rules = [
            (policy.pattern, policy.required_distribution, policy.reason)
            for policy in manifest.source_path_policies
            if policy.repository == collection.repository
            and _matches_policy(relative, policy.pattern)
        ]
        for pattern, (required_distribution, reason) in MANDATORY_SOURCE_PATH_RULES.items():
            if _matches_policy(relative, pattern) and not any(
                candidate[0] == pattern and candidate[1] == required_distribution
                for candidate in rules
            ):
                # These rules are deliberately repository-independent. Renaming or aliasing a
                # protected source entry must not turn restricted bytes into committed output.
                rules.append((pattern, required_distribution, reason))
        for pattern, required_distribution, reason in rules:
            if required_distribution == "catalog-only":
                raise BuildError(
                    f"{collection.id}: {relative} is catalog-only and cannot be generated"
                )
            if collection.distribution != required_distribution:
                raise BuildError(
                    f"{collection.id}: {relative} requires {required_distribution} output"
                )
            matched.append(
                {
                    "path": relative,
                    "pattern": pattern,
                    "required_distribution": required_distribution,
                    "reason": reason,
                }
            )
    return matched


def _license_notice(license_info: LicenseInfo, checkout: Path) -> str:
    header = [
        f"Source license: {license_info.name} ({license_info.spdx})",
        f"License URL: {license_info.url}",
        f"Attribution: {license_info.attribution}",
        f"License audit date: {license_info.audited}",
    ]
    if license_info.warning:
        header.extend(["", f"WARNING: {license_info.warning}"])
    if license_info.evidence_path:
        evidence = _evidence_file(checkout / license_info.evidence_path, checkout, "license notice")
        header.extend(
            [
                "",
                f"The upstream license text below is copied from {license_info.evidence_path}.",
                "",
                evidence.read_text(encoding="utf-8").rstrip(),
            ]
        )
    else:
        header.extend(
            [
                "",
                "The source files carry the file-level license notice recorded in source.json.",
                "Follow the linked legal terms; this generator does not grant extra rights.",
            ]
        )
    return "\n".join(header).rstrip() + "\n"


def verify_license_evidence(
    manifest: Manifest, collection: Collection, checkout: Path
) -> LicenseInfo:
    """Fail closed if required repository or file-level license evidence disappears."""
    license_info = manifest.license_for(collection)
    if collection.distribution == "committed" and not license_info.allow_committed_output:
        raise BuildError(
            f"{collection.id}: recorded license policy forbids committed generated output"
        )
    revision = manifest.repositories[collection.repository].revision
    if license_info.evidence_path:
        evidence = _evidence_file(
            checkout / license_info.evidence_path,
            checkout,
            collection.id,
        )
        _assert_matches_revision(evidence, checkout, revision, collection.id)
    if license_info.evidence_glob:
        files = sorted(checkout.glob(license_info.evidence_glob))
        if not files:
            raise BuildError(
                f"{collection.id}: license evidence glob matched no files: "
                f"{license_info.evidence_glob}"
            )
        for path in files:
            evidence = _evidence_file(path, checkout, collection.id)
            _assert_matches_revision(evidence, checkout, revision, collection.id)
        if license_info.evidence_contains:
            missing = [
                path.relative_to(checkout).as_posix()
                for path in files
                if license_info.evidence_contains.lower()
                not in path.read_text(encoding="utf-8").lower()
            ]
            if missing:
                preview = ", ".join(missing[:5])
                raise BuildError(
                    f"{collection.id}: {len(missing)} files lost the required license notice: "
                    f"{preview}"
                )
    return license_info


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FULL_REFERENCE_IMAGE_RE = re.compile(r"(?<!\\)!\[([^]\n]*)\]\[([^]\n]*)\]")
SHORT_REFERENCE_IMAGE_RE = re.compile(r"(?<!\\)!\[([^]\n]*)\](?!\s*[\[(])")
FULL_REFERENCE_LINK_RE = re.compile(r"(?<![!\\])\[([^]\n]+)\]\[([^]\n]*)\]")
SHORT_REFERENCE_LINK_RE = re.compile(r"(?<![!\\])\[([^]\n]+)\](?!\s*[\[(])")
REFERENCE_DEFINITION_RE = re.compile(r"(?m)^ {0,3}\[([^]\n]+)\]:[ \t]*(?:<([^>\n]+)>|(\S+))")
ESCAPED_MARKDOWN_RE = re.compile(r"\\!?\[[^]\n]*\](?:\[[^]\n]*\]|\([^\n)]*\))?")
OMITTED_LOCAL_REFERENCE = "\ue002"


def _reference_label(value: str) -> str:
    """Normalize a Markdown reference label for matching."""
    return " ".join(value.split()).casefold()


def _heading_text(value: str) -> str:
    return " ".join(value.split())


def _markdown_blocks(lines: list[str]) -> tuple[str, ...]:
    """Split a Markdown section into stable paragraph, list, table, or code blocks."""
    blocks: list[str] = []
    current: list[str] = []
    fence: tuple[str, int] | None = None

    def finish() -> None:
        text = "\n".join(current).rstrip()
        if text.strip():
            blocks.append(text.lstrip("\n"))
        current.clear()

    for line in lines:
        fence = next_markdown_fence(line, fence)
        if not line.strip() and fence is None:
            finish()
        else:
            current.append(line.rstrip())
    finish()
    return tuple(blocks)


def _section_blocks(markdown: str, heading: str, source: str) -> tuple[str, str, tuple[str, ...]]:
    """Return the document title and direct content blocks under one exact heading."""
    lines = markdown.splitlines()
    headings: list[tuple[int, int, str]] = []
    fence: tuple[str, int] | None = None
    for index, line in enumerate(lines):
        was_fenced = fence is not None
        next_fence = next_markdown_fence(line, fence)
        is_fence_line = next_fence != fence
        fence = next_fence
        if was_fenced or is_fence_line:
            continue
        if fence is None and (match := HEADING_RE.match(line)):
            headings.append((index, len(match.group(1)), _heading_text(match.group(2))))
    if not headings:
        raise BuildError(f"{source}: converted source has no Markdown headings")
    wanted = _heading_text(heading).casefold()
    matches = [item for item in headings if item[2].casefold() == wanted]
    if len(matches) != 1:
        raise BuildError(f"{source}: expected one heading {heading!r}, found {len(matches)}")
    selected_index, selected_level, selected_heading = matches[0]
    start = selected_index + 1
    end = next((index for index, _level, _value in headings if index >= start), len(lines))
    blocks = _markdown_blocks(lines[start:end])
    if not blocks:
        raise BuildError(f"{source}: heading {heading!r} has no direct content blocks")
    display_heading = selected_heading
    if re.match(r"^\d+(?:\.\d+)+\s+Decision$", selected_heading, re.IGNORECASE):
        parent = next(
            (
                value
                for index, level, value in reversed(headings)
                if index < selected_index and level < selected_level
            ),
            None,
        )
        if parent:
            display_heading = parent
    return headings[0][2], display_heading, blocks


def _sanitize_excerpt(
    block: str,
    reference_links: dict[str, str] | None = None,
    context: str = "Selected excerpt",
) -> str:
    """Remove links that would break outside the source site while retaining their text."""
    reference_links = reference_links or {}
    fenced_segments = markdown_fenced_segments(block)
    if len(fenced_segments) == 1 and fenced_segments[0][0]:
        return block.rstrip()

    def sanitize_text(text: str) -> str:
        placeholders: dict[str, str] = {}

        def protect(value: str) -> str:
            token = f"\ue000{len(placeholders)}\ue001"
            placeholders[token] = value
            return token

        text = ESCAPED_MARKDOWN_RE.sub(lambda match: protect(match.group(0)), text)
        protected: list[str] = []
        for is_code, segment in markdown_inline_segments(text):
            if is_code:
                protected.append(protect(segment))
            else:
                protected.append(segment)
        text = "".join(protected)
        text = MARKDOWN_IMAGE_RE.sub(lambda match: match.group(1).strip(), text)
        text = FULL_REFERENCE_IMAGE_RE.sub(lambda match: match.group(1).strip(), text)
        text = SHORT_REFERENCE_IMAGE_RE.sub(lambda match: match.group(1).strip(), text)

        def restore(value: str) -> str:
            for token, code in placeholders.items():
                value = value.replace(token, code)
            return value

        def replace_link(match: re.Match[str]) -> str:
            label, target = match.groups()
            if target.startswith(("https://", "http://", "mailto:")):
                return match.group(0)
            plain_label = restore(label).strip()
            if (
                plain_label == "??"
                or target.casefold().startswith("#example")
                or re.fullmatch(
                    r"(?:Figure|Table|Example)\s+\d+(?:[-.]\d+)?",
                    plain_label,
                    flags=re.IGNORECASE,
                )
            ):
                return OMITTED_LOCAL_REFERENCE
            if plain_label.isdigit():
                return ""
            return label

        cleaned = MARKDOWN_LINK_RE.sub(replace_link, text)
        parenthetical = re.compile(
            rf"\s*\((?:(?:see\s+the\s+example\s+in|see|but\s+see)\s+)?"
            rf"{OMITTED_LOCAL_REFERENCE}(?:\s+and\s+{OMITTED_LOCAL_REFERENCE})*\)"
            rf"(?P<punct>[.,]?)",
            re.IGNORECASE,
        )

        def remove_parenthetical(match: re.Match[str]) -> str:
            punctuation = match.group("punct")
            before = match.string[: match.start()].rstrip()
            if punctuation == "." and before.endswith((".", "!", "?")):
                return ""
            if punctuation == ",":
                return ","
            return punctuation

        cleaned = parenthetical.sub(remove_parenthetical, cleaned)
        cleaned = re.sub(rf",\s+as\s+explained\s+in\s+{OMITTED_LOCAL_REFERENCE}", "", cleaned)
        cleaned = re.sub(
            rf"\s+as\s+defined\s+in\s+{OMITTED_LOCAL_REFERENCE}\.[ \t]*",
            ".\n",
            cleaned,
        )
        cleaned = re.sub(
            rf",\s+as\s+(?:demonstrated|illustrated)\s+in\s+"
            rf"(?:Figure\s+\d+(?:-\d+)?|{OMITTED_LOCAL_REFERENCE})",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"\s*(?:Figure\s+\d+(?:-\d+)?|{OMITTED_LOCAL_REFERENCE})\s+depicts[^.]*\.",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf",\s+such\s+as\s+that\s+shown\s+in\s+{OMITTED_LOCAL_REFERENCE}",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf",\s+such\s+as\s+{OMITTED_LOCAL_REFERENCE}\s+that\s+[^.]*\.",
            ".",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"\s+To\s+illustrate,\s+{OMITTED_LOCAL_REFERENCE}\s+presents[^.]*\.",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"\s+{OMITTED_LOCAL_REFERENCE}\s+(?:illustrates|presents|shows)[^.]*\.",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"\bAs\s+shown\s+in\s+(?:the\s+)?{OMITTED_LOCAL_REFERENCE},\s+the\s+",
            "The ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\s*\(See\s+the\s+example\s+in\s+Section\s+[^)]*\)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"[ \t]*We(?:'|’)ll\s+look\s+at\s+an\s+example[^.]*"
            r"later\s+in\s+this\s+chapter\.",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"[ \t]*\(see\s+(?:Case\s+Study:\s+[^)]+|Style\s+Guides\s+and\s+Rules)\)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r",\s+which\s+we\s+explore\s+further\s+in\s+[^.]+\.",
            ".",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"[ \t]*We(?:'|’)ll\s+cover\s+[^.]+\s+in\s+the\s+next\s+section\.",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"[ \t]*\(we\s+look\s+at\s+[^)]*later\s+in\s+this\s+chapter\)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"[ \t]*See\s+Style\s+Guides\s+and\s+Rules\.",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r";\s+see\s+below\s+for\s+details\.",
            ".",
            cleaned,
            flags=re.IGNORECASE,
        )
        if OMITTED_LOCAL_REFERENCE in cleaned:
            raise BuildError(f"{context} contains an unresolved source cross-reference")

        def render_reference(label: str, reference: str) -> str:
            key = _reference_label(restore(reference or label))
            target = reference_links.get(key, "").strip("<>")
            if target.startswith(("https://", "http://", "mailto:")):
                return f"[{label}]({target})"
            return label

        cleaned = FULL_REFERENCE_LINK_RE.sub(
            lambda match: render_reference(match.group(1), match.group(2)),
            cleaned,
        )

        def replace_short_reference(match: re.Match[str]) -> str:
            label = match.group(1)
            restored = restore(label)
            key = _reference_label(restored)
            return render_reference(label, key) if key in reference_links else match.group(0)

        return restore(SHORT_REFERENCE_LINK_RE.sub(replace_short_reference, cleaned))

    cleaned = (
        "".join(
            segment if is_code else sanitize_text(segment) for is_code, segment in fenced_segments
        )
        .rstrip()
        .lstrip("\n")
    )
    first_line = cleaned.lstrip().splitlines()[0] if cleaned.strip() else ""
    if cleaned[:1].isspace() and not re.match(r"(?:[-*+] |\d+[.)] )", first_line):
        cleaned = textwrap.dedent(cleaned)
    return cleaned


def _reference_links(markdown: str) -> dict[str, str]:
    """Collect reference-link targets outside fenced examples."""
    links: dict[str, str] = {}
    for is_code, segment in markdown_fenced_segments(markdown):
        if is_code:
            continue
        for label, angle_target, bare_target in REFERENCE_DEFINITION_RE.findall(segment):
            links.setdefault(_reference_label(label), angle_target or bare_target)
    return links


def _display_heading(value: str) -> str:
    """Remove source-only anchor syntax from a rendered heading."""
    return re.sub(r"\s+\{#[^{}]+\}$", "", _sanitize_excerpt(value)).replace(r"\_", "_")


def _selected_excerpts(
    artifact: Artifact, inputs: tuple[Path, ...], checkout: Path
) -> tuple[list[_SelectedExcerpt], dict[str, str]]:
    """Convert source files and resolve manifest-declared excerpt selectors."""
    input_paths = {path.relative_to(checkout).as_posix(): path for path in inputs}
    converted: dict[str, str] = {}
    conversions: dict[str, str] = {}
    reference_links: dict[str, dict[str, str]] = {}
    sections: list[_SelectedExcerpt] = []
    for selector in artifact.excerpts:
        source_path = input_paths.get(selector.input)
        if source_path is None:
            raise BuildError(f"{artifact.name}: excerpt input was not expanded: {selector.input}")
        if selector.input not in converted:
            converted[selector.input], conversions[selector.input] = source_to_markdown(source_path)
            reference_links[selector.input] = _reference_links(converted[selector.input])
        source_title, section_heading, available = _section_blocks(
            converted[selector.input], selector.heading, selector.input
        )
        invalid = [index for index in selector.blocks if index >= len(available)]
        if invalid:
            raise BuildError(
                f"{selector.input}: heading {selector.heading!r} has {len(available)} blocks; "
                f"cannot select {invalid}"
            )
        blocks = tuple(
            cleaned
            for index in selector.blocks
            if (
                cleaned := _sanitize_excerpt(
                    available[index],
                    reference_links[selector.input],
                    f"{selector.input}: heading {selector.heading!r} block {index}",
                )
            )
        )
        if not blocks:
            raise BuildError(
                f"{selector.input}: heading {selector.heading!r} selected no usable content"
            )
        sections.append(
            _SelectedExcerpt(
                source_title=_display_heading(source_title),
                heading=_display_heading(section_heading),
                blocks=blocks,
            )
        )
    return sections, conversions


def _render_excerpts(artifact: Artifact, sections: list[_SelectedExcerpt]) -> str:
    """Render selected source blocks as one self-contained skill."""
    lines = [
        _frontmatter(artifact.name, artifact.description).rstrip(),
        "",
        f"# {artifact.title}",
        "",
        "Apply this guidance to the actual project. Repository requirements and newer "
        "authoritative guidance take precedence.",
    ]
    previous_source: str | None = None
    for section in sections:
        show_source = section.source_title.casefold() != artifact.title.casefold()
        if section.source_title != previous_source:
            if show_source:
                lines.extend(["", f"## {section.source_title}", ""])
            previous_source = section.source_title
        if section.heading.casefold() != section.source_title.casefold():
            level = "###" if show_source else "##"
            if lines[-1]:
                lines.append("")
            lines.extend([f"{level} {section.heading}", ""])
        lines.extend([*section.blocks, ""])
    return "\n".join(lines).rstrip() + "\n"


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _replace_generated_directory(staged: Path, target: Path, output_root: Path) -> None:
    if target.parent.resolve() != output_root.resolve():
        raise BuildError(f"Refusing to replace output outside {output_root}: {target}")
    if target.exists():
        markers = (target / "source.json", target / "references" / "source.json")
        if not any(marker.is_file() for marker in markers):
            raise BuildError(
                f"Refusing to replace unrecognized directory without generated source metadata: "
                f"{target}"
            )
        shutil.rmtree(target)
    staged.replace(target)


def _generated_provenance(skill_dir: Path, manifest: Manifest) -> dict[str, object] | None:
    """Read current or legacy provenance only from a physically safe generated directory."""
    for candidate in (skill_dir / "source.json", skill_dir / "references" / "source.json"):
        try:
            marker = require_safe_project_path(
                manifest.project_root,
                candidate,
                context="Generated source metadata",
                error_type=BuildError,
            )
        except BuildError:
            continue
        if marker.is_symlink() or not marker.is_file():
            continue
        try:
            value = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            return value
    return None


def _prune_stale_generated_skills(
    manifest: Manifest,
    collections: list[Collection],
) -> None:
    """Remove obsolete directories that carry this generator's trusted provenance."""
    for collection in collections:
        output_root = _assert_safe_output_root(manifest, collection.distribution)
        if not output_root.is_dir():
            continue
        expected = {artifact.name for artifact in collection.artifacts}
        for skill_dir in sorted(output_root.iterdir()):
            if skill_dir.name in expected or skill_dir.is_symlink() or not skill_dir.is_dir():
                continue
            provenance = _generated_provenance(skill_dir, manifest)
            generated_by = provenance.get("generated_by") if provenance else None
            if (
                provenance is None
                or provenance.get("artifact") != skill_dir.name
                or provenance.get("collection") != collection.id
                or provenance.get("distribution") != collection.distribution
                or not isinstance(generated_by, str)
                or not generated_by.startswith("google-guide-skills/")
            ):
                continue
            shutil.rmtree(skill_dir)


def _verified_checkout(manifest: Manifest, collection: Collection) -> tuple[Repository, Path]:
    repository = manifest.repositories[collection.repository]
    checkout = require_safe_project_path(
        manifest.project_root,
        checkout_path(manifest, repository.id),
        context="Source checkout",
        error_type=BuildError,
    )
    if not git_dir_is_safe(checkout):
        raise BuildError(f"Missing checkout for {repository.id}; run `google-guides sync` first")
    config_problem = repository_config_problem(checkout, repository.url, repository.default_branch)
    if config_problem:
        raise BuildError(f"Checkout {repository.id} has unsafe local Git config: {config_problem}")
    revision = subprocess_revision(checkout)
    if revision != repository.revision:
        raise BuildError(
            f"Checkout {repository.id} is at {revision}, expected pinned {repository.revision}"
        )
    return repository, checkout


def _prepare_sources(
    manifest: Manifest,
    collection: Collection,
    artifact: Artifact,
    running_python: str,
) -> _PreparedSources:
    repository, checkout = _verified_checkout(manifest, collection)
    license_info = verify_license_evidence(manifest, collection, checkout)
    inputs = _expand_inputs(checkout, artifact)
    matched_policies = _enforce_source_path_policies(manifest, collection, inputs, checkout)
    for source_path in inputs:
        _assert_matches_revision(source_path, checkout, repository.revision, artifact.name)
    for supplemental in artifact.supplemental_licenses:
        has_evidence = any(
            supplemental.evidence_contains.lower()
            in source_path.read_text(encoding="utf-8").lower()
            for source_path in inputs
        )
        if not has_evidence:
            raise BuildError(
                f"{artifact.name}: supplemental {supplemental.spdx} evidence disappeared"
            )
    return _PreparedSources(
        running_python=running_python,
        repository=repository,
        checkout=checkout,
        inputs=tuple(inputs),
        license_info=license_info,
        matched_path_policies=tuple(matched_policies),
    )


def _input_provenance(
    inputs: tuple[Path, ...], checkout: Path, conversions: dict[str, str] | None = None
) -> list[dict[str, str]]:
    """Describe pinned source inputs without exposing them as skill references."""
    records: list[dict[str, str]] = []
    for source_path in inputs:
        relative = source_path.relative_to(checkout).as_posix()
        records.append(
            {
                "path": relative,
                "sha256": _sha256(source_path),
                "conversion": (conversions or {}).get(relative, "not-rendered"),
            }
        )
    return records


def _write_licenses(
    manifest: Manifest,
    artifact: Artifact,
    prepared: _PreparedSources,
    output_dir: Path,
) -> None:
    license_notice = _license_notice(prepared.license_info, prepared.checkout)
    if artifact.license_note:
        license_notice = (
            f"{license_notice.rstrip()}\n\n"
            f"Artifact-specific license note: {artifact.license_note}\n"
        )
    (output_dir / "LICENSE.txt").write_text(license_notice, encoding="utf-8")
    shutil.copyfile(
        verified_project_license(manifest.project_root, error_type=BuildError),
        output_dir / WRAPPER_LICENSE_FILENAME,
    )
    for supplemental in artifact.supplemental_licenses:
        source = _project_license_file(
            manifest,
            supplemental.spdx,
            supplemental.license_file,
            supplemental.sha256,
            artifact.name,
        )
        shutil.copyfile(source, output_dir / f"LICENSE-{supplemental.spdx}.txt")


def _source_metadata(
    collection: Collection,
    artifact: Artifact,
    prepared: _PreparedSources,
    provenance_inputs: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "artifact": artifact.name,
        "collection": collection.id,
        "distribution": collection.distribution,
        "generated_by": f"google-guide-skills/{__version__}",
        "generator_runtime": {
            "python": prepared.running_python,
            "beautifulsoup4": importlib.metadata.version("beautifulsoup4"),
            "lxml": importlib.metadata.version("lxml"),
            "markdownify": importlib.metadata.version("markdownify"),
        },
        "inputs": provenance_inputs,
        "excerpts": [excerpt.to_dict() for excerpt in artifact.excerpts],
        "rendering": "source-excerpts",
        "license": prepared.license_info.to_dict(),
        "license_note": artifact.license_note,
        "wrapper_license": wrapper_license_metadata(),
        "supplemental_licenses": [
            supplemental.to_dict() for supplemental in artifact.supplemental_licenses
        ],
        "repository": {
            "id": prepared.repository.id,
            "url": prepared.repository.url,
            "revision": prepared.repository.revision,
        },
        "source_path_policies": list(prepared.matched_path_policies),
    }


def _stage_skill(
    manifest: Manifest,
    collection: Collection,
    artifact: Artifact,
    prepared: _PreparedSources,
    staged: Path,
) -> list[dict[str, str]]:
    staged.mkdir(parents=True)
    sections, conversions = _selected_excerpts(artifact, prepared.inputs, prepared.checkout)
    skill_text = _render_excerpts(artifact, sections)
    provenance_inputs = _input_provenance(prepared.inputs, prepared.checkout, conversions)
    (staged / "SKILL.md").write_text(skill_text, encoding="utf-8")
    _write_licenses(
        manifest,
        artifact,
        prepared,
        staged,
    )
    _write_json(
        staged / "source.json",
        _source_metadata(
            collection,
            artifact,
            prepared,
            provenance_inputs,
        ),
    )
    return provenance_inputs


def build_skill(
    manifest: Manifest,
    collection: Collection,
    artifact: Artifact,
) -> BuiltSkill:
    """Build one artifact into its policy-selected root."""
    running_python = assert_canonical_runtime(manifest)
    prepared = _prepare_sources(manifest, collection, artifact, running_python)
    output_root = _assert_safe_output_root(manifest, collection.distribution)
    output_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f".{artifact.name}-", dir=output_root) as temporary:
        staged = Path(temporary) / artifact.name
        provenance_inputs = _stage_skill(
            manifest,
            collection,
            artifact,
            prepared,
            staged,
        )
        target = output_root / artifact.name
        _replace_generated_directory(staged, target, output_root)

    return BuiltSkill(
        collection=collection.id,
        name=artifact.name,
        distribution=collection.distribution,
        path=target,
        source_files=tuple(item["path"] for item in provenance_inputs),
    )


def subprocess_revision(checkout: Path) -> str:
    """Return the checkout's current commit SHA."""
    completed = subprocess.run(
        git_command("rev-parse", "HEAD"),
        cwd=checkout,
        env=git_environment(checkout),
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def _selected_collections(
    manifest: Manifest, collection_ids: list[str] | None, include_local: bool
) -> list[str]:
    selected = collection_ids or list(manifest.collections)
    unknown = sorted(set(selected) - set(manifest.collections))
    if unknown:
        raise BuildError(f"Unknown collections: {', '.join(unknown)}")
    blocked = sorted(
        collection_id
        for collection_id in selected
        if manifest.collections[collection_id].distribution == "local-only" and not include_local
    )
    if collection_ids and blocked:
        raise BuildError(
            "Explicit local-only collections require --include-swe-book: " + ", ".join(blocked)
        )
    return selected


def _selected_artifacts(manifest: Manifest, artifact_names: list[str] | None) -> set[str]:
    selected = set(artifact_names or [])
    known = {
        artifact.name
        for collection in manifest.collections.values()
        for artifact in collection.artifacts
    }
    unknown = sorted(selected - known)
    if unknown:
        raise BuildError(f"Unknown artifacts: {', '.join(unknown)}")
    return selected


def _build_pairs(
    manifest: Manifest,
    collection_ids: list[str],
    artifact_names: set[str],
    include_local: bool,
) -> list[tuple[Collection, Artifact]]:
    pairs: list[tuple[Collection, Artifact]] = []
    for collection_id in collection_ids:
        collection = manifest.collections[collection_id]
        if collection.distribution == "local-only" and not include_local:
            continue
        pairs.extend(
            (collection, artifact)
            for artifact in collection.artifacts
            if not artifact_names or artifact.name in artifact_names
        )
    omitted = sorted(artifact_names - {artifact.name for _collection, artifact in pairs})
    if omitted:
        raise BuildError(
            "Selected artifacts are outside the selected collections or local-only policy: "
            + ", ".join(omitted)
        )
    return pairs


def build(
    manifest: Manifest,
    collection_ids: list[str] | None = None,
    artifact_names: list[str] | None = None,
    include_local: bool = False,
    sync_first: bool = True,
) -> list[BuiltSkill]:
    """Build selected skills; local-only material remains in its ignored root."""
    assert_canonical_runtime(manifest)
    selected_collections = _selected_collections(manifest, collection_ids, include_local)
    selected_artifacts = _selected_artifacts(manifest, artifact_names)
    build_pairs = _build_pairs(manifest, selected_collections, selected_artifacts, include_local)
    if sync_first:
        repository_ids = list(dict.fromkeys(pair[0].repository for pair in build_pairs))
        sync(manifest, repository_ids)

    results = [build_skill(manifest, collection, artifact) for collection, artifact in build_pairs]
    if not artifact_names:
        built_collections = list(dict.fromkeys(collection for collection, _artifact in build_pairs))
        _prune_stale_generated_skills(manifest, built_collections)
    return results
