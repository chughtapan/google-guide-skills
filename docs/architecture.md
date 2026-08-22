# Architecture

## Data flow

```text
corpus.yaml
    |
    v
.cache/sources/<repository> @ exact commit
    |
    +-- license evidence gate
    +-- input glob expansion and SHA-256 capture
    +-- copy Markdown or convert HTML/XML without editing the source prose
    |
    +--> skills/             redistributable output, committed
    +--> .generated/skills/  restricted output, gitignored
              |
              v
       catalog + token metrics + validation + cross-agent evals
```

The manifest separates repositories from collections because a single repository can contain
files with different licenses. `abseil` is the motivating case: the repository-level Apache-2.0
license governs the selected Abseil docs, while the SWE-book collection has a
CC-BY-NC-ND-4.0 override backed by a notice check across every chapter file.

## Reproducibility

- Every Git repository uses a full 40-character commit SHA.
- Source input patterns expand to a sorted, de-duplicated list.
- Every input's SHA-256 digest and converter mode are written to `source.json`.
- Generated files contain no wall-clock timestamp.
- Catalog and JSON output are sorted before writing.
- CI rebuilds the committed outputs and fails on a diff.

## Output rules

- Output roots are fixed by `corpus.yaml`; the CLI has no flag that can redirect local-only
  content into `skills/`.
- Replacement is limited to a direct child of a generated root that already carries generated
  provenance.
- Cache checkouts with local edits or an unexpected remote fail instead of being reset.
- File patterns cannot be absolute or contain `..`.
- A build fails when license evidence is missing.
- Validation rejects local-only provenance inside the committed root and checks that
  `.generated/` is ignored and contains no tracked files, including force-added files.
- User-level local-only installation is symlink-only: `install --include-swe-book` points an
  agent home back to `.generated/skills/`, while project and copy export remain prohibited.

## Skill layout

In version 0.1, the `inline` layout puts converted source in `SKILL.md`, even when it exceeds Agent
Skills context recommendations. The `references` layout is used for collections such as Abseil
tips and the SWE book. Both preserve the source prose; the difference is when an agent loads it.

Token reports and evaluations show which inline skills should move into references. Version 0.1
does not edit the guides to reduce their size.
