---
name: google-typescript-style
description: >-
  Use when writing or reviewing TypeScript under Google's source, type-system, naming, module,
  documentation, and conformance conventions. Do not use for plain JavaScript; use
  google-javascript-style instead.
---

# Google TypeScript Style Guide

## Scope and precedence

Apply this guide to TypeScript, not plain JavaScript. Repository rules, the configured compiler,
formatter, linter, and applicable conformance frameworks remain authoritative. New files must use
Google style. In existing files, preserve local choices only where this guide is silent; avoid
mixing opportunistic reformatting into an unrelated change. Generated code is mostly exempt, but
generated identifiers referenced by hand-written code follow the naming rules.

## Workflow

1. Read repository instructions, compiler options, conformance rules, formatter configuration,
   module boundaries, and surrounding code.
2. Identify exported API, runtime imports and side effects, nullability, mutable state, structural
   contracts, thrown errors, and target JavaScript environments.
3. Design the smallest typed surface. Prefer named module exports, interfaces for object shapes,
   explicit narrowing, and ordinary functions over namespace or class-based containers.
4. Implement using compiler-supported standard features. Add JSDoc where users need contract
   information and implementation comments only for non-obvious reasoning.
5. Run the standard formatter, compiler/type checker, linter, conformance checks, and relevant
   tests.
6. Review the diff for unsafe assertions, `any`, mutable exports, import correctness, exception
   behavior, API visibility, and suppressions before reporting completion.

## High-impact rules

### Files and modules

- Encode source as UTF-8 and use ordinary spaces as whitespace. Order present sections as
  copyright JSDoc, `@fileoverview`, imports, then implementation, with exactly one blank line
  between sections.
- Import TypeScript with ES module syntax. Prefer named imports for clear or frequently used
  symbols and namespace imports for large APIs whose members need context. Use default imports
  only for external code that requires them and side-effect imports only for deliberate load-time
  behavior.
- Prefer relative paths within the same logical project and limit deep parent traversal. Use
  `import type` and `export type` when a symbol is type-only and file-by-file transpilation needs
  the distinction.
- Use named exports, never default exports. Minimize exported surface and do not use mutable
  exports such as `export let`; expose controlled getters when external access to changing state
  is required.
- Use files and named exports for namespacing. Do not use TypeScript `namespace`, triple-slash
  references, or `import x = require(...)` except a namespace required to interoperate with
  third-party code.
- Do not create static container classes merely to group constants and functions; export the
  individual symbols from the module.

### Variables, functions, and classes

- Declare one variable per statement. Use `const` by default and `let` only for reassignment;
  never use `var` or a variable before declaration.
- Use array and object literals rather than `Array()` or `Object()`. Spread only values matching
  the created container: iterables into arrays and plain objects into objects. Keep destructured
  parameters shallow and put defaults on the left-hand side.
- Prefer function declarations for named functions. Use arrows for callbacks and closures,
  especially when capturing outer `this`; do not use function expressions except when dynamic
  `this` rebinding or a generator requires one.
- Forward callback parameters explicitly when a higher-order API may pass extra arguments. Use a
  block-bodied arrow when the return value is unused so a value cannot leak accidentally.
- Use `this` only in class constructors and methods, explicitly typed functions, or arrows inside
  a valid `this` scope. Do not bind `this` implicitly at an event installation site; retain a
  stable handler reference when it must later be removed.
- Mark never-reassigned members `readonly`. Prefer constructor parameter properties for obvious
  assignments and field initializers for non-parameter state. Initialize optional later-filled
  fields to `undefined` to preserve object shape.
- Use TypeScript `private`, not `#private` fields or bracket access that bypasses visibility.
  Minimize visibility, omit redundant `public`, and do not mark framework template properties
  private when they are accessed outside class lexical scope.
- Accessor getters must be pure and at least one accessor must do meaningful work. Prefer a public
  field over pass-through accessors. Avoid private static methods when a module-local function is
  equally readable, and never use static `this` or inherited static dispatch.

### Control flow and errors

- Use braced blocks for control flow; only a complete one-line `if` may omit braces. Prefer
  assignment before a condition; use extra parentheses when assignment in a condition is truly
  intentional.
