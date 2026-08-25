# Google Common Lisp Style Guide

## Scope and precedence

Apply this guide to Common Lisp, not other Lisp dialects. Follow project rules and established
package conventions when they complement or override this guide. Treat `MUST` and `MUST NOT`
rules as requirements that need owner permission to violate; treat `SHOULD` rules as defaults
whose exceptions need a nearby explanation and reviewer agreement. Fix relevant old violations
while touching code, but coordinate before mass reformatting or other broad mechanical changes.

Prefer, in order: correct customer behavior, debuggability and testability, readability,
extensibility, then runtime efficiency. Choose the simpler design until profiling identifies a
real bottleneck.

## Workflow

1. Read repository instructions and nearby code. Identify the package API, existing assignment
   conventions, indentation style, condition hierarchy, and supported Lisp implementations.
2. Choose explicit packages, data representations, function contracts, and error conditions
   before writing implementation details. Reuse an appropriate library rather than starting one
   without checking available alternatives and obtaining required approval.
3. Implement with small top-level forms, minimal mutable state, explicit validation at API
   boundaries, and ordinary functions unless syntactic abstraction is necessary.
4. Add docstrings, focused comments, tests, and any type or safety checks required by the
   contract.
5. Format with the project's configured Common Lisp indentation, then inspect warnings,
   package boundaries, macro expansions, cleanup paths, and unsafe declarations.
6. Compile without errors or warnings and run the project's precheckin and unit tests before
   reporting completion.

## High-impact rules

### Files, formatting, and comments

- Begin each source file with a brief contents description, then `(in-package #:package-name)`,
  followed by any file-specific optimization declaration. Omit authorship and per-file copyright
  text unless the file is distributed standalone.
- Keep lines within 100 characters. Use spaces, never tabs. Follow configured GNU Emacs Common
  Lisp indentation; do not add whitespace inside parentheses, vertically align unrelated forms,
  or leave closing parentheses alone on a line.
- Put one blank line between top-level forms. Prefer short forms and split functions that require
  page-length bodies or blank lines merely to explain their internal phases.
- Document visible functions and top-level types, classes, variables, and macros. Function
  docstrings state purpose, argument meaning, returned values, and signaled conditions; comments
  explain implementation reasons rather than restating code.
- Use `;;;;` for file or major-section comments, `;;;` for a top-level form or group, `;;` within
  a form, and `;` for an end-of-line aside. Comment every non-obvious regular expression.
- Write searchable `TODO` comments with a responsible identifier and a concrete problem. Use
  `YYYY-MM-DD` for dates and precise release identifiers for milestones.

### Names and packages

- Write symbols in lowercase with hyphens between words. Use descriptive, correctly spelled
  names and only common or domain-specific abbreviations; short lexical names are acceptable only
  in a small scope.
- Name by intent, not representation. Do not add `list`, `array`, or `hash-table` merely because
  that is the current storage type.
- Surround global constants with `+plus-signs+` and special variables with `*asterisks*`. End
  predicates with `p` for a one-word stem or `-p` for a multiword stem.
- Do not repeat the package name inside its symbols. Do not access another package's internals
  with `::` in production code; export the contract or introduce separate user and extension
  packages. Tests may inspect the package they test.
- New packages should normally require explicit package qualification rather than being added to
  other packages' `:use` lists. Do not shadow Common Lisp symbols except for a rare, documented,
  reviewed replacement.

### State, control flow, and data

- Prefer mostly functional code: initialize objects completely, avoid unnecessary assignment,
  and keep classes immutable where practical. Use special variables sparingly and bind them per
  thread of control rather than relying on mutable global defaults.
- Preserve the package's `SETF`/`SETQ` and grouping convention. For a new package, prefer `SETF`
  and group related assignments, while still minimizing side effects.
- Prefer iteration or mapping functions to recursion that depends on tail-call optimization.
- Use `WHEN` or `UNLESS` for one branch, `IF` for two, and `COND` for several. Prefer `ECASE` and
  `ETYPECASE` when unexpected values indicate bugs. Use `CASE` only for `EQL`-appropriate values
  such as numbers, characters, and symbols.
- Use `EQL` for identity unless low-level profiling justifies `EQ`; never use `EQ` for numbers or
  characters. Use type-specific string, character, and numeric predicates, and never compare
  floating-point results for exact equality.
- Use lists for sequential traversal or known-small collections, not random access, large sets,
  or heterogeneous records. Use arrays for random access and structures or classes for product
  types. Use multiple values only when callers will destructure a small result immediately.
- Distinguish false, empty, unknown, and nonexistent values. Do not overload `NIL` when the
  representation would become ambiguous.

### Conditions, APIs, and CLOS

- Use `ASSERT`, `CHECK-TYPE`, and `ETYPECASE` for internal bugs and invariants, not invalid user
  input. Prefer `CHECK-TYPE` at public API boundaries; type declarations alone may remove checks
  under optimization.
- Signal invalid input or unusual outcomes with `ERROR` and an explicit condition type. Document
  every condition in the function contract. Do not call `SIGNAL`; avoid `THROW`/`CATCH` in favor
  of conditions and restarts.
- Catch only expected conditions. Do not handle `T`, use `IGNORE-ERRORS`, or suppress arbitrary
  conditions. At a true isolation boundary, handle `ERROR`, not `T` or `SERIOUS-CONDITION`.
- Perform cleanup with `UNWIND-PROTECT`; do not resignal merely to clean up, and do not let cleanup
  code mask the original failure. Servers use their logging framework instead of `WARN` or
  standard output streams.
- Define an explicit, documented `DEFGENERIC` for module entry points and generic functions with
  multiple methods. List accepted keyword arguments. Use accessors instead of `SLOT-VALUE` or
  `WITH-SLOTS` unless intentionally bypassing method behavior.
- Use generic functions for a shared protocol, not unrelated overloads. Do not perform MOP
  intercession at runtime, override synthesized primary accessors, or use `&ALLOW-OTHER-KEYS` to
  hide misspelled keywords.

### Macros and performance

- Use an existing macro when it expresses intent, but never define a macro where a function has
  the required semantics. Keep new macros rare, document macro-defining macros, evaluate input
  forms once, and prefer a `WITH-...` wrapper over a semantic `CALL-WITH-...` function.
- Use all three situations in ordinary `EVAL-WHEN` forms:
  `:compile-toplevel`, `:load-toplevel`, and `:execute`. Avoid `#.` and read-time side effects.
  Do not use `EVAL`, `INTERN`, or `UNINTERN` at runtime.
- Do not add reader macros without project consensus; contain them with a readtable library so
  they cannot leak to clients.
- Use unsafe operations, low-safety declarations, or `DYNAMIC-EXTENT` only with profiling evidence
  and documentation proving the required invariant. Keep unsafe helpers internal and validate
  inputs before calling them.
- Avoid unnecessary consing, `NCONC`, and quadratic reductions. Prefer `APPEND`, appropriate
  sequences, and `REDUCE` only when its complexity is sound. Use `UIOP` abstractions for portable
  pathname handling.

## Verification and review output

Report:

- `Result`: `Ready`, `Needs changes`, or `Blocked`.
- `Required violations`: each violated requirement with location, impact, and concrete fix.
- `Recommended deviations`: each `SHOULD` exception, its local justification, and whether reviewer
  agreement is still needed.
- `Validation`: compiler and warning results, unit and precheckin tests, coverage checked, and
  anything not run.
- `Residual risk`: package-internal access, implementation portability, macro staging, condition
  handling, or unsafe optimization not fully exercised.
