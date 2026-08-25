---
name: google-cpp-style
description: >-
  Use when writing or reviewing C++ under Google's C++ style conventions, including headers,
  naming, classes, functions, ownership, exceptions, and formatting. Do not use as a general C++
  language tutorial.
---

# Google C++ Style

## Scope and precedence

Use this guide when writing or reviewing C++ that is expected to follow Google style. The pinned
guide targets C++20; do not introduce C++23 features under that baseline. Project requirements,
checked-in formatter and linter configuration, platform constraints, and newer authoritative rules
take precedence. Preserve local consistency when touching nonconforming code, but do not use an
old local pattern to spread a dangerous construct or block an established migration.

## Workflow

1. Read repository instructions and identify the supported C++ version, build targets, formatter,
   linter, and test commands.
2. Inspect the surrounding headers, source files, names, ownership model, error model, and local
   conventions before designing the change.
3. Define the API contract first: inputs, outputs, ownership, lifetimes, nullability, copy and move
   behavior, failure behavior, and thread-safety.
4. Implement with the simplest standard mechanism that keeps those properties visible at call
   sites. Keep declarations, definitions, dependencies, and comments synchronized.
5. Format the touched code, run `cpplint.py` or the project equivalent, compile affected targets,
   and run focused tests.
6. Review the final diff for API clarity, unsafe language features, hidden dependencies, lifetime
   errors, and unrelated formatting churn.

## High-impact rules

### Headers and dependencies

- Give each ordinary `.cc` file an associated `.h` file, except small `main` files and tests where
  a header adds no value. Use `.inc` only for rare, intentionally non-self-contained inclusions.
- Make every header self-contained. Add a path-derived `<PROJECT>_<PATH>_<FILE>_H_` include guard
  and directly include every declaration the file uses. Do not rely on transitive includes.
- Prefer includes to forward declarations. Never forward-declare entities owned by another
  project or anything in `std`.
- Order includes as: related header; C and other `.h` system headers; C++ standard headers; other
  libraries; project headers. Separate nonempty groups and alphabetize within each group.
- Put a function body at its public declaration only when it is short. Keep templates and other
  required header definitions out of the public portion when practical, and make header
  definitions ODR-safe.

### Scope, storage, and ownership

- Put code in a globally recognizable project namespace. Do not use `using namespace`, inline
  namespaces, or declarations in `std`. Give `.cc`-only definitions internal linkage; never put
  unnamed namespaces or file-local `static` definitions in headers.
- Declare variables in the narrowest useful scope and initialize them at declaration.
- Allow static-storage objects only when they are trivially destructible. Prefer constant
  initialization marked `constexpr` or `constinit`; scrutinize nonlocal dynamic initialization.
  Non-function `thread_local` variables require true compile-time initialization enforced by
  `constinit`, and their destruction must not depend on other thread-local objects.
- Prefer values and a single fixed owner. Use `std::unique_ptr` to express ownership transfer.
  Use shared ownership only for a strong reason, normally with immutable shared data. A raw
  pointer or reference normally represents non-ownership, with lifetime and nullability clear.

### APIs and types

- Keep constructors simple. Never call virtual methods from constructors; use a factory when
  initialization can fail and the constructor cannot report the failure.
- Mark conversion operators and constructors callable with one argument `explicit`, except copy
  and move constructors and the documented initializer-list case.
- Make copyability and movability obvious in the public API by declaring, defaulting, or deleting
  the relevant operations. Do not support an operation whose meaning or cost would surprise a
  caller.
- Use `struct` only for passive public data without cross-field invariants; otherwise use `class`
  and keep data members private. Prefer a named struct to a pair or tuple when fields have useful
  names. Prefer composition to implementation inheritance and mark an override with exactly one
  of `override` or `final`.
- Prefer return values to output parameters. Use values or `const` references for non-optional
  inputs, references for non-optional outputs, and pointers when optionality is part of the
  contract. Put input-only parameters before outputs and avoid retained references when possible.
- Keep functions focused. Use overloads only when all variants have the same meaning at the call
  site. Do not put default arguments on virtual functions or use defaults whose value varies.

### Language features and safety

- Do not use C++ exceptions. Avoid RTTI outside tests; prefer virtual dispatch or a better class
  design. Do not build a hand-rolled RTTI substitute.
- Use C++ casts or brace initialization, never C-style casts except a cast to `void`. Use
  `nullptr` for pointers and `'\0'` for the null character.
- Use `const` accurately in APIs and `constexpr` for true constants, not to force inlining. Use
  `int` for ordinary integers and exact-width types when size matters; avoid unsigned types merely
  to express non-negativity and avoid `long double`.
- Avoid macros, especially exported macros and macros that form an API. If unavoidable, give them
  a globally unique project prefix, define them near use, and `#undef` them afterward.
- Use type deduction only when it improves clarity or safety. Do not hide an important interface
  type, use `decltype(auto)` when a simpler form works, or use deduced return types for broad APIs.
- Avoid complicated template metaprogramming. Use concepts sparingly, prefer standard concepts and
  `requires(Concept<T>)`, and do not expose new concepts at public API boundaries.
- Do not use C++20 modules. Use coroutines only through a project-approved library. Do not use
  nonstandard extensions, user-defined literals, `<ratio>`, `<cfenv>`/`<fenv.h>`, or
  `<filesystem>` under this guide.

### Names, comments, and layout

- Use lowercase filenames, normally with underscores; `PascalCase` for types, concepts, and
  ordinary functions; `snake_case` for variables, parameters, namespaces, and accessors;
  `snake_case_` for class data members; `kPascalCase` for fixed-duration constants and enum
  values; and `PROJECT_UPPER_SNAKE_CASE` for unavoidable macros.
- Choose names for a reader outside the team. Keep abbreviations recognizable and size local names
  in proportion to their scope.
- Document non-obvious APIs at declarations: behavior, ownership, lifetime, nullability, outputs,
  and performance constraints. At definitions, explain tricky reasoning rather than restating the
  code. Document class invariants and thread-safety, and give every global a purpose comment.
- Use UTF-8, two-space indentation, spaces only, and normally an 80-column limit. Use braces for
  controlled statements; the guide permits only its brief one- or two-line historical exception,
  which a project may forbid. Keep opening braces on the preceding line, do not indent namespace
  contents, avoid trailing whitespace, and use vertical space sparingly.

## Verification and review output

Run the project formatter or verify the touched layout manually, run the configured linter,
compile every affected target, and run focused tests. If any check is unavailable, say so.

For a review, lead with `Ready` or `Needs changes`. For each material issue report `Location`,
`Rule`, `Evidence`, `Impact`, and `Fix`. Separate correctness, lifetime, ownership, portability,
and API-contract findings from mechanical formatting. State the commands run, their results, and
any platform, target, or test coverage not verified.
