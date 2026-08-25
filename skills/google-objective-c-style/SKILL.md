---
name: google-objective-c-style
description: >-
  Use when writing or reviewing Objective-C and Objective-C++ under Google's naming, formatting,
  Cocoa-pattern, memory-management, and documentation conventions. Do not use as a Swift style
  guide.
---

# Google Objective-C Style Guide

## Scope and precedence

Apply this guide to Objective-C and Objective-C++. Read and follow the applicable Apple Cocoa
coding conventions as well. Project rules and consistent surrounding style decide choices the
guide leaves open. In an Objective-C++ file, use Objective-C conventions inside Objective-C
methods and C++ conventions inside C++ class methods; keep file-scope code internally consistent.
Do not apply these rules to Swift.

## Workflow

1. Read repository instructions and surrounding code. Identify the project's prefix, ivar
   convention, ARC status, deployment targets, formatter, and public API boundaries.
2. Inspect class responsibilities, designated initializers, ownership transfers, mutability,
   nullability, threading assumptions, and Objective-C/C++ boundaries before changing code.
3. Keep the public surface small. Declare properties, class methods, initializers, then instance
   methods, and put overridden `NSObject` methods near the top of the implementation.
4. Implement ownership and initialization explicitly, add lightweight generics and nullability,
   and document every non-trivial interface contract.
5. Format imports, declarations, invocations, control flow, and comments consistently with this
   guide and the file.
6. Run project format, compile, static-analysis, and test checks; report checks that were not
   available or not run.

## High-impact rules

### Names and API design

- Use descriptive, inclusive names and avoid unfamiliar abbreviations. Capitalize acronyms and
  initialisms as Apple does, including `URL` and `ID`.
- Name classes, protocols, and categories in mixed `UpperCamelCase`. Shared code should use a
  unique prefix of at least three characters; Apple reserves two-letter prefixes.
- Name category files `Class+Category.h`. Prefix shared category names and methods to avoid the
  global namespace; a category on a project-private class may omit those prefixes.
- Start Objective-C methods and parameters with lowercase mixed case. Make selectors read like
  sentences, use conjunctions only where they clarify meaning, and name attribute getters after
  the attribute. Do not prefix getters with `get`.
- Boolean getter methods begin with `is`, while their property names omit `is`. Use dot notation
  for properties only, not arbitrary no-argument methods.
- Use `UpperCamelCase` for C functions and typedefs, with a project prefix for external linkage.
  Use lower mixed case for locals, leading underscores for ivars, and `g` for rare file-scope or
  global variables.
- Use mixed-case constant names with an appropriate prefix for external linkage. Static
  implementation constants may use a standalone lowercase `k` prefix. Enum values extend the
  typedef name for Swift interoperability.
- Keep public APIs focused. Give private methods names unlikely to collide accidentally with a
  superclass's private implementation.

### Files, declarations, and formatting

- Match filenames to the implemented class. Use `.h` for headers, `.m` for Objective-C, `.mm`
  for Objective-C++, `.cc` for pure C++, and `.c` for C.
- Use `#import` for Objective-C headers and `#include` for C/C++ headers. Import the related
  header first, then system, language-library, and other dependency groups; separate groups with
  one blank line and alphabetize within each group. Use system-framework umbrella headers.
- Declare variables near first use, in the narrowest practical scope, and initialize them in the
  declaration. Keep implementation-only file-scope state `static`; never place static-storage
  definitions in headers.
- Avoid unsigned integers except when matching system interfaces or representing flags. Use
  fixed-width integer types where exact size matters and `int64_t` for potentially large file or
  buffer sizes. Keep `CGFloat` literal precision consistent within a project.
- Use two-space indentation, spaces rather than tabs, and a 100-column limit. Put each parameter
  of a wrapped method declaration or invocation on its own line and align colons when practical;
  otherwise indent continuation lines at least four spaces.
