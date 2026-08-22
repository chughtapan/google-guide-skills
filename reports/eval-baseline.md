# Cross-agent evaluation baseline

Status: release gates not passed.

Runs were attempted on 2026-08-22 with Codex CLI 0.147.0, Claude Code 2.1.233, and
`skills` CLI 1.5.23. They used the old workspace isolation and status handling and did not require
model IDs or measure paired index routing or exact routing. Raw traces remain ignored under
`evals/results/`; this report contains only the results that can be redistributed.

## Executed controls

| Test | Profile | Codex | Claude Code | Result |
| --- | --- | --- | --- | --- |
| Implicit C# discovery | all 24 committed skills | Loaded `google-csharp-style` by `SKILL.md` path | 24/24 project skills visible; `Skill` event for `google-csharp-style` | 2/2 correct; index did not steal the direct prompt |
| Abseil Python reference navigation | single skill | Loaded skill and four references | `Skill` event and the same four references | 2/2 correct; installed copies matched source hashes |
| C# answer quality A/B | none versus single | Both answers covered 2/3 wording checks | Both answers covered 3/3 wording checks | All four processes completed; no keyword-score lift |

All eight processes exited successfully. No Codex metadata-shortening warning appeared.
Claude calls cost $0.438242 in total; Codex reported tokens rather than a dollar cost. The runs did
not record requested model IDs. They test the adapters and rubrics but do not form a reproducible
model benchmark.

The post-tuning pack has 5,142 description characters (975 `o200k_base` tokens). Its
path-independent rendered-list cost is 6,700 characters; at the recorded reference path it uses
7,780 of Codex's 8,000 fallback characters, leaving 220. The maximum full install-root length is
54 characters. In deeper projects or hosts with other skills, install only the needed skills.

## Quality finding

The keyword score did not capture a factual difference. Claude's no-skill C# answer invented three
claims contradicted by the installed guide: that ordinary fields must be private, that public
fields are allowed only in narrow special cases, and that private static fields require an `s_`
prefix. The skill-backed answer correctly stated that the guide permits public fields and that
modifiers do not alter its `_camelCase` rule for non-public fields.

The evaluation corpus now checks those claims as forbidden patterns. Claude's score improved by 3
points with the skill. Codex made none of the forbidden claims in either condition, so its score
did not change. Because this run used the old profile isolation, it tests the harness rather than
showing a general quality improvement.

## Full-smoke attempt

A later Claude full-pack attempt covered all 24 implicit smoke prompts and cost $5.245474. Only 17
processes exited successfully; seven ended in `error_max_budget_usd`. Among the 17 exit-zero runs,
JavaScript, Python, and index discovery missed. Eight unrelated direct prompts loaded all three
Abseil guide/design/tips skills in addition to their intended guide, revealing a specificity
problem that the old expected-subset score did not penalize. The trace reported a Claude Opus 5
family model, but no requested model ID was pinned.

The Codex attempt exited nonzero for all 24 cases under an old command adapter and cannot be
interpreted. The old harness also counted some budget failures as completed and placed workspaces
beneath the source repository. Do not use these attempts to report recall, specificity, or index
lift. The harness now uses OS temporary workspaces, a Bubblewrap allowlist, failed-status
exclusion, model records, and unexpected-skill counts.

## Scope and next run

The committed corpus contains 24 installed skills (23 generated guides plus the authored index).
[`evals/cases.yaml`](../evals/cases.yaml) defines 24 explicit controls, 24 implicit all-skill smoke
cases, 80 repeated representative positive/near-miss cases, 6 paired broad index cases, and 8
local-only planning cases. No full run has passed the documented gates with the current harness,
and no valid index-versus-no-index experiment has run. The index and descriptions have not been
validated.

On Linux with Bubblewrap installed, set both one-use key variables, replace the model
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

Run each training case three times when tuning descriptions. Then stop changing descriptions and
run `validation`. Do not claim a release-gate pass until both agents meet the invocation, recall,
specificity, exact-routing, index, and quality criteria in
[`docs/evaluation.md`](../docs/evaluation.md).
