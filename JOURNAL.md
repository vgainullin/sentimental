# Development journal

## Summary

_Updated: 2026-10-15 · through 77982d3_

- **State:** Pipeline code, Cloudflare search Worker, and CI/CD workflows exist on `feat/pipeline`, and all offline checks pass. Nothing has run live yet. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
- **Decisions:**
  - One Actions job per author; R2 holds per-shard state, a private HF dataset holds derived data. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - `mypy --strict` for §5 type checking (pyright strict rejects pandas rows). [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - No silent fallbacks (GROBID), explicit `--overwrite` and `--dry-run` for destructive sync. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - Only the journal is published to Pages, never the repo. [2026-10-15](journal/2026-10-15-agent-setup.md)
  - Ponytail is loaded as a plugin, not vendored. [2026-10-15](journal/2026-10-15-agent-setup.md)
- **Results:** 32 + 5 offline tests pass; no pipeline metrics yet. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
- **Open:**
  - First live run: secrets, wiki, Pages source, `deploy-worker`, then `pipeline` for one author.
  - Verify zbMATH fields (`msp debug-zbmath`) and author codes (`msp resolve`).
  - `/ponytail-review` on the pipeline diff; plugin auto-enable still untested.
  - torch `shortcut:` entries (PyPI lock, Lambda Stack on GPU).

## Entries

- [2026-10-15: Pipeline and deployment](journal/2026-10-15-agent-setup.md#pipeline-and-deployment): pipeline, Worker, CI/CD, wiki; offline checks green.
- [2026-10-15: Agent setup](journal/2026-10-15-agent-setup.md): AGENTS.md, required Ponytail, journal and historian.
