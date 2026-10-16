# Data contracts

Every table is parquet under `data/tables/` (per shard: `data/shards/<key>/tables/`).
**Missing values are NaN or None. Never test them for truthiness.**

Every table and embedding file has a sidecar `<file>.meta.json`: its sha256, the git SHA, the seed, parameters, and the sha256 of each input table. Write through `provenance.write_table` / `write_array`.

## papers
One row per merged work. Producer: `harvest` (per shard), `merge` (union).

| Column | Type | Notes |
|---|---|---|
| `paper_id` | str | OpenAlex `W…`, else `zbl-<id>`, else `arxiv-<id with / → _>`. Stable. |
| `title`, `abstract` | str? | Abstract prefers arXiv over the OpenAlex reconstruction. |
| `year` | int? | |
| `doi` | str? | Lowercase, no `https://doi.org/`. |
| `arxiv_id` | str? | No version suffix. |
| `openalex_id`, `zbmath_id`, `zbl` | str? | |
| `msc` | list[str] | MSC codes from zbMATH. Input to MSC entropy. |
| `arxiv_cats` | list[str] | |
| `reviews` | list[str] | zbMATH review texts. License varies, so keep them private. |
| `cited_by_count` | int? | From OpenAlex. |
| `pdf_urls` | list[str] | arXiv first. |
| `openalex_content`, `openalex_tei` | bool | Paid full text is available. |
| `author_keys` | list[str] | Keys from `authors.yaml`. Empty for citing papers. |
| `role` | `own` \| `citing` | `own` wins on merge. |
| `sources` | list[str] | Which of openalex, zbmath, arxiv contributed. |

Merge rule: records link on DOI, arXiv id, or normalized title (at least 12 characters) with both years known and within one. A merged group's years span at most one year, so title links cannot chain.

## fetch_status, parse_status
One row per paper: `pdf_path`, `tei_path`, `via` (host or `openalex-tei`, `cached-*`), and `parser` (`grobid`, `pymupdf`, or None).

## sections
`paper_id, section_idx, head, text, parser`. Formulas are replaced by `⟨math⟩`.

## references, contexts
`references`: `paper_id, ref_id, title, doi, year, first_author` (GROBID only).
`contexts`: `paper_id, ref_id, sentence, section`. The sentence contains the in-text citation.

## citation_contexts
The input to the stance/sentiment model. Producer: `link`.

| Column | Notes |
|---|---|
| `citing_paper_id`, `cited_paper_id` | The cited paper is an own paper. |
| `author_key` | Whose work is cited. |
| `sentence`, `section` | |
| `match` | `doi` or `title:<score>`. Title matches need a token-sort score of 90+ and both years known and within one. |

## chunks
`chunk_id = <paper_id>::<section_idx>::<j>`, `paper_id, section, text, n_words` (at most 250 words, 40 overlap, at least 25 words).

## Embeddings (`data/emb/`)

| File | Shape | Model | Row order |
|---|---|---|---|
| `papers.npy` | float32 [n, 768] | SPECTER2 base + proximity adapter, CLS, L2-normalized | `papers_ids.parquet` (`paper_id, model, text_source` ∈ abstract, review, fulltext, title_only) |
| `chunks.npy` | float16 [n, 768] | `BAAI/bge-base-en-v1.5`, CLS, normalized | `chunks_ids.parquet` (`chunk_id, paper_id, model`), aligned with `chunks` |

The `model` column records what produced the vectors. Vectorize upload refuses anything except BGE base.

## author_similarity, author_sim_matrix
`author_key, name, birth_year, n_papers, dispersion, coherence` (NaN below `min_papers`). The matrix is the cosine similarity of author centroids, indexed by key.

## Vectorize records (index `math-style-chunks`, 768-d, cosine)
- `id`: sha1(chunk_id), because ids are capped at 64 bytes.
- `metadata`: `chunk_id, paper_id, author` (first key, string-indexed), `authors`, `title`, `year` (number-indexed, 0 if unknown), `section`, `text`. Clipped by UTF-8 bytes to stay under 10 KiB.
- Own papers only, unless `--include-citing`.
