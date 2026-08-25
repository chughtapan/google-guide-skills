# Google Shell Style Guide

## Scope and precedence

Use Bash for executable shell scripts unless a constrained environment requires Bourne shell.
Use shell only for small utilities and simple wrappers that mostly invoke other programs. Move to
a structured language when performance matters, control flow becomes non-trivial, or the script
grows beyond roughly 100 lines. Follow project rules and existing file style where applicable;
new code must follow this guide. Never use SUID or SGID shell scripts.

## Workflow

1. Read repository instructions and inspect the target shell, deployment method, supported Bash
   version, inputs, environment variables, and surrounding conventions.
2. Confirm shell is still the right language. Trace every argument, expansion, pathname, command
   substitution, pipeline, and return status through normal and failure paths.
3. Structure the script with a header, constants, functions, then `main`. Keep state local and
   represent argument lists with arrays.
4. Add API comments for library functions and any function that is not both short and obvious.
   Send diagnostics to standard error.
5. Run ShellCheck and the project's tests using representative empty, whitespace-containing,
   wildcard-like, and failing inputs.
6. Review quoting, subshell boundaries, pipeline statuses, cleanup, and exit values before
   reporting completion.

## High-impact rules

### Language, files, and structure

- Executable scripts start with `#!/bin/bash` and minimal flags; set shell options with `set` so
  `bash script_name` behaves the same. Executables use `.sh` or no extension according to how
  they are deployed. Libraries use `.sh` and are not executable.
- Start every file with a brief contents comment. Put includes, option settings, and constants
  first; group all functions together; leave executable flow after the functions.
- A script with any helper function must have a bottom-most `main` function. Make the final
  non-comment line `main "$@"`.
- Keep functions `lower_case_with_underscores`; package functions may use `package::function`.
  Use the `function` keyword consistently if the project chooses it. Use lowercase variable names
  and `UPPER_CASE` for constants, readonly values, and exported environment variables.
- Declare function state with `local`. When assigning command substitution, separate declaration
  from assignment so `local` does not hide the command's exit status.

### Quoting and expansion

- Quote strings containing variables, command substitutions, whitespace, or shell metacharacters
  unless unquoted expansion is specifically required. Prefer `"${name}"` for named variables and
  braces where they disambiguate positional parameters; braces do not replace quotes.
- Use `"$@"` to forward arguments. Use `$*` only when deliberately joining all arguments into one
  string.
- Use `$(command)` instead of backticks, and quote command substitutions even when an integer is
  expected.
- Store lists and command arguments in arrays, then expand them with `"${array[@]}"`. Do not
  encode an argument vector in a string or recover it with `eval`.
- Use explicit paths for globs, such as `./*`, so filenames beginning with `-` are not interpreted
  as options.

### Tests, loops, and arithmetic

- Prefer `[[ ... ]]` over `[ ... ]` or `test`. Use `-z` and `-n` for string emptiness, `==` for
  string equality, and quote expansions inside tests. Leave a regex or glob pattern unquoted only
  when pattern matching is intended.
- Use `(( ... ))` for numeric tests and assignments and `$(( ... ))` for arithmetic expansion.
  Do not use `let`, `$[...]`, or `expr`; remember that `<` and `>` inside `[[ ... ]]` compare
  lexicographically.
- Put `; then` and `; do` on the control statement line. Align `fi`, `done`, and `esac` with the
  opener. In a function, declare loop variables local, and write `for arg in "$@"` explicitly.
- Prefer process substitution or `readarray` to piping into `while`; a pipeline loop runs in a
  subshell and its assignments do not reach the parent. Do not iterate over `$(command)` output
  unless whitespace splitting is demonstrably correct.
- Avoid standalone arithmetic expressions whose zero result could trigger an unexpected exit
  when `set -e` is active.

### Commands and failures

- Always check command return values. Prefer a direct `if ! command; then ...` check for unpiped
  commands. For pipelines, inspect `PIPESTATUS` and copy it immediately if another command will
  run before analysis.
- Write error messages and diagnostics to `STDERR`; reserve `STDOUT` for normal output intended
  for callers.
- Prefer Bash builtins and parameter expansion to external commands when they express the same
  operation more clearly and robustly.
- Avoid `eval` and aliases. Use functions instead of aliases.
- Use process cleanup and explicit return or exit values so callers can distinguish success from
  failure.

### Formatting and documentation

- Indent two spaces and never tabs, except tabs required by a `<<-` here-document. Keep lines to
  80 characters where practical and avoid trailing whitespace.
- Keep a pipeline on one line when it fits. Otherwise put one segment per line, indent continuation
  segments two spaces, and place `|`, `&&`, or `||` at the start of the continuation line after a
  backslash.
- Format `case` alternatives two spaces inside `case`; put multi-command bodies and `;;` on their
  own indented lines. Avoid `;&` and `;;&`.
- Function comments describe purpose and, when applicable, globals, arguments, output streams,
  and non-default return meanings. Comment tricky implementation decisions, not obvious commands.
- Use searchable `TODO(identifier): explanation` comments for temporary or incomplete work.

## Verification and review output

Lead with `Ready`, `Needs changes`, or `Wrong language`, then report:

- `Required findings`: location, quoting/control-flow/error-handling defect, impact, and fix.
- `Shell suitability`: whether the script remains small and straightforward enough for Bash.
- `Validation`: ShellCheck, syntax checks, tests, and adversarial input cases run with results.
- `Not run`: unavailable checks and why.
- `Residual risk`: environment dependence, unsafe expansion, unverified external command,
  pipeline status, or cleanup path.
