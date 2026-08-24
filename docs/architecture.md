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
- SWE-book installation requires license acceptance and links agent directories back to
  `.generated/skills/`. User installation is recommended; an explicit project install uses the
  same checked links. Copy mode applies only to public skills.

## Skill layout

The `inline` layout puts converted source in `SKILL.md`. The `references` layout keeps the entry
file short and stores converted source in `references/`. Version 0.1 uses references for the Go
guide, Abseil collections, and the SWE book. Both layouts preserve the source prose; the difference
is when an agent loads it.

Token reports and evaluations determine whether another inline skill should move into references.
Version 0.1 does not edit the guides to reduce their size.
