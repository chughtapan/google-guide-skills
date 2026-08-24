# Google Guide Skills

Convert Google's engineering guides into [Agent Skills](https://agentskills.io/), install them for
a user or repository, and test whether agents select them. Installation supports Codex and Claude
Code. Evaluation supports Codex, Claude Code, OpenCode, OpenClaw, and Hermes.

The generator pins each source revision, copies Markdown, converts HTML/XML to Markdown, and writes
skill metadata, provenance, license files, a catalog, and token counts. `corpus.yaml` defines the
corpus and output rules.

## Quick start

Requirements: Git and [uv](https://docs.astral.sh/uv/). Project installation of public skills also
requires Node.js/npm. The package and unit tests support Python 3.11+, while byte-for-byte
generation is pinned to Python 3.13.7 in `.python-version` and `corpus.yaml`; `uv` provisions that
interpreter.

```bash
uv sync --all-groups
uv run google-guides all
```

That command checks out the revisions in `corpus.yaml`, builds the public skill set, regenerates
the catalog and `o200k_base` token report, and validates the result.

## Commands

```text
google-guides sync                         clone and checkout pinned repositories
google-guides build [--collection ID]     build selected redistributable skills
google-guides build --include-swe-book     also build the SWE-book skills locally
google-guides catalog                      regenerate catalog files
google-guides metrics [--include-swe-book] count every generated text file with o200k_base
google-guides validate [--include-swe-book] check skill, reference, and license boundaries
google-guides install --agent codex        install for the current user (recommended)
google-guides install --project PATH       install into a repository
google-guides install --include-swe-book   add the SWE-book skills after license acceptance
google-guides eval triggers                plan skill-selection tests
google-guides eval quality                 plan answers with and without skills
google-guides all                           sync, build, catalog, measure, and validate
```

## Installation

Per-user installation is recommended because one setup works across repositories:

```bash
uv run google-guides install \
  --agent codex \
  --agent claude-code
```

Add the eight Software Engineering at Google skills with `--include-swe-book`. The installer shows
the CC BY-NC-ND 4.0 terms and asks for acceptance before it generates or links them:

```bash
uv run google-guides install \
  --agent codex \
  --agent claude-code \
  --include-swe-book
```

For a noninteractive run, review the license first and pass `--accept-swe-book-license`.

To install into a repository instead, add `--project`. Public skills can be copied; SWE-book
skills are linked back to this checkout:

```bash
uv run google-guides install \
  --project /path/to/project \
  --agent codex \
  --agent claude-code \
  --copy \
  --include-swe-book
```

Keep project SWE-book links out of version control. Use `--dry-run` to inspect an install. Project
installation of public skills uses pinned
[`npx skills@1.5.23`](https://github.com/vercel-labs/skills). For repository setup, follow the
[new-repository onboarding guide](docs/onboarding.md) or the
[existing-repository migration guide](docs/migration.md).

## Evaluation

The full pack uses most of Codex's fallback startup-metadata budget; the generated token report
records the current total and supported path length. Deeper projects or unrelated host skills can
exceed the budget.
Install only the skills a project needs. Use the full pack for discovery tests. Live evaluations
are Linux-only in v0.1 and require Bubblewrap plus logged-in client CLIs. OpenCode, OpenClaw, and
Hermes reuse the Codex ChatGPT login; Claude Code uses its own login. Use `--model AGENT=MODEL`
only when a run needs an override. In a one-pass full-pack smoke run, all 115 client/case pairs
reported the expected skill; 69 routes were trace-proven and exact, while 46 used verified
self-report proxies. Repeated near-miss and broader quality cases remain. Live evaluations do not
run in CI. See [`docs/evaluation.md`](docs/evaluation.md) for profiles, evidence, and gates.

## Outputs

- [`docs/onboarding.md`](docs/onboarding.md) and [`docs/migration.md`](docs/migration.md): add
  selected skills to new or existing repositories.
- [`catalog/catalog.md`](catalog/catalog.md): source and skill catalog in Markdown.
- [`catalog/catalog.json`](catalog/catalog.json): source and skill catalog in JSON.
- [`catalog/tokens.json`](catalog/tokens.json): per-file and per-skill token totals.
- `skills/*/references/source.json`: source URL, commit, input hashes, converter mode, and
  license evidence.
- [`reports/generator-comparison.md`](reports/generator-comparison.md): generator and plugin
  comparison used to choose the pipeline.
- [`reports/v0.1-plan-review.md`](reports/v0.1-plan-review.md): original goals, current status,
  deletions, and follow-up work.
- [`evals/cases.yaml`](evals/cases.yaml): prompts and scoring rules for client evaluations.
- [`docs/architecture.md`](docs/architecture.md): generation flow and output boundaries.
- [`docs/agent-skills-research.md`](docs/agent-skills-research.md): format, installer, and creator
  findings.

Version 0.1 leaves most source prose inline. The Go guide and multi-file collections keep source
text in `references/`. Validation warns when a main skill file exceeds the context recommendations.
Use routing and quality results before moving another guide.

Version 0.1 does not bundle upstream images or rewrite relative links. Use the repository and
revision in each `source.json` to view missing diagrams or follow those links.

The catalog lists four sources that the generator does not build: R style, Developer
Documentation Style, Technical Writing, and a Google Cloud product-management article. Their
snapshot or license work is unfinished.

## Licensing and attribution

The generator code, skill metadata, and navigation it adds are Apache-2.0. Source material stays
under the license recorded in each skill's `references/LICENSE.txt` and
`references/source.json`; the project license does not replace those terms. See
[`docs/licensing.md`](docs/licensing.md) for the policy.

Public generated skills are written to `skills/`. SWE-book skills are written to the ignored
`.generated/skills/` tree because the selected book chapters carry CC BY-NC-ND 4.0 notices. Their
installer requires license acceptance and uses links rather than publishing those generated
files. Do not commit or redistribute them.

Google, Abseil, and related marks belong to their owners. This independent project is not
affiliated with or endorsed by Google.

## Development

[`AGENTS.md`](AGENTS.md) is the source of truth for skill routing and review.

```bash
uv run ruff format --check src tests
uv run ruff check .
uv run pytest --cov=google_guide_skills --cov-report=term-missing
uv run google-guides all
git diff --exit-code -- skills catalog
```

Maintainers run `uv run google-guides all --include-swe-book` as a local release check.
Hosted CI uses synthetic restricted-source fixtures and never materializes the real SWE-book
derivatives.

Contributions should update `corpus.yaml`, tests, generated outputs, and license evidence in one
change. Never add a source whose distribution rights are unclear.

Run the project from a source checkout. Python build metadata supports local tools and CI smoke
tests. The project is marked `Private :: Do Not Upload`; wheels exclude generated guide trees and
do not contain an initialized corpus.
