# Source licensing policy

This is an engineering control, not legal advice. Verify licenses again before publishing a new
source or using generated local-only material in a different way.

## Distribution classes

| Class | Output | Repository policy |
| --- | --- | --- |
| `committed` | `skills/` | Generated files may be committed with attribution and source terms. |
| `local-only` | `.generated/skills/` | Generated files stay ignored and are not distributed by this project. |
| `catalog-only` | Catalog metadata only | The source is inventoried but no page content is shipped yet. |

Every repository or override license also declares `allow_committed_output`. Manifest loading and
the builder both reject a `committed` collection when that flag is false, so changing only the
distribution label cannot move restricted content across the boundary.

Protected GitHub repository identities are normalized across common HTTPS, SSH, and Git URL
forms; aliases must use the canonical manifest ID and URL. Mandatory source-path rules are also
enforced by the builder independently of the manifest entry name: `resources/swe-book/html/**`
can only target local output, and `Rguide.md` cannot be generated. Inputs and every license-evidence
file must be tracked bytes from the pinned commit. Validation rejects restricted skills in the
committed root, tracked `.generated/` output, and provenance that names the wrong owning
collection.

## Audited sources

| Source | Selected material | License | Evidence |
| --- | --- | --- | --- |
| `google/styleguide` | Language and documentation guides | CC BY 3.0 | Repository `LICENSE` at the pinned commit |
| `google/eng-practices` | Code-review author and reviewer guides | CC BY 3.0 | Repository `LICENSE` at the pinned commit |
| `abseil/abseil.github.io` | Selected Abseil docs, design notes, and posts | Apache-2.0 | Repository `LICENSE` at the pinned commit |
| `abseil/abseil.github.io` | `resources/swe-book/html/*.html` | CC BY-NC-ND 4.0 | Required notice in every matched chapter file |

The top-level Abseil license does not erase the narrower file-level notice on the book. The
manifest therefore models the book as a separate collection with a license override. A build
fails if any matched chapter loses the expected notice.

The local-only generator does not grant permission beyond the upstream license. In particular,
do not assume that mechanical conversion, local generation, or an ignored directory makes
adapted material redistributable or commercially usable. The SWE-book recipe is explicitly for
noncommercial local use and its generated output must not be shared.

The R guide remains catalog-only because its source identifies a CC BY-SA 2.0 Tidyverse base in
addition to the repository's CC BY 3.0 license. The pipeline will not generate it until composite
license and ShareAlike attribution are modeled. The Google Cloud product-management article is
also catalog-only with `NOASSERTION`; an official page is not automatically open content.

## Standalone skill license files

Every generated skill includes `references/LICENSE.txt` for its converted upstream prose and
`references/LICENSE-Generator-Apache-2.0.txt` for the project-authored frontmatter, navigation,
and provenance wrapper. The authored index includes its Apache-2.0 license and provenance too.
These scopes are recorded separately in `source.json`; Apache-2.0 never replaces the upstream
license. The JSON API style guide additionally includes `LICENSE-Apache-2.0.txt` for upstream code
samples, whose page notice distinguishes them from the CC BY 3.0 prose.

## Adding a source

1. Prefer an official repository or first-party page.
2. Pin a full commit SHA for Git sources.
3. Record the SPDX identifier, canonical license URL, attribution, audit date, and concrete
   evidence path or file-level notice.
4. Check subdirectories for exceptions; never infer that a root license covers every file.
5. Choose `local-only` or `catalog-only` when redistribution is uncertain or reproducible web
   snapshots are not yet available.
6. Add a regression test proving restricted material cannot enter `skills/`.
7. Rebuild and review every generated `source.json` before shipping.

## Project and trademark boundary

The Apache-2.0 project license covers original generator code, authored project docs, and the thin
wrapper layer identified above. Each converted source remains under its recorded upstream terms.
Google and Abseil names are used solely to identify provenance; the project is independent and
unendorsed.
