# Architecture

The project turns pinned Google sources into inline skills and keeps the source license
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
    +-- public guide -> selected source passages -> skills/
    |
    +-- SWE book -> selected source passages -> .generated/skills/
                                                   |
                                                   v
                                  catalog + metrics + validation + evaluation
```

`corpus.yaml` is the source of truth. Schema 3 declares repositories, pinned revisions, licenses,
collections, artifacts, output class, and exact source headings and blocks. Generated
`source.json` files record each selection and input hash so a reviewer can trace every included
passage.

Schema 2 remains readable and gets a legacy pack containing its original artifacts. Schema 3 adds
named `packs` and `web_sources`. Each collection names exactly one `repository` or `web_source`.
Web inputs must be explicitly enumerated page filenames; wildcard discovery and automatic crawling
are not supported.

## Source adapters and web snapshots

| Source | Adapter | Acceptance rule |
| --- | --- | --- |
| General AIPs | `aip` | Strip frontmatter; require `state: approved` |
| DORA | `dora` | Require `draft: false`, insert the title, unwrap known callouts |
| Secure/reliable systems book | `html-book` | Extract one chapter and retain nested headings and sidebars |
| Google documentation | `google-docs` | Extract one configured article; omit navigation, feedback, and AI summaries |

Unknown Hugo-style shortcodes in selected prose fail the build. The original sources retain their
existing conversion path. New adapters preserve paragraph boundaries and use the same explicit
heading and block selection as the original skills.

Capture or refresh a web source deliberately:

```bash
uv run google-guides snapshot --source cloud-adr
uv run google-guides build --collection web-cloud-adr --no-sync
uv run google-guides validate
```

`sources/web/<id>/lock.json` records each requested and resolved URL, selector, SHA-256 digest, and
license evidence digest. The lock identifies an immutable bundle under `snapshots/<hash>/`.
Stored HTML excludes scripts, styles, and browser fallback markup, which can contain unrelated
site configuration. Hashes cover these stored bytes; article content and license notices remain.
Capture validates all pages before atomically replacing the accepted lock. Failed captures leave
the previous lock intact; older bundles remain available. Review the new lock, page changes,
license notices, and generated excerpts together before accepting a refresh in version control.

The snapshotter accepts HTTPS URLs only in the declared public Google documentation namespaces,
including redirects. It checks each page's CC BY 4.0 notice and Apache-2.0 code-sample notice.
Builds verify the stored bytes and extraction selectors offline. `build --no-sync` makes no
network requests; Git caches must already contain the pinned revisions. `sync` fetches Git
sources only. It never refreshes web snapshots.

## Skill design

The pack is organized around jobs, not books or chapter numbers.

- Public language, documentation, and review skills contain selected passages from the pinned
  guides.
- The eight SWE-book skills combine related chapters around testing, standards, review systems,
  change management, builds and CI, teamwork, developer productivity, and compute platforms.
- Every `SKILL.md` contains the guidance it expects an agent to use. There is no navigation-only
  skill and no required reference-file search.
- Source excerpts keep the selected upstream wording. The generator removes page chrome, images,
  broken local link markup, and navigation-only clauses selected during review.

The current main files remain below the Agent Skills recommendation of roughly 5,000 tokens and
500 lines. Token metrics are regenerated with the skills.

## Reproducibility

- Every Git source uses a full commit SHA.
- Every web source uses a locked, content-addressed bundle with verified license evidence.
- Inputs and license evidence must be tracked and byte-identical to that revision.
- Every input hash, selector, runtime, and rendering mode is written to `source.json`.
- Generated files contain no wall-clock timestamp.
- Catalog and metrics output are sorted before writing.
- Rebuilding the same manifest on the pinned Python runtime must produce the same bytes.

## Installation packs

The default pack contains all 41 public and 8 local skills. Compact descriptions keep the complete
selection within the startup budget at the documented reference path. Validation checks each
declared pack, including local members that have not been generated. The installer
checks the union of selected and existing skills at the actual target path before generating or
installing anything. Overflow causes an error and never triggers pruning or partial installation.
This check covers the target directory; it does not enumerate every additional skill root a
client might load.

No flags selects `default`. Manifests without that pack retain the previous `legacy` fallback.
Repeat `--pack` and `--skill` to select a smaller union, or use `--pack legacy` for the original
24 skills. Project copy installation still uses the pinned Skills CLI; user installation uses
symlinks.

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
