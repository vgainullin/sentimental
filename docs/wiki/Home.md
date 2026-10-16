# math-style-pipeline

Harvests mathematicians' papers, mines the full text, and builds embeddings and
a search API. These feed a fox/hedgehog style analysis: breadth across fields,
semantic dispersion and coherence, and how citing papers describe the work.

**If you are an LLM coding agent, read `AGENTS.md` in the repo, then [[Agent Guide|Agent-Guide]], before touching anything.**

| Page | Read it when |
|---|---|
| [[Agent Guide|Agent-Guide]] | Before any change. Rules, invariants, workflow. |
| [[Architecture]] | You need the big picture or where something runs. |
| [[Data Contracts|Data-Contracts]] | You read or write any table, embedding, or vector. |
| [[Runbook]] | Setting up, running, rerunning, or fixing the pipeline. |
| [[Cost Guardrails|Cost-Guardrails]] | Anything that calls a paid API or starts a GPU. |
| [[Known Pitfalls|Known-Pitfalls]] | Something behaves strangely. Check here first. |
| [[Methodology]] | You need the scientific intent behind a feature. |
| [[Decisions]] | You want to know why it is built this way. |
| [[Glossary]] | A term is unfamiliar. |
| [[CLI Reference|CLI-Reference]] | Generated from the code on every push. |
| [[Data Status|Data-Status]] | Generated after every pipeline run. |
| [Development journal](https://vgainullin.github.io/sentimental/) | Why things changed, with evidence. Kept by the historian agent (`AGENTS.md` §10), published to GitHub Pages. |

Pages are written in `docs/wiki/` in the repo and published by the `wiki`
workflow. **Edit them in the repo, never in the wiki UI**: the next publish
overwrites wiki-side edits.
