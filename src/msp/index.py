"""Vector search over paper or chunk embeddings (FAISS if installed, else NumPy)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config


class VectorIndex:
    def __init__(self, X: np.ndarray):
        self.X = np.ascontiguousarray(X, dtype=np.float32)
        try:
            import faiss

            self.faiss = faiss.IndexFlatIP(self.X.shape[1])  # cosine on unit vectors
            self.faiss.add(self.X)
        except ImportError:
            self.faiss = None

    def search(
        self, q: np.ndarray, k: int = 10, mask: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        q = np.ascontiguousarray(q.reshape(1, -1), dtype=np.float32)
        if mask is not None or self.faiss is None:
            s = self.X @ q[0]
            if mask is not None:
                s = np.where(mask, s, -np.inf)
            idx = np.argsort(-s)[:k]
            return idx[np.isfinite(s[idx])], s[idx][np.isfinite(s[idx])]
        s, idx = self.faiss.search(q, k)
        return idx[0], s[0]


def search(
    cfg: Config,
    query: str,
    k: int = 10,
    level: str = "chunk",
    author: str | None = None,
    fake: bool = False,
) -> pd.DataFrame:
    from .embed import chunk_embedder, paper_embedder

    papers = pd.read_parquet(cfg.table("papers"))
    ids = pd.read_parquet(cfg.emb_dir / f"{level}s_ids.parquet")
    X = np.load(cfg.emb_dir / f"{level}s.npy")
    emb = (chunk_embedder if level == "chunk" else paper_embedder)(cfg, fake)
    qv = emb.encode([query], query=True)[0]
    meta = ids.merge(
        papers[["paper_id", "title", "year", "author_keys", "role"]], on="paper_id", how="left"
    )
    mask = None
    if author:
        mask = meta["author_keys"].apply(lambda ks: author in list(ks)).to_numpy()
    idx, scores = VectorIndex(X).search(qv, k, mask)
    out = meta.iloc[idx].copy()
    out["score"] = np.round(scores, 3)
    if level == "chunk":
        chunks = pd.read_parquet(cfg.table("chunks"))[["chunk_id", "section", "text"]]
        out = out.merge(chunks, on="chunk_id", how="left")
        out["text"] = out["text"].str.slice(0, 300)
    return out.reset_index(drop=True)
