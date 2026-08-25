# Google Go Style

## Scope and precedence

Use this guide for Go implementation and review under Google's conventions. Apply its source
documents in this order: the core Go Style Guide is canonical and normative; Go Style Decisions
is normative but subordinate to the core; Go Style Best Practices is advisory. Repository rules,
the supported Go version, and checked-in tooling still apply. Do not convert an advisory option
into a blocking rule without project evidence or a concrete readability defect.

## Workflow

1. Read repository instructions and inspect `go.mod`, package boundaries, nearby APIs, build
   rules, formatter, static checks, and tests.
2. Identify the behavior and API contract, then optimize in order for clarity, simplicity,
   concision, maintainability, and finally consistency.
3. Prefer the least mechanism that works: core language construct, then standard library, then an
   established project library, before adding an abstraction or dependency.
4. Implement with explicit error, context, concurrency, ownership, and cleanup behavior. Keep
   exported documentation and tests with the change.
5. Run `gofmt`, applicable static analysis, focused tests, and the package's broader test target.
   Inspect test failure output, not only the pass/fail result.

## High-impact rules

### Formatting, names, and imports

- Format every source file, including generated source where practical, with `gofmt`. Do not add a
  fixed line-length rule. If a line is hard to read, refactor it; do not wrap a function signature,
  condition, loop, switch, or long string merely to meet a column target.
- Use `MixedCaps` or `mixedCaps`, not snake case, for identifiers. Constants follow the same rule,
  never `UPPER_SNAKE_CASE` or a `K` prefix. Keep initialisms consistently cased, such as `URL` and
  `ID`.
- Use concise lowercase package names without underscores. Avoid vague packages such as `util`,
  `common`, or `helper`. Avoid package/symbol repetition: prefer `widget.New` to
  `widget.NewWidget`.
- Give receivers a short, consistent abbreviation of their type; never `this`, `self`, or `_`.
  Size other names in proportion to scope and omit type or context words that the reader already
  knows. Do not prefix ordinary accessors with `Get`; use a verb such as `Fetch` when cost or
  failure is important.
- Group imports as standard library; other project and vendored packages; protocol buffers; then
  side-effect imports. Rename only for collisions or genuine clarity. Never use dot imports.
  Restrict blank imports to `main`, tests, and the documented compiler-directive exceptions.

### APIs, values, and state

- Keep packages cohesive rather than following one-type-per-file. Split conceptually distinct
  packages, but do not create packages that clients must always import together.
- Avoid interfaces until a real consumer need exists. Let the consumer define the smallest
  interface it needs, keep internal interfaces unexported, and normally accept interfaces while
  returning concrete types. Do not wrap generated RPC clients solely for testing.
- Pass small fixed-size values directly; do not use pointers merely to save bytes. Use pointer
  receivers for mutation, noncopyable fields, or large and evolving structs; otherwise choose by
  semantics and keep receiver choice consistent across a type. Never copy values containing a
  mutex or another noncopyable field.
- Prefer zero values for ready-to-use empty state and composite literals for known members. Prefer
  a nil slice for a local empty slice, but design APIs so callers need not distinguish nil from an
  empty slice. Supply field names for literals of structs from another package.
- Keep argument lists comprehensible. When configuration grows, consider a last-parameter options
  struct; use functional options only when their additional mechanism earns its cost. Never place
  a context in an options struct.
- Avoid package-level mutable state in libraries. Let clients construct isolated instances and
  pass dependencies explicitly. Flags belong in `main`, not an imported library.

### Errors, context, and concurrency

- Return `error` as the last result for operations that can fail. Do not encode failure as `-1`,
  an empty string, or another in-band value when a separate `error` or `ok` result is appropriate.
- Handle every error deliberately: resolve it, return it, or terminate only in an exceptional
  program-level case. If an error is safely ignored, explain why. Keep error strings lowercase and
  without terminal punctuation.
- Add useful, nonredundant context to errors. Give errors structure when callers need to inspect
  them; never parse error text for control flow. Use `%w` only when exposing the wrapped error is
  part of the contract, normally at the end of the message; translate errors at system boundaries
  when callers should not see implementation details.
- Handle terminal error paths first and leave the normal path unindented. Do not use `panic` for
  normal errors. Restrict `MustX` helpers to initialization with constant input or test setup.
- Pass `context.Context` as the first parameter. Do not store it in a struct or invent a custom
  context type. Propagate the caller's context and document only nonstandard cancellation or
  lifetime behavior.
- Prefer synchronous functions. For every spawned goroutine, make its exit, cancellation, and
  synchronization evident; do not let work silently outlive its owning operation. Specify channel
  direction where possible.

### Documentation and tests

- Give every exported top-level name a full-sentence doc comment beginning with that name. Keep
  exactly one package comment immediately above a package clause. Document non-obvious behavior,
  cleanup, significant errors, concurrency contracts, and API caveats; explain why rather than
  restating code.
- Use runnable examples for important package usage when practical and preview rendered package
  documentation during review.
- Use the standard `testing` package, not a third-party framework or assertion library. Keep
  correctness checks and failures visible in the test function; mark setup and cleanup helpers
  with `t.Helper()`.
- Make failures diagnosable without reading source: identify the function and input, print got
  before want, and label diff direction. Prefer `cmp.Diff` for complex values, compare stable
  semantics, and do not assert error strings when `errors.Is`, `errors.As`, or an error-presence
  check expresses the contract.
- Use table-driven tests when cases share the same logic, and subtests when they aid isolation or
  filtering. Keep cases independent and identify each input. Prefer `t.Error` so independent
  checks continue; use `t.Fatal` only when further work is meaningless, and never from another
  goroutine.

## Verification and review output

Run `gofmt` and verify no diff remains, then run the configured static analyzer and tests. Trigger
or inspect representative failures when diagnostics changed. State checks that were unavailable.

For a review, lead with `Ready` or `Needs changes`. Report each issue as `Location`, `Authority`
(`Core`, `Decision`, `Best practice`, or `Project`), `Evidence`, `Impact`, and `Fix`. Do not block
on advisory guidance alone. Summarize formatter, analyzer, and test results and any unverified
package, platform, race, or integration behavior.
