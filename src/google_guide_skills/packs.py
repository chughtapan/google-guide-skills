"""Resolve explicit installation packs and the corpus's default selection."""

from __future__ import annotations

from .errors import GoogleGuideSkillsError
from .models import Manifest


def select_skills(
    manifest: Manifest, skills: list[str] | None = None, packs: list[str] | None = None
) -> list[str]:
    """Return the explicit union, or the declared default when no selection was supplied."""
    known = {artifact.name for _, artifact in manifest.artifacts(include_local=True)}
    requested = set(skills or [])
    for name in packs or []:
        if name not in manifest.packs:
            raise GoogleGuideSkillsError(f"Unknown pack: {name}")
        requested.update(manifest.packs[name])
    if skills is None and not packs:
        requested.update(manifest.packs.get("default", manifest.packs.get("legacy", known)))
    unknown = requested - known
    if unknown:
        raise GoogleGuideSkillsError(f"Unknown skills: {', '.join(sorted(unknown))}")
    return sorted(requested)
