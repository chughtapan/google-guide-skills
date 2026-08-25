# Google Java Style

## Scope and precedence

Use this guide when Java source must conform to Google Java Style. Within its scope, the source
defines hard formatting and naming rules; its examples are non-normative and must not be treated
as the only allowed layout. Repository requirements, supported Java version, generated-code
policy, and checked-in formatter or linter configuration take precedence when explicitly stated.
Do not use this style guide as a substitute for API or architecture review.

## Workflow

1. Read repository instructions and identify the Java version, build system, formatter, static
   checks, annotation processors, and test targets.
2. Inspect the containing package and class for its logical member order, naming, Javadoc depth,
   and local use of current Java constructs.
3. Make the behavioral change first, keeping each file to one top-level class and every overload
   group contiguous.
4. Apply source order, import order, names, Javadoc, and formatting. Let the formatter resolve
   ambiguous wrapping; do not infer extra rules from examples.
5. Format, compile affected targets, run static checks and focused tests, then inspect the final
   diff for accidental reordering or unrelated churn.

## High-impact rules

### Files, packages, imports, and members

- Name a source file after its case-sensitive top-level class and use `.java`. Encode it as UTF-8,
  use ASCII space as source whitespace, and never indent with tabs.
- Order an ordinary file as license information, package declaration, imports, then exactly one
  top-level class, with exactly one blank line between present sections. Every source file has a
  package declaration; do not use compact source files.
- Do not wrap package or import declarations. Do not use wildcard imports or module imports.
  Group all static imports first and non-static imports second, separated by one blank line; sort
  imported names in ASCII order within each group. Import static nested classes normally.
- Choose a logical, explainable member order. Never append members merely by chronology. Keep
  methods with the same name contiguous and keep constructors contiguous.
- In `module-info.java`, group directives as `requires`, `exports`, `opens`, `uses`, then
  `provides`, with one blank line between present groups.

### Formatting and constructs

- Indent blocks by two spaces, put one statement on each line, and keep ordinary code within 100
  columns. The documented exceptions include package and import declarations, text-block content,
  unsplittable material, copyable command lines, and rare long identifiers.
- Use braces for `if`, `else`, `for`, `do`, and `while`, including single-statement and empty
  bodies. Use K&R braces. A standalone empty block may be `{}`, but an empty part of a multi-block
  statement may not be concise.
- Break lines at a high syntactic level. Break before non-assignment operators, normally after an
  assignment operator, keep a method name with `(` and a comma with the preceding token, and
  indent continuation lines at least four spaces. Horizontal alignment is never required.
- Declare one variable per declaration, except in a `for` header. Declare locals near first use and
  normally initialize them immediately. Attach array brackets to the type, as in `String[] args`.
- Make every switch exhaustive. In old-style switches, terminate each statement group or mark
  possible fall-through with a comment. Use new-style syntax for switch expressions.
- Put class, package, module, method, and constructor annotations one per line after Javadoc, except
  that a single parameterless method or constructor annotation may share the signature line.
  Place type-use annotations immediately before the annotated type.
- Order modifiers as `public protected private abstract default static final sealed non-sealed
  transient volatile synchronized native strictfp`. Write long integer suffixes with uppercase
  `L`.

### Naming

- Use ASCII letters and digits in identifiers, with underscores only in the documented cases. Do
  not add member prefixes or suffixes such as `mName`, `name_`, or `kName`.
- Use lowercase concatenated package and module names; `UpperCamelCase` class names;
  `lowerCamelCase` method, field, parameter, and local names; and `UPPER_SNAKE_CASE` only for
  deeply immutable `static final` constants.
- Name test classes with a `Test` suffix. JUnit test methods may use underscores to separate
  lower-camel components.
- Name a type variable with one capital letter optionally followed by one digit, or an
  `UpperCamelCaseT` name. Treat acronyms as ordinary words: use `XmlHttpRequest` and
  `newCustomerId`, not all-cap acronym segments.

### Programming practices and Javadoc

- Add `@Override` whenever legal, including interface implementations and record accessors; it may
  be omitted only when the parent method is deprecated.
- Do not silently ignore a caught exception. Handle it, propagate it, or explain in the catch block
  why doing nothing is correct.
- Qualify a static member with its declaring class, not an instance expression. Never override
  `Object.finalize`.
- Provide Javadoc for every visible class, member, and record component unless it is genuinely
  self-explanatory or an override needs no additional contract. Use Javadoc, not an implementation
  comment, to define a class or member's overall purpose.
- Start Javadoc with a short capitalized and punctuated summary fragment. Separate later paragraphs
  with a blank `*` line and `<p>`, and order nonempty block tags as `@param`, `@return`, `@throws`,
  then `@deprecated`.
- Format temporary work as `TODO: tracked-context - explanation`; prefer a bug or durable resource
  over a person's name.

## Verification and review output

Run the configured formatter, compile affected targets, run static analysis, and execute focused
tests. Check that imports, overload groups, annotations, and Javadoc remained attached to the
correct declarations. State checks that were unavailable.

For a review, lead with `Ready` or `Needs changes`. Report each material issue as `Location`,
`Rule`, `Evidence`, `Impact`, and `Fix`. Separate formatter-enforceable violations from naming,
documentation, or programming-practice findings, and list commands run, results, and unverified
targets.
