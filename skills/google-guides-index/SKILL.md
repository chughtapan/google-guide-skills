---
name: google-guides-index
description: >-
  Use only when several Google guide skills could apply, the request spans guide categories, or
  the right guide is unclear. Route to the narrowest installed skill and identify catalog-only or
  local-only coverage gaps. Do not use when one named language, library, or code-review role
  clearly selects a direct skill.
---

# Google Guides Index

Read [the generated catalog](references/catalog.md), select the narrowest guide that matches the
task, and then read that guide's `SKILL.md`. Prefer project instructions and current requirements
when they conflict with upstream guidance.

Treat distribution labels as hard boundaries:

- Use `committed` skills normally under their recorded source licenses.
- Generate `local-only` skills for local use, keep them under `.generated/`, and do
  not redistribute them.
- Treat `catalog-only` entries as discovery leads, not installed guidance.

When no single guide covers the task, name the small set of guides you are combining and keep
their scopes distinct.
