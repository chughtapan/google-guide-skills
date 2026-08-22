# Discoverability and quality evaluation

The evaluation harness starts every case in a fresh Git repository under an OS temporary
directory, installs an allowlisted profile with pinned `skills@1.5.23` in copy mode, and launches a
new non-persistent agent process. On Linux, Bubblewrap presents a temporary root containing only
the system runtime and that one run directory. The source checkout, case labels, persistent
results, previous answers, user homes, and unrelated skills are not mounted. Each workspace is
destroyed after its record is normalized; `--keep-raw` copies only the completed run's trace into
ignored results after the agent exits.

Every run mounts its workspace at the same short agent-visible path, `/w`. Codex therefore sees
installed skills under `/w/.agents/skills`, regardless of the host temporary-directory name or
profile. Before model invocation, the harness recomputes the rendered metadata list at that exact
path and rejects an over-budget install. This prevents profile-dependent paths or truncation from
confounding the `all-no-index` versus `all` comparison.

Live evaluation is Linux-only in v0.1 and requires a working `bwrap` executable. Agent homes and
ambient environment variables are isolated, reusable session files are never copied, and the
pinned npm installer receives a minimal environment. Live runs require dedicated disposable keys
in `GOOGLE_GUIDES_EVAL_OPENAI_API_KEY` and `GOOGLE_GUIDES_EVAL_ANTHROPIC_API_KEY`; cap and revoke
them after the run.

Evaluation is plan-only by default. Live model calls require explicit models and both risk
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

Replace `MODEL_ID` and `BUDGET_USD` with explicit values. A Claude soft cap is required for every
live Claude run; calibrate it on one case before launching a matrix. The exploratory `$0.25`
full-smoke run exhausted its cap on 7/24 calls, so it is not a known-good full-corpus default. Raw
traces are discarded after normalization unless `--keep-raw` is passed. Normalized reports and any kept traces live under ignored,
mode-0700 `evals/results/`; they can contain answers derived from complete skill text and must
never be committed. Claude's per-case dollar cap is a soft safety bound: a terminal event can
report an overrun after producing an answer, so process status and model evidence are recorded
separately and failed terminal states never count toward accuracy.

Codex is launched with a strict `shell_environment_policy.inherit=none`; both adapters use a
minimal process environment, and exact key values are redacted from normalized output. This is
best-effort defense, not a secret broker: transformed leaks remain possible, so use capped,
disposable keys and explicitly accept the residual credential risk. Local-only derived book
material is never sent to hosted agents; `local-smoke` supports planning and offline boundary
tests only.

## Corpus and stages

[`evals/cases.yaml`](../evals/cases.yaml) contains:

- 24 explicit invocation controls, rendered as `$skill-name` for Codex and `/skill-name` for
  Claude Code;
- 24 implicit smoke prompts, one for every committed guide plus the index;
- 8 local-only smoke plans, one for every restricted SWE-book recipe;
- 80 representative cases across Python style, reviewer workflow, documentation, and the large
  Abseil C++ tips reference collection;
- 6 broad-routing cases for a paired index/no-index experiment;
- for each representative skill, 10 positives and 10 near-miss negatives with a fixed 60/40
  train/validation split;
- deterministic concept rubrics for a small quality A/B subset.

Use `--repeat 3` only after the one-pass smoke stage is healthy. Tune descriptions against
`--split train`, then evaluate once against the frozen `--split validation`. Paid live evals never
run in CI.

## Installation profiles

| Profile | Purpose |
| --- | --- |
| `single` | Isolate the expected or forbidden skill and validate its metadata. |
| `all-no-index` | Measure direct-skill discovery without router competition. |
| `all` | Measure the normal full pack, including the index and metadata-budget pressure. |
| `index` | Test broad routing and graceful behavior when sibling skills are absent. |
| `index-ab` | Run each broad case with `all-no-index` and then `all`, producing a paired index comparison. |

Quality mode runs each selected rubric case twice: with no installed skills and with the selected
profile. It reports the deterministic rubric delta without pretending that keyword checks are a
complete judge of answer quality.

## Evidence semantics

Claude Code emits an authoritative `Skill` tool-use event and a model-visible skill inventory;
the harness records both. Codex 0.147 does not expose a stable skill-selection event in JSONL. A
`SKILL.md` read is authoritative when present; otherwise Codex results use a clearly labeled
terminal self-report proxy, cross-checked by answer rubrics in quality mode. Never compare these
two evidence types as if they were identical.

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

Three repetitions produce weak statistical evidence. Reports keep raw denominators; larger runs
should add Wilson intervals before claiming stable model-level behavior.

The v0.1 release ships the hardened harness and corpus, but it does not claim these live-model
gates have passed. Earlier exploratory runs predated final isolation and status handling; see the
[baseline report](../reports/eval-baseline.md) for the evidence and its limitations.
