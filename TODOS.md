# TODOS

## Evaluation

### Run and tune the hardened cross-agent matrix

**Priority:** P1

Run explicit controls, exact full-pack smoke routing, paired `index-ab`, repeated representative
specificity, and quality A/Bs with pinned Codex and Claude model IDs. Tune descriptions/index only
against the training split, then publish one frozen validation run with exact denominators and
costs.

## Distribution

### Add an optional OpenAI plugin wrapper

**Priority:** P2

Package the stable host-neutral skill set as a Codex/ChatGPT plugin after trigger descriptions
and skill grouping have passed the cross-agent validation matrix. Keep `skills/` as the portable
source of truth.

## Sources

### Add reproducibly locked web snapshots

**Priority:** P2

Implement stable page enumeration, canonical-content extraction, and content-hash lock updates
for the cataloged Google Developer documentation style, technical-writing, and product-management
pages before committing their prose.

## Content fidelity

### Preserve non-text navigation

**Priority:** P2

Decide whether to mirror permitted upstream image assets or mechanically rewrite relative image
and cross-document links to pinned upstream URLs. Version 0.1 is explicitly text-only.
