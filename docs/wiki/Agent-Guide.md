# Agent guide

**`AGENTS.md` in the repo root is the governing document**: Ponytail, precedence,
scientific rigor, code style, tooling, tests, commits, and output style. This page
adds only what is specific to this project. When the two disagree, AGENTS.md wins.

## Before you change anything

1. Read `AGENTS.md`, this page, [[Data Contracts|Data-Contracts]], and [[Known Pitfalls|Known-Pitfalls]].
2. Set up and run the checks. They are fully offline, with no network, models, or keys:
   ```bash
   uv sync --group dev
   uv run ruff check src tests scripts && uv run ruff format --check src tests scripts
   uv run mypy
   uv run pytest -q
   (cd worker && npm test)
   ```
3. Find the stage you are touching in [[Architecture]] and the tables it reads and writes.

## Project invariants

- **Never commit data.** `data/`, PDFs, TEI, parquet, and `.npy` stay out of git. The repo is public; papers are copyrighted.
- **Secrets travel in `secret_params`**, which keeps them out of cache keys and logs. Tests assert this.
- **Paid calls never run in tests.** Use the fakes in `tests/` (FakeS3, fake Lambda session, monkeypatched `requests`).
- **Treat parquet values as possibly NaN.** Missing strings come back as truthy `NaN`. Use `isinstance(x, str)` or `pd.notna(x)`. This has caused two real bugs.
- **Write derived artifacts through `provenance.write_table` / `write_array`.** Never call `to_parquet` or `np.save` directly. The sidecar records input hashes, the git SHA, the seed, and parameters.
- **No silent fallbacks.** `parse` raises if GROBID is requested but unreachable. Choices that change results are recorded in a column (`parse_status.parser`, `papers_ids.text_source`).
- **Overwrites need a flag.** `sync r2-push/r2-pull` refuse to replace files without `--overwrite`, and `vectorize-upsert` refuses without `--overwrite`. Every one has `--dry-run`.
- **Never change the chunk embedding model or pooling alone.** The Worker embeds queries with Workers AI BGE and CLS pooling; `msp parity-check` enforces agreement. Change both sides and re-embed everything.
- **GPUs must always be torn down.** Use an `if: always()` terminate step and an instance name of `msp-embed-<run_id>`, so the reaper can find it.
- **Workflows never use `pull_request_target`** and never interpolate `${{ inputs.* }}` or `${{ github.event.* }}` into `run:`. Pass them through `env:`.
- **Don't edit generated pages** (CLI-Reference, Data-Status) or any page in the wiki UI. Edit `docs/wiki/` in the repo.

## Extending

- **New source:** a client in `src/msp/sources/` returning `empty_record()`-shaped dicts, a parser test from a recorded fixture plus a malformed-record test, and a rate limit in `Config.rate_limits`.
- **New stage:** `stage(cfg) -> DataFrame` writing via `write_table`, a subcommand in `build_parser()`, a key in `shards.KEYS` if it runs per shard, and a row in [[Data Contracts|Data-Contracts]].
- **New workflow:** run `actionlint` locally first.
- **Unsure of an external API's fields?** Parse defensively, add a `debug-*` command, and list it in [[Known Pitfalls|Known-Pitfalls]].

## History

End every session with the historian agent, as `AGENTS.md` §10 requires. The journal (`JOURNAL.md`,
`journal/`) is the record of why things changed; this wiki describes how things are now.
