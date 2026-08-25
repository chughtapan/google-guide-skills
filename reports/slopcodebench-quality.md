# SlopCodeBench quality experiment

The guide-led workflow did not improve hidden-test correctness on this run. The baseline and
guided solutions both finished at 93 of 104 tests, and the review loop changed no hidden-test
score at any checkpoint.

It did change the code. The guided solution spread complexity across smaller units, had less
structural erosion at every checkpoint, and its reviewers found contract defects that the hidden
suite did not cover, including a fix path that could truncate a source file. It was also more
verbose, used four times as many model calls, and lost one earlier review fix because no regression
test preserved it.

This is evidence for improving the workflow, not evidence that the current workflow raises task
correctness.

## Hypothesis

Reading the applicable style guide before implementation, then running separate code and testing
reviews in parallel and applying verified findings, should produce code that is easier to maintain
and more correct than a just-solve prompt.

The experiment tested both parts:

- hidden tests measured checkpoint correctness;
- `scb-check` and a source review measured structural quality;
- the trajectories showed which defects the reviews found, fixed, missed, or later regressed.

## Setup

Both arms solved all five checkpoints of SlopCodeBench's `code_search` problem. Each arm had its
own persistent workspace, while each model call started without conversation history. Agents
could see the public specification through the current checkpoint, but not future specifications,
hidden tests, the benchmark repository, or the other arm.

| Input | Value |
| --- | --- |
| SlopCodeBench | `06b5c0687d4c05ee502e9696a4d0c22fc1eec5e0` |
| Problem corpus | `4d38d300059667d57e43c31969bc455f5c338b52` |
| Guide pack | `ee16171f13032b2e1fab9462458e23ab81174569` |
| Client | Codex CLI 0.149.0 with the existing ChatGPT login |
| Model | `gpt-5.6-sol`, Codex CLI default reasoning effort |
| Structural scorer | `scb-check==0.1.3` |
| Cyclomatic-complexity scorer | Radon 6.0.1 |
| Scope | One problem, five checkpoints, one run per arm |

The baseline made one just-solve call per checkpoint.

The guided arm used this sequence at every checkpoint:

1. Invoke `google-python-style` and implement the public specification.
2. Review separate copies in parallel with:
   - `google-code-review-reviewer` and `google-python-style`;
   - `google-swe-testing` and `google-python-style`.
3. Invoke `google-python-style` and apply reproduced Required findings.
4. Snapshot the workspace before revealing hidden results.

The review copies did not contain the implementation workspace's virtual environment. This
prevented both checkpoint-4 reviewers and the final code reviewer from running the program. The
final testing reviewer installed dependencies separately. That flaw is part of the result.

## Correctness result

The arms tied at every checkpoint. The guided review-and-fix stage also produced zero hidden-test
lift at every checkpoint.

| Checkpoint | Baseline | Guided before review | Guided after review |
| ---: | ---: | ---: | ---: |
| 1 | 13/13 | 13/13 | 13/13 |
| 2 | 25/25 | 25/25 | 25/25 |
| 3 | 42/47 | 42/47 | 42/47 |
| 4 | 69/75 | 69/75 | 69/75 |
| 5 | 93/104 | 93/104 | 93/104 |

At checkpoint 5 the failures were not identical. The guided solution retained a JavaScript
selector behavior that the baseline lost, but it failed a different cross-language structural
pattern case. The equal total therefore hides one changed tradeoff, not identical programs.

The repository's checkpoint-5 reference implementation scored 103/104 under the same pinned
runtime. It failed one selector regression, so it is context rather than a perfect control.

## Structural result

Lower verbosity and erosion scores are better. Erosion is the share of measured complexity mass
concentrated in high-complexity code. The line count is included to show scale, not to score
quality: the reference implementation is the largest solution and has the lowest erosion.

| Final snapshot | Hidden tests | Verbosity | Erosion | Cognitive erosion | Average CC | Maximum CC | LOC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 93/104 | 0.185 | 0.916 | 0.949 | 8.95 | 47 | 276 |
| Guided | 93/104 | 0.241 | 0.752 | 0.898 | 5.00 | 37 | 1,235 |
| Reference | 103/104 | 0.215 | 0.324 | 0.778 | 4.06 | 24 | 4,395 |

The guided arm had lower structural erosion at every checkpoint and higher measured verbosity at
every checkpoint:

| Checkpoint | Baseline erosion | Guided erosion | Baseline verbosity | Guided verbosity |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.852 | 0.644 | 0.035 | 0.339 |
| 2 | 0.856 | 0.588 | 0.032 | 0.287 |
| 3 | 0.828 | 0.638 | 0.191 | 0.341 |
| 4 | 0.874 | 0.758 | 0.188 | 0.312 |
| 5 | 0.916 | 0.752 | 0.185 | 0.241 |

### What the code looks like

The baseline put validated rule state into a compact mutable object and handled the schema in one
dense function:

