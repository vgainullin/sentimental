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

## Pipeline merged; first runs on main

Commits: 8733a79..677ec18

### Changed
- `8733a79`: merged `main` (Pages enabled) into `feat/pipeline` to resolve the journal conflict; only `JOURNAL.md` and this file changed.
- `677ec18`: PR #1 merged `feat/pipeline` into `main` (61 files, +7,021/−7), so the pipeline, Worker, workflows, `docs/wiki/` and `.github/dependabot.yml` are now on `main`.

### Why
- Merged `main` into the branch instead of rebasing, so the journal commits already on `main` (`2d40da0`, `d0c9b6d`) keep their SHAs. The reason was not recorded in the commit (unverified).

### Results
- Workflow runs on `677ec18` (GitHub Actions API, 2026-10-16T04:21Z):
  - `ci`: success. Jobs python 3.12, python 3.13, worker, workflows (actionlint + shellcheck) all pass. This is the first run of ruff, `mypy --strict`, pytest and the Worker tests on GitHub runners.
  - `deploy-worker`: success, but every step after "Check secrets" was skipped because Cloudflare secrets are not set (by design).
  - `journal`: success; Pages publishes. The earlier run on `2d40da0` failed because Pages was not yet enabled.
- Dependabot update jobs for pip, npm (`worker/`) and github-actions started on `677ec18`; still running when this entry was written.

### Negative results
- `wiki`: failed at "Publish". Logs need auth to read. Likely cause: the repo wiki has no first page yet, so its git repo does not exist; `scripts/publish_wiki.sh` exits 1 in that case (unverified).

### Open
- Create one placeholder wiki page, then rerun `wiki`.
- Set secrets with `scripts/bootstrap_secrets.sh`, then run `deploy-worker` for real.
- `wiki.yml` trigger path is `msp/cli.py`, but the file is `src/msp/cli.py`, so CLI changes alone will not republish the wiki (reasoned from the diff, not run).

## Dependabot fix and Ponytail review gate

Commits: d4bfa2a..f8c69ff

### Changed
- `d4bfa2a`: `wiki.yml` push path filter `msp/cli.py` → `src/msp/cli.py`.
- `7cc72df`: `.github/dependabot.yml` Python ecosystem `pip` → `uv`, so updates also rewrite `uv.lock`.
- `5e5f695`: PR #4 merged `d4bfa2a` and `7cc72df` (plus the previous journal entry) into `main`.
- `46dea9f` (branch `ci/ponytail-review`): new `.github/workflows/ponytail.yml`. On non-draft same-repo PRs and manual dispatch it runs `anthropics/claude-code-action@v1` through OpenRouter (`ANTHROPIC_BASE_URL=https://openrouter.ai/api`, key from secret `OPENROUTER_API_KEY`), installs plugin `ponytail@ponytail` from `DietrichGebert/ponytail`, asks for `/ponytail:ponytail-review`, posts a sticky PR comment, and fails unless the report's last line is `VERDICT: PASS`. It skips with a warning when the secret is missing. `scripts/bootstrap_secrets.sh` now prompts for the key.
- `f8c69ff`: `docs/wiki/` (Architecture, Cost-Guardrails, Decisions, Known-Pitfalls, Runbook) documents the gate, its cost limits (`--max-turns 40`, 25 min timeout, cancel-in-progress), and how to make it required.

### Why
- Dependabot PR #3 (pip group, 24 updates) changed only `pyproject.toml` (+21/−21), so `uv sync --locked` rejected it. The `uv` ecosystem updates the lockfile as well.
- `AGENTS.md` §0/§11 require `/ponytail-review` on every diff, but the authoring Claude sessions cannot load plugins; CI can. OpenRouter is used because no Anthropic or OpenRouter key was found in the authoring environment (only variable names were checked), and that environment cannot see repo secrets. Revisit if an Anthropic key is added.

### Results
- PR #4: `ci` passed on `d4bfa2a` and `7cc72df`; merged as `5e5f695`.
- Dependabot PR #2 (actions: checkout v4→v7, setup-node, wrangler-action): `ci` passed. wrangler-action was not exercised because `deploy-worker` skips without Cloudflare secrets.
- `ci/ponytail-review`, locally: actionlint clean, shellcheck clean, 32 pytest pass. `ponytail.yml` has not run.

### Negative results
- Dependabot PR #3 failed `ci` at the setup-msp step on Python 3.12 and 3.13: lockfile out of date.

### Open
- Unverified: that Dependabot's uv updater works here (known at its next run); the command name `/ponytail:ponytail-review` and marketplace name `ponytail`; that OpenRouter routing works with `claude-code-action@v1`; that `gh pr comment --edit-last` edits the right comment.
- Set `OPENROUTER_API_KEY`, then make `ponytail / review` a required check on `main`.
- Close Dependabot #3 so it reopens through `uv`.