- Iterate arrays with `for...of` unless an index is required. Never use `for...in` for arrays;
  prefer `Object.keys`, `Object.values`, or `Object.entries` for objects, or filter inherited
  properties explicitly.
- Use `===` and `!==`; comparison with literal `null` may use `==` or `!=` when intentionally
  covering both `null` and `undefined`.
- Every `switch` has a final `default`. Non-empty cases terminate with `break`, `return`, or
  `throw`; only empty case groups may fall through.
- Instantiate and throw `Error` or a subclass, including for Promise rejection. Catch as
  `unknown`, narrow to `Error`, and handle non-`Error` values only for a documented violating API.
  Explain a deliberately empty catch block and keep `try` blocks focused when readability allows.
- Compare enum values explicitly rather than coercing them to booleans. Use `Number()` for numeric
  parsing and validate `NaN` or non-finite cases; do not use unary `+`, `parseFloat`, or decimal
  `parseInt` as shortcuts.

### Types

- Rely on inference for obvious literal and constructor types. Add annotations when they clarify
  a complex expression, stabilize an API, or surface errors earlier.
- Use interfaces for object shapes and type aliases for unions, tuples, primitives, and other
  expressions. Put the interface type on structural implementations so errors appear at the
  declaration rather than a distant call site.
- Add `|null` or `|undefined` at each use site, not inside a reusable alias. Prefer optional fields
  and parameters to `|undefined` when omission is valid, and handle absence near its source.
- Use `T[]` or `readonly T[]` for simple element types and `Array<T>` or `ReadonlyArray<T>` for
  complex element types. Prefer `Map` and `Set` to object dictionaries when their semantics fit.
- Avoid `any`; use a specific interface, generic, or `unknown` plus narrowing. If `any` is truly
  necessary, suppress the lint rule narrowly and explain why. Avoid `{}`; choose `unknown`,
  `object`, or `Record<string, T>` according to the contract.
- Prefer simple explicit types over mapped and conditional types when a little repetition is
  easier to understand and refactor. Avoid APIs with generics used only in the return type.
- Avoid type and non-null assertions. Prefer runtime checks; when an assertion is locally safe,
  make the reason obvious or document it. Use `as`, never angle-bracket assertion syntax, and use
  a type annotation rather than asserting an object literal.
- Use primitive types `string`, `boolean`, and `number`, never wrapper types. Do not instantiate
  wrapper objects.

### Names, documentation, and forbidden features

- Use `UpperCamelCase` for classes, interfaces, types, enums, decorators, and type parameters;
  `lowerCamelCase` for variables, parameters, functions, methods, properties, and module aliases;
  and `CONSTANT_CASE` only for module-level constants, module-level enum values, and static
  readonly constants.
- Use descriptive ASCII names. Treat acronyms as words, such as `loadHttpUrl` and `customerId`.
  Do not encode type information in names, prefix interfaces with `I`, or use leading/trailing
  underscores. Short names are allowed only in a non-exported scope of roughly ten lines or less.
- Document every top-level export with JSDoc unless it exists only for tooling. Document public or
  non-obvious members without restating types. Use JSDoc for user contracts and `//` comments for
  implementation details; multi-line implementation comments use consecutive `//` lines.
- Do not repeat TypeScript types or modifiers in JSDoc. Put documentation before decorators and
  place each JSDoc block tag on its own line.
- Do not define new decorators; use only framework decorators. Do not use `eval`, the
  `Function(string)` constructor, `const enum`, debugger statements, `with`, prototype mutation,
  or nonstandard platform/language features.
- Do not use `@ts-ignore`, `@ts-nocheck`, or related blanket suppression. `@ts-expect-error` is
  permitted in tests only rarely; prefer a narrow cast with an explanation.

## Verification and review output

Lead with `Ready`, `Needs changes`, or `Blocked`, then report:

- `Required findings`: location, violated rule or conformance requirement, impact, and fix.
- `API and type safety`: exports, nullability, inference, assertions, `any`, and error contracts.
- `Tool results`: formatter, compiler, linter, conformance checks, and tests, with exact outcomes.
- `Not run`: unavailable checks and why.
- `Residual risk`: runtime import effects, target compatibility, unsafe narrowing, suppression, or
  exception path not exercised.
