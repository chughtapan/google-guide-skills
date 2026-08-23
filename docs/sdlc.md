# Development lifecycle

This document is for contributors and maintainers of Google Guide Skills. It defines how a
change moves from an issue to a pull request and which Agent Skills apply at each stage.

The process is risk-based. Small changes use the core build, test, review, and ship loop. Changes
to public behavior, source policy, installation, evaluation, or distribution add planning and
review gates.

## Records

Use these records as the sources of truth:

- A GitHub issue states the problem, affected user, outcome, acceptance criteria, non-goals,
  risk, and validation plan for nontrivial work.
- `docs/architecture.md` records project-wide architecture. Add `docs/designs/<topic>.md` when a
  change needs a lasting design record that does not belong in the project-wide document.
- A pull request explains what changed and why, links the issue or design record, and records
  tests, generated outputs, licensing impact, and skill reviews.
- `TODOS.md` holds deferred work with enough context to resume it. It is not a substitute for an
  issue that defines the current change.

Documentation changes travel with the code they describe. The README remains the landing page;
details live in `docs/`.

## Risk levels

| Level | Examples | Required planning |
|---|---|---|
| Routine | Typo, wording, test-only change, or metadata with no behavior or policy change | No issue or engineering review required |
| Standard | Bug fix, new behavior, CLI change, corpus entry, public format, dependency, or refactor across modules | Issue or design record; use `plan-eng-review` when interfaces or several modules change |
| High | Licensing, generated-output boundary, source trust, credentials, sandbox, installer, evaluator isolation, or distribution | Issue and `plan-eng-review`; name rollback and failure tests |

Product-facing work also uses `plan-ceo-review`. UI and interaction changes use a design review.
A narrow bug fix can skip `plan-eng-review` when the cause, fix, and regression test are local to
one component.

## Skill routing

Use only the skills that match the decision being made.

| Stage | Skills | Gate |
|---|---|---|
| Discover | `office-hours`; `plan-ceo-review`; `google-swe-culture-and-leadership` for ownership or team practice | Problem, user, outcome, scope, and non-goals are clear |
| Design | `design-consultation`; `plan-design-review` for UI or interaction changes | States and user flow are decided |
| Plan | `plan-eng-review`; `google-swe-infrastructure`; `google-swe-maintenance-and-delivery` | Interfaces, data flow, failures, tests, distribution, and work order are decided |
| Implement | Applicable language or format guide; `google-swe-style-and-readability` | Code, tests, and documentation form one coherent change |
| Test | `google-swe-testing` and the applicable language guide | Behavior, error paths, and integration risks have tests at the right scope |
| Document | `google-documentation-guide`; `google-swe-documentation` | Documentation is accurate for its audience and reviewed with the change |
| Prepare review | `google-code-review-author` | Commits and pull-request text explain what and why |
| Review | `google-code-review-reviewer`; `google-swe-code-review`; `google-swe-style-and-readability`; `google-swe-testing`; diff-specific guides | All `Required:` findings are resolved |
| Release | `google-swe-maintenance-and-delivery`; `ship` | Fresh checks pass and the pull request reflects the shipped diff |
| Learn | `document-release`; `retro`; `benchmark` or `canary` when applicable | Follow-up work and release evidence are recorded |

`google-swe-book-front-matter` is not a development gate. Use it only for questions about the
book's scope, authorship, publication, navigation, or attribution.

## Local SWE-book skills

Eight SWE-book skills are generated under `.generated/skills/` and linked into a maintainer's
agent homes. They are not committed or published:

- `google-swe-code-review`
- `google-swe-testing`
- `google-swe-style-and-readability`
- `google-swe-documentation`
- `google-swe-maintenance-and-delivery`
- `google-swe-infrastructure`
- `google-swe-culture-and-leadership`
- `google-swe-book-front-matter`

The README contains the generation and self-install commands. If a local skill is missing, state
that it was unavailable. Use a committed counterpart when one exists, but do not claim that the
local review ran.

## Implementation rules

- Keep each change small enough to review. Separate preparatory refactors from behavior changes
  when each can land independently.
- Include tests and affected documentation in the same change.
- Test observable behavior through public interfaces. Prefer the smallest deterministic test
  with enough fidelity; use larger tests when integration behavior is the risk.
- For generated skills, edit the generator or `corpus.yaml` and regenerate. Do not hand-edit
  converted upstream prose.
- Record deferred work instead of hiding it in comments or a pull-request discussion.

## Repository gates

The Development section of the README contains the canonical local commands. CI in
`.github/workflows/ci.yml` is the executable source of truth.

Apply these extra gates by change type:

| Change | Extra gate |
|---|---|
| Python or shell | Format, lint, and run the affected tests |
| Generator, manifest, or catalog | Regenerate committed outputs and confirm `skills/` and `catalog/` have only expected changes |
| SWE-book collection | Run the local `--include-swe-book` release check and confirm `.generated/skills/` remains ignored and untracked |
| Source or license policy | Verify pinned inputs, evidence, attribution, distribution class, and output root |
| Skill description or index | Recompute the metadata budget and run the applicable discoverability plan or evaluation |
| Installer, evaluator, sandbox, or credentials | Run isolation, path-boundary, subprocess-environment, and failure-path tests |
| Package contents | Build the wheel and source distribution and confirm neither contains `skills/` nor `.generated/` |
| Documentation | Check commands against `--help`, check links and names, and obtain a technical and audience review |

Live model evaluations require the safety controls documented in `docs/evaluation.md`. Do not
use normal provider credentials or treat an unrun live gate as passed.

## Review and ship

The author reviews the change before requesting another review. The reviewer checks design first,
then every changed human-authored line. Use these labels:

- `Required:` blocks shipping.
- `Nit:` identifies non-blocking polish.
- `Optional:` offers another valid approach.

When the change is ready, `AGENTS.md` routes the diff through the applicable Google review
skills. Resolve required findings, rerun affected tests, and invoke `ship`. The repository does
not wrap or replace the installed `ship` skill.

`ship` owns the final test, coverage, scope, documentation, version, changelog, commit, push, and
pull-request workflow. A completion claim requires fresh output from the checks run against the
final diff.
