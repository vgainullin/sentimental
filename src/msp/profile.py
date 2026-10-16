"""Per-author similarity features from paper embeddings (the 'similarity branch').

* dispersion: mean pairwise cosine distance among the author's papers
  (semantic breadth, independent of the MSC taxonomy).
* coherence: mean cosine similarity between consecutive papers in date order
  (a sustained program scores high even when it crosses fields).
* centroid: mean direction, saved for author-author similarity and clustering.

Authors with fewer than `min_papers` embedded papers get NaN; these features are
noisy below ~20 papers (see the precision analysis).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .provenance import write_table


def author_features(cfg: Config, min_papers: int = 5) -> pd.DataFrame:
    papers = pd.read_parquet(cfg.table("papers"))
    ids = pd.read_parquet(cfg.emb_dir / "papers_ids.parquet")
    X = np.load(cfg.emb_dir / "papers.npy").astype(np.float32)
    pos = {pid: i for i, pid in enumerate(ids["paper_id"])}
    own = papers[(papers["role"] == "own") & papers["paper_id"].isin(pos)]
    rows, cents = [], {}
    for a in cfg.authors:
        sub = own[own["author_keys"].apply(lambda ks, k=a.key: k in list(ks))]
        sub = sub.sort_values("year", na_position="last")
        n = len(sub)
        row = {
            "author_key": a.key,
            "name": a.name,
            "birth_year": a.birth_year,
            "n_papers": n,
            "dispersion": np.nan,
            "coherence": np.nan,
        }
        if n >= min_papers:
            V = X[[pos[p] for p in sub["paper_id"]]]
            S = V @ V.T
            iu = np.triu_indices(n, 1)
            row["dispersion"] = float(np.mean(1 - S[iu]))
            row["coherence"] = float(np.mean(np.sum(V[1:] * V[:-1], axis=1)))
            c = V.mean(0)
            cents[a.key] = c / np.linalg.norm(c)
        rows.append(row)
    feats = pd.DataFrame(rows)
    write_table(
        cfg, "author_similarity", feats, inputs=["papers"], params={"min_papers": min_papers}
    )
    if cents:
        keys = list(cents)
        C = np.vstack([cents[k] for k in keys])
        sim = (
            pd.DataFrame(C @ C.T, index=keys, columns=keys).rename_axis("author_key").reset_index()
        )
        write_table(
            cfg, "author_sim_matrix", sim, inputs=["papers"], params={"min_papers": min_papers}
        )
    return feats
