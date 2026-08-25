---
name: google-python-style
description: >-
  Use when writing or reviewing Python under Google's conventions for language rules, imports,
  exceptions, typing, naming, comments, tests, and formatting. Do not use as a Python beginner
  tutorial.
---

# Google Python Style Guide

## Scope and precedence

Apply this guide when writing or reviewing Python. Repository instructions, `pyproject.toml`,
configured formatters and linters, and newer project requirements take precedence. Use
surrounding conventions only for choices the guide leaves open; do not preserve an obsolete
local pattern merely for consistency. This is a style and maintainability guide, not a Python
tutorial.

## Workflow

1. Read repository instructions and inspect `pyproject.toml`, lint and type-check configuration,
   supported Python versions, nearby code, and test conventions.
2. Identify public APIs, import boundaries, mutable state, resource lifetimes, error contracts,
   and code that runs at import time.
3. Implement the simplest readable control flow. Add type annotations to new or changed public
   APIs and to code where types are difficult to infer or have caused bugs.
4. Add contract docstrings and comments for non-obvious reasoning. Keep module import safe and
   executable behavior behind `main()`.
5. Run the configured formatter, `pylint`, type checker, and relevant tests. Use narrow,
   explained suppressions only when the tool is wrong or an exception is necessary.
6. Review the complete diff for naming, import order, exception breadth, mutable defaults,
   cleanup, and documentation accuracy before reporting completion.

## High-impact rules

### Imports and module structure

- Import packages and modules, not individual classes or functions. Specific imports from
  `typing`, `collections.abc`, and `typing_extensions` are allowed for static analysis.
- Use absolute package names. Prefer `import x`, `from package import module`, and aliases only
  for collisions, standard abbreviations, overly generic names, or genuinely unwieldy modules.
  Do not use relative imports.
- Put imports after the module docstring and before globals. Group future imports, standard
  library, third-party packages, then repository packages; sort each group lexicographically by
  full package path. Put imports on separate lines except allowed typing imports.
- Keep module top level free of work that should not run during import. Executables put behavior
  in `main()` and guard it with `if __name__ == '__main__':`; use `app.run(main)` when using
  Abseil.
- Avoid mutable global state. If it is unavoidable, keep it internal, expose controlled access,
  and document the design reason. Module constants use `CAPS_WITH_UNDERSCORES`.

### Language and control flow

- Use built-in exception classes where appropriate; custom exception names end in `Error` and
  inherit from an existing exception type.
- Never use a bare `except` or catch `Exception` unless re-raising or implementing a documented
  outer isolation boundary. Keep `try` bodies narrow, use `finally` for mandatory cleanup, and do
  not use `assert` for validation or application logic. `assert` is appropriate for test
  expectations and internal facts whose removal would not change behavior.
- Do not use mutable or dynamically evaluated default arguments. Use an immutable value or
  `None`, then create state inside the function; never read an Abseil flag value in a default.
- Prefer implicit truth testing for sequences and mappings. Compare explicitly with `None`, do
  not compare booleans with `False`, and use explicit numeric comparisons where falsiness could
  confuse zero with absence. Check NumPy array emptiness with `.size`.
- Keep comprehensions simple: at most one `for` clause and one filter expression. Use ordinary
  loops for nested or complicated transformations. Prefer default iterators and membership
  operators, and never mutate a container while iterating over it.
- Use generators when helpful, document them with `Yields:`, and ensure expensive resources are
  closed even when iteration stops early.
- Keep lambdas to simple one-line expressions; prefer a named function when the body approaches
  60–80 characters. Use decorators only for a clear advantage, keep them free of fragile import-
  time dependencies, and test them. Avoid `staticmethod`; reserve `classmethod` for named
  constructors or necessary class-wide state.
- Properties must be cheap, straightforward, and unsurprising. Make a plain attribute public
  when access requires no logic; use a method when work or side effects are significant.
- Do not rely on built-in operation atomicity across threads. Prefer `queue.Queue` for handoff and
  `threading.Condition` over low-level locking where appropriate. Avoid metaclass tricks,
  bytecode manipulation, import hacks, dynamic inheritance, and other power features.

### Types and names

- Strongly prefer build-time type analysis. Annotate public APIs and code whose types are complex,
  error-prone, or stable enough to express clearly; do not add annotations that obscure the code.
- Spell nullable values explicitly as `X | None` in supported Python versions. Use `Any` only
  when the type truly cannot be expressed. Parameterize generic types rather than relying on
  implicit `Any`.
- Import typing symbols directly. Prefer abstract parameter types such as `Sequence` or `Mapping`
  when callers need not provide a concrete container, and prefer built-in generic forms such as
  `tuple[int, ...]`.
- Name type aliases in `CapWords`, with a leading underscore when module-private. Give constrained
  or public type variables descriptive names; single-letter private type variables are allowed
  only when unconstrained and not externally visible.
- Use `module_name.py`, `package_name`, `ClassName`, `ExceptionName`, `function_name`,
  `method_name`, `local_variable`, and `GLOBAL_CONSTANT`. Prefix internal module and class members
  with one underscore; avoid double-leading name mangling.
- Prefer descriptive names and avoid unfamiliar abbreviations, embedded type names, offensive
  terms, and single-character names outside small conventional scopes. Python filenames end in
  `.py` and contain no dashes.

### Formatting, strings, and resources

- Use four spaces per indentation level and never tabs. Do not use semicolons or multiple
  statements per line. Prefer lines of at most 80 characters, subject to documented exceptions
  and the configured formatter; use implicit continuation inside delimiters, not backslashes.
- Use two blank lines between top-level definitions and one between methods. Do not vertically
  align assignment, comment, or dictionary punctuation with extra spaces.
- Be consistent about single or double quotes within a file. Use f-strings, `%`, or `format()` for
  formatting rather than repeated `+`; accumulate many fragments in a list and `''.join()` or an
  `io.StringIO`.
- Pass logging format literals and arguments separately rather than using f-strings. Error
  messages must precisely describe the condition, clearly delimit interpolated values, and stay
  stable enough to search.
- Close files, sockets, database connections, and similar resources promptly with `with`; use
  `contextlib.closing()` when no context manager exists. Document lifetime management when a
  context manager is infeasible.

### Documentation and comments

- Begin non-test modules with a triple-double-quoted docstring describing contents and usage.
  Omit a test-module docstring when it would say nothing beyond “tests for X.”
- Give public, non-trivial, or non-obvious functions docstrings sufficient to call them without
  reading their bodies. Start with a summary line of at most 80 characters, then use `Args:`,
  `Returns:` or `Yields:`, and `Raises:` sections only as needed by the contract.
- Document classes as the thing an instance represents and list public non-property attributes.
  An `@override` method may inherit documentation unless it changes the contract or side effects.
- Comments explain why difficult code exists, not how Python syntax works. Write searchable TODOs
  as `TODO: issue-or-context - explanation`, preferably with a tracked issue.
- Prefer small, focused functions; reconsider a function beyond roughly 40 lines.

## Verification and review output

Lead with `Ready`, `Needs changes`, or `Blocked`, then report:

- `Required findings`: location, violated rule, behavioral or maintenance impact, and correction.
- `API and typing`: missing or misleading contracts, annotations, exceptions, and mutable state.
- `Tool results`: formatter, `pylint`, type checker, and tests run, including exact failures and
  justified suppressions.
- `Not run`: checks omitted and why.
- `Residual risk`: import-time behavior, resource cleanup, threading, type suppression, or error
  paths not exercised.
