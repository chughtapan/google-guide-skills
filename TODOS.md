# TODOS

## Evaluation

### Run and tune the cross-agent matrix

**Priority:** P1

Run invocation controls, full-pack routing, paired `index-ab`, specificity cases, and quality A/Bs
with pinned Codex and Claude model IDs. Tune descriptions and the index against the training split,
then publish one validation run with denominators and costs.

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

## Content fidelity

### Preserve non-text navigation

**Priority:** P2

Decide whether to mirror permitted upstream image assets or mechanically rewrite relative image
and cross-document links to pinned upstream URLs. Version 0.1 omits them.
