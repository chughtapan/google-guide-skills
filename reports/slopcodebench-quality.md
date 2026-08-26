# SlopCodeBench quality experiment

On this task, the Google skills improved code structure without improving hidden-test correctness.
At the default reasoning effort, the guided and baseline arms both scored 95/104. At `xhigh`, the
baseline scored 100/104 and the guided arm scored 97/104.

The result supports a narrow claim: the skills can help an agent organize code without requiring a
large workflow. It does not show that the skills make the implementation more correct.

## Question

Can an agent use the rewritten source-excerpt skills under a short project instruction and produce
code that is easier to maintain without losing correctness?

## Method

Both arms solved all five checkpoints of SlopCodeBench's `code_search` problem. Each checkpoint
started a fresh model conversation and continued from the previous checkpoint's files. Hidden tests
ran only after each snapshot was frozen.

The task prompt was the same in every call:

> Implement the current checkpoint described in `TASK.md`.

`TASK.md` contained the cumulative public specification. The baseline received no skills or project
instructions. The guided arm received these four skills:

- `google-python-style`
- `google-code-review-author`
- `google-code-review-reviewer`
- `google-swe-testing`

Its lifecycle instruction was:

> For material changes, own the work through verification. Use your judgment and the relevant
> skills.

The agent chose which skills to read and how to implement, test, and review the change. The harness
did not create review rounds or ask for specific tests.

| Input | Value |
| --- | --- |
| SlopCodeBench | `06b5c0687d4c05ee502e9696a4d0c22fc1eec5e0` |
| Problem corpus | `4d38d300059667d57e43c31969bc455f5c338b52` |
| Guide pack digest | `edb8a9de246cc4cfb9eeae21c3ed4406b1a926d8dd3175f400f36c88b737722b` |
| Client | Codex CLI 0.149.0 with the existing ChatGPT login |
| Model | `gpt-5.6-sol` |
| Structural scorer | `scb-check==0.1.3` |
| Scope | One problem, five checkpoints, one run per cell |

## Correctness

| Effort | Checkpoint | Baseline | Guided |
| --- | ---: | ---: | ---: |
| Default | 1 | 13/13 | 13/13 |
| Default | 2 | 25/25 | 25/25 |
| Default | 3 | 45/47 | 46/47 |
| Default | 4 | 70/75 | 70/75 |
| Default | 5 | 95/104 | 95/104 |
| `xhigh` | 1 | 13/13 | 13/13 |
| `xhigh` | 2 | 25/25 | 25/25 |
| `xhigh` | 3 | 44/47 | 43/47 |
| `xhigh` | 4 | 72/75 | 70/75 |
| `xhigh` | 5 | 100/104 | 97/104 |

The pinned reference implementation scored 103/104. It is useful context, not a perfect control.

At default effort, the guided arm gained one test at checkpoint 3, then finished tied with the
baseline. At `xhigh`, the guided arm finished three tests behind the baseline. Higher effort raised
the final baseline score by five and the final guided score by two, but these are single runs rather
than variance estimates.

The final `xhigh` guided failures covered literal-dollar handling, optional metavariables,
multiline Python patterns, same-start ordering, match-before-fix ordering, a Go structural pattern,
and a Java method pattern. Reading the testing guide did not make those cases apparent from the
public specification.

## Structure

Lower scores are better. Verbosity measures the share of code flagged by structural heuristics.
Erosion measures how much measured complexity is concentrated in high-complexity functions.

| Effort | Arm | Hidden tests | Verbosity | Erosion | Cognitive erosion |
| --- | --- | ---: | ---: | ---: | ---: |
| Default | Baseline | 95/104 | 0.430 | 0.864 | 0.964 |
| Default | Guided | 95/104 | 0.328 | 0.803 | 0.936 |
| `xhigh` | Baseline | 100/104 | 0.494 | 0.966 | 0.989 |
| `xhigh` | Guided | 97/104 | 0.242 | 0.741 | 0.920 |
| — | Reference | 103/104 | 0.269 | 0.367 | 0.781 |

The guided arm improved all three measures at both effort levels. The `xhigh` guided solution also
contained more duplicated code than its baseline, so the structural result is positive but not
uniform. These heuristics support a source review; they do not prove readability by themselves.

## Agent behavior

At default effort, the guided agent loaded Python style and testing for checkpoints 1–3, retained a
passing test file, and used no skill for checkpoints 4–5. At `xhigh`, it loaded Python style and
testing at every checkpoint and the author guide at checkpoint 5. Both guided workspaces retained
tests.

An earlier `xhigh` guided attempt used a lifecycle sentence that explicitly mentioned independent
reviews. The agent entered repeated review and fix work, attempted a nested agent review, and hit
the 30-minute cap at checkpoint 3. Its frozen state passed 33 self-written tests but only 42/47
hidden tests. Removing the review cue let the same model and effort complete all five checkpoints.
This is why the repository lifecycle states an outcome and leaves the workflow to the agent.

## Cost

OAuth runs did not report dollar cost, so the report uses elapsed time and tokens. Input counts
exclude cached tokens.

| Effort | Arm | Calls | Wall time | Uncached input | Output |
| --- | --- | ---: | ---: | ---: | ---: |
| Default | Baseline | 5 | 10m 54s | 173,667 | 26,944 |
| Default | Guided | 5 | 11m 55s | 189,415 | 30,887 |
| `xhigh` | Baseline | 5 | 48m 07s | 487,762 | 122,158 |
| `xhigh` | Guided | 5 | 60m 03s | 610,777 | 154,602 |

At default effort, the guided arm used 9% more uncached input and took 9% longer. At `xhigh`, it
used 25% more uncached input and took 25% longer. The `xhigh` baseline itself took more than four
times as long as the default baseline.

## Takeaway

Use the minimal lifecycle. It produced the clearest result and avoided turning review into an
unbounded process.

The current evidence says:

- the skills route without a manually orchestrated prompt;
- the guided solutions have better measured structure;
- default-effort correctness was unchanged;
- `xhigh` improved both arms in absolute terms, but did not make the guided arm beat its baseline;
- `ultra` is not justified for this demo because `xhigh` already cost about an hour per guided run
  without closing the correctness gap.

The next useful experiment is another problem, not another effort level on this one. A broader
quality claim needs multiple tasks and repeated runs.

## Limits and artifacts

This is one problem and one run per cell. It cannot establish a general effect or estimate
variance. Both arms used the benchmark's local environment rather than its container image. The
test collection hash was identical within each checkpoint.

Raw prompts, traces, snapshots, hidden-test output, and metrics remain in ignored local directories:

- `evals/results/slopcodebench-autonomous-20260826T165249Z/`
- `evals/results/slopcodebench-autonomous-xhigh-20260826T172910Z/`

See the [SlopCodeBench paper](https://arxiv.org/pdf/2603.24755),
[project](https://www.scbench.ai/), and
[source repository](https://github.com/SprocketLab/slop-code-bench) for benchmark context.
