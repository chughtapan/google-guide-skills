# TODOS

## Evaluation

### Run repeated specificity and quality cases

**Priority:** P1

The one-pass full-pack smoke run reported the expected skill for all 115 client/case pairs. Of
those, 69 routes were trace-proven and exact; 46 used verified self-report proxies. Before tuning
a description, run that skill's positive and near-miss training cases with `--repeat 3`. After
tuning, run the frozen validation split with `--repeat 3` once; do not retune on it. Extend quality
rubrics only when they test source-specific claims.

### Reduce startup metadata and large inline skills

**Priority:** P2

The committed pack uses 7,361 of Codex's 8,000 fallback metadata characters at the recorded path.
The Go guide now uses references after OpenClaw omitted its oversized inline form; its follow-up
routing passed 5/5 clients, and a retrospective rescore found no quality regression. The other
large inline skills routed in the one-pass smoke run. Use a routing or quality comparison before
moving another guide; do not shorten source prose.

## Sources

### Add cataloged web sources

**Priority:** P2

Create reproducible snapshots and verify licenses for the cataloged Developer Documentation Style,
Technical Writing, and product-management pages before generating them. Model the R guide's
combined CC BY 3.0 and CC BY-SA 2.0 terms separately. Use the acceptance checklist in
`docs/licensing.md` for every addition.

## Content fidelity

### Preserve non-text navigation

**Priority:** P2

Decide whether to mirror permitted upstream image assets or mechanically rewrite relative image
and cross-document links to pinned upstream URLs. Version 0.1 omits them.
