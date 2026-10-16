# sentimental

Advanced scientific sentiment analysis pipeline. It harvests mathematicians' papers
(OpenAlex, zbMATH, arXiv) and mines the full text: sections, references, and the
sentences in which other papers cite them. It then builds embeddings and a search
API. These are the inputs to a fox/hedgehog style analysis: breadth across fields,
semantic dispersion and coherence, and stance in citation contexts.

**Docs live in the [wiki](../../wiki)**: architecture, data contracts, runbook, cost
guardrails, journal, and development history. Coding agents start with
[`AGENTS.md`](AGENTS.md), then the wiki's Agent Guide.

## Quick start

```bash
uv sync --group dev
cp config.example.yaml config.yaml
uv run pytest -q                                  # offline: no network, models, or keys
docker run --rm -p 8070:8070 grobid/grobid:0.9.1-crf
uv run msp resolve "Terence Tao" --zbmath-name "Tao, Terence"   # confirm ids → authors.yaml
uv run msp --shard tao harvest
uv run msp --shard tao fetch --limit 20
uv run msp --shard tao parse
```

In production, GitHub Actions runs the whole pipeline weekly, one job per author.
State lives in Cloudflare R2, derived tables and embeddings in a private Hugging Face
dataset, embeddings run on Lambda GPUs when the corpus is large, and search is served
by a Cloudflare Worker. See the wiki's Runbook for the secrets to set
(`scripts/bootstrap_secrets.sh` sets them for you).

## Layout

| Path | What |
|---|---|
| `src/msp/` | The pipeline package and `msp` CLI |
| `worker/` | Cloudflare Worker search API |
| `scripts/` | CI helpers: shard planning, Lambda GPUs, wiki publishing, history |
| `docs/wiki/` | Wiki source, published by the `wiki` workflow |
| `docs/journal/` | Development journal, maintained by the historian agent |
| `.claude/agents/historian.md` | The historian agent |
| `authors.yaml` | The mathematicians covered; CI shards by `key` |

MIT licensed.
