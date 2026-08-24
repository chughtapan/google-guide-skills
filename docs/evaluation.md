# Discoverability and quality evaluation

For each case, the harness creates a Git repository in an OS temporary directory, copies the
selected skills into it, and starts a client without a saved session. Bubblewrap exposes the
system runtime and that run directory, but not the source checkout, case labels, earlier answers,
user homes, or other skills. The harness deletes the workspace after recording the result.
`--keep-raw` preserves the trace under the ignored results directory.

Every run mounts its workspace at the same short agent-visible path, `/w`. Codex therefore sees
installed skills under `/w/.agents/skills`, regardless of the host temporary-directory name or
profile. Before model invocation, the harness recomputes the rendered metadata list at that exact
path and rejects an over-budget install. This prevents host paths or truncation from confounding
the result.

Live evaluation is Linux-only in v0.1 and requires `bwrap` plus the selected client binaries. It
uses existing OAuth logins, copied into temporary client homes for each run:

| Client | Login used |
| --- | --- |
| Codex | Codex ChatGPT login |
| Claude Code | Claude Code login |
| OpenCode | Codex ChatGPT login, translated to OpenCode's local format |
| OpenClaw | Codex ChatGPT login through OpenClaw's Codex provider |
| Hermes | Codex ChatGPT login, translated to Hermes's local format |

OpenClaw needs the official `@openclaw/codex` package. The harness registers it once under
`~/.cache/google-guide-skills/` and reuses that provider while keeping run state separate.

Evaluation is plan-only by default. Add `--live` to run the selected clients:

```bash
uv run google-guides eval triggers --stage smoke --profile all
uv run google-guides eval triggers --stage controls --profile all
uv run google-guides eval triggers --stage smoke --profile all --limit 2 \
  --agent codex --live
uv run google-guides eval quality --profile single \
  --agent claude-code --model claude-code=haiku --live
```

Without `--agent`, the plan and live run target all five clients. Missing binaries matter only for
selected live clients. `--model AGENT=MODEL` is optional and repeatable. Use `--limit` before a
large matrix. Raw traces are discarded unless `--keep-raw` is passed. Reports and kept traces live
under mode-0700 `evals/results/`, which Git ignores. Failed runs do not count toward accuracy.

Each client receives a reduced process environment. Codex shell commands inherit none of it. Live
client runs exclude SWE-book output; `local-smoke` supports planning and offline tests only.

## Test cases

[`evals/cases.yaml`](../evals/cases.yaml) contains:

- 23 explicit invocation controls, rendered for each client adapter;
- 23 implicit smoke prompts, one for every committed guide;
- 8 local-only smoke plans, one for every restricted SWE-book recipe;
- 80 representative cases across Python style, reviewer workflow, documentation, and the
  Abseil C++ tips reference collection;
- for each representative skill, 10 positives and 10 near-miss negatives with a fixed 60/40
  train/validation split;
- concept-check rubrics for a quality A/B subset.

Smoke prompts must be answerable in the empty evaluation repository. Include the relevant code or
ask a guidance question; do not ask a client to inspect files that are not present.

Use `--repeat 3` after the one-pass smoke stage passes. Tune descriptions against
`--split train`, then evaluate once against the frozen `--split validation`. Live evals never
run in CI.

## Installation profiles

| Profile | Purpose |
| --- | --- |
| `single` | Isolate the expected or forbidden skill and validate its metadata. |
| `all` | Measure exact routing with every committed guide installed. |

Quality mode runs each rubric case twice: with no skills and with the selected profile. It reports
the change in rubric score. Keyword checks do not fully judge answer quality.

## How skill loads are counted

The harness records client tool events when available. It also asks each client for a terminal
skill marker and accepts it only when the named skill was installed for that run. A `SKILL.md`
read or successful skill-tool event is stronger evidence than the marker, so the report keeps the
evidence source.

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
- Client adapter probe: one explicit invocation must pass per client before interpreting implicit
  cases.
- Positive recall: at least 80%; repeated cases should pass at least two of three runs.
- Near-miss specificity: at least 90%.
- Direct full-pack routing: at least 90% expected-skill recall and at least 90% exact matches among
  trace-proven routes. Report the trace and proxy denominators separately.
- Quality A/B: no correctness regression and a positive aggregate rubric delta.

Version 0.1 ships the harness and cases. One explicit-control case passed on all five clients. In
the one-pass full-pack smoke run, all 115 client/case pairs reported the expected skill. Of those,
69 routes were trace-proven and exact, with no unrelated loads; 46 OpenClaw and Hermes routes used
verified self-report proxies, which cannot prove that no second skill loaded. No process failed.
This passes the stated one-pass thresholds; it does not replace repeated positive and near-miss
validation.

The saved outputs from a focused Go comparison were rescored after the naming rubric was aligned
with the guide heading. The retrospective score was 4/4 concepts with and without the skill on
all five clients, so it found no regression and no lift. The original run report remains unchanged
at 32/40 and includes two negative deltas; this rescore is not an independent quality gate.
OpenClaw included and selected the reference-based Go skill, fixing the earlier oversized-inline
omission. A discarded routing index had loaded on only two clients and changed no rubric scores,
so it was removed. See the [version 0.1 plan review](../reports/v0.1-plan-review.md).
