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

## Review must-fix fixes

Commits: a61eba3..2620202 (branch `fix/review-must-fix`, not merged). Also on `main` since the last entry: `d4bfa2a` (`wiki.yml` watches `src/msp/cli.py`), `7cc72df` (Dependabot uses the uv ecosystem so `uv.lock` is updated).

### Changed
- Review of `main` at `5e5f695`: three parallel read-only reviews (Python pipeline; workflows, GPU and Worker; tests against contracts). The main agent checked all five must-fix findings in the code before fixing them. One commit per fix.
- `a61eba3` GPU reaper (`scripts/lambda_gpu.py`, `reap-gpus.yml`, `pipeline.yml`, `embed-lambda.yml`): a run GitHub cannot find counts as finished. Any other lookup failure exits non-zero after reaping what it can. Instances are named `msp-embed-<run>-<epoch>` and are reaped once older than `--max-age` (default 4 h), whatever their status. `--finished-run` lets the pipeline's `reap` job kill its own instance. On failure, `reap-gpus` opens or updates a `gpu-reaper-failure` issue, and `on-failure` now needs `reap`.
- `94a7cf6` R2 (`storage.py`, `provenance.py`, `cli.py`, `pipeline.yml`): sync compares MD5 with single-part ETags, not size alone; uploads are forced single-part up to 4 GiB. The failure path pushes `--new-only`, and tables are pushed with `--overwrite` only on `success()`. `write_table`, `write_array` and sidecars write to `.part` and then rename.
- `5eca370` Linking (`harvest.py`, `citations.py`, `Data-Contracts.md`): a harvest title link needs both years known, and a merged group's years may span at most one (no 1960→1961→1962 chains). Citation title matching uses `token_sort_ratio` and needs both years known and within one.
- `2620202` HTTP (`http.py`, `parse.py`): API keys are redacted from logs and error messages. A dropped download stream or a GROBID timeout fails one paper, not the shard. TEI is written atomically.

### Why
- Reaper: a lookup error used to look the same as "run still active", so GPUs could bill indefinitely. The age cap is the backstop if a runner dies before it reaps.
- R2: comparing size alone missed same-size content changes, and an always-run `--overwrite` let a failed run replace good tables with partial state.
- Linking: `token_set_ratio` scores 100 when one title's words are a subset of the other's. Unknown years, and chained ±1 links, merged distinct papers.
- HTTP: keys could leak into logs and failure issues, and one network error lost a whole shard.

### Results
- Each commit passes ruff, `mypy --strict` and pytest on its own. On `2620202`: 47 pytest pass (up from 32) and 5 Worker tests pass (local, offline).
- The new linking and HTTP tests fail on the pre-fix code (confirmed by running them).
- Mutation run: 9 of 41 single-line mutations were caught by tests. Reported by a reviewer, not re-run (unverified).

### Negative results
- Requiring known years drops title links for records without a year. This trades recall for precision; the recall loss was not measured.
- Ponytail was not available, so `AGENTS.md` §2 was applied by hand. `/ponytail-review` was not run.

### Open
- Should-fix findings not done:
  - The HTTP cache never expires.
  - Rate limits are per process, so 8 parallel shards exceed arXiv's policy.
  - `norm_title` drops non-ASCII characters.
  - Provenance lacks the lockfile hash, model revisions, a dirty-tree flag, and merge inputs.
  - A GROBID non-200 still falls back to PyMuPDF, contrary to the no-fallback decision.
  - Network-error retries have no backoff.
  - The Vectorize index name has drifted.
  - Deploy uses `|| true`.
  - Secrets are set at workflow level.
  - Actions are not SHA-pinned.
  - Tests for profile, NaN handling and merge keys are weak.
  - MSC entropy is documented but not implemented.
- Unverified: no live run (secrets unset), no workflow run on this branch, and actionlint not run locally.
