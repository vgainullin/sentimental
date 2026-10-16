# Known pitfalls

Things that have bitten this project or are unverified. Add to this page when you find a new one.

## Verified bugs (fixed, with tests)
- **NaN is truthy.** Parquet stores missing strings as NaN, so `if doi:` was true for missing DOIs. Every citation without a DOI then "matched" the same paper. Use `isinstance(x, str)`. (`citations.py`, `embed.paper_texts`, `fetch`, `parse`)
- **Vectorize metadata limit is in bytes, not characters.** Non-ASCII text (Greek, accents) is 2–4 bytes per character. Clip with `.encode()[:n]`.
- **Vectorize ids are capped at 64 bytes.** Chunk ids can be longer, so the vector id is sha1(chunk_id).
- **GitHub expressions:** `inputs.index` is empty on scheduled runs. Conditions use `github.event_name == 'schedule' || inputs.index`.
- **YAML:** a `run:` line containing `": "` inside quotes breaks parsing. actionlint catches this in CI.
- **Type checking:** pyright strict rejects pandas row access (`itertuples()` rows are typed `tuple[Any, ...]`), so the repo uses `mypy --strict`, which AGENTS.md allows as the alternative.

## Embedding parity
- Workers AI BGE defaults to **mean pooling**, but sentence-transformers BGE uses **CLS**. The Worker passes `pooling: "cls"`, and `msp parity-check` (cosine ≥ 0.98 on 16 texts) blocks uploads if they ever diverge.
- BGE truncates at 512 tokens. Chunks are 250 words (~350–400 tokens) so nothing is cut silently. Math-heavy text tokenizes longer, so check before raising `chunk_tokens`.

## Unverified external details (check on first live run)
- **zbMATH API field names** (`msc`, `links`, `editorial_contributions`, `contributors`) are parsed defensively but unconfirmed. Run `msp debug-zbmath ai:<code>`.
- **zbMATH author codes** in `authors.yaml` follow the `lastname.firstname` pattern but are unverified.
- **Lambda Cloud API base URL** defaults to `https://cloud.lambdalabs.com/api/v1`. Lambda has been moving to lambda.ai, so set `LAMBDA_API_BASE` if it changes.
- **OpenAlex coverage before ~1950 is thin.** zbMATH (back to 1868) is the main source for historical figures.

## GitHub Actions
- The GPU host installs locked versions of everything except torch and CUDA, which come from Lambda Stack (a recorded `shortcut:`). Embedding logs print the torch and CUDA versions.

## Ponytail in CI
- Claude Code runs through OpenRouter (`ANTHROPIC_BASE_URL=https://openrouter.ai/api`). OpenRouter only guarantees Claude Code with the Anthropic first-party provider, so set Anthropic as the top provider in OpenRouter.
- The review is pinned to `anthropic/claude-sonnet-5.5` (background tasks: `anthropic/claude-haiku-5.5`). Allow exactly these two slugs in the OpenRouter key's guardrail; change them in `ponytail.yml` and the guardrail together.
- The model's report goes to a public PR comment. The workflow keeps git credentials off disk, scopes `GH_TOKEN` to the steps that call `gh`, and refuses to post a report containing the OpenRouter key or the GitHub token.
- The review uses the committed skill `/ponytail-review` from `.claude/skills/`. On PRs, claude-code-action restores `.claude/` from the base branch, so a PR can't alter the skill that reviews it.
- Locally, the plugin and the committed skills both load, so Ponytail appears twice (`ponytail-review` and `ponytail:ponytail-review`). Same text, harmless; use either.
- `shortcut:` vendored skills are a snapshot of upstream `84740e3`. To update: copy `skills/{ponytail,ponytail-review,ponytail-audit,ponytail-debt}/SKILL.md` from a newer upstream commit, keep `.claude/skills/LICENSE-ponytail`, and record the commit in the journal.

## Data quality
- Title-based merging can join different papers with the same generic title in the same year. Spot-check `papers` for authors with common titles ("On a theorem of…").
- PDF text garbles mathematics, so formulas become `⟨math⟩`. A LaTeX OCR model (Nougat or Marker) is the upgrade path.
- `author` metadata in Vectorize holds only the first author key. Coauthored papers by two tracked mathematicians are filterable by the first one only. `authors` holds all keys but isn't indexed.
