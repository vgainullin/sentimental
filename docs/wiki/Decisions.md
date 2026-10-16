# Decisions

Newest first. One line of context, the decision, and what would make us revisit it.

| Date | Decision | Why | Revisit if |
|---|---|---|---|
| 2026-10 | Ponytail review runs in Actions via OpenRouter and gates PRs | AGENTS.md §11 requires a clean review; the authoring sessions can't load plugins, CI can | OpenRouter stops supporting Claude Code, or an Anthropic key is added |
| 2026-10 | `mypy --strict` instead of pyright strict | pyright strict rejects pandas row access throughout; AGENTS.md allows either | pandas ships complete typing for `itertuples` |
| 2026-10 | torch locked from PyPI (CUDA wheels) | The PyTorch CPU index wasn't reachable when the lock was made | embed-cpu install time matters |
| 2026-10 | GROBID unreachable is an error, not a fallback | A plain-text fallback silently drops every citation context (AGENTS.md: no silent fallbacks) | — |
| 2026-10 | Shard by author in Actions; state in R2 per shard | Parallel and free on a public repo; jobs never share files | Need cross-author dedup before parse, or more than 256 authors (matrix limit) |
| 2026-10 | R2 for raw data, Hugging Face for derived data | R2 has no egress fees and suits blobs; HF gives versioned, loadable datasets | HF storage limits or costs bite |
| 2026-10 | Chunk embeddings offline with BGE; queries via Workers AI with the same model and CLS pooling | No embedding server to run; parity check guards drift | Workers AI drops or changes the model |
| 2026-10 | Lambda GPU only above a chunk threshold | CPU is fine for small corpora; GPUs cost per hour | Corpus grows so CPU runs exceed Actions' 6-hour limit routinely |
| 2026-10 | GROBID `0.9.1-crf` image in CI | 500 MB vs 8 GB for the full image; fast enough on CPU | Citation-context quality is too low; then use the full image on a GPU host |
| 2026-10 | Own papers only in Vectorize | Search is about the mathematicians' work; keeps cost down | Stance analysis needs searchable citing text |
| 2026-10 | Paid OpenAlex content off by default | Free arXiv and OA PDFs cover most modern math | Coverage of paywalled journals matters more than ~$0.01 per file |
| 2026-10 | Wiki is generated from `docs/wiki/` | Docs reviewed in PRs alongside code; LLM agents read the same text humans do | — |
