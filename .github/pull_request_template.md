## Summary
<!-- Briefly explain what changes were made and why. Reference tasks if applicable (e.g. feat(T0.3): CI skeleton) -->

## Global Definition of Done Checklist
- [ ] Code compiles and type-checks cleanly:
  - `uv run ruff check .` and `uv run ruff format --check .` pass
  - `uv run mypy` strict passes for touched Python modules
  - `pnpm -r --if-present lint` and `typecheck` pass
- [ ] Unit & integration tests added for new logic and endpoints (coverage ≥ 85% for touched modules)
- [ ] No secrets, unresolved TODOs without ticket references, or commented-out code
- [ ] Public functions/classes have docstrings; non-obvious architecture decisions documented
- [ ] `README.md` or docs updated if setup, configuration, or environment variables changed
- [ ] CI workflow is green on the branch
