# Agent Skills and distribution research

Research checked on 2026-08-22 against first-party documentation.

## Format and context

The [Agent Skills specification](https://agentskills.io/specification) requires a skill directory
with `SKILL.md`, a 1-64 character lowercase/hyphen `name`, and a non-empty `description` of at
most 1024 characters. It recommends progressive disclosure: metadata at startup, a main skill
under roughly 5,000 tokens/500 lines, and focused resources loaded only when needed.

This project deliberately retains oversized inline baselines for single guides. The validator
warns on those thresholds and the token report makes the cost explicit. Large collections use
one-level `references/` from the start.

The specification's [description optimization guide](https://agentskills.io/skill-creation/optimizing-descriptions)
recommends realistic positive and near-miss negative queries, about 20 cases per skill, three
runs per query, and a fixed 60/40 train/validation split. The evaluation design follows that
shape and adds a cheaper all-skill smoke stage before repeated runs.

## Codex behavior

The official [Codex skill documentation](https://developers.openai.com/codex/skills) says Codex:

- loads names and descriptions first, then reads a selected `SKILL.md`;
- budgets at most 2% of context, or 8,000 characters when context size is unknown, for the
  initial skill list and may shorten or omit descriptions in very large collections;
- discovers repository skills under `.agents/skills` from the working directory to repository
  root, plus user, admin, and system locations;
- follows symlinked skill directories;
- supports explicit `$skill-name` and implicit description-based invocation.

These constraints make catalog-only discovery insufficient by itself: the staged evals must test
whether a broad index plus many narrow descriptions still fit and trigger in a fresh process.

The v0.1 committed pack contains 24 skills and 5,142 description characters (975 `o200k_base`
tokens). Its path-independent rendered-list cost is 6,700 characters. At the recorded 45-character
reference install root, the full list is 7,780 characters, or 97.25% of the 8,000-character
fallback, leaving 220 characters. The current descriptions fit only while the full skill install
root is at most 54 characters; a deep monorepo path or unrelated host skills can force round-robin
shortening. Targeted installs are therefore the recommended distribution mode, while the full
pack is an explicit discovery stress test.

The same documentation identifies three creation paths:

- built-in `$skill-creator` for described workflows;
- Record & Replay for generating a draft from a demonstrated workflow;
- manual `SKILL.md` authoring.

It recommends plugins for reusable distribution of multiple skills, while standalone skill
folders remain the portable authoring format. This project keeps the v0.1 core host-neutral and
records an optional Codex plugin wrapper as a later packaging layer after cross-agent trigger
behavior is stable.

## Cross-agent installer

[`vercel-labs/skills`](https://github.com/vercel-labs/skills) provides the open `npx skills` CLI.
It accepts local paths, supports Codex and Claude Code among many agents, lists source skills,
installs selected skills, and can symlink or copy them. `google-guides install` is a thin,
inspectable wrapper around that CLI; the generated folders do not depend on it.

## Generator decision

Generic creators are useful for one handcrafted workflow. This corpus needs deterministic bulk
conversion, full input hashes, repository pinning, per-path license policy, stable indexes, and
repeatable metrics. The custom generator owns those functions while still using the official
skill initializer and validators as compatibility checks. See
[`reports/generator-comparison.md`](../reports/generator-comparison.md).
