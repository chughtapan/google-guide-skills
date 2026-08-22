# Skill generator comparison

Status: initial capability comparison. On 2026-08-22, `npx skills init` 1.5.23 was run against an
ignored fixture: it produced a valid minimal `SKILL.md`, but no corpus manifest, provenance,
license evidence, distribution policy, catalog, or metrics. The Codex initializer created the
authored index skill, which passed its bundled `quick_validate.py` check. Deterministic fixture
coverage lives in the test suite and should be refreshed when creator tools change.

| Approach | Strength | Gap for this corpus | Role here |
| --- | --- | --- | --- |
| Codex `$skill-creator` | Strong interactive scoping, frontmatter, resources, validation, and forward testing | One skill at a time; output depends on the agent conversation; no corpus/license manifest | Used to initialize and validate the authored index skill |
| Agent Skills `skill-creator` workflow | Description optimization with positive/negative trigger queries and repeated runs | Optimizes a skill after it exists; does not pin or license a source corpus | Evaluation methodology |
| `npx skills init` | Fast ecosystem-neutral `SKILL.md` scaffold | Scaffold only; no source conversion, attribution, or reproducibility | Compatibility fixture and installer ecosystem |
| Codex Record & Replay | Drafts a skill from a demonstrated workflow | Suited to interactive procedures, not a content corpus; demonstration can hide source/license state | Not used for first-cut conversion |
| OpenAI plugin packaging | Installs multiple skills and optional connectors as one reusable package | OpenAI-specific distribution layer; does not solve cross-agent generation or source licensing | Candidate wrapper after host-neutral evals stabilize |
| This manifest pipeline | Exact commits, deterministic conversion, path-level licenses, local-only boundary, catalog, metrics, and eval matrix | Intentionally does not rewrite or optimize upstream prose in v0.1 | Selected production generator |

## Decision

Keep the first release boring and inspectable: a Python pipeline whose output is a pure Agent
Skills tree. Use existing creators as format/evaluation or packaging tools, not as the source of
truth for a large licensed corpus.

The main reason is not conversion quality. It is policy reproducibility. Given the same
`corpus.yaml`, an auditor must be able to answer which bytes came from which commit, which
license evidence permitted each committed output, and why the SWE-book bytes could only land in
an ignored directory. A conversational generator cannot provide that invariant by itself.

## Comparison fixtures

Repository tests exercise the manifest generator on:

- valid Agent Skills frontmatter;
- deterministic repeat output;
- provenance and input hashes;
- license evidence;
- committed versus local-only output enforcement;
- token/report integration.

Trigger quality is evaluated separately because scaffold validity is not discoverability.
The Codex and `npx skills init` observations above are recorded capability probes, not committed
initializer-output fixtures.
