# Project instructions

## Communication

Read this section before routing or acting. It applies to every task.

- Lead with the answer, decision, or result.
- Say what you mean simply and directly. Prefer concrete terms, and define terms that could be
  read more than one way.
- Separate facts, inferences, decisions, and remaining work. Do not turn a bounded result into a
  broad claim.
- Keep updates short. Cut filler, hype, unnecessary adjectives, and process narration.
- Be cooperative. Discuss the work, not the person; listen, admit uncertainty, and make criticism
  specific and actionable.

Use `$google-documentation-guide` for substantial technical writing. Use
`$google-swe-teamwork-and-leadership` for collaboration, feedback, or knowledge sharing.

## Routing

This file is the source of truth for skill routing. Use only the skills that match the task. Do
not add another lifecycle document or a wrapper around `$ship`.

| Work | Skills |
| --- | --- |
| Product, requirements, architecture, or project plan | `$plan-eng-review` |
| Python or shell | The matching Google language skill |
| Code structure and readability | `$google-code-review-reviewer` and the matching language skill |
| Tests | `$google-swe-testing` |
| Documentation | `$google-documentation-guide` |
| Organization-wide standards or static analysis | `$google-swe-engineering-standards` |
| Developer-productivity measurement or code search | `$google-swe-developer-productivity` |
| Infrastructure or compute platforms | `$google-swe-compute-platforms` |
| Builds, dependencies, version control, or CI | `$google-swe-builds-dependencies-and-ci` |
| Deprecation, migration, rollout, or release | `$google-swe-change-management` |
| Ownership or team practice | `$google-swe-teamwork-and-leadership` |
| Code-review policy or tooling | `$google-swe-code-review-systems` |
| Review preparation | `$google-code-review-author` |
| Code review | `$google-code-review-reviewer`, testing, and any diff-specific guide |
| Ship, push, or pull request | Complete the review above, then use `$ship` |

Do not use the safer skills unless the user asks.

## Project rules

- Keep behavior changes, tests, and affected documentation in the same change.
- Follow `pyproject.toml` for Python formatting and test commands. Its settings override general
  style defaults.
- Fix every `Required:` review finding before shipping. Nits do not block shipping.
- If a local SWE-book skill is unavailable, say so instead of claiming that its review ran.
- Change the generator or `corpus.yaml`, then regenerate; do not hand-edit converted upstream
  prose.
- Keep SWE-book output under ignored `.generated/skills/`. Never commit or redistribute it.
