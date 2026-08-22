"""Project-specific exceptions with user-facing messages."""


class GoogleGuideSkillsError(Exception):
    """Base class for expected command failures."""


class ManifestError(GoogleGuideSkillsError):
    """Raised when corpus.yaml is missing, unsafe, or internally inconsistent."""


class SourceError(GoogleGuideSkillsError):
    """Raised when an upstream checkout cannot be synchronized safely."""


class BuildError(GoogleGuideSkillsError):
    """Raised when source material cannot be converted into a skill."""


class ValidationError(GoogleGuideSkillsError):
    """Raised when generated artifacts violate a required invariant."""


class EvaluationError(GoogleGuideSkillsError):
    """Raised when an evaluation corpus or fresh-agent run is invalid."""
