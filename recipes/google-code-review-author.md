# Google's Code Review Guide for Authors

## Objective

Prepare the smallest self-contained change that solves one problem, keeps the system working,
and gives reviewers enough context and evidence to evaluate it efficiently.

## Workflow

1. Read repository instructions, inspect the working tree and diff, and identify the behavior the
   change is intended to add, remove, or preserve.
2. Define one reviewable purpose. Split unrelated behavior, preparatory refactoring, generated
   changes, or independently reviewable layers before polishing the change.
3. Include the tests and documentation needed for the change. Ensure every submitted step leaves
   the system in a usable, buildable state.
4. Write a description that explains what changes and why. Record relevant tradeoffs,
   limitations, dependencies, and validation.
5. Self-review the complete diff and rerun proportionate checks. Update the description after
   review changes so it still describes the final result.
6. Respond to feedback by improving the code or document first, then explaining only what future
   readers would not need recorded in the artifact.

## Decision rules

### Keep the change reviewable

- Make one minimal, coherent change. Judge size by conceptual scope and review difficulty, not
  line count alone.
- Include related production code, tests, and documentation together. Include a use of a new API
  when reviewers need it to understand the contract and avoid landing an unused interface.
- Separate behavior-preserving refactoring from feature work or bug fixes when combining them
  would hide the behavioral change. Small local cleanups may remain when they do not distract.
- Split work by independent files or reviewers, architectural layers, or vertical user-visible
  behavior. Stack dependent changes when each step is understandable and safe, and identify the
  dependency chain for reviewers.
- Keep each intermediate change working. Do not rely on a later change to restore the build,
  tests, or supported behavior.
- Permit a large deletion or trusted mechanical transformation when its review burden is small,
  but still validate its scope and effects. Obtain reviewer agreement before sending any other
  unavoidably large change.

### Write the change description

- Start with a short, specific, complete imperative sentence describing what the change does.
  Follow it with a blank line.
- Explain the problem and why this approach is appropriate. Include context not recoverable from
  the diff, such as constraints, decisions, tradeoffs, known shortcomings, and future direction.
- Include issue identifiers, design decisions, and benchmark or test results when relevant, but
  provide enough context that the description remains understandable if an external link becomes
  unavailable.
- Avoid generic summaries such as “fix bug,” phase labels, or implementation activity without an
  outcome. Apply the same standard to generated descriptions.
- Re-read the description immediately before submission and after substantial review revisions.

### Include evidence

- Add or update tests for changed logic. Cover refactoring with existing tests or add tests first
  when coverage is missing.
- Keep independent test improvements or test-infrastructure changes separate when they can land
  safely before the main change.
- Update READMEs, API documentation, operational instructions, and generated documentation when
  the change affects how users build, test, use, debug, or release the system.
- Report commands actually run and their results. Never imply that a check passed when it was not
  run or its result is unknown.

### Handle comments collaboratively

- Understand the request before answering. Ask for clarification when its intent or severity is
  unclear.
- If a reviewer cannot understand the code, clarify the code first. Add a code comment only when
  the code cannot express necessary reasoning; do not hide lasting context in the review thread.
- Address disagreement with technical facts, constraints, and explicit tradeoffs. Explain the
  current choice and ask which premise or priority the reviewer sees differently.
- Stay courteous and do not respond while angry. Seek consensus; move a stalled discussion to a
  direct conversation when useful, record the result, and then use the project's escalation path.

### Treat emergencies narrowly

- Treat a change as an emergency only when it addresses an active, serious production impact, a
  major security or legal issue, or a genuinely disastrous hard deadline.
- Do not classify ordinary schedule pressure, personal urgency, unavailable reviewers, or a soft
  launch target as an emergency.
- Keep an emergency change small, optimize the immediate review for correctness and response
  speed, and arrange a full follow-up review after the incident is controlled.

## Output contract

Produce a review package with:

- `Readiness`: `Ready`, `Not ready`, or `Blocked`, with the decisive reason.
- `Scope`: the one purpose of this change and any work deliberately excluded.
- `Split plan`: ordered dependent changes, or `Not needed` with a reason.
- `Description`: the exact proposed summary line, a blank line, and the informative body.
- `Validation`: commands run, results, and checks not run.
- `Tests and docs`: what changed and any justified omission.
- `Risks and dependencies`: rollout, compatibility, ordering, or reviewer context.
- `Open review items`: each comment's requested outcome, chosen action, and unresolved decision.

Do not claim readiness while required tests, documentation, build integrity, or material reviewer
context is missing.
