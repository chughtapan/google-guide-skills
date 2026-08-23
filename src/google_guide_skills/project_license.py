"""Project-authored wrapper license metadata and verified license asset access."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TypeVar

from .errors import GoogleGuideSkillsError

PROJECT_LICENSE_SHA256 = "c45f612629a31a2141d071c37b981c6c45b193eb4d857fe072ec78bff8a97f8f"
WRAPPER_LICENSE_FILENAME = "LICENSE-Generator-Apache-2.0.txt"

ErrorType = TypeVar("ErrorType", bound=Exception)


def wrapper_license_metadata(
    path: str = f"references/{WRAPPER_LICENSE_FILENAME}",
) -> dict[str, str]:
    """Return the license metadata embedded in generated wrappers."""
    return {
        "spdx": "Apache-2.0",
        "name": "Apache License 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0",
        "attribution": "Google Guide Skills contributors",
        "scope": "Generator-authored skill wrapper, metadata, navigation, and index content.",
        "path": path,
        "sha256": PROJECT_LICENSE_SHA256,
    }


def verified_project_license(
    project_root: Path,
    *,
    error_type: type[ErrorType] = GoogleGuideSkillsError,
) -> Path:
    """Return the allowlisted project license or raise the requested error type."""
    path = project_root / "LICENSE"
    if (
        path.is_symlink()
        or not path.is_file()
        or not path.resolve().is_relative_to(project_root.resolve())
    ):
        raise error_type("Project Apache license asset is missing or unsafe")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != PROJECT_LICENSE_SHA256:
        raise error_type("Project Apache license asset hash does not match the allowlist")
    return path
