# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.4.0.0] - 2026-10-29

### Added

- Use 25 new Google guide skills for API design, design documents and ADRs, security,
  reliability, delivery, and developer documentation.
- Select related skills with `install --pack` and plan focused evaluations with `eval --pack`.
  Repeated pack and skill options combine their selections.
- Capture approved public documentation with `snapshot --source`. Saved pages, content hashes,
  and license evidence support repeatable offline builds.

### Changed

- Installation selects all 49 skills by default: 41 public guides and eight local SWE-book skills.
  Use `--pack legacy` for the original 24. The SWE-book license acceptance still applies.
- Installation checks selected and existing skills at each destination before changing either
  client. The check includes nested skills, directory links, and aliased folder names.
- Startup descriptions fit the default pack within the documented metadata budget at the
  reference installation path. Existing skills and longer paths can require a smaller selection.

### Evaluation

- Live routing and quality evaluations for the expanded pack remain deferred. The new cases and
  offline checks do not establish model routing accuracy or answer quality.

## [0.3.0.0] - 2026-08-26

### Changed

- All 24 retained skills now contain selected source passages organized around their tasks.
- The generator selects exact headings and paragraph blocks, preserves Markdown structure, and
  records the selections in each skill's source record.
- Project instructions now state the development outcome and leave the workflow to the agent.

### Removed

- The 16 hand-written public recipes and broad progressive-disclosure bodies they replaced.

### Evaluation

- On one five-checkpoint SlopCodeBench task, the source-excerpt skills tied the baseline at 95/104
  under default effort and improved the measured code structure. At `xhigh`, the guided arm scored
  97/104 against a 100/104 baseline while retaining the structure advantage. This single-run demo
  does not establish a general correctness effect.

## [0.2.0.0] - 2026-08-25

### Changed

- The normal install flow now offers the SWE-book skills and handles license acceptance without a
  separate `--include-swe-book` option.
- The README now focuses on what the skills improve, installation, and repository use.
- Public guides are now reviewed, self-contained recipes instead of large converted documents or
  vague routers over reference files.
- The SWE-book material is now eight task-based skills built from selected source passages:
  teamwork and leadership, developer productivity, engineering standards, code-review systems,
  testing, change management, builds/dependencies/CI, and compute platforms.
- Generated source records now identify the exact headings and paragraph blocks selected from
  each SWE-book chapter.

### Removed

- The SWE-book front matter, standalone SWE documentation skill, historical AngularJS and JSON
  style skills, and the Abseil guide, design-note, C++ tip, performance-tip, and Python bundles.
  They were obsolete, duplicated another skill, or lacked a clear recurring task.

## [0.1.0.0] - 2026-08-24

### Added

- Conversion of 23 redistributable Google and Abseil guides from pinned revisions.
- Recipes for eight Software Engineering at Google skill groups that write only to the ignored
  local output root.
- Source and license records, input hashes, a catalog, and `o200k_base` token counts.
- Installation for Codex and Claude Code, plus evaluation cases and runners for Codex, Claude
  Code, OpenCode, OpenClaw, and Hermes.
- License-gated SWE-book installation with checked links for user homes and explicit projects.
- Onboarding and incremental migration guides for selecting and routing skills in repositories.
- Agent skill routing and issue and pull-request templates.

### Changed

- User installation replaces a byte-identical skill copy with a link so later generated changes
  reach both supported agents.
- Per-user installation is recommended; project installation supports public copies and SWE-book
  links when requested.
- Project and command descriptions now state the repository's outcomes and use `local-only` for
  the SWE-book distribution class.
- Install and evaluation checks share one tree-hashing implementation.
- The Go skill keeps its source body in references after an oversized inline form was omitted by
  OpenClaw. In the follow-up full-pack smoke run, all 115 client/case pairs reported the expected
  skill; 69 routes were trace-proven and exact, while 46 used verified self-report proxies.

### Removed

- The evaluation baseline from the retired harness; its results did not meet the current model,
  isolation, status, and scoring requirements.
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
