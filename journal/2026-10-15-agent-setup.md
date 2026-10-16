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

## Ponytail in cloud sessions

Commits: 7e2844e

### Changed
- `7e2844e` (branch `ci/ponytail-review`): `AGENTS.md` §0 install table gains a "Claude cloud sessions (web, mobile app, `--cloud`)" row: upload upstream skills `ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt` as claude.ai skills; no hooks, so no `/ponytail <level>` switching; the `ponytail` workflow still reviews every PR.
- Outside the repo: four upload zips (`ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt`), each `SKILL.md` + `LICENSE`, built from upstream `84740e3` and given to the user.

### Why
- Claude Code docs (cloud-environments, settings) say cloud sessions, including ones started from the Claude mobile app, do not install plugins declared through `enabledPlugins`/`extraKnownMarketplaces` in `.claude/settings.json`, and `/plugin` is not available there. They do load skills enabled on claude.ai. That is why the plugin auto-enable has no effect in these sessions.
- The user chose claude.ai skills. Rejected: an environment setup script; committing the skills to `.claude/skills` (that would undo the "not vendored" decision and load Ponytail twice locally).
- `ponytail-gain` and `ponytail-help` were left out: without the plugin, the benchmark display and the hook-level help do nothing useful.

### Results
- Upstream `84740e3` checked: six self-contained skills; none reference scripts, hooks or binaries; no `.exe`/`.dll`; MIT license. Frontmatter checked in all four zips.

### Negative results
- Plugin auto-enable via `.claude/settings.json` does not work in cloud sessions (from the docs, see Why). This resolves the "not tested" item under Agent setup for cloud sessions; local Claude Code is still untested.

### Open
- Unverified: that the user uploaded the zips, that claude.ai accepts them as they are, and that the skills trigger in cloud sessions.
- Cloud sessions cannot switch levels through hooks (by design).
- Open the PR for `ci/ponytail-review`: it carries the CI gate, its docs, and this `AGENTS.md` row.
- Set `OPENROUTER_API_KEY`.

## Ponytail skills vendored

Commits: 6857b08..6d786fa

### Changed
- `6857b08`: upstream Ponytail skills `ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt` copied unchanged into `.claude/skills/<name>/`, each with `SKILL.md` and the MIT `LICENSE`. The `AGENTS.md` §0 cloud-sessions row now reads "nothing to install"; level is fixed at `full` there.
- `702e733`: `ponytail.yml` no longer installs plugin `ponytail@ponytail` from the upstream marketplace, which was unpinned `HEAD`. It asks for the committed `/ponytail-review` skill.
- `6d786fa`: `docs/wiki/` Decisions (new row), Known-Pitfalls (base-branch `.claude/` restore, duplicate local load, `shortcut:` update procedure) and Runbook ("produced no report" row).

### Why
- Reversal of "Ponytail loaded as a plugin, not vendored" ([Agent setup](#agent-setup)) and of the claude.ai-skills choice ([Ponytail in cloud sessions](#ponytail-in-cloud-sessions)). The user chose to commit the skills after learning that cloud sessions (web, mobile) load repo skills but not plugins. The plugin stays enabled in `.claude/settings.json` for local hooks.
- This also closes the CI supply-chain gap from the best-practices research: CI fetched unpinned upstream code. The review now runs a copy pinned by this repo's history.

### Results
- `cmp`: each of the four `SKILL.md` is byte-identical to upstream `84740e3`.
- actionlint clean; 32 pytest pass (local, `ci/ponytail-review`).

### Negative results
- none

### Open
- Unverified: that cloud sessions pick up the committed skills (test in a new mobile session), and that the CI run works end to end.
- Reasoned, not run: claude-code-action restores `.claude/` from the base branch on PRs, so a PR cannot alter the skill that reviews it. As a result, this PR's own Ponytail run would not find the skill, because `main` does not have it yet. The first effective run is the next PR after merge.
- Locally the skills load twice (plugin and repo), with the same text (reasoned).
- `shortcut:` vendored snapshot of `84740e3`; the update procedure is in `docs/wiki/Known-Pitfalls.md`.
- Superseded: "user uploads the four skill zips" is no longer needed for this repo. Uploading stays optional for other repos.

## First Ponytail review applied

Commits: 2bf264b..11129da

### Changed
- `2bf264b`: `ponytail.yml`: `persist-credentials: false` on checkout; `GH_TOKEN` moved from job level to the two `gh` steps; the post step refuses to post a report that contains the OpenRouter key or the GitHub token; the gate takes the last line matching `^VERDICT: (PASS|FAIL)$` instead of the file's last line; model pinned with `--model anthropic/claude-sonnet-5.5` and `ANTHROPIC_DEFAULT_HAIKU_MODEL=anthropic/claude-haiku-5.5`, replacing the `~...-latest` aliases.
- `10cec4d`: four identical skill `LICENSE` copies replaced by one `.claude/skills/LICENSE-ponytail` (−63 lines).
- `11129da`: `docs/wiki/Known-Pitfalls.md` documents the model pin, the OpenRouter guardrail, the secret guard and the new license path.

### Why
- First `/ponytail-review`, on PR #5 (`origin/main...ci/ponytail-review`), found 1 Must fix, 2 Should fix and 1 Nice to have. The user approved all four:
  - Must fix: the model-written report goes to a public PR comment and could contain secrets: the OpenRouter key in the step env, `GH_TOKEN` at job level, and the token kept in `.git/config`. GitHub masks secrets in logs but not in comments.
  - Should fix: the gate failed a clean review if the file ended with a blank line, and it trusted whatever the model wrote last.
  - Should fix: `latest` aliases change verdicts without a commit (`AGENTS.md` §3).
  - Nice to have: duplicate licenses.
- Exact model slugs were read from OpenRouter's public `/api/v1/models` listing.
- Reasoned, not run: an encoded secret could get past the exact-match guard. That gives a same-repo PR author no new capability, because they can already edit the workflow in their PR.

### Results
- The committed Ponytail skills loaded in this Claude Code cloud session: they showed up as available skills once the branch had `.claude/skills/`. This resolves the open "cloud sessions pick up the committed skills" item from [Ponytail skills vendored](#ponytail-skills-vendored).
- The guard and gate shell logic were run by hand on 9 sample reports, and all behaved as intended: trailing blank lines → pass; CRLF → pass; two verdicts → last wins; no verdict → fail; inline mention → fail; leaked key → blocked; leaked GH token → blocked; clean → posts; missing report → placeholder posted. These tests are not committed.
- actionlint clean.
- Second `/ponytail-review` (`07ad90d..HEAD`): no Must fix; 1 Should fix; verdict Ship.
- PR #5 (opened by the user): its `ponytail` check reports success only because it skips without `OPENROUTER_API_KEY`. No live review has run.

### Negative results
- Staged `git mv`/`git rm` changes leaked into the first fix commit. The commit was split before pushing, so each commit holds one change.

### Open
- Should fix from the second review: move the guard and gate into `scripts/ponytail_gate.sh` and commit a pytest over the 9 samples.
- Set `OPENROUTER_API_KEY` and an OpenRouter guardrail that allows exactly `anthropic/claude-sonnet-5.5` and `anthropic/claude-haiku-5.5`.
- Merge PR #5. The first live review runs on the next PR.
