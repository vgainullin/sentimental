# Glossary

| Term | Meaning here |
|---|---|
| Fox / hedgehog | Berlin's split: many ideas and breadth (fox) versus one big idea pursued deeply (hedgehog). |
| MSC | Mathematics Subject Classification, the field codes zbMATH assigns to each paper. |
| Fox score / MSC entropy | Normalized Shannon entropy of a person's papers across MSC fields: 0 means one field, 1 means evenly spread. |
| Dispersion | Mean pairwise cosine distance between a person's paper embeddings. |
| Coherence | Mean cosine similarity between consecutive papers in date order. |
| Citation context | The sentence in a citing paper that contains the in-text citation of a work. |
| Stance | How a citation context treats the cited work: uses, extends, praises, critiques. |
| Shard | One author's slice of the pipeline: `data/shards/<key>/` locally, `shards/<key>/` in R2. |
| Own / citing | `role` of a paper: written by a tracked mathematician, or harvested because it cites one. |
| TEI | XML that GROBID produces from a PDF: sections, sentences, references, citation markers. |
| Parity check | Proof that Workers AI and local BGE embeddings agree (mean cosine ≥ 0.98) before vectors are uploaded. |
| Sidecar | `<artifact>.meta.json` holding an artifact's provenance. |
| Historian | The agent that writes `docs/journal/` entries from git history. |
| `shortcut:` | AGENTS.md marker for a known limit and when to upgrade it. |
