# Architecture

## Stages

```
authors.yaml
   │
   ▼  per author (one Actions job each, state in R2 under shards/<key>/)
harvest ──► fetch ──► parse ──► link ──► chunk
OpenAlex    arXiv     GROBID    citing      250-word
zbMATH      OA PDFs   (TEI) or  sentence →  windows
arXiv       OpenAlex  PyMuPDF   own paper
            content
   │
   ▼  once, across authors
merge ──► embed ──────────────► index ──────────► report
shards    SPECTER2 (papers)     parity check,     Data-Status wiki page,
→ HF      BGE (chunks)          Vectorize upsert  author dispersion/coherence
          CPU runner or
          Lambda GPU
```

## Where things run

| Piece | Runs on | Why |
|---|---|---|
| Per-author stages | GitHub Actions matrix, GROBID `0.9.1-crf` as a service container | Free and parallel on a public repo. Each shard has its own data dir, so jobs never collide. |
| Raw state (PDFs, TEI, HTTP cache, shard tables) | Cloudflare R2, private | S3 API, no egress fees. The HTTP cache means paid API calls are never repeated. |
| Merged tables, embeddings | Hugging Face dataset, private | Versioned, easy to load from notebooks. |
| Embeddings, small corpus | Actions CPU runner (CPU torch) | No setup. |
| Embeddings, large corpus | Lambda Cloud GPU via `embed-lambda.yml` | Chosen automatically above `EMBED_GPU_THRESHOLD` chunks. |
| Search API | Cloudflare Worker + Vectorize + Workers AI | Query embeddings come from the same BGE model; no server to run. |
| Docs | GitHub wiki, published from `docs/wiki/` | One source of truth, reviewed in PRs. |
| Journal | GitHub Pages, published from `JOURNAL.md` and `journal/` by the `journal` workflow | Only the journal is public on Pages (`AGENTS.md` §10). |

## Storage layout

R2 mirrors the local data dir exactly:

```
data/                       r2://$R2_BUCKET/
  shards/<key>/               shards/<key>/
    tables/*.parquet            tables/*.parquet
    pdf/  tei/                  pdf/  tei/
    cache/http/                 cache/http/
  tables/*.parquet          → hf://datasets/$HF_DATASET/tables/
  emb/*.npy, *_ids.parquet  → hf://datasets/$HF_DATASET/emb/
```

## Workflows

| Workflow | Trigger | Does |
|---|---|---|
| `ci` | push, PR | ruff, mypy --strict, pytest (3.12, 3.13), Worker tests, actionlint, shellcheck |
| `pipeline` | Mondays 06:17 UTC, manual | Everything above. Opens a `pipeline-failure` issue on failure. |
| `embed-lambda` | called by pipeline, manual | GPU embedding with guaranteed teardown |
| `reap-gpus` | every 2 h | Terminates Lambda instances from finished runs |
| `deploy-worker` | changes under `worker/` | Tests, creates the Vectorize index if needed, deploys the Worker |
| `wiki` | changes under `docs/wiki/` or the CLI | Publishes pages plus a generated CLI reference |
| `journal` | journal changes on main | Publishes the development journal to GitHub Pages |

## Search API

`GET https://math-style-search.<subdomain>.workers.dev/search?q=...&k=10&author=tao&year_min=1990`
with `Authorization: Bearer $SEARCH_TOKEN`. It returns the top chunks with
title, year, section, and a text snippet. `/health` needs no token.
