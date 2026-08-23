# Discoverability and quality evaluation

For each case, the harness creates a Git repository in an OS temporary directory, installs the
selected profile with pinned `skills@1.5.23` in copy mode, and starts an agent without a saved
session. On Linux, Bubblewrap exposes only the system runtime and the run directory. It does not
mount the source checkout, case labels, saved results, previous answers, user homes, or other
skills. The harness deletes the workspace after recording the result. `--keep-raw` copies the
trace into ignored results after the agent exits.

Every run mounts its workspace at the same short agent-visible path, `/w`. Codex therefore sees
installed skills under `/w/.agents/skills`, regardless of the host temporary-directory name or
profile. Before model invocation, the harness recomputes the rendered metadata list at that exact
path and rejects an over-budget install. This prevents profile-dependent paths or truncation from
confounding the `all-no-index` versus `all` comparison.

Live evaluation is Linux-only in v0.1 and requires `bwrap`. The harness creates agent homes, drops
ambient environment variables, does not copy session files, and limits the environment passed to
the npm installer. Set one-use keys in `GOOGLE_GUIDES_EVAL_OPENAI_API_KEY` and
`GOOGLE_GUIDES_EVAL_ANTHROPIC_API_KEY`; cap and revoke them after the run.

Evaluation is plan-only by default. Live model calls require model IDs and both risk
acknowledgements:

```bash
uv run google-guides eval triggers --stage smoke --profile all
uv run google-guides eval triggers --stage controls --profile all
uv run google-guides eval triggers --stage index-experiment --profile index-ab
uv run google-guides eval triggers --stage smoke --profile all --limit 2 \
  --agent codex --codex-model MODEL_ID \
  --live --accept-cost --accept-credential-risk
uv run google-guides eval quality --profile single \
  --agent claude-code --claude-model MODEL_ID \
  --max-budget-usd BUDGET_USD \
  --live --accept-cost --accept-credential-risk
```

Replace `MODEL_ID` and `BUDGET_USD`. Every live Claude run requires a per-case spending cap. Test
the cap on one case before launching a matrix. A `$0.25` full-smoke run exhausted its cap on 7/24
calls. Raw traces are discarded unless `--keep-raw` is passed. Reports and kept traces live under
mode-0700 `evals/results/`, which Git ignores. They can contain answers based on complete skill
text; never commit them. The cap is soft: Claude may report an overrun after producing an answer.
The report records process status and model evidence separately, and failed runs do not count
toward accuracy.

Codex runs with `shell_environment_policy.inherit=none`; both adapters receive a reduced process
environment, and reports redact exact key values. Redaction may miss transformed keys, so use
capped, one-use keys and pass `--accept-credential-risk`. The harness does not send SWE-book
output to hosted agents; `local-smoke` supports planning and offline tests only.

## Test cases

[`evals/cases.yaml`](../evals/cases.yaml) contains:

- 24 explicit invocation controls, rendered as `$skill-name` for Codex and `/skill-name` for
  Claude Code;
- 24 implicit smoke prompts, one for every committed guide plus the index;
- 8 local-only smoke plans, one for every restricted SWE-book recipe;
- 80 representative cases across Python style, reviewer workflow, documentation, and the
  Abseil C++ tips reference collection;
- 6 broad-routing cases for a paired index/no-index experiment;
- for each representative skill, 10 positives and 10 near-miss negatives with a fixed 60/40
  train/validation split;
- concept-check rubrics for a quality A/B subset.

Use `--repeat 3` only after the one-pass smoke stage passes. Tune descriptions against
`--split train`, then evaluate once against the frozen `--split validation`. Paid live evals never
run in CI.

## Installation profiles

| Profile | Purpose |
| --- | --- |
| `single` | Isolate the expected or forbidden skill and validate its metadata. |
| `all-no-index` | Measure direct-skill discovery without router competition. |
| `all` | Measure the normal full pack, including the index and metadata-budget pressure. |
| `index` | Test broad routing when sibling skills are absent. |
| `index-ab` | Run each broad case with `all-no-index` and then `all`, producing a paired index comparison. |

Quality mode runs each rubric case twice: with no skills and with the selected profile. It reports
the change in rubric score. Keyword checks do not fully judge answer quality.

## How skill loads are counted

Claude Code emits a `Skill` tool-use event and a skill inventory; the harness records both. Codex
0.147 does not expose a skill-selection event in JSONL. A `SKILL.md` read proves that Codex loaded
the skill. Without one, the report uses a terminal self-report proxy and checks the answer against
the rubric in quality mode. These evidence types are not equivalent.

Infrastructure failures, nonzero terminal status, installed-file hash verification, visible
inventory, loaded skills, self-reported skills, expected-skill recall, forbidden-skill avoidance,
unexpected loaded skills, exact trigger correctness, duration, and rubric score are separate
report fields. In the full-pack smoke stage, a direct prompt passes exact routing only when it
loads the intended skill and no other installed skill. This exposes over-broad descriptions even
when the desired guide was also loaded. Reports also record the manifest, selected-case, installed
skill-tree and pack digests, generator version, repository commit/dirty state, requested/resolved
models, and bounded redacted diagnostics for failed processes.

## Release gates

- Static generation, validation, installation, and installed-file hash checks: 100%.
- Explicit controls: 100% before interpreting implicit cases.
- Positive recall: at least 80%; repeated cases should pass at least two of three runs.
- Near-miss specificity: at least 90%.
- Direct full-pack routing: at least 90% exact matches, with unexpected loads reported separately.
- Index experiment: at least 5/6 broad prompts load the index, positive paired lift over
  `all-no-index`, and a 0% index steal rate on direct smoke prompts.
- Quality A/B: no correctness regression and a positive aggregate rubric delta.

Three repetitions provide little statistical evidence. Reports keep the denominators; larger
runs should add Wilson intervals before making claims about model behavior.

Version 0.1 ships the harness and cases, but the live-model gates have not passed. Runs from older
versions of the harness are not release evidence. The current status and next work are recorded in
the [version 0.1 plan review](../reports/v0.1-plan-review.md).
