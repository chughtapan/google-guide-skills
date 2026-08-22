# Google Guide Skills

Turn Google's public engineering guides into installable, discoverable
[Agent Skills](https://agentskills.io/) for Codex and Claude.
The generator preserves Markdown source text and mechanically converts HTML/XML to Markdown. It
adds only skill metadata, navigation, provenance, and license files around that source material.
Version 0.1 is a deliberately text-only baseline: it does not bundle upstream images or rewrite
source-relative links, so some diagrams and cross-document links require opening the pinned
upstream repository recorded in `source.json`.

This repository has a hard distribution boundary:

- `skills/` contains generated material whose source license permits redistribution.
- `.generated/skills/` contains optional local-only output and is ignored by git.
- `corpus.yaml` records every source, revision, license, file pattern, output policy, and skill
  description.

The boundary matters for [`abseil/abseil.github.io`](https://github.com/abseil/abseil.github.io):
most repository documentation is Apache-2.0, but `resources/swe-book/html/` carries file-level
CC BY-NC-ND 4.0 notices. The pipeline can generate those chapters locally, but it refuses to put
them in the committed skill tree.

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

Generate the restricted SWE-book skills for private local evaluation:

```bash
uv run google-guides all --include-local
```

The resulting `.generated/` files retain their upstream license restrictions. Generate and use
the adapted material only for noncommercial purposes, and do not commit, share, or redistribute
it merely because the conversion happened locally. Review the full recorded license before use.

## Commands

```text
google-guides sync                         clone and checkout pinned repositories
google-guides build [--collection ID]     build selected redistributable skills
google-guides build --include-local        also build local-only collections
google-guides catalog                      regenerate catalog and index
google-guides metrics [--include-local]    count every generated text file with o200k_base
google-guides validate [--include-local]   check skill, reference, and license boundaries
google-guides install --agent codex        install through the open `skills` CLI
google-guides eval triggers                plan fresh-agent discoverability cases
google-guides eval quality                 plan no-skill versus skill answer A/Bs
google-guides all                           run the deterministic end-to-end pipeline
```

Install the generated skills into a project for Codex and Claude Code:

```bash
uv run google-guides install \
  --project /path/to/project \
  --agent codex \
  --agent claude-code \
  --copy
```

The wrapper delegates to pinned [`npx skills@1.5.23`](https://github.com/vercel-labs/skills), so the same skill
folders remain usable across supported agents. Use `--dry-run` to inspect commands first.
The public installer enumerates only manifest-declared redistributable skills; it cannot export
local-only output.

The 24-skill pack uses 7,780 of Codex's 8,000 fallback startup-metadata characters at the recorded
reference path. That leaves 220 characters and supports an install-root path of at most 54
characters before truncation; deeper projects or unrelated host skills can exceed the budget.
Prefer targeted installs for normal projects and reserve the full pack for discovery tests. Live
evaluations are Linux-only in v0.1 and require Bubblewrap, explicit model IDs, dedicated disposable
provider keys, `--live --accept-cost`, and `--accept-credential-risk`; they never run in CI. See
[`docs/evaluation.md`](docs/evaluation.md) for profiles, evidence limitations, and gates.

## Outputs

- [`catalog/catalog.md`](catalog/catalog.md): human-readable source and skill index.
- [`catalog/catalog.json`](catalog/catalog.json): machine-readable discovery index.
- [`catalog/tokens.json`](catalog/tokens.json): per-file and per-skill token totals.
- `skills/*/references/source.json`: exact source URL, commit, input hashes, converter mode, and
  license evidence.
- [`reports/generator-comparison.md`](reports/generator-comparison.md): generator and plugin
  comparison behind the architecture choice.
- [`evals/cases.yaml`](evals/cases.yaml): staged cross-agent trigger and quality corpus.

Large inline skills are intentional in the unedited baseline. Validation reports their context
cost as a warning rather than rewriting them. Later iterations can compare inline files with
progressive-disclosure reference layouts using the committed token and trigger results.

The four catalog-only entries (R style, Developer Documentation Style, Technical Writing, and a
Google Cloud product-management article) are inventory leads, not generated skills. Their
snapshot or composite-license work is intentionally deferred rather than guessed.

## Licensing and attribution

The generator code and the thin skill wrapper it authors are Apache-2.0. Generated source material
stays under the upstream license recorded in each skill's `references/LICENSE.txt` and
`references/source.json`; the wrapper license does not replace those terms. See
[`docs/licensing.md`](docs/licensing.md) for the full policy.

Google, Abseil, and related marks belong to their owners. This independent project is not
affiliated with or endorsed by Google.

## Development

```bash
uv run ruff check .
uv run pytest --cov=google_guide_skills --cov-report=term-missing
uv run google-guides all
git diff --exit-code -- skills catalog
```

Maintainers run `uv run google-guides all --include-local` as an explicit local release check.
Hosted CI uses synthetic restricted-source fixtures and never materializes the real SWE-book
derivatives.

Contributions should update `corpus.yaml`, tests, generated outputs, and license evidence in one
change. Never add a source whose distribution rights are unclear.

The supported distribution is this source checkout. The Python build metadata exists for local
tooling and CI smoke tests; the project is marked `Private :: Do Not Upload`, and wheels exclude
generated guide trees and do not provide a standalone initialized corpus.
