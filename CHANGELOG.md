# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0.0] - 2026-08-24

### Added

- Conversion of 23 redistributable Google and Abseil guides from pinned revisions.
- Recipes for eight Software Engineering at Google skill groups that write only to the ignored
  local output root.
- Source and license records, input hashes, a catalog, and `o200k_base` token counts.
- Installation for Codex and Claude Code, plus evaluation cases and runners for Codex, Claude
  Code, OpenCode, OpenClaw, and Hermes.
- A user install command that links SWE-book skills from the ignored output root without copying
  or publishing them.
- Onboarding and incremental migration guides for selecting and routing skills in repositories.
- Agent skill routing and issue and pull-request templates.

### Changed

- User installation replaces a byte-identical skill copy with a link so later generated changes
  reach both supported agents.
- Project and command descriptions now state the repository's outcomes and use `local-only` for
  the SWE-book distribution class.
- Install and evaluation checks share one tree-hashing implementation.
- The Go skill keeps its source body in references after an oversized inline form was omitted by
  OpenClaw. In the follow-up full-pack smoke run, all 115 client/case pairs reported the expected
  skill; 69 routes were trace-proven and exact, while 46 used verified self-report proxies.

### Removed

- The evaluation baseline from the retired harness; its results did not meet the current model,
  isolation, status, and scoring requirements.
- Unused local-only and global project-install modes; SWE-book installation uses the user-link
  path.
- The persistent routing index and its index-only evaluation profiles and cases.

### Security

- Checks for protected source identities, source-path distribution rules, pinned Git bytes,
  license evidence, output paths, and tracked restricted output.
- Evaluation isolation with temporary workspaces and Bubblewrap, copied OAuth login state,
  reduced process environments, installed-tree checks, and failure-status handling.

### Known limitations

- The one-pass routing thresholds passed; repeated near-miss specificity and broader quality cases
  have not run.
- Version 0.1 is text-only; upstream images and some relative links are not bundled or rewritten.
- Run the project from a source checkout. Wheels omit the corpus and generated skill trees; source
  archives omit generated skill trees. Both are marked private/do-not-upload.
