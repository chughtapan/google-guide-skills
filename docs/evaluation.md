# Discoverability and quality evaluation

For each case, the harness creates a Git repository in an OS temporary directory, copies the
selected skills into it, and starts a client without a saved session. Bubblewrap exposes the
system runtime and that run directory, but not the source checkout, case labels, earlier answers,
user homes, or other skills. The harness deletes the workspace after recording the result.
`--keep-raw` preserves the trace under the ignored results directory.

Every run mounts its workspace at the same short agent-visible path, `/w`. Codex therefore sees
installed skills under `/w/.agents/skills`, regardless of the host temporary-directory name or
profile. Before model invocation, the harness recomputes the rendered metadata list at that exact
path and rejects an over-budget install. This prevents profile-dependent paths or truncation from
confounding the `all-no-index` versus `all` comparison.

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
uv run google-guides eval triggers --stage index-experiment --profile index-ab
uv run google-guides eval triggers --stage smoke --profile all --limit 2 \
  --agent codex --live
uv run google-guides eval quality --profile single \
  --agent claude-code --model claude-code=haiku --live
```

Without `--agent`, the plan and live run target all five clients. Missing binaries matter only for
selected live clients. `--model AGENT=MODEL` is optional and repeatable. Use `--limit` before a
large matrix. Raw traces are discarded unless `--keep-raw` is passed. Reports and kept traces live
under mode-0700 `evals/results/`, which Git ignores. Failed runs do not count toward accuracy.

Each client receives a reduced process environment. Codex shell commands inherit none of it. The
harness does not send SWE-book output to hosted agents; `local-smoke` supports planning and
offline tests only.

## Test cases

[`evals/cases.yaml`](../evals/cases.yaml) contains:

- 24 explicit invocation controls, rendered for each client adapter;
- 24 implicit smoke prompts, one for every committed guide plus the index;
- 8 local-only smoke plans, one for every restricted SWE-book recipe;
- 80 representative cases across Python style, reviewer workflow, documentation, and the
  Abseil C++ tips reference collection;
- 6 broad-routing cases for a paired index/no-index experiment;
- for each representative skill, 10 positives and 10 near-miss negatives with a fixed 60/40
  train/validation split;
- concept-check rubrics for a quality A/B subset.

Use `--repeat 3` after the one-pass smoke stage passes. Tune descriptions against
`--split train`, then evaluate once against the frozen `--split validation`. Live evals never
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
- Explicit controls: 100% before interpreting implicit cases.
- Positive recall: at least 80%; repeated cases should pass at least two of three runs.
- Near-miss specificity: at least 90%.
- Direct full-pack routing: at least 90% exact matches, with unexpected loads reported separately.
- Index experiment: at least 5/6 broad prompts load the index, positive paired lift over
  `all-no-index`, and a 0% index steal rate on direct smoke prompts.
- Quality A/B: no correctness regression and a positive aggregate rubric delta.

Version 0.1 ships the harness and cases. A one-case explicit-control probe completed correctly on
all five clients (5/5). One implicit documentation case also routed exactly on all five clients;
three loads were trace-proven and two used the installed-skill self-report proxy. In one paired
broad-routing case, the index loaded on Codex and OpenCode (2/5 clients) and changed no rubric
scores. An OpenClaw Go probe scored a miss because OpenClaw omitted the oversized skill from its
inventory; the harness rejected the model's unverified self-report. These probes do not satisfy
the routing or quality gates. See the
[version 0.1 plan review](../reports/v0.1-plan-review.md).
