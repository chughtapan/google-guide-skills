# Source licensing policy

This policy is not legal advice. Recheck a license before publishing a new source or using
local-only output in another way.

## Distribution classes

| Class | Output | Repository policy |
| --- | --- | --- |
| `committed` | `skills/` | Generated files may be committed with attribution and source terms. |
| `local-only` | `.generated/skills/` | Generated files stay ignored and are not distributed by this project. |
| `catalog-only` | Catalog metadata only | The source is inventoried but no page content is shipped yet. |

Every repository or override license also declares `allow_committed_output`. Manifest loading and
the builder both reject a `committed` collection when that flag is false, so changing only the
distribution label cannot move restricted content across the boundary.

The manifest normalizes GitHub HTTPS, SSH, and Git URLs. Protected repositories must use their
assigned manifest ID and URL. The builder also applies source-path rules regardless of the entry
name: `resources/swe-book/html/**` can only target local output, and `Rguide.md` cannot be
generated. Every input and license-evidence file must be tracked at the pinned commit. Validation
rejects restricted skills in `skills/`, tracked `.generated/` output, and source records that name
the wrong collection.

## Audited sources

| Source | Selected material | License | Evidence |
| --- | --- | --- | --- |
| `google/styleguide` | Language and documentation guides | CC BY 3.0 | Repository `LICENSE` at the pinned commit |
| `google/eng-practices` | Code-review author and reviewer guides | CC BY 3.0 | Repository `LICENSE` at the pinned commit |
| `abseil/abseil.github.io` | Selected Abseil docs, design notes, and posts | Apache-2.0 | Repository `LICENSE` at the pinned commit |
| `abseil/abseil.github.io` | `resources/swe-book/html/*.html` | CC BY-NC-ND 4.0 | Required notice in every matched chapter file |

The top-level Abseil license does not override the file-level notice on the book. The
manifest therefore models the book as a separate collection with a license override. A build
fails if a matched chapter lacks that notice.

Generating files does not change their license. Mechanical conversion, local generation, and an
ignored directory do not make adapted material redistributable or commercially usable. The
SWE-book recipe is for noncommercial local use. Do not share its output.

`google-guides install --include-swe-book` links generated book skills into the current user's
agent directories. Each link points to `.generated/skills/`; the installer does not copy the files
into agent homes, projects, packages, or Git history. This command rejects `--copy`, project
destinations, and existing user skills with different content. It replaces a byte-identical copy
with a link.

The R guide remains catalog-only because its source identifies a CC BY-SA 2.0 Tidyverse base in
addition to the repository's CC BY 3.0 license. The pipeline will not generate it until composite
license and ShareAlike attribution are modeled. The Google Cloud product-management article is
also catalog-only with `NOASSERTION`; publication on a Google page does not grant reuse rights.

## Standalone skill license files

Every generated skill includes `references/LICENSE.txt` for its converted upstream prose and
`references/LICENSE-Generator-Apache-2.0.txt` for the project-authored frontmatter, navigation,
and source-record wrapper. The index includes its Apache-2.0 license and source record.
These scopes are recorded separately in `source.json`; Apache-2.0 never replaces the upstream
license. The JSON API style guide additionally includes `LICENSE-Apache-2.0.txt` for upstream code
samples, whose page notice distinguishes them from the CC BY 3.0 prose.

## Adding a source

1. Prefer a first-party repository or page.
2. Pin a full commit SHA for Git sources.
3. Record the SPDX identifier, license URL, attribution, audit date, and
   evidence path or file-level notice.
4. Check subdirectories for exceptions; never infer that a root license covers every file.
5. Choose `local-only` or `catalog-only` when redistribution is uncertain or web snapshots are
   not pinned.
6. Add a regression test proving restricted material cannot enter `skills/`.
7. Rebuild and review every generated `source.json` before shipping.

## Project and trademark boundary

The Apache-2.0 project license covers generator code, project docs, and the metadata, navigation,
and source records added to each skill. Each converted source remains under its recorded terms.
Google and Abseil names are used solely to identify provenance; the project is independent and
unendorsed.
