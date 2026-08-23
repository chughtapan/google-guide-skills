# Project instructions

Read [`docs/sdlc.md`](docs/sdlc.md) before planning or shipping a nontrivial change. Match the
process to the change risk. Do not invoke every skill for every task.

## Planning and design

- Use `$office-hours` when the problem or user is unclear.
- Use `$plan-ceo-review` for product value, priorities, scope, and non-goals.
- Use `$design-consultation` for a new design system and `$plan-design-review` for UI or
  interaction changes.
- Use `$plan-eng-review` to harden requirements and review architecture, data flow, failure
  modes, tests, performance, distribution, and work breakdown. Do not substitute the safer
  requirements or architecture skills unless the user asks.
- Add `$google-swe-infrastructure` when the change affects compute, deployment, services, or
  infrastructure boundaries.
- Add `$google-swe-maintenance-and-delivery` when the change affects dependencies, builds,
  static analysis, CI, releases, or distribution.
- Add `$google-swe-culture-and-leadership` when the task concerns ownership, team practices,
  knowledge sharing, or project health.

## Implementation

- Select the narrow language or format skill that matches the changed files. This repository
  normally uses `$google-python-style`, `$google-shell-style`, `$google-json-style`, and
  `$google-documentation-guide`.
- Use `$google-swe-style-and-readability` for code structure and readability.
- Keep behavior changes, tests, and affected documentation in the same change. Separate a
  preparatory refactor when it can stand alone.
- Optimize for the reader. Keep functions focused, use direct control flow, and name values by
  purpose. Comments should explain a constraint or decision, not restate the code.

### Python changes

- Use `$google-python-style` before changing Python code.
- Follow `pyproject.toml`; its 100-character line length overrides the guide's default.
- Run the formatter, linter, and relevant tests after each refactor.

### Documentation changes

- Use both `$google-documentation-guide` and `$google-swe-documentation` when the local
  SWE-book skill is installed.
- Give each document one job and a named audience. Keep stable documentation in the repository
  and update it with the code it describes.
- Keep the README as the landing page. Put detailed design, evaluation, licensing, and process
  material in `docs/` and link to it.

## Testing

- Use `$google-swe-testing` when planning, writing, or reviewing tests.
- Test observable behavior through public interfaces. Prefer the smallest deterministic test
  with the fidelity the risk requires.
- Add a regression test for every bug fix. Cover error paths and boundary cases introduced by
  the change.
- Prefer real implementations or fakes when interaction-heavy mocks would make tests brittle.
  Use larger tests for integration risks that small tests cannot represent.

## Reviews

- Use `$google-code-review-author` before requesting review.
- For code reviews, use `$google-code-review-reviewer`, `$google-swe-code-review`,
  `$google-swe-style-and-readability`, and `$google-swe-testing`. Add the applicable language,
  documentation, infrastructure, or maintenance skill.
- Review the design first, then every changed human-authored line. Check behavior, security and
  license boundaries, complexity, tests, names, comments, and documentation.
- Mark blocking findings as `Required:`. Mark non-blocking polish as `Nit:` or `Optional:`.
- Let automated formatting and lint checks handle mechanical style.
- Prefer changes that improve the codebase, even when surrounding code predates these rules.

## Shipping

- On a request to ship, push, create a pull request, or deploy, review the current diff with the
  applicable Google skills above before invoking `$ship`.
- Fix all `Required:` findings and rerun affected tests. Nits do not block shipping.
- Use `$google-swe-maintenance-and-delivery` for the release and distribution pass when it is
  installed, then run `$ship`. Do not add a repository wrapper around `$ship`.
- If a local SWE-book skill is unavailable, say which review could not run and use its committed
  counterpart when one exists. Do not silently claim that the review ran.

## Local SWE-book skills

The following skills are local-only: `$google-swe-code-review`, `$google-swe-testing`,
`$google-swe-style-and-readability`, `$google-swe-documentation`,
`$google-swe-maintenance-and-delivery`, `$google-swe-infrastructure`,
`$google-swe-culture-and-leadership`, and `$google-swe-book-front-matter`.

Use `$google-swe-book-front-matter` only for the book's scope, authorship, navigation, or
attribution. Install the local collection using the commands in the README. Never commit or
redistribute its generated files.

## Generated sources

- Do not rewrite converted upstream prose in `skills/*/SKILL.md` or `skills/*/references/` for
  local style. Change the generator or manifest and regenerate it.
- Keep SWE-book output under the ignored `.generated/` root. Do not commit or redistribute it.
