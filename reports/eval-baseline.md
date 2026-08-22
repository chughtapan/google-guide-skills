# Cross-agent evaluation baseline

Status: exploratory evidence, not a passed release gate.

Runs were attempted on 2026-08-22 with Codex CLI 0.147.0, Claude Code 2.1.233, and
`skills` CLI 1.5.23. They predated the final OS-level workspace isolation, strict terminal-status
handling, explicit model requirement, paired index profile, and exact-routing metric. Raw traces
remain ignored under `evals/results/`; this report contains only normalized, redistributable
findings.

## Executed controls

| Test | Profile | Codex | Claude Code | Result |
| --- | --- | --- | --- | --- |
| Implicit C# discovery | all 24 committed skills | Loaded `google-csharp-style` by `SKILL.md` path | 24/24 project skills visible; authoritative `Skill` event for `google-csharp-style` | 2/2 correct; index did not steal the direct prompt |
| Abseil Python reference navigation | single skill | Loaded skill and four focused references | Authoritative `Skill` event and the same four focused references | 2/2 correct; installed copies matched source hashes |
| C# answer quality A/B | none versus single | Both answers covered 2/3 deterministic wording checks | Both answers covered 3/3 deterministic wording checks | All four processes completed; no keyword-score lift |

All eight small-probe processes exited successfully. No Codex metadata-shortening warning appeared.
Claude calls cost $0.438242 in total; Codex reported tokens rather than a dollar cost. The runs did
not record requested model IDs, so they are useful adapter and rubric probes but are not a
reproducible model benchmark.

The post-tuning pack has 5,142 description characters (975 `o200k_base` tokens). Its
path-independent rendered-list cost is 6,700 characters; at the recorded reference path it uses
7,780 of Codex's 8,000 fallback characters, leaving 220. The maximum full install-root length is
54 characters, so targeted installs remain safer in deep projects or hosts with other skills.

## Quality finding

Keyword coverage alone hid the useful difference. Claude's no-skill C# answer invented three
claims contradicted by the installed guide: that ordinary fields must be private, that public
fields are allowed only in narrow special cases, and that private static fields require an `s_`
prefix. The skill-backed answer correctly stated that the guide permits public fields and that
modifiers do not alter its `_camelCase` rule for non-public fields.

Those claims are now explicit forbidden-pattern checks in the evaluation corpus. On that corrected
fidelity score, Claude improved by 3 points with the skill; Codex made none of the forbidden claims
in either condition and was unchanged on this easy case. Because this run predates final profile
isolation, it is a harness-development finding, not evidence of broad quality improvement.

## Exploratory full-smoke attempt

A later Claude full-pack attempt covered all 24 implicit smoke prompts and cost $5.245474. Only 17
processes exited successfully; seven ended in `error_max_budget_usd`. Among the clean runs,
JavaScript, Python, and index discovery missed. Eight unrelated direct prompts loaded all three
Abseil guide/design/tips skills in addition to their intended guide, revealing a specificity
problem that the old expected-subset score did not penalize. The trace reported a Claude Opus 5
family model, but no requested model ID was pinned.

The sibling Codex attempt exited nonzero for all 24 cases under an obsolete command adapter and is
not interpretable. The old harness also counted some budget-terminal failures as completed and
placed workspaces beneath the source repository. Therefore no headline recall, specificity, or
index-lift rate from these attempts is publishable. The findings motivated the current external
temporary workspaces, Bubblewrap allowlist, failed-status exclusion, explicit model provenance,
and exact unexpected-skill accounting.

## Scope and next run

The committed corpus contains 24 installed skills (23 generated guides plus the authored index).
[`evals/cases.yaml`](../evals/cases.yaml) defines 24 explicit controls, 24 implicit all-skill smoke
cases, 80 repeated representative positive/near-miss cases, 6 paired broad index cases, and 8
local-only planning cases. No full run has yet passed the documented gates under the hardened
harness, and no valid broad index-versus-no-index experiment has run. The index and descriptions
therefore remain candidates for tuning rather than validated routing decisions.

On Linux with Bubblewrap installed, set both dedicated disposable key variables, replace the model
placeholders, and run the gates in order:

```bash
uv run google-guides eval triggers \
  --stage controls --profile all --agent codex --agent claude-code \
  --codex-model CODEX_MODEL_ID --claude-model CLAUDE_MODEL_ID \
  --max-budget-usd CLAUDE_BUDGET_USD \
  --live --accept-cost --accept-credential-risk
uv run google-guides eval triggers \
  --stage smoke --profile all --agent codex --agent claude-code \
  --codex-model CODEX_MODEL_ID --claude-model CLAUDE_MODEL_ID \
  --max-budget-usd CLAUDE_BUDGET_USD \
  --live --accept-cost --accept-credential-risk
uv run google-guides eval triggers \
  --stage index-experiment --profile index-ab --agent codex --agent claude-code \
  --codex-model CODEX_MODEL_ID --claude-model CLAUDE_MODEL_ID \
  --max-budget-usd CLAUDE_BUDGET_USD \
  --live --accept-cost --accept-credential-risk
```

Repeated description tuning should use three runs against `train`, freeze descriptions, and only
then evaluate `validation`. Do not claim a release-gate pass until both agents meet the explicit,
recall, specificity, exact-routing, index, and quality criteria in
[`docs/evaluation.md`](../docs/evaluation.md).
