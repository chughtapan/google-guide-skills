# Skill generator comparison

Status: capability comparison. On 2026-08-22, `npx skills init` 1.5.23 was run against an ignored
fixture. It produced a `SKILL.md`, but no corpus manifest, source record,
license evidence, distribution policy, catalog, or metrics. The Codex initializer created the
index skill, which passed its bundled `quick_validate.py` check. Tests cover the manifest
generator and should be updated when creator tools change.

| Approach | What it provides | Gap for this corpus | Role here |
| --- | --- | --- | --- |
| Codex `$skill-creator` | Prompts for scope, frontmatter, resources, validation, and tests | One skill at a time; output depends on the agent conversation; no corpus/license manifest | Used to initialize and validate the index skill |
| Agent Skills `skill-creator` workflow | Description optimization with positive/negative trigger queries and repeated runs | Optimizes a skill after it exists; does not pin or license a source corpus | Evaluation methodology |
| `npx skills init` | Creates a `SKILL.md` scaffold for several agents | Scaffold only; no source conversion, attribution, or reproducibility | Compatibility fixture and installer ecosystem |
| Codex Record & Replay | Drafts a skill from a demonstrated workflow | Suited to interactive procedures, not a content corpus; demonstration can hide source/license state | Not used for first-cut conversion |
| OpenAI plugin packaging | Installs multiple skills and connectors as one package | OpenAI-specific distribution layer; does not solve cross-agent generation or source licensing | Possible wrapper after cross-agent tests pass |
| This manifest pipeline | Pinned commits, repeatable conversion, path-level licenses, output rules, catalog, metrics, and evaluations | Does not rewrite or optimize upstream prose in v0.1 | Used here |

## Decision

Use a Python pipeline that writes an Agent Skills tree. Use existing creators for format checks,
evaluation methods, or packaging, not for source and license tracking across the corpus.

The choice is driven by source and license tracking, not conversion quality. Given the same
`corpus.yaml`, a reviewer must be able to identify the commit for every input, the license evidence
for every committed output, and the rule that keeps SWE-book files in an ignored directory. A
conversational generator does not record all of this by itself.

## Tests

Repository tests exercise the manifest generator on:

- Agent Skills frontmatter;
- identical output from repeated builds;
- source records and input hashes;
- license checks;
- committed and local-only output rules;
- token reports.

A valid scaffold does not show whether an agent will select the skill, so evaluations test that
separately. The Codex and `npx skills init` observations above are capability probes, not committed
initializer fixtures.
