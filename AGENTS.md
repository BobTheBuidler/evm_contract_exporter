# Agent Requirements

All agents must follow these rules:

1) Fully test your changes before submitting a PR (run the full suite or all relevant tests).
2) PR titles must be descriptive and follow Conventional Commits-style prefixes:
   - Common: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`, `perf:`
   - Support titles: `fix(docs):`, `fix(benchmarks):`, `fix(cicd):`
3) If you touch ypricemagic-driven price lookups or related docs, keep the `y.stuck?` logger guidance accurate (DEBUG-only, 5-minute interval) so long-running calls can be diagnosed.
4) If the branch you're assigned to work on is from a remote (ie origin/master or upstream/awesome-feature) you must ensure you fetch and pull from the remote before you begin your work.

Reference: https://www.conventionalcommits.org/en/v1.0.0/
