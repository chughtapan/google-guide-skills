# Skill generator comparison

Use the manifest pipeline for corpus generation. It records pinned source files, per-path license
rules, output boundaries, a catalog, metrics, and evaluation inputs. Existing skill creators still
serve as format, authoring, and packaging references, but they do not replace that corpus record.

The choice is driven by corpus-wide source and license tracking. Given the same `corpus.yaml`, a
reviewer must be able to identify the commit for every input, the license evidence for every
output, the reviewed recipe or exact excerpt selectors used, and the rule that keeps SWE-book
files in an ignored directory. A conversational generator does not record all of this by itself.

Status: capability comparison. On 2026-08-22, `npx skills init` 1.5.23 was run against an ignored
fixture. It produced a `SKILL.md`, but no corpus manifest, source record,
license evidence, distribution policy, catalog, or metrics. The Codex creator documentation was
reviewed for format, resource, validation, and evaluation guidance. Tests cover the manifest
generator and should be updated when creator tools change.

| Approach | What it provides | Gap for this corpus | Role here |
| --- | --- | --- | --- |
| Codex `$skill-creator` | Prompts for scope, frontmatter, resources, validation, and tests | One skill at a time; output depends on the agent conversation; no corpus/license manifest | Format and authoring reference |
| Agent Skills `skill-creator` workflow | Description optimization with positive/negative trigger queries and repeated runs | Optimizes a skill after it exists; does not pin or license a source corpus | Evaluation methodology |
| `npx skills init` | Creates a `SKILL.md` scaffold for several agents | Scaffold only; no source conversion, attribution, or reproducibility | Compatibility fixture and installer ecosystem |
| Codex Record & Replay | Drafts a skill from a demonstrated workflow | Suited to interactive procedures, not a content corpus; demonstration can hide source/license state | Not used for first-cut conversion |
| OpenAI plugin packaging | Installs multiple skills and connectors as one package | OpenAI-specific distribution layer; does not solve cross-agent generation or source licensing | Not needed for the source-checkout installer |
| This manifest pipeline | Pinned commits, reviewed recipes or exact excerpt selectors, path-level licenses, output rules, catalog, metrics, and evaluations | Requires human review of what each skill should retain | Used here |

## Tests

Repository tests exercise the manifest generator on:

- Agent Skills frontmatter;
- identical output from repeated builds;
- source records and input hashes;
- recipe hashes and exact source-excerpt selectors;
- license checks;
- committed and local-only output rules;
- token reports.

A valid scaffold does not show whether an agent will select the skill, so evaluations test that
separately. The Codex and `npx skills init` observations above are capability probes, not committed
initializer fixtures.
