# Development journal

## Summary

_Updated: 2026-10-15 · through 2620202_

- **State:** The pipeline, the Cloudflare search Worker and CI/CD are on `main`, and `ci` passes there. Branch `fix/review-must-fix` fixes the five must-fix review findings (GPU reaper, R2 sync, title linking, HTTP failures and key redaction). It is not merged and its workflows have not run. Nothing has run live because secrets are unset. [2026-10-15](journal/2026-10-15-agent-setup.md#review-must-fix-fixes)
- **Decisions:**
  - Title links and matches need both years known and within one; merged groups span at most one year; matching uses token-sort, not token-set. [2026-10-15](journal/2026-10-15-agent-setup.md#review-must-fix-fixes)
  - A failed run never replaces R2 tables (`--new-only`). The GPU reaper fails closed with a 4 h age cap. [2026-10-15](journal/2026-10-15-agent-setup.md#review-must-fix-fixes)
  - One Actions job per author; R2 holds per-shard state and a private HF dataset holds derived data. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - `mypy --strict` for §5 type checking, because pyright strict rejects pandas rows. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - No silent fallbacks (GROBID); destructive sync needs explicit `--overwrite` and offers `--dry-run`. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - Only the journal is published to Pages, never the repo. Ponytail is loaded as a plugin, not vendored. [2026-10-15](journal/2026-10-15-agent-setup.md)
- **Results:** 47 + 5 offline tests pass locally on `2620202` (`ci` last passed on `677ec18`, with 32 + 5). A reviewer reported that tests catch 9 of 41 mutations (unverified). No pipeline metrics yet. [2026-10-15](journal/2026-10-15-agent-setup.md#review-must-fix-fixes)
- **Open:**
  - Set secrets with `scripts/bootstrap_secrets.sh`, run `deploy-worker`, then `pipeline` for one author. Create a wiki page and rerun `wiki`.
  - Verify zbMATH fields (`msp debug-zbmath`) and author codes (`msp resolve`).
  - Should-fix findings: the HTTP cache never expires; per-process rate limits × 8 shards exceed arXiv's policy; network retries have no backoff.
  - More should-fix: `norm_title` drops non-ASCII; GROBID non-200 still falls back to PyMuPDF; provenance lacks the lockfile hash, model revisions, dirty flag and merge inputs.
  - CI hardening: deploy `|| true`, workflow-level secrets, actions not SHA-pinned, Vectorize index name drift. Tests for profile, NaN and merge keys are weak. MSC entropy is not implemented.
  - Recall loss from dropping year-less title links is unmeasured. torch `shortcut:` entries (PyPI lock; Lambda Stack on GPU) remain.

## Entries

- [2026-10-15: Review must-fix fixes](journal/2026-10-15-agent-setup.md#review-must-fix-fixes): five must-fix findings fixed on `fix/review-must-fix`; 47 + 5 tests pass; should-fix list open.
- [2026-10-15: Pipeline merged; first runs on main](journal/2026-10-15-agent-setup.md#pipeline-merged-first-runs-on-main): PR #1 on `main`; `ci`, `journal` pass; `wiki` fails; secrets unset.
- [2026-10-15: Pipeline and deployment](journal/2026-10-15-agent-setup.md#pipeline-and-deployment): pipeline, Worker, CI/CD, wiki; offline checks green.
- [2026-10-15: Agent setup](journal/2026-10-15-agent-setup.md): AGENTS.md, required Ponytail, journal and historian.
