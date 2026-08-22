# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0.0] - 2026-08-22

### Added

- Conversion of 23 redistributable Google and Abseil guides from pinned revisions, plus a
  discovery index.
- Recipes for eight Software Engineering at Google skill groups that write only to the ignored
  local output root.
- Source and license records, input hashes, a catalog, and `o200k_base` token counts.
- Cross-agent installation and Codex/Claude Code discovery and quality evaluations.
- A user install command that links SWE-book skills from the ignored output root without copying
  or publishing them.

### Security

- Checks for protected source identities, source-path distribution rules, pinned Git bytes,
  license evidence, output paths, and tracked restricted output.
- Evaluation isolation with temporary workspaces and Bubblewrap, one-use keys, reduced process
  environments, installed-tree checks, and failure-status handling.

### Known limitations

- Live-model release gates have not yet passed under the current harness.
- Version 0.1 is text-only; upstream images and some relative links are not bundled or rewritten.
- Run the project from a source checkout. Package archives omit the corpus and generated skill
  trees and are marked private/do-not-upload.
