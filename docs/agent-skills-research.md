# Agent Skills and distribution research

Research checked on 2026-08-22 against first-party documentation.

## Format and context

The [Agent Skills specification](https://agentskills.io/specification) requires a skill directory
with `SKILL.md`, a 1-64 character lowercase/hyphen `name`, and a non-empty `description` of at
most 1024 characters. It recommends progressive disclosure: metadata at startup, a main skill
under roughly 5,000 tokens/500 lines, and focused resources loaded only when needed.

Version 0.1 leaves many single guides inline even when they exceed these limits. The Go guide and
larger collections use one-level `references/`. The validator warns about oversized main files,
and the token report records every generated text file.

The specification's [description optimization guide](https://agentskills.io/skill-creation/optimizing-descriptions)
recommends positive and near-miss queries, about 20 cases per skill, three runs per query, and a
60/40 train/validation split. The evaluation follows that shape and adds an all-skill smoke stage
before repeated runs.

## Codex behavior

The official [Codex skill documentation](https://developers.openai.com/codex/skills) says Codex:

- loads names and descriptions first, then reads a selected `SKILL.md`;
- budgets at most 2% of context, or 8,000 characters when context size is unknown, for the
  initial skill list and may shorten or omit descriptions in very large collections;
- discovers repository skills under `.agents/skills` from the working directory to repository
  root, plus user, admin, and system locations;
- follows symlinked skill directories;
- supports explicit `$skill-name` and implicit description-based invocation.

A catalog alone cannot show whether agents select the skills. The evaluations test whether skill
descriptions fit the metadata budget and trigger in a new process.

The v0.1 committed pack contains 23 skills and 4,830 description characters (915 `o200k_base`
tokens). Its path-independent rendered-list cost is 6,326 characters. At the recorded 45-character
reference install root, the full list is 7,361 characters, or 92.01% of the 8,000-character
fallback, leaving 639 characters. The descriptions fit only while the full skill install
root is at most 72 characters; a deep monorepo path or unrelated host skills can force round-robin
shortening. Install only the skills a project needs. Use the full pack for discovery tests.

The same documentation identifies three creation paths:

- built-in `$skill-creator` for described workflows;
- Record & Replay for generating a draft from a demonstrated workflow;
- manual `SKILL.md` authoring.

It recommends plugins for distributing multiple skills. Standalone skill folders work across
hosts, and this project already installs them through a source-checkout command, so a plugin is
not part of version 0.1.

## Cross-agent installer

[`vercel-labs/skills`](https://github.com/vercel-labs/skills) provides the open `npx skills` CLI.
It accepts local paths, supports Codex and Claude Code among many agents, lists source skills,
installs selected skills, and can symlink or copy them. `google-guides install` calls that CLI;
the generated folders do not depend on it.

SWE-book output cannot be published through an npm or GitHub source. The source-checkout CLI
supports `google-guides install --include-swe-book`, which generates the book skills and links the
current user's Codex or Claude skill directory to the ignored output root. It does not copy the
files into a project or package.

## Generator decision

Skill creators handle one workflow at a time. This corpus needs bulk conversion from pinned
commits, hashes for every input, per-path license rules, a catalog, and token counts. The generator
provides those features and uses Agent Skills validators for compatibility. See
[`reports/generator-comparison.md`](../reports/generator-comparison.md).
