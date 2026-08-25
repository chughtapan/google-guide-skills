# Architecture

The project turns pinned Google sources into self-contained skills and keeps the source license
attached. Public skills go to `skills/`. Selected passages from *Software Engineering at Google*
go only to the ignored `.generated/skills/` tree.

## Data flow

```text
corpus.yaml
    |
    v
.cache/sources/<repository> @ exact commit
    |
    +-- verify source and license bytes
    +-- record input SHA-256 hashes
    |
    +-- public guide -> reviewed recipe -> skills/
    |
    +-- SWE book -> selected source passages -> .generated/skills/
                                                   |
                                                   v
                                  catalog + metrics + validation + evaluation
```

`corpus.yaml` is the source of truth. It declares repositories, pinned revisions, licenses,
collections, artifacts, and output class. Public artifacts name a reviewed recipe. Local SWE-book
artifacts name exact source headings and paragraph blocks. Generated `source.json` files record
the choice and hashes so a reviewer can trace every included passage.

## Skill design

The pack is organized around jobs, not books or chapter numbers.

- Public language, documentation, and review skills are concise recipes grounded in the pinned
  guides.
- The eight SWE-book skills combine related chapters around testing, standards, review systems,
  change management, builds and CI, teamwork, developer productivity, and compute platforms.
- Every `SKILL.md` contains the guidance it expects an agent to use. There is no navigation-only
  skill and no required reference-file search.
- Source excerpts keep the upstream wording. The generator removes page chrome, broken local link
  markup, images, and passages that were not selected.

The current main files remain below the Agent Skills recommendation of roughly 5,000 tokens and
500 lines. Token metrics are regenerated with the skills.

## Reproducibility

- Every Git source uses a full commit SHA.
- Inputs and license evidence must be tracked and byte-identical to that revision.
- Every input hash, selector, recipe, runtime, and rendering mode is written to `source.json`.
- Generated files contain no wall-clock timestamp.
- Catalog and metrics output are sorted before writing.
- Rebuilding the same manifest on the pinned Python runtime must produce the same bytes.

## Distribution boundary

- Output roots are fixed by the manifest; local-only content cannot target `skills/`.
- Protected repository paths keep their required distribution class even if a collection is
  renamed.
- Replacement is limited to generated child directories under a checked output root.
- File patterns cannot be absolute, escape the checkout, or follow an escaping symlink.
- Validation rejects local-only provenance in `skills/`, tracked `.generated/` files, and source
  records that name the wrong artifact or collection.
- Installing SWE-book skills requires license acceptance. They are always linked from the ignored
  generated root; copy mode applies only to public skills.

Hosted CI exercises these boundaries with synthetic restricted-source fixtures. Maintainers run
`uv run google-guides all --include-swe-book` locally before release so the actual chapter
selectors are checked without generating licensed book output on a hosted runner.
