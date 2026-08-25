# Google JavaScript Style for Existing Code

> The upstream Google JavaScript guide is no longer updated. Apply this recipe only when
> maintaining existing JavaScript. Prefer migrating new work to TypeScript and use the Google
> TypeScript conventions there. This recipe does not define AngularJS conventions.

## Scope and precedence

Use this guide for existing JavaScript files that are intentionally kept in JavaScript and are
expected to follow Google style. Do not apply its Closure-specific rules to unrelated module
systems, and do not use it for TypeScript. Repository requirements, current security rules,
supported runtimes, checked-in formatter and compiler configuration, and newer authoritative
standards take precedence over this frozen guide. Avoid broad reformatting that obscures a focused
maintenance change.

## Workflow

1. Confirm that the target is existing JavaScript and that migration to TypeScript is outside the
   current change. Identify its module system, runtime, Closure Compiler use, formatter, linter,
   conformance checks, and tests.
2. Inspect neighboring files for module naming, imports, exports, private-name convention, JSDoc
   types, and any documented legacy-platform constraints.
3. Preserve the existing module boundary and public contract. Define new names, nullability,
   fields, errors, and exports explicitly before implementation.
4. Use current standardized JavaScript supported by the project. Keep Closure-only syntax limited
   to code that is already built and checked with Closure tooling.
5. Format, compile or type-check, lint, run conformance checks, and execute focused tests. Review
   warnings and suppress only proven false positives at the narrowest scope.

## High-impact rules

### Files, modules, and dependencies

- Use lowercase `.js` filenames with only dashes or underscores as separators and encode files as
  UTF-8. Use spaces only; never indent with tabs.
- If an existing JavaScript system requires a new JS file, make it an ES module or
  `goog.module`; do not introduce deprecated `goog.provide` or `goog.scope` patterns.
- Order present sections as license, `@fileoverview`, module declaration or ES imports,
  `goog.require`/`goog.requireType`, then implementation, with exactly one blank line between
  sections except the implementation may have two.
- In ES modules, include `.js` in import paths, import a file only once, avoid named-import aliases
  unless resolving a real collision, use named exports, and do not create module cycles. Never use
  default exports in conforming code. Do not mutate an exported binding after initialization.
- In Closure modules, keep requires in one top-level block. Use `goog.requireType` only for types,
  `goog.require` for runtime use, and aliases rather than fully qualified names. Order single
  aliases, then destructuring aliases, then standalone side-effect requires; sort each named group
  by its left-hand names and do not wrap these statements.
- Export only symbols intended for consumers. Module-local symbols are already private and must
  not be annotated `@private`.

### Formatting

- Indent blocks by two spaces, put one statement on each line, require semicolons, and normally
  keep code within 80 columns. Module, import, export-from, require, unsplittable URL, command, and
  searchable literal lines are documented exceptions.
- Use braces for control structures and K&R placement. The only brace omission allowed is a
  simple, unwrapped, one-line `if` without `else` when it improves readability. A standalone empty
  block may be `{}`, but an empty block in `if`/`else` or `try`/`catch`/`finally` may not.
- Break at a high syntactic level, after an operator, and never between `return` and its value.
  Indent continuation lines at least four spaces. Prefer all call arguments on the same line; when
  wrapping, use a readable four-space form. Do not preserve horizontal alignment for its own sake.
- Include trailing commas in multiline array and object literals. Use single quotes for ordinary
  strings and template literals for interpolation or genuinely multiline content. Never use
  backslash line continuations.

### Language features and APIs

- Declare one local per statement. Use `const` by default and `let` only for reassignment; do not
  use `var` except in a genuinely legacy platform that cannot support modern syntax. Declare near
  first use and initialize promptly.
- Use array and object literals instead of variadic `Array` and `Object` constructors. Do not put
  nonnumeric properties on arrays or mix quoted/computed dictionary keys with unquoted struct
  keys in one object literal.
- Prefer ES classes. Define every instance field in the constructor, including later-initialized
  fields, and annotate non-public visibility and never-reassigned fields. Do not manipulate
  prototypes unless an existing framework requires it; never modify built-ins, create static-only
  container classes, or nest exported types under another type.
- Prefer module-local functions to private static methods when clear. Prefer arrow functions for
  nested callbacks and lexical `this`; use method shorthand for object methods. Use rest
  parameters instead of `arguments` and spread instead of `apply` when unpacking iterables.
- Prefer `for...of` for iterable values. Use `for...in` only for dictionary objects and guard
  inherited properties. Use `===` and `!==`, except `value == null` may deliberately test both
  null and undefined.
- Throw `new Error(...)` or an `Error` subclass and reject promises with errors, never strings or
  arbitrary objects. Explain a deliberately empty catch block. Require a last `default` group in
  every switch and comment intentional fall-through.
- Never use `with`, `eval`, string-built `Function`, automatic semicolon insertion, primitive
  wrapper objects constructed with `new`, nonstandard language extensions, or a constructor call
  without `()`.

### Names and JSDoc

- Use `UpperCamelCase` for classes, interfaces, records, typedefs, and enums; `lowerCamelCase` for
  methods, parameters, locals, fields, and packages; and `CONSTANT_CASE` only for deeply immutable
  constants and enum members. Private methods and fields may use a trailing underscore. Treat
  acronyms as words, such as `xmlHttpRequest` and `customerId`.
- Choose descriptive names without team-only abbreviations. Single-letter names are acceptable
  only in a scope of roughly ten lines or fewer and not in an exported API.
- Use well-formed JSDoc on classes, fields, and methods. Document function parameter and return
  types, including overrides; descriptions may be omitted only when obvious. Start method
  descriptions with a third-person verb phrase.
- Mark every reference type explicitly non-null (`!Type`) or nullable (`?Type`); primitives and
  literal types are non-null by default. Supply template parameters and explicit return types in
  function type expressions. Put casts in parentheses after `/** @type {...} */`.
- Document public enums and typedefs with descriptions and appropriate tags. Keep visibility tags
  off module-local names. Mark deprecations with a replacement or clear migration direction.

### Existing code and warnings

- Do not require wholesale cleanup of an otherwise focused change. If significant reformatting is
  necessary, separate it when practical; newly added code must not deepen an existing violation.
- Understand each compiler warning, then fix or avoid it. Suppress only a demonstrated false
  positive, with a convincing comment, at the narrowest reasonable scope. An unsuppressed TODO is
  the last resort.
- Generated source is generally exempt from formatting, but generated identifiers referenced by
  handwritten code must follow naming rules; underscores are allowed to prevent collisions.

## Verification and review output

Run the project-selected formatter, Closure Compiler or other configured type checker, linter,
conformance checks, and focused tests. Confirm module graph integrity and inspect warning
suppressions. State any runtime, compiler mode, or browser behavior not verified.

For a review, lead with `Ready` or `Needs changes`. Report material findings as `Location`,
`Area` (`Module`, `Formatting`, `Language`, `Naming`, `JSDoc`, `Warning`, or `Legacy`),
`Evidence`, `Impact`, and `Fix`. Distinguish frozen-guide advice from current project or security
requirements, and never recommend expanding JavaScript when TypeScript is the intended target.
