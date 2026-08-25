---
name: google-code-review-reviewer
description: >-
  Use when reviewing a code change, deciding what to inspect, applying Google's review standard,
  writing comments, reviewing quickly, navigating a change, or handling pushback. Do not use
  when only preparing your own change for review.
---

# Google's Code Review Guide for Reviewers

## Objective

Decide whether a change improves the overall health of the system and give the author prioritized,
evidence-based feedback that makes the next action clear. Require sound code, not perfection.

## Workflow

1. Read repository instructions and establish the assigned scope. Read the change description,
   inspect the complete diff, and identify generated files or areas owned by other reviewers.
2. Take a broad view first. Decide whether the change belongs in the system and whether its
   design and direction make sense. Send major design objections immediately.
3. Review the main implementation path, then inspect tests and the remaining files in a logical
   order. Read surrounding code when the diff lacks enough context.
4. Understand every assigned human-written line. Request clarification or a qualified specialist
   for security, privacy, concurrency, accessibility, internationalization, or another domain you
   cannot assess responsibly.
5. Run or inspect proportionate validation when it materially reduces uncertainty. Review test
   code with the same care as production code.
6. Report findings by severity, recheck the author's revisions, and state an approval decision,
   reviewed scope, and residual risk.

## Decision rules

### Apply the review standard

- Favor approval once the change definitely improves code health, even if minor polish remains.
- Do not approve a change that makes the system less maintainable, understandable, tested, or
  safe merely because cleanup is promised later. Allow a documented exception only for a real
  emergency.
- Balance the value of a requested improvement against its cost and the need for progress. Mark
  educational advice and personal polish preferences as nonblocking.
- Prefer technical facts, project requirements, and measured evidence over opinion. Treat the
  applicable style guide as authoritative. When several approaches are equally sound, accept the
  author's choice.

### Inspect the change

- **Purpose and design:** Confirm that the intended behavior is valuable, belongs in this
  codebase, composes with the existing system, and does not create an unnecessary abstraction.
- **Correctness:** Check normal behavior, boundaries, failure paths, state transitions,
  concurrency, cleanup, compatibility, and user-visible effects. Consider abuse and specialist
  risks when relevant.
- **Complexity:** Reject overengineering and speculative functionality. Prefer code that readers
  can understand quickly and modify without surprising consequences.
- **Tests:** Require the appropriate unit, integration, or end-to-end evidence. Confirm that tests
  would fail for the defect or regression, assert useful behavior, avoid needless complexity,
  and remain stable as implementation details change.
- **Names and comments:** Require names that communicate purpose. Prefer code that explains what
  it does and comments that explain non-obvious reasons, constraints, or contracts.
- **Style and consistency:** Apply repository rules first. Do not block on an undocumented
  personal preference; use surrounding conventions only when no stronger rule applies and doing
  so does not reduce code health.
- **Documentation:** Require updates when users must build, test, configure, operate, debug,
  migrate, or release the system differently. Remove or update documentation for deleted or
  deprecated behavior.
- **Context:** Inspect enough surrounding code to detect growing methods, duplicated behavior,
  ownership mistakes, and small additions that cumulatively degrade the system.

### Write actionable comments

- Comment on the code or outcome, never the person. Be direct, courteous, and specific.
- Explain why an issue matters when the impact is not obvious. State the violated invariant,
  likely failure, maintenance cost, or governing rule.
- Balance identifying the problem with prescribing a solution. Give a concrete direction when it
  saves time, but leave implementation choice to the author when several fixes are valid.
- Label intent explicitly:
  - `Required`: must change before approval.
  - `Nit`: minor polish that should not block submission.
  - `Optional` or `Consider`: potentially useful, not required.
  - `FYI`: information for future work; no action expected now.
- If an explanation is necessary for ordinary future readers, ask the author to clarify the code
  or add an appropriate comment instead of preserving the explanation only in the review tool.
- Acknowledge especially clear design, cleanup, or test coverage when doing so reinforces a useful
  practice.

### Keep review moving

- Respond promptly at a natural break in focused work. If a full review must wait, provide an
  honest timing update, suggest another reviewer, or send broad design feedback that unblocks the
  author.
- Ask the author to split a change that is too large to review reliably. If it cannot be split,
  review the overall design first and agree on a tractable sequence.
- Approve with unresolved comments only when all remaining items are explicitly nonblocking or
  you are confident they will be handled correctly.
- When the author pushes back, reconsider the argument fairly; they may know the code better.
  Explain any continuing objection using evidence and code-health impact. Seek consensus, record
  decisions from direct conversation, and escalate rather than letting the change stall.

## Output contract

Lead with one of `Approve`, `Approve with nonblocking comments`, `Request changes`, or `Blocked`,
followed by:

- `Scope reviewed`: files, components, and review dimensions covered; identify exclusions.
- `Required findings`: `Required: path:line — issue; impact; concrete correction.`
- `Nonblocking findings`: labeled `Nit`, `Optional`, or `FYI` with location and rationale.
- `Validation`: checks performed, evidence inspected, and checks not performed.
- `Residual risks`: uncertainty, missing specialist review, or behavior not exercised.

Order findings by severity and user or system impact. Do not fabricate file locations, failures,
or test results. If there are no required findings, say so explicitly rather than inventing one.
