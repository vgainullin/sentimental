# 2026-10-15: Agent setup

Commits: b0801ca..74faaf3

## Changed
- Added `AGENTS.md`: scientific development rules, required Ponytail, terse agent output, definition of done.
- Added `CLAUDE.md` (imports `AGENTS.md`) and `.claude/settings.json` (enables the Ponytail plugin in Claude Code).
- Added the `historian` agent, this journal, and `journal.yml` to publish the journal to GitHub Pages.

## Why
- Ponytail loaded as a plugin, not vendored: avoids double-loading and drift, keeps its review/audit/debt commands. Rejected: copying its rules into `AGENTS.md`.
- Only the journal is published, so code and data never reach Pages.

## Results
- none (no code yet)

## Negative results
- none

## Open
- Pipeline code, environment and tests not started; `AGENTS.md` §5 tooling not yet set up here.
- Journal workflow not yet run on GitHub; needs Pages source set to GitHub Actions (unverified).
- Plugin auto-enable through `.claude/settings.json` not tested (unverified).
