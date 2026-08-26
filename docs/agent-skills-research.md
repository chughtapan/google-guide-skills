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
`SKILL.md`. The 16 public main files are 1,635–4,984 tokens; the 8 local SWE-book files are
4,160–4,893 tokens.

The specification's
[description optimization guide](https://agentskills.io/skill-creation/optimizing-descriptions)
recommends positive and near-miss queries, repeated runs, and a held-out validation split. The
evaluation follows that shape and adds one direct-routing smoke case per skill.

## Codex behavior

The official [Codex skill documentation](https://developers.openai.com/codex/skills) says Codex
loads skill names and descriptions first, follows repository and user skill directories, supports
symlinks, and accepts explicit `$skill-name` or implicit selection. It budgets at most 2% of the
context, or 8,000 characters when the context size is unknown, for the initial skill list.

For the 16 public skills, the rendered list costs 5,140 characters at the recorded
`/workspace/google-guide-skills/.agents/skills` root. The complete 24-skill pack costs 7,664
characters there, leaving 336 characters. It fits the fallback only while the visible install root
is at most 59 characters, so a deep repository or many unrelated host skills can trigger metadata
shortening. Per-user installation uses a shorter path. Project installs should select only the
skills that repository uses.

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
