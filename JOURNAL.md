# Development journal

## Summary

_Updated: 2026-10-15 · through 46cb70e_

- **State:** The pipeline, Cloudflare search Worker and CI/CD are on `main`. `ci` passes and the journal publishes to Pages. PR #5 (`ci/ponytail-review`) is not merged. It adds the Ponytail PR gate, the vendored skills and the autopilot for agent PRs (`agent-push` → `autopilot`, `scripts/repo_bootstrap.sh`). It changes gate files, so a human must merge it. Nothing has run live: secrets are unset and `wiki` fails. [2026-10-15](journal/2026-10-15-agent-setup.md#autopilot-for-agent-prs)
- **Decisions:**
  - Agents push to `agent/<topic>`, never to `main`. `autopilot` runs `main`'s copy (via `workflow_run`), opens the PR and enables auto-merge with merge commits, so cited SHAs survive. The PAT lives in an `autopilot` environment only `main` can use. PRs that touch gate files wait for a human. [2026-10-15](journal/2026-10-15-agent-setup.md#autopilot-for-agent-prs)
  - The Ponytail gate keeps secrets out of the public comment, reads the last `^VERDICT: (PASS|FAIL)$` line, and pins `anthropic/claude-sonnet-5.5` / `anthropic/claude-haiku-5.5`. [2026-10-15](journal/2026-10-15-agent-setup.md#first-ponytail-review-applied)
  - Four Ponytail skills are vendored in `.claude/skills/` (upstream `84740e3`) because cloud sessions load repo skills but not plugins. CI uses the same copy, and the plugin stays on for local hooks. [2026-10-15](journal/2026-10-15-agent-setup.md#ponytail-skills-vendored)
  - Ponytail review runs in Actions via Claude Code on OpenRouter and gates PRs on `VERDICT: PASS`. [2026-10-15](journal/2026-10-15-agent-setup.md#dependabot-fix-and-ponytail-review-gate)
  - Dependabot uses the `uv` ecosystem so `uv.lock` stays in sync. [2026-10-15](journal/2026-10-15-agent-setup.md#dependabot-fix-and-ponytail-review-gate)
  - One Actions job per author. R2 holds per-shard state; a private HF dataset holds derived data. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - `mypy --strict` for type checking, because pyright strict rejects pandas rows. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - No silent fallbacks (GROBID). Destructive sync needs explicit `--overwrite` and offers `--dry-run`. [2026-10-15](journal/2026-10-15-agent-setup.md#pipeline-and-deployment)
  - Only the journal is published to Pages. [2026-10-15](journal/2026-10-15-agent-setup.md)
- **Results:** 38 pytest pass locally on `ci/ponytail-review` (`ci` on `main` last passed 32 + 5 offline tests). ruff, actionlint and shellcheck are clean. The gate and guard logic pass 9 hand-run samples (not committed). No pipeline metrics yet. [2026-10-15](journal/2026-10-15-agent-setup.md#autopilot-for-agent-prs)
- **Open:**
  - Run `scripts/repo_bootstrap.sh vgainullin/sentimental` as a dry run, then with `--apply`, with `AUTOPILOT_TOKEN` and `OPENROUTER_API_KEY` exported. Add an OpenRouter guardrail that allows only the two pinned slugs. Merge PR #5 by hand. The first `agent/<topic>` push is the live test of autopilot and Ponytail; both are unverified, including the GitHub API calls.
  - `shortcut:` a branch can add a workflow that uses `GITHUB_TOKEN` to enable auto-merge, and required checks run the PR's own workflows. The upgrade is rulesets that require workflows from `main`.
  - Port autopilot and the bootstrap to the `agent_dev` template and other repos.
  - Should fix: move the gate and guard to `scripts/ponytail_gate.sh` with a committed pytest over the 9 samples.
  - Close Dependabot #3 so it reopens via `uv` (uv updater unverified).
  - Create one placeholder wiki page, then rerun `wiki` (failed at Publish; cause unverified).
  - Set the Cloudflare secrets with `scripts/bootstrap_secrets.sh`, run `deploy-worker`, then run `pipeline` for one author.
  - Verify zbMATH fields (`msp debug-zbmath`) and author codes (`msp resolve`).
  - `shortcut:` entries: torch (PyPI lock; Lambda Stack on GPU); vendored Ponytail snapshot `84740e3`.

## Entries

- [2026-10-15: Autopilot for agent PRs](journal/2026-10-15-agent-setup.md#autopilot-for-agent-prs): `agent/<topic>` pushes open a PR and auto-merge via `main`'s `autopilot`; gate files wait for a human; one-command `repo_bootstrap.sh`.
- [2026-10-15: First Ponytail review applied](journal/2026-10-15-agent-setup.md#first-ponytail-review-applied): first `/ponytail-review` on PR #5; secret guard, robust gate, pinned model, one license; second review says Ship.
- [2026-10-15: Ponytail skills vendored](journal/2026-10-15-agent-setup.md#ponytail-skills-vendored): four Ponytail skills committed to `.claude/skills/` for cloud sessions; CI review uses the pinned copy; reverses "not vendored".
- [2026-10-15: Ponytail in cloud sessions](journal/2026-10-15-agent-setup.md#ponytail-in-cloud-sessions): plugins do not load in cloud sessions; Ponytail goes in as four claude.ai skills; `AGENTS.md` row added.
- [2026-10-15: Dependabot fix and Ponytail review gate](journal/2026-10-15-agent-setup.md#dependabot-fix-and-ponytail-review-gate): Dependabot on `uv`; `wiki` path fixed; Ponytail PR gate via OpenRouter (not yet run).
- [2026-10-15: Pipeline merged; first runs on main](journal/2026-10-15-agent-setup.md#pipeline-merged-first-runs-on-main): PR #1 on `main`; `ci`, `journal` pass; `wiki` fails; secrets unset.
- [2026-10-15: Pipeline and deployment](journal/2026-10-15-agent-setup.md#pipeline-and-deployment): pipeline, Worker, CI/CD, wiki; offline checks green.
- [2026-10-15: Agent setup](journal/2026-10-15-agent-setup.md): AGENTS.md, required Ponytail, journal and historian.