```python
@dataclass
class Rule:
 id:str; kind:str; pattern:str; languages:frozenset[str]; regex:Pattern[str]|None=None; plans:dict[str,Plan]=field(default_factory=dict); fix:str|None=None
def load_rules(path):
 try:raw=json.loads(path.read_text(encoding="utf-8"))
 except (OSError,UnicodeError,json.JSONDecodeError) as e:fail(f"cannot read rules file: {e}")
 if not isinstance(raw,list):fail("rules file must contain a JSON array")
 out=[];seen=set()
```

The guided result used named immutable records and separated argument parsing from rule loading:

```python
@dataclasses.dataclass(frozen=True)
class _Rule:
    """A validated search rule."""

    rule_id: str
    languages: frozenset[str]
    text_pattern: re.Pattern[str] | None = None
    structural_patterns: dict[str, _Pattern] | None = None
    selector: str | None = None
    fix: _Fix | None = None
```

The guided code is easier to scan locally and has lower average complexity. It still has a large
selector table, a 37-complexity rule loader, and more code to navigate. The result is a
maintainability improvement in one dimension, not a clean finish.

## What the reviews changed

Without access to hidden results, the reviewers found these defects. Several were not covered by
the hidden suite:

- Checkpoint 2: lone-CR line endings produced wrong coordinates.
- Checkpoint 3: placeholder identifiers could collide with source identifiers; optional
  metavariables mishandled list separators; literal-dollar handling was incomplete.
- Checkpoint 4: several selectors returned containers or duplicate expressions instead of code
  elements; fix templates could reference undefined captures.
- Checkpoint 5: Rust and Haskell selector aliases were incomplete; nested arguments were skipped;
  an unencodable replacement truncated the source file before returning an error.

The final guided solution passes the review-derived ten-test contract suite. The baseline fails
individual parameter and argument selection, nested arguments, two Rust selector cases, and the
non-destructive encoding failure. This comparison is post hoc: the guided reviewers created the
cases after seeing the guided code, so it shows what the workflow found, not an unbiased score.

The trajectory also shows a failure in the workflow. The checkpoint-3 fix made optional leading
arguments work and verified the behavior with a temporary probe. Checkpoint 5 regressed it. Both
final solutions now fail that public-contract probe. A temporary check proved the fix once; it did
not protect later checkpoints.

## Why hidden correctness did not improve

1. The prompt said not to add permanent tests. That contradicted the review guide's instruction
   to require a test that fails for a confirmed defect. The missing regression let an accepted
   fix disappear two checkpoints later.
2. Reviewers did not receive a runnable copy of the environment. Several reviews relied on source
   inspection where a public black-box check would have been stronger.
3. The cumulative specification was included as prose, but no artifact mapped each normative
   behavior to a test. Agents concentrated on the newest and most visible grammar mappings while
   older ordering, default-language, optional, and dollar-escape behavior remained uncovered.
4. The two reviewers were parallel but not independent in model or training. They found
   complementary defects, yet shared blind spots around the hidden cross-language cases.
5. The fix agent could make broad changes for valid findings without rerunning a stable
   cumulative suite. Checkpoint 4 added 214 implementation lines and new tests while leaving the
   benchmark score unchanged.

The guides did provide useful review principles. The experiment prompt and workspace failed to
turn them into a durable verification process.

## Cost

OAuth runs did not report a dollar cost, so token and elapsed counts are the honest comparison.
Input counts below exclude cached input tokens.

| Measure | Baseline | Guided | Ratio |
| --- | ---: | ---: | ---: |
| Model calls | 5 | 20 | 4.00× |
| Wall time | 13m 43s | 45m 09s | 3.29× |
| Sum of call time | 13m 43s | 56m 01s | 4.08× |
| Uncached input tokens | 205,198 | 853,086 | 4.16× |
| Output tokens | 33,048 | 129,441 | 3.92× |

Parallel reviews account for the difference between guided wall time and summed call time.

## Next pipeline

Keep the same basic flow, with four changes:

1. Implement after loading the applicable style guide.
2. Maintain a small cumulative public-contract suite. Map each normative behavior to at least one
   normal, boundary, or failure check where applicable.
3. Run code and testing reviews in parallel inside runnable copies of the same environment. Every
   Required correctness finding must include a reproducer.
4. Apply only reproduced Required findings. Keep the smallest regression test for each accepted
   defect, then run the cumulative suite before taking the snapshot. Skip the fix call when both
   reviews have no Required findings.

Rerun this same five-checkpoint case once with that pipeline before adding more benchmark
problems. The next run should be judged on hidden correctness, preservation of accepted fixes,
erosion, verbosity, and cost. More scenarios are useful only after the process stops losing known
behavior.

## Limits and artifacts

This is one problem, one model, and one run per arm. It cannot estimate variance or establish a
general quality lift. The reviewer-created probes are diagnostic rather than preregistered. Both
arms used SlopCodeBench's local environment instead of its container image, with identical test
collection hashes at each checkpoint.

Raw prompts, traces, snapshots, review reports, hidden-test output, and metrics remain in the
ignored local directory
`evals/results/slopcodebench-v0.2-20260825T202647Z/`.

See the [SlopCodeBench paper](https://arxiv.org/pdf/2603.24755),
[project](https://www.scbench.ai/), and
[source repository](https://github.com/SprocketLab/slop-code-bench) for benchmark context.
