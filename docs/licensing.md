# Source licensing policy

The project uses sources with different reuse terms. The manifest records whether an artifact may
be committed, may be generated only for local use, or must remain catalog metadata. This policy is
not legal advice; recheck the source terms before publishing a new artifact or using local output
in another way.

## Distribution classes

| Class | Output | Rule |
| --- | --- | --- |
| `committed` | `skills/` | May be committed with attribution and source terms. |
| `local-only` | `.generated/skills/` | Ignored and not distributed by this project. |
| `catalog-only` | Catalog metadata | No source page content is generated. |

Every repository or collection license declares whether committed output is allowed. The builder
also applies rules to protected repository paths: the SWE-book chapters can only produce local
output, and the R guide cannot be generated. These rules apply even if a manifest entry is renamed
or uses another spelling of the repository URL.

Inputs and license evidence must be tracked at the pinned revision. Validation rejects restricted
skills in `skills/`, tracked `.generated/` output, and source records that do not match the owning
artifact and collection.

## Audited sources

| Source | Selected material | License | Evidence |
| --- | --- | --- | --- |
| `google/styleguide` | Language and documentation guides | CC BY 3.0 | Repository `LICENSE` at the pinned commit |
| `google/eng-practices` | Code-review author and reviewer guides | CC BY 3.0 | Repository `LICENSE` at the pinned commit |
| `abseil/abseil.github.io` | `resources/swe-book/html/*.html` | CC BY-NC-ND 4.0 | Required notice in every selected chapter |

The Abseil repository's Apache-2.0 license does not replace the file-level SWE-book notice.
Mechanical conversion, selected excerpts, local generation, and an ignored directory do not make
the book text redistributable or commercially usable.

The normal `google-guides install` flow shows the book license and requires acceptance before it
generates or installs those skills. `--accept-swe-book-license` provides acceptance for that
noninteractive run. User and project installs link the generated skills back to
`.generated/skills/`; `--copy` applies only to public skills. Do not commit or publish those links
or generated files. Direct maintainer build commands with `--include-swe-book` do not prompt; run
them only after reviewing these terms.

The R guide remains catalog-only because it identifies a CC BY-SA 2.0 Tidyverse base in addition
to the repository's CC BY 3.0 license. The Google Cloud product-management article remains
catalog-only with `NOASSERTION` because no first-party open-content notice was found.

## License files in a skill

Each generated skill carries:

- `LICENSE.txt` for the source guidance;
- `LICENSE-Generator-Apache-2.0.txt` for project-authored metadata and workflow text;
- `source.json` with the source revision, hashes, rendering choice, and license scopes.

Apache-2.0 covers only the project-authored wrapper. It does not replace the source license.

## Adding a source

1. Use a first-party source and pin a full commit SHA.
2. Record its SPDX identifier, attribution, license URL, and concrete evidence file.
3. Check subdirectories for different terms.
4. Choose `local-only` or `catalog-only` when redistribution is unclear.
5. Add the artifact, selectors or recipe, provenance checks, and an evaluation case.
6. Regenerate and review the skill and `source.json` before shipping.

Google and Abseil names identify provenance only. This project is independent and unendorsed.
