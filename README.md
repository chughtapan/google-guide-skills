# Google Guide Skills

Convert Google's public engineering guides into [Agent Skills](https://agentskills.io/), install
them, and test whether agents select them. Project installation supports Codex and Claude Code.
Evaluation supports Codex, Claude Code, OpenCode, OpenClaw, and Hermes.
The generator copies Markdown and converts HTML/XML to Markdown. It adds skill metadata,
navigation, source records, and license files. Version 0.1 does not bundle images or rewrite
relative links. Open the source repository named in `source.json` to view missing diagrams or
follow those links.

Generated files go to one of two places:

- `skills/` contains material that can be redistributed and committed.
- `.generated/skills/` contains SWE-book output for local use and is ignored by git.

`corpus.yaml` records every source, revision, license, file pattern, output policy, and skill
description.

This split is required for
[`abseil/abseil.github.io`](https://github.com/abseil/abseil.github.io). Most files used here are
Apache-2.0, but `resources/swe-book/html/` has CC BY-NC-ND 4.0 notices. The generator writes those
chapters only to `.generated/skills/`.

## Quick start

Requirements: Git, [uv](https://docs.astral.sh/uv/), and Node.js/npm for cross-agent
installation. The package and unit tests support Python 3.11+, while byte-for-byte generation is
pinned to Python 3.13.7 in `.python-version` and `corpus.yaml`; `uv` provisions that interpreter.

```bash
uv sync --all-groups
uv run google-guides all
```

That command checks out the exact revisions in `corpus.yaml`, builds redistributable skills,
regenerates the catalog and `o200k_base` token report, and validates the result.

Generate the SWE-book skills on your machine:

```bash
uv run google-guides all --include-swe-book
```

The files in `.generated/` remain subject to CC BY-NC-ND 4.0. Use them only for noncommercial
purposes. Do not commit, share, or redistribute them. Read the recorded license before use.

## Commands

```text
google-guides sync                         clone and checkout pinned repositories
google-guides build [--collection ID]     build selected redistributable skills
google-guides build --include-swe-book     also build the SWE-book skills locally
google-guides catalog                      regenerate catalog files
google-guides metrics [--include-swe-book] count every generated text file with o200k_base
google-guides validate [--include-swe-book] check skill, reference, and license boundaries
google-guides install --agent codex        install for the current user
google-guides install --include-swe-book   also generate and link the SWE-book skills
google-guides eval triggers                plan skill-selection tests
google-guides eval quality                 plan answers with and without skills
google-guides all                           sync, build, catalog, measure, and validate
```

Install the generated skills into a project for Codex and Claude Code:

```bash
uv run google-guides install \
  --project /path/to/project \
  --agent codex \
  --agent claude-code \
  --copy
```

The command uses pinned [`npx skills@1.5.23`](https://github.com/vercel-labs/skills). The same
folders work with Codex and Claude Code. Use `--dry-run` to inspect commands first. Without
`--project`, the command installs for the current user. For repository setup, follow the
[new-repository onboarding guide](docs/onboarding.md) or the
[existing-repository migration guide](docs/migration.md). To include the SWE-book skills for both
supported agents, run:

```bash
uv run google-guides install \
  --agent codex \
  --agent claude-code \
  --include-swe-book
```

The flag generates all eight book skills and links them from `.generated/skills/`; it does not copy
or publish them. A byte-identical skill copy is replaced with a link so later source updates flow
through it; a destination with different content stops the install. `--project` installs include
only the 23 redistributable skills.

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

The catalog lists four sources that the generator does not build: R style, Developer
Documentation Style, Technical Writing, and a Google Cloud product-management article. Their
snapshot or license work is unfinished.

## Licensing and attribution

The generator code, skill metadata, and navigation it adds are Apache-2.0. Source material stays
under the license recorded in each skill's `references/LICENSE.txt` and
`references/source.json`; the project license does not replace those terms. See
[`docs/licensing.md`](docs/licensing.md) for the policy.

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
