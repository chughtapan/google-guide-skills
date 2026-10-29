# Agent Skills and distribution research

This note records why the project uses standard skill folders, inline guides, a
source-checkout installer, and a manifest-driven generator. Research was checked on 2026-08-22
against first-party documentation.

## Format and context

The [Agent Skills specification](https://agentskills.io/specification) requires a directory with
`SKILL.md`, a 1–64 character lowercase-hyphen name, and a non-empty description of at most 1,024
characters. It recommends keeping the main file under roughly 5,000 tokens and 500 lines, then
using focused resources when a task genuinely needs more material.

The first generated pack treated large guides as navigation files over chapter references. In
practice, a generic instruction to read “the relevant sections” did not tell agents which file to
open, and selective reading skipped important rules. The current pack instead prunes obsolete,
historical, and navigational material, groups guidance by task, and keeps each usable guide in one
`SKILL.md`. At the initial audit, the original 16 public main files were 1,635–4,984 tokens and
the 8 local SWE-book files were 4,160–4,893 tokens. The October 2026 expansion adds 25 public skills
under the same per-file limits and shortens all descriptions for the combined default. See the
generated [metrics](../catalog/tokens.json) for current measurements.

The specification's
[description optimization guide](https://agentskills.io/skill-creation/optimizing-descriptions)
recommends positive and near-miss queries, repeated runs, and a held-out validation split. The
evaluation follows that shape and adds one direct-routing smoke case per skill.

## Codex behavior

The official [Codex skill documentation](https://developers.openai.com/codex/skills) says Codex
loads skill names and descriptions first, follows repository and user skill directories, supports
symlinks, and accepts explicit `$skill-name` or implicit selection. It budgets at most 2% of the
context, or 8,000 characters when the context size is unknown, for the initial skill list.

The default now includes all 49 skills, with compact descriptions that fit the fallback budget
at the recorded `/workspace/google-guide-skills/.agents/skills` root. Full guidance remains in
each skill body. Named packs provide smaller installation scopes, and `legacy` retains the
original membership. Validation measures every declared pack; installation checks the resulting
directory at its actual path before changing files. Deep paths or unrelated installed skills can
still exceed the budget. That check does not include other skill roots the client may also load.

## Creation and distribution choices

First-party and ecosystem tools cover parts of the workflow:

- `$skill-creator` helps design and forward-test one skill;
- Record & Replay can draft a workflow from a demonstration;
- `npx skills` discovers and installs skill folders across clients;
- plugins can package several OpenAI-specific capabilities.

This corpus additionally needs pinned commits, input hashes, per-path license rules, local-only
output, a catalog, and token counts. The manifest pipeline supplies those controls, while the
project's installer uses standard skill folders so the output is not tied to one client.

SWE-book output cannot be published through npm or GitHub. `google-guides install` generates it in
the ignored tree after license acceptance and links it into Codex or Claude Code. See the
[generator comparison](../reports/generator-comparison.md) for the narrower tool comparison.
