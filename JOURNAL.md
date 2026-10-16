# Development journal

## Summary

_Updated: 2026-10-15 · through f8c69ff_

- **State:** Pipeline, Cloudflare search Worker, and CI/CD are on `main`. `ci` passes on GitHub runners, and the journal publishes to Pages. PR #4 (`5e5f695`) fixed the `wiki` path filter and moved Dependabot to `uv`. The Ponytail PR gate (`ponytail.yml`) is on `ci/ponytail-review` and has not run. Nothing has run live: secrets are unset and `wiki` fails. [2026-10-15](journal/2026-10-15-agent-setup.md#dependabot-fix-and-ponytail-review-gate)
- **Decisions:**
  - Ponytail review runs in Actions via Claude Code on OpenRouter and gates PRs on `VERDICT: PASS`. [2026-10-15](journal/2026-10-15-agent-setup.md#dependabot-fix-and-ponytail-review-gate)
  - Dependabot uses the `uv` ecosystem so `uv.lock` stays in sync. [2026-10-15](journal/2026-10-15-agent-setup.md#dependabot-fix-and-ponytail-review-gate)
  - One Actions job per author; R2 holds per-shard state, a private HF dataset holds derived data. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - `mypy --strict` for §5 type checking (pyright strict rejects pandas rows). [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - No silent fallbacks (GROBID), explicit `--overwrite` and `--dry-run` for destructive sync. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - Only the journal is published to Pages, never the repo. [2026-10-15](journal/2026-10-15-agent-setup.md)
  - Ponytail is loaded as a plugin, not vendored. [2026-10-15](journal/2026-10-15-agent-setup.md)
- **Results:** 32 + 5 offline tests pass in `ci`; 32 pytest pass locally on `f8c69ff`; no pipeline metrics yet. [2026-10-15](journal/2026-10-15-agent-setup.md#dependabot-fix-and-ponytail-review-gate)
- **Open:**
  - Set `OPENROUTER_API_KEY`, make `ponytail / review` required; plugin command name and OpenRouter routing unverified.
  - Close Dependabot #3 so it reopens via `uv` (uv updater unverified).
  - Create one placeholder wiki page, then rerun `wiki` (failed at Publish; cause unverified).
  - Set secrets with `scripts/bootstrap_secrets.sh`, run `deploy-worker`, then `pipeline` for one author.
  - Verify zbMATH fields (`msp debug-zbmath`) and author codes (`msp resolve`).
  - torch `shortcut:` entries (PyPI lock, Lambda Stack on GPU).

## Entries

- [2026-10-15: Dependabot fix and Ponytail review gate](journal/2026-10-15-agent-setup.md#dependabot-fix-and-ponytail-review-gate): Dependabot on `uv`; `wiki` path fixed; Ponytail PR gate via OpenRouter (not yet run).
- [2026-10-15: Pipeline merged; first runs on main](journal/2026-10-15-agent-setup.md#pipeline-merged-first-runs-on-main): PR #1 on `main`; `ci`, `journal` pass; `wiki` fails; secrets unset.
- [2026-10-15: Pipeline and deployment](journal/2026-10-15-agent-setup.md#pipeline-and-deployment): pipeline, Worker, CI/CD, wiki; offline checks green.
- [2026-10-15: Agent setup](journal/2026-10-15-agent-setup.md): AGENTS.md, required Ponytail, journal and historian.
