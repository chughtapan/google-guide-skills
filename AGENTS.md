# Project instructions

This file is the source of truth for skill routing. Use only the skills that match the task. Do
not add another lifecycle document or a wrapper around `$ship`.

## Routing

| Work | Skills |
| --- | --- |
| Product, requirements, architecture, or project plan | `$plan-eng-review` |
| Python, shell, JSON, or documentation | The matching Google language or format skill |
| Code structure and readability | `$google-swe-style-and-readability` |
| Tests | `$google-swe-testing` |
| Documentation | `$google-documentation-guide` and `$google-swe-documentation` |
| Infrastructure | `$google-swe-infrastructure` |
| Builds, dependencies, CI, installation, or release | `$google-swe-maintenance-and-delivery` |
| Ownership or team practice | `$google-swe-culture-and-leadership` |
| Review preparation | `$google-code-review-author` |
| Code review | `$google-code-review-reviewer`, `$google-swe-code-review`, readability, testing, and any diff-specific guide |
| Ship, push, or pull request | Complete the review above, then use `$ship` |

Use `$google-swe-book-front-matter` only for the book's scope, authorship, navigation, or
attribution. Do not use the safer skills unless the user asks.

## Project rules

- Keep behavior changes, tests, and affected documentation in the same change.
- Follow `pyproject.toml` for Python formatting and test commands. Its settings override general
  style defaults.
- Fix every `Required:` review finding before shipping. Nits do not block shipping.
- If a local SWE-book skill is unavailable, say so instead of claiming that its review ran.
- Change the generator or `corpus.yaml`, then regenerate; do not hand-edit converted upstream
  prose.
- Keep SWE-book output under ignored `.generated/skills/`. Never commit or redistribute it.
