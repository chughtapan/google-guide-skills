# Project instructions

## Python changes

- Use `$google-python-style` before changing Python code.
- Follow `pyproject.toml`; its 100-character line length overrides the guide's default.
- Optimize for the reader. Keep functions focused, use direct control flow, and name values by
  purpose.
- Comments should explain a constraint or decision, not restate the code.
- Run the formatter, linter, and relevant tests after each refactor.

## Reviews

- Use both `$google-code-review-reviewer` and `$google-swe-style-and-readability` for code reviews.
- Review every changed human-authored line. Check behavior, security and license boundaries,
  complexity, tests, names, comments, and documentation.
- Mark blocking findings as `Required:`. Mark non-blocking polish as `Nit:` or `Optional:`.
- Let automated formatting and lint checks handle mechanical style.
- Prefer changes that improve the codebase, even when the surrounding code predates these rules.

## Generated sources

- Do not rewrite converted upstream prose in `skills/*/SKILL.md` or `skills/*/references/` for
  local style. Change the generator or manifest and regenerate it.
- Keep SWE-book output under the ignored `.generated/` root. Do not commit or redistribute it.
