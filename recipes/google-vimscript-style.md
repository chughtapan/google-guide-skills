# Google Vimscript Style Guide

## Scope and precedence

Apply this recipe to Vimscript plugins and reviews using the abbreviated Google guide. Do not
import additional requirements from the separate heavy guide, and do not apply it to Lua-based
Neovim code. Project conventions still govern matters the abbreviated guide does not address.
Protect user configuration: scripts must not depend accidentally on mappings, case settings,
regular-expression magic, or global options.

Rules that name `maktaba#...`, Glaive, or Maktaba-specific directories apply only when the plugin
uses Maktaba. Keep the portable Vimscript rule even when its suggested Maktaba helper is
unavailable.

## Workflow

1. Read repository instructions and inspect the plugin layout, supported Vim versions, user-
   configurable settings, mappings, autocommands, and whether Maktaba is a declared dependency.
2. Identify commands affected by user settings, regex and string comparisons, type assumptions,
   global state, messages, and code that runs during plugin startup.
3. Move reusable logic into autoloaded functions. Keep commands and autocommands declarative and
   delegate their behavior to functions.
4. Apply explicit case, regex, scope, and local-setting rules; then format to the abbreviated
   guide.
5. Exercise the plugin with changed `ignorecase` and magic settings, conflicting mappings or
   commands, and representative type errors. Re-source it to expose re-entry problems.
6. Run project checks and report any behavior, Vim version, or user-setting combination not
   verified.

## High-impact rules

### Portable behavior

- Prefer single-quoted strings. Use double quotes when an escape sequence is required or when
  embedding single quotes is clearer and semantic differences do not matter.
- Compare strings with an explicit case operator family such as `=~#` or `=~?`, not `=~`, unless
  the code deliberately honors the user's case settings.
- Prefix regular expressions with `\m\C` by default. Another magic level such as `\v` or case mode
  such as `\c` is acceptable only when chosen explicitly.
- Prefer built-in functions over commands with cursor, message, or setting-dependent side
  effects. Avoid `:substitute`; always use `normal!` rather than `normal`.
- Match caught Vim errors by error code, not localized text.
- Message users only when an error occurs or a long-running operation begins.
- Check types explicitly. Use strict comparison where possible and `is#` for a string literal;
  otherwise inspect `type()` and throw an appropriate error. `:unlet` a variable before reusing it
  with a different type, especially in loops.
- Use embedded Python only for critical functionality such as work requiring threads. Avoid Ruby,
  Lua, and other embedded languages because the user's Vim may not support them.

### Layout, whitespace, and names

- Organize a plugin in one descriptively named directory or repository, split into standard
  `plugin/`, `autoload/`, `ftplugin/`, and other required subdirectories.
- Indent two spaces, never tabs. Indent continuations four spaces, keep lines within 80 columns,
  avoid trailing whitespace, and do not add padding merely to align similar commands.
- Put spaces around operators, but not around command arguments where spaces change Vimscript
  syntax.
- Use `plugin-names-like-this`, `FunctionNamesLikeThis`, `CommandNamesLikeThis`,
  `augroup_names_like_this`, and `variable_names_like_this`.
- Prefix variables by scope: `g:` for globals, `s:` for script-local values, `a:` for arguments,
  `l:` for function locals, `v:` for Vim predefined values, and `b:` for buffer-local state.
  Always use `g:`, `s:`, and `a:`; add `l:` and `v:` in new code.
- Keep globals for plugin configuration. Set options locally with `setlocal` or `&l:` unless a
  global change is explicitly intended.

### Functions, commands, autocommands, and mappings

- Put functions in `autoload/` so they load on demand and are namespaced. Script-local functions
  use `s:`; do not create global functions. Non-library plugins should expose commands and keep
  their implementation in functions.
- Define functions with `function!` and `abort`. The bang permits safe re-sourcing; `abort` makes
  error behavior independent of the calling stack.
- Put general commands in `plugin/commands.vim` and filetype commands under `ftplugin/`. Define
  commands without a bang so name collisions fail visibly rather than silently overwriting an
  existing command.
- Put autocommands in `plugin/autocmds.vim`, inside a uniquely named augroup based on the plugin
  name. Clear the group with `autocmd!` before redefining it.
- Put complete mappings in `plugin/mappings.vim` and partial `<Plug>` mappings in
  `plugin/plugs.vim`. Keep mapping logic in functions.

### Maktaba-based plugins only

- Use Maktaba for plugin creation, dependency checks, and error-handling boilerplate when Maktaba
  is the plugin's chosen framework and declared dependency.
- Use `maktaba#ensure` or `maktaba#value` helpers for explicit validation and equality when
  available; the underlying requirement is still strict type checking.
- Obtain a mapping prefix with `maktaba#plugin#MapPrefix`. Keep configuration in Maktaba flags so
  users can change it through Glaive.
- Declare plugin metadata and dependencies in `addon-info.json` when using the corresponding
  Maktaba/VAM plugin-management conventions.

## Verification and review output

Lead with `Ready`, `Needs changes`, or `Blocked`, then report:

- `Required findings`: location, portability or style rule, user-visible impact, and fix.
- `User-setting safety`: regex magic, case behavior, mappings, commands, autocommands, and local
  option handling checked.
- `Framework scope`: whether Maktaba-specific findings actually apply to this plugin.
- `Validation`: project checks, Vim versions, re-sourcing, and altered-setting scenarios run.
- `Residual risk`: unsupported Vim configuration, unverified user setting, type path, or command
  side effect.
