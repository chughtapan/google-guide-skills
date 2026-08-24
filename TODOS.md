# TODOS

## Evaluation

### Run and tune the cross-agent matrix

**Priority:** P1

Run the 23 full-pack smoke cases across Codex, Claude Code, OpenCode, OpenClaw, and Hermes. Fix
only reproduced routing failures, then run the affected training and validation cases. Record the
resolved models and denominators. Run quality A/Bs for guides whose layout or description changes.

### Reduce startup metadata and large inline skills

**Priority:** P1

The committed pack uses 7,361 of Codex's 8,000 fallback metadata characters at the recorded path.
The Go guide now uses references after OpenClaw omitted its oversized inline form. Use routing and
quality results before moving another guide; do not shorten source prose.

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
