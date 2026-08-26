# TODOs

## Evaluate the rewritten pack

**Priority:** P1

Run fresh direct-routing probes against the 16 public skills. The saved five-client routing
results used the retired 23-skill committed corpus and do not validate the new descriptions.
Start with one pass, inspect the trajectories, then repeat only the cases that show a concrete
problem.

The current source-excerpt [SlopCodeBench quality run](reports/slopcodebench-quality.md) is
complete. At default effort, the guided arm tied the baseline on hidden correctness and improved
the structure metrics. At `xhigh`, both arms improved, but the guided arm finished three tests
behind its baseline. Run another problem, with repeats, only before making a broader quality claim.

The complete 24-skill metadata list uses 7,664 of Codex's 8,000 fallback characters at the
recorded path. Test per-user installation first; use selected project packs when a deep repository
path or unrelated host skills pushes the list over budget.

## Add cataloged web sources

**Priority:** P2

Create reproducible snapshots and verify licenses for the cataloged Developer Documentation
Style, Technical Writing, and product-management pages before generating them. Model the R
guide's CC BY 3.0 and CC BY-SA 2.0 terms separately.

## Decide how to handle source images and links

**Priority:** P2

The current skills are text-only. If a selected rule depends on an upstream diagram, either mirror
the asset when its license permits that or replace the selection with source text that stands on
its own. Do not ship broken relative links.
