# Runbook

## One-time setup

1. **Repo:** public, with Wiki enabled. Create one placeholder wiki page so GitHub creates the wiki's git repo.
2. **Cloudflare:**
   - Create an R2 bucket (for example `math-style-data`) and an R2 API token with Object Read & Write on it.
   - Create an API token with Workers Scripts edit, Workers AI read, and Vectorize edit.
3. **Hugging Face:** a write token. The dataset repo is created private on first push.
4. **OpenAlex:** a free API key, which raises the budget to $1/day.
5. **Lambda Cloud (optional):**
   - An API key.
   - Register an SSH public key named `gh-actions`; its private key becomes `LAMBDA_SSH_PRIVATE_KEY`.
6. **Secrets and variables:** from your own terminal:
   ```bash
   LAMBDA_SSH_KEY_FILE=~/.ssh/lambda_gh scripts/bootstrap_secrets.sh owner/repo
   ```

| Kind | Name | Used by |
|---|---|---|
| secret | `OPENALEX_API_KEY` | harvest |
| secret | `HF_TOKEN` | merge, embed, index, report |
| secret | `CF_ACCOUNT_ID`, `CF_API_TOKEN` | index, deploy-worker |
| secret | `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | shard, merge |
| secret | `SEARCH_TOKEN` | Worker auth |
| secret | `LAMBDA_API_KEY`, `LAMBDA_SSH_PRIVATE_KEY` | embed-lambda, reap |
| secret | `OPENROUTER_API_KEY` | ponytail (PR review gate) |
| var | `HF_DATASET` (for example `you/math-style-data`), `R2_BUCKET`, `VECTORIZE_INDEX` | |
| var | `MSP_MAILTO`, `LAMBDA_SSH_KEY_NAME`, `LAMBDA_INSTANCE_TYPES`, `EMBED_GPU_THRESHOLD` | |

7. **Journal on Pages:** Settings → Pages → Source: GitHub Actions.
8. **Deploy the Worker:** run `deploy-worker` manually once. It creates the Vectorize index and metadata indexes.

## Autopilot (agent PRs merge themselves)

Agents push `agent/<topic>` branches. `autopilot` opens the PR and enables auto-merge. GitHub merges with a merge commit (keeping each commit's SHA for the journal) after the required checks pass: CI and the Ponytail review. PRs that touch `.github/`, `.claude/`, `AGENTS.md`, `CLAUDE.md`, `pyproject.toml`, `.pre-commit-config.yaml`, or `scripts/protected_paths.sh` (including moving them) are opened but left for you to merge, because they change the checks themselves.

One-time per repo, from your terminal (dry run first, then `--apply`):

```bash
export AUTOPILOT_TOKEN=...       # fine-grained PAT; Contents, Pull requests, Workflows: read & write
export OPENROUTER_API_KEY=...
scripts/repo_bootstrap.sh vgainullin/sentimental
scripts/repo_bootstrap.sh vgainullin/sentimental --apply
```

The script stores the PAT in an `autopilot` environment that only `main` may use, so a workflow added on a branch can't read it. One PAT scoped to "All repositories" serves every repo, so another repo only needs the same two commands. The script is portable: copy it with the workflows. Branch protection leaves admins able to push to `main`.

## Add a mathematician

1. `msp resolve "Name" --zbmath-name "Last, First"` locally.
2. Check the candidates (works count, years, topics) and add an entry to `authors.yaml` with a new `key`.
3. Open a PR. After merge, run `pipeline` manually with `authors: <key>`.

## Common operations

| Goal | How |
|---|---|
| Rerun one author | `pipeline` → Run workflow → `authors: tao`. Unchanged files are skipped and cached responses reused. |
| Only re-parse and re-chunk | `stages: parse link chunk` |
| Force GPU or CPU embedding | `embed: lambda` or `embed: cpu` |
| Skip Vectorize upload | untick `index` |
| See what's in the data | wiki [[Data Status|Data-Status]], or `msp status` after `msp sync hf-pull` |
| Query search | `curl -H "Authorization: Bearer $SEARCH_TOKEN" "https://<worker>/search?q=sieve+weights&author=tao"` |
| Rotate a key | Update the secret. Nothing caches keys. |
| Bring the journal up to date | End the session with the historian agent (`AGENTS.md` §10), commit on a branch, merge. |
| Preview a sync | `msp --shard tao sync r2-push --dry-run` |
| Re-run Ponytail on a PR | Actions → ponytail → Run workflow → PR number |
| Make Ponytail required | Settings → Branches → protect `main` → require the `ponytail / review` check |

## When it breaks

| Symptom | Likely cause and fix |
|---|---|
| `plan` fails with "Missing secrets/variables" | Set the listed names (see the table above). |
| Shard: 429 or budget errors from OpenAlex | Daily budget spent. Rerun tomorrow: cached responses make the rerun cheap. |
| Shard: "GROBID did not come up" | Image pull was slow. Parse falls back to plain text with no citation contexts. Rerun with `stages: parse link chunk`. |
| zbMATH records with no MSC or reviews | Field names differ. Run `msp debug-zbmath ai:<code>` and adjust `sources/zbmath.py`. |
| `parity-check` fails | Workers AI changed the model or pooling. **Do not upload.** See [[Known Pitfalls|Known-Pitfalls]]. |
| `embed-lambda`: no capacity | Add more types to `LAMBDA_INSTANCE_TYPES`, or rerun with `embed: cpu`. |
| Wiki publish: "Wiki repo not found" | Enable the wiki and create one page in the UI. |
| `parse` fails with "GROBID not reachable" | Intended: no silent fallback. Rerun once GROBID is up, or pass `--no-grobid` knowingly (no citation contexts). |
| Sync fails with "would replace … pass --overwrite" | Intended. Check with `--dry-run`, then add `--overwrite`. |
| Historian PR shows no CI checks | PRs opened with `GITHUB_TOKEN` don't trigger workflows. Close and reopen the PR, or push an empty commit, to run CI. |
| `ponytail` says "produced no report" | The model call failed or the skill didn't run. Check the run log: OpenRouter credit, model access, or whether `.claude/skills/ponytail-review/` exists on the base branch. |
| A Lambda instance is still running | `reap-gpus` runs every 2 hours. To kill one now, run `python scripts/lambda_gpu.py terminate --id <id>`. |
