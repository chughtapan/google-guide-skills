# Discoverability and quality evaluation

The evaluation answers two questions: does each client select the intended guide, and does that
guide improve a source-specific answer? A valid skill folder or visible catalog cannot answer
either question, so routing and answer quality are measured separately.

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

- 16 explicit invocation controls, rendered for each client adapter;
- 16 implicit smoke prompts, one for every committed guide;
- 8 local-only smoke plans, one for every restricted SWE-book skill;
- 60 representative cases across Python style, reviewer workflow, and documentation;
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

The saved five-client routing runs belong to an earlier 23-skill committed corpus. They helped
expose an oversized Go skill, vague reference routing, and a routing index that added no measured
value. Do not use their routing rates for the current 16-public/8-local pack.

A current-corpus [SlopCodeBench quality experiment](../reports/slopcodebench-quality.md) compares
a five-checkpoint just-solve trajectory with a guide, parallel review, and fix trajectory. The
arms tied on hidden correctness. The guided code had less structural erosion and its reviewers
found additional contract defects, but the workflow cost four times as many calls and later lost
one accepted fix. The report defines the smaller next iteration. See the
[version 0.1 plan review](../reports/v0.1-plan-review.md) for the broader release history.
