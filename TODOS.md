# TODOS

## Evaluation

### Run and tune the cross-agent matrix

**Priority:** P1

Run invocation controls, full-pack routing, paired `index-ab`, specificity cases, and quality A/Bs
with pinned Codex and Claude model IDs. Tune descriptions and the index against the training split,
then publish one validation run with denominators and costs. Treat the earlier Abseil over-selection
and Claude budget failures as hypotheses until the current harness reproduces them.

### Reduce startup metadata and large inline skills

**Priority:** P1

The full committed pack fits Codex's fallback metadata budget only when the skill install root is
54 characters or shorter and no unrelated skills consume the same budget. After the routing run,
shorten descriptions or split the pack without lowering recall. Move oversized inline guides into
references and compare selection and answer quality before changing the default layout.

## Distribution

### Add an OpenAI plugin wrapper

**Priority:** P2

Package the skills as a Codex/ChatGPT plugin after their descriptions and grouping pass the
cross-agent tests. Keep `skills/` as the source.

## Sources

### Add locked web snapshots

**Priority:** P2

Implement page enumeration, content extraction, and content-hash lock updates for the cataloged
Google Developer documentation style, technical-writing, and product-management pages before
committing their prose.

### Complete and maintain the source inventory

**Priority:** P2

The manifest is a curated list, not an exhaustive inventory of Google-authored guides. Define the
source acceptance checklist, add an upstream revision check, and record when a guide is added,
rejected, or left catalog-only. Model the R guide's combined CC BY 3.0 and CC BY-SA 2.0 terms before
generating it.

## Content fidelity

### Preserve non-text navigation

**Priority:** P2

Decide whether to mirror permitted upstream image assets or mechanically rewrite relative image
and cross-document links to pinned upstream URLs. Version 0.1 omits them.

## Completed

- Removed unsupported local-only and global project-install branches.
- Shared one checked tree-hashing implementation between user installs and evaluations.
- Replaced tests for unreachable branches with install and tree-boundary tests.
