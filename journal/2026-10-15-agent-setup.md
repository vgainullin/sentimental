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
- Journal workflow: first run failed at deploy because Pages was off.
- Plugin auto-enable through `.claude/settings.json` not tested (unverified).

## Pages enabled

Commits: 2d40da0

### Changed
- Pages source set to GitHub Actions in repo settings (done on mobile Safari; the iOS app has no Pages setting).

### Open
- Confirm the journal workflow publishes on this commit.

## Pipeline and deployment

Commits: d9e2ab8..77982d3

### Changed
- `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`: uv project, ruff, `mypy --strict`, pytest + hypothesis, pre-commit (`AGENTS.md` §5).
- `src/msp/`: harvest (OpenAlex, zbMATH, arXiv) → fetch → parse (GROBID) → link citation contexts → chunk → embed (SPECTER2 papers, BGE chunks) → profile → search. Every table and embedding is written with a `.meta.json` sidecar (input sha256, git SHA, seed, params).
- `worker/`: Cloudflare Worker search API (Vectorize + Workers AI BGE, CLS pooling, bearer token).
- `.github/workflows/`: `ci`, `pipeline` (one job per author, GROBID service, R2 state, HF dataset, CPU or Lambda GPU embedding, Vectorize upload, failure issue), `embed-lambda`, `reap-gpus`, `deploy-worker`, `wiki`.
- `docs/wiki/`: developer guide published to the repo wiki; it points to this journal for history.

### Why
- One Actions job per author with per-shard R2 state: parallel, no shared files. Rejected: a single long job (6 h limit).
- `mypy --strict` over pyright strict: pyright strict rejects pandas row access throughout; §5 allows either.
- GROBID unreachable raises instead of falling back to plain text: the fallback silently drops every citation context (§4).
- R2 sync and Vectorize upsert need `--overwrite` and offer `--dry-run` (§7).
- Chunks of 250 words, down from 350: stay under BGE's 512-token limit so nothing is truncated silently.
- Dropped a parallel history system (`docs/journal/`, wiki history pages, CI historian) in favour of this journal and `AGENTS.md` §10.

### Results
- Tests: 32 pytest pass (Python 3.13, offline, seed 0; includes 5 hypothesis properties) and 5 Worker tests pass (Node 22).
- Static checks: ruff, `mypy --strict` (20 files), actionlint, and shellcheck are clean.
- No pipeline metrics yet: no live run.

### Negative results
- Bugs caught by tests, all fixed with regression tests:
  - Parquet NaN is truthy, so every DOI-less citation matched one paper.
  - Vectorize metadata was clipped by characters, not bytes (12,237 B > 10 KiB limit).
- pyright strict was not viable without pandas typing, hence mypy.
- The PyTorch CPU index was unreachable when the lock was made, so torch is locked from PyPI (`shortcut:` in `pyproject.toml`).

### Open
- Unverified: live behaviour of every external API, zbMATH field names and author codes, the Lambda API base URL, and all workflows on GitHub.
- Ponytail was unavailable in the authoring environment; §2 was applied by hand and `/ponytail-review` was not run.
- `shortcut:` GPU host uses Lambda Stack torch, not the locked torch (`embed-lambda.yml`).
- Title-based record merging may join distinct papers with generic titles.