- Put braces around both sides of an `if`/`else`. A single-line body without `else` may omit
  braces only when it remains on one line; never put an unbraced body on the following line.
  Mark intentional `switch` fallthrough.
- Prefer small, focused functions. Reconsider functions or methods beyond roughly 40 lines and
  use vertical whitespace sparingly.

### Initialization, ownership, and Cocoa behavior

- Identify designated initializers with `NS_DESIGNATED_INITIALIZER` when available and prefer one
  designated initializer. Override inherited designated initializers so every supported path
  reaches valid subclass initialization; mark unsupported initializers unavailable where useful.
- Do not use or override `+new`; instantiate with `+alloc` and an initializer. Do not redundantly
  assign zero or `nil` to newly allocated ivars.
- Avoid messaging `self` in initializers and `-dealloc`, including property accessors, because a
  subclass may observe partially initialized or destroyed state. Assign ivars directly when
  practical; use established framework exceptions deliberately.
- Declare ivars in implementations or synthesize them from properties. If a header must expose
  ivars, mark them `@protected` or `@private`.
- Copy retained values whose declared type has a mutable variant, especially strings,
  collections, and protos. Use `copy` properties and reproduce copy semantics in custom setters
  and direct ivar assignments. Copy potentially mutable data before asynchronous dispatch.
- Return a copy when exposing internal mutable state. Do not add a redundant copy when clearly
  transferring ownership of a newly built mutable value through an immutable return type.
- Avoid delegate, target, and callback retain cycles. Release delegates or targets when no longer
  needed, otherwise hold them weakly. Use block callbacks only when they can be released after
  use.
- Use lightweight generics for every `NSArray`, `NSDictionary`, and `NSSet` reference when the
  toolchain supports them. Annotate interface nullability, but never treat `nonnull` as a runtime
  check.

### Errors, booleans, and language features

- Do not throw Objective-C exceptions. Catch exceptions only when required by an OS or third-party
  API, and document exactly which calls may throw. Use error objects for ordinary failures.
- Do not add a check merely to avoid messaging `nil`; Objective-C defines that behavior. Still
  validate `nil` arguments according to each API contract and check C/C++ and block pointers
  before dereferencing or calling them.
- Convert general integral values to `BOOL` with a comparison or conditional that produces
  `YES`/`NO`. Do not compare a `BOOL` directly with `YES`, compare arbitrary true `BOOL` values
  with equality, or box general integral expressions as booleans. Use `@YES` and `@NO` literals.
- Avoid macros when a constant, enum, function, or language construct works. Required macros use
  a unique name, balanced syntax, limited scope where practical, and `SHOUTY_SNAKE_CASE` unless
  intentionally styled like a C function.
- Do not use nonstandard language extensions except those the guide explicitly permits. Limit
  `__auto_type` to local block or function-pointer values, and prefer an existing typedef.

### Documentation

- Document every non-trivial public or private interface, including classes, categories,
  protocols, properties, functions, enums, and non-obvious ivars.
- Method comments describe behavior, parameters, return value, side effects, thread or queue
  assumptions, and sentinel values. Put public API documentation in headers and non-trivial
  private documentation immediately before the declaration or method.
- Use descriptive present-tense comments such as “Opens the file.” Put implementation rationale
  next to the implementation, and comment tricky, subtle, or reentrancy-sensitive code.
- Use `// NOLINT` or `// NOLINTNEXTLINE` only for an intentional style exception on the affected
  line.

## Verification and review output

Lead with `Ready`, `Needs changes`, or `Blocked`, then report:

- `Required findings`: location, violated rule, runtime or maintenance impact, and smallest fix.
- `API and ownership`: designated initialization, copy semantics, retain-cycle, nullability, and
  visibility findings.
- `Formatting and documentation`: only material issues not handled automatically.
- `Validation`: formatter, compiler, analyzer, and tests run, with exact results and omissions.
- `Residual risk`: platform-width, Objective-C++ boundary, third-party exception, threading, or
  lifecycle behavior not exercised.
