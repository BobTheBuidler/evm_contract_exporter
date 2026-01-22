# Agent Requirements

All agents must follow these rules:

1) Fully test your changes before submitting a PR (run the full suite or all relevant tests).
2) PR titles must be descriptive and follow Conventional Commits-style prefixes:
   - Common: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`, `perf:`
   - Support titles: `fix(docs):`, `fix(benchmarks):`, `fix(cicd):`
3) If you touch ypricemagic-driven price lookups or related docs, keep the `y.stuck?` logger guidance accurate (DEBUG-only, 5-minute interval) so long-running calls can be diagnosed.
4) If the branch you're assigned to work on is from a remote (ie origin/master or upstream/awesome-feature) you must ensure you fetch and pull from the remote before you begin your work.
5) Commit messages must follow the same Conventional Commits-style prefixes and include a short functional description plus a user-facing value proposition.
6) PR descriptions must include Summary, Rationale, and Details sections.
7) Run relevant Python tests for changes (pytest/unittest or the repo's configured runner).
8) Follow formatting/linting configured in pyproject.toml, setup.cfg, tox.ini, or ruff.toml.
9) Update dependency lockfiles when adding or removing Python dependencies.
10) When adding or refactoring async RPC/price-fetching code, keep or add `y._decorators.stuck_coro_debugger` so the `y.stuck?` DEBUG logger continues emitting "still executing" messages at the default 5-minute interval (via `a_sync.debugging.stuck_coro_debugger`).
11) Maximize the use of caching in GitHub workflow files to minimize run duration.
12) Use one of `paths` or `paths-ignore` in every workflow file to make sure workflows only run when required.

Reference: https://www.conventionalcommits.org/en/v1.0.0/
