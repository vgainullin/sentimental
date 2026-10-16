# Cost guardrails

Prices as checked in October 2026. Re-check before scaling up.

| Resource | Price | Guardrail in code |
|---|---|---|
| OpenAlex list/filter | ~$0.10 per 1,000 calls | Disk cache in R2; reruns are free. 100 results per page. |
| OpenAlex search | ~$1 per 1,000 | Only `msp resolve` uses it. |
| OpenAlex content (PDF or TEI) | $0.01 per file | **Off by default** (`use_openalex_content`); free PDFs are tried first. |
| OpenAlex free key | $1/day budget | A 429 stops the run; cached work is saved by the `always()` R2 push. |
| arXiv, zbMATH | free | Rate limits of 3.1 s and 0.5 s per request, set in `Config.rate_limits`. |
| GitHub Actions | free on a public repo | `max-parallel: 8`; job timeouts of 340 min or less; `cancel-in-progress: false`, so no wasted half-runs. |
| Lambda GPU | billed per hour while running | Terminate in `if: always()`; `reap-gpus` every 2 h; job timeout 180 min; only above `EMBED_GPU_THRESHOLD` chunks. |
| Workers AI | per-neuron pricing | Only query embeddings plus 16 texts per parity check. |
| Vectorize | per stored and queried dimension | Own papers only by default; upserts replace rather than duplicate (sha1 ids). |
| R2 | storage only, no egress fees | PDFs are the bulk; `.part` files are never uploaded. |
| Hugging Face | private dataset storage | Only tables and embeddings, never PDFs. |
| Anthropic API (historian) | per token | Runs only when commits lack journal entries; `--max-turns 30`; 20-minute timeout; skipped for journal commits so it can't loop. |

**Rule for agents:** any new paid call needs a cache or an idempotency key, a
config switch that defaults to off, and a row in this table.
