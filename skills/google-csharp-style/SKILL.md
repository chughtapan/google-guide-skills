---
name: google-csharp-style
description: >-
  Use when writing or reviewing C# under Google's conventions for naming, formatting, language
  features, and source organization. Do not use for unrelated .NET architecture or framework
  selection.
---

# C# at Google Style

## Scope and precedence

Use this guide for C# code expected to follow Google's internal C# conventions. It covers source
organization, naming, formatting, and selected readability choices; it is not a general .NET API
or architecture guide. Repository rules, checked-in analyzer and formatter settings, target
framework constraints, and newer authoritative language guidance take precedence over this older
source. Follow the surrounding project where this guide deliberately leaves a choice.

## Workflow

1. Read repository instructions and inspect the project file, nullable settings, language version,
   analyzer configuration, formatter, build, and test commands.
2. Examine nearby files for namespace depth, file layout, member order, collection contracts,
   naming, and established error-handling patterns.
3. Choose explicit API contracts for mutability, ownership, nullability, return values, and
   configuration before implementing.
4. Write the smallest readable implementation, using named types and arguments where literals,
   tuples, or long call signatures would obscure meaning.
5. Format, build, run analyzers, and execute focused tests. Review the diff separately for style
   and behavioral correctness.

## High-impact rules

### Names, files, and organization

- Use `PascalCase` for classes, methods, enums and enum members, public fields and properties, and
  namespaces. Use `camelCase` for locals and parameters, and `_camelCase` for non-public fields
  and properties. Treat an acronym as one word, as in `MyRpc`. Prefix interface names with `I`.
- Use `PascalCase` file and directory names. Match a file to its main class where possible and
  normally keep one core class per file.
- Put `using` declarations before namespaces. Put `System` imports first, then sort imports
  alphabetically. Avoid aliases that merely hide a long or complicated type.
- Order modifiers as `public protected internal private new abstract virtual override sealed
  static readonly extern unsafe volatile async`.
- Group members as nested types, delegates, and events; static, const, and readonly fields; fields
  and properties; constructors and finalizers; then methods. Within a group use public, internal,
  protected internal, protected, then private visibility, and keep interface implementations
  together when practical.

### Formatting

- Indent with two spaces and no tabs. Keep lines within 100 columns unless project tooling makes a
  narrower or more specific decision.
- Put at most one statement on a line and one assignment in a statement. Use braces even when
  optional. Keep the opening brace on the declaration or control line and write `} else {` without
  an intervening line break.
- Put a space after control keywords and commas, around binary operators, and before opening
  braces. Do not pad parentheses or separate a unary operator from its operand. Remove trailing
  whitespace.
- Indent ordinary continuation lines four spaces. For long calls and declarations, align wrapped
  arguments with the first argument when readable; otherwise place them on following lines with a
  four-space continuation indent.
- Put each attribute on its own line immediately above the target member.

### Types, collections, and values

- Make values `const` when possible; otherwise consider `readonly`. Replace magic numbers with
  named constants.
- Almost always use a class. Use a struct only for a small, value-like type that is commonly
  short-lived or embedded, and account for copy semantics explicitly.
- For inputs, accept the most restrictive suitable collection interface, such as
  `IEnumerable<T>`, `IReadOnlyCollection<T>`, or `IReadOnlyList<T>`. For outputs, use `IList<T>`
  when transferring ownership of a mutable container; otherwise expose the most restrictive
  useful contract.
- Prefer `List<T>` for mutable, public, or variable-sized collections. Prefer arrays for a fixed
  size known at construction and for multidimensional data.
- Prefer a named class to `Tuple<...>` for a complex return. Prefer a flat directory structure and
  do not force folders to mirror namespaces. Keep namespaces generally no more than two levels
  deep and make a new top-level namespace globally recognizable.

### Functions and readability

- Use generators when lazy processing materially helps. Do not generate a sequence only to call
  `ToList()`, and remember that repeated enumeration reruns generator work.
- Use expression bodies judiciously for short read-only properties and lambdas. Under the pinned
  guide, use block bodies for method definitions unless a newer project rule explicitly permits
  otherwise.
- Turn a nontrivial or reused lambda into a named method. Prefer short member-style LINQ calls or
  straightforward imperative code over long query chains; do not use `ForEach` for multi-statement
  work.
- Use extension methods only when the original type cannot feasibly be changed and the operation
  is a core, general feature available consistently to clients. Err against introducing them.
- Use `out` for an output that is not also an input and place it after ordinary parameters. Use
  `ref` rarely for necessary input mutation, never merely to optimize struct passing or to mutate
  an existing container.
- Use `var` only when the type is obvious, noisy, or unimportant. Spell out basic and numeric types
  and any type a reader needs to understand the code.
- Use object initializers for plain data objects, not to bypass the semantics of classes or
  structs with constructors. Invoke delegates as `SomeDelegate?.Invoke()`.
- Clarify opaque call arguments with named constants, enums instead of booleans, named arguments,
  local variables, or an options object.

## Verification and review output

Run the repository formatter, analyzer, build, and focused test commands. Confirm that public
collection types, nullability, and value/reference semantics match the intended contract.

For a review, lead with `Ready` or `Needs changes`. Report each material issue as `Location`,
`Rule`, `Evidence`, `Impact`, and `Fix`. Distinguish analyzer or build failures from readability
advice, and list commands run, results, and anything not verified.
