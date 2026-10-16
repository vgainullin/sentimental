# Development journal

## Summary

_Updated: 2026-10-15 · through 677ec18_

- **State:** Pipeline, Cloudflare search Worker, and CI/CD are on `main` (PR #1). `ci` passes on GitHub runners (Python 3.12 and 3.13, Worker, actionlint, shellcheck), and the journal publishes to Pages. Nothing has run live: secrets are unset and `wiki` fails. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-merged-first-runs-on-main)
- **Decisions:**
  - One Actions job per author; R2 holds per-shard state, a private HF dataset holds derived data. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - `mypy --strict` for §5 type checking (pyright strict rejects pandas rows). [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - No silent fallbacks (GROBID), explicit `--overwrite` and `--dry-run` for destructive sync. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - Only the journal is published to Pages, never the repo. [2026-10-15](journal/2026-10-15-agent-setup.md)
  - Ponytail is loaded as a plugin, not vendored. [2026-10-15](journal/2026-10-15-agent-setup.md)
- **Results:** 32 + 5 offline tests pass locally and in `ci` on `677ec18`; no pipeline metrics yet. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-merged-first-runs-on-main)
- **Open:**
  - Create one placeholder wiki page, then rerun `wiki` (failed at Publish; cause unverified).
  - Set secrets with `scripts/bootstrap_secrets.sh`, run `deploy-worker`, then `pipeline` for one author.
  - Verify zbMATH fields (`msp debug-zbmath`) and author codes (`msp resolve`).
  - `/ponytail-review` on the merged diff; plugin auto-enable still untested.
  - torch `shortcut:` entries (PyPI lock, Lambda Stack on GPU).
  - `wiki.yml` path filter `msp/cli.py` should be `src/msp/cli.py` (reasoned, not run).

## Entries

- [2026-10-15: Pipeline merged; first runs on main](journal/2026-10-15-agent-setup.md#pipeline-merged-first-runs-on-main): PR #1 on `main`; `ci`, `journal` pass; `wiki` fails; secrets unset.
- [2026-10-15: Pipeline and deployment](journal/2026-10-15-agent-setup.md#pipeline-and-deployment): pipeline, Worker, CI/CD, wiki; offline checks green.
- [2026-10-15: Agent setup](journal/2026-10-15-agent-setup.md): AGENTS.md, required Ponytail, journal and historian.
