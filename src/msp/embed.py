"""Embeddings at two levels.

* Paper level: SPECTER2 (base + proximity adapter) on "title [SEP] abstract".
  Trained on citation structure, so nearby papers are ones that cite alike;
  this is the input for author dispersion/coherence and clustering.
* Chunk level: a general retrieval model (default BGE) on full-text windows,
  for search over the mined PDFs.

`HashEmbedder` is a dependency-free stand-in for tests and dry runs; it is not
semantic and must not be used for analysis.
"""

from __future__ import annotations

import hashlib
import logging
import re
from itertools import pairwise
from typing import Protocol

import numpy as np
import pandas as pd

from .config import Config
from .provenance import write_array

log = logging.getLogger(__name__)

QUERY_PREFIX = {  # retrieval models that expect an instruction on the query side
    "BAAI/bge-base-en-v1.5": "Represent this sentence for searching relevant passages: ",
    "BAAI/bge-small-en-v1.5": "Represent this sentence for searching relevant passages: ",
    "BAAI/bge-large-en-v1.5": "Represent this sentence for searching relevant passages: ",
}


class Embedder(Protocol):
    name: str
    sep: str  # separator between title and body for paper texts

    def encode(self, texts: list[str], query: bool = False) -> np.ndarray: ...


def _l2(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True)
    out: np.ndarray = x / np.clip(n, 1e-12, None)
    return out


class HashEmbedder:
    name = "hash-512"
    sep = " [SEP] "

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def encode(self, texts: list[str], query: bool = False) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            toks = re.findall(r"[a-z0-9]+", (t or "").lower())
            for g in toks + [a + "_" + b for a, b in pairwise(toks)]:
                h = int(hashlib.md5(g.encode()).hexdigest()[:8], 16)
                out[i, h % self.dim] += 1.0 if (h >> 31) & 1 else -1.0
        return _l2(out)


class Specter2Embedder:
    def __init__(
        self, base: str, adapter: str | None, device: str | None = None, batch_size: int = 16
    ):
        import torch
        from transformers import AutoTokenizer

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tok = AutoTokenizer.from_pretrained(base)
        if adapter:
            from adapters import AutoAdapterModel

            self.model = AutoAdapterModel.from_pretrained(base)
            self.model.load_adapter(adapter, source="hf", load_as="proximity", set_active=True)
        else:
            from transformers import AutoModel

            self.model = AutoModel.from_pretrained(base)
        self.model.to(self.device).eval()
        self.batch_size = batch_size
        self.name = f"{base}+{adapter}"
        self.sep = f" {self.tok.sep_token} "

    def encode(self, texts: list[str], query: bool = False) -> np.ndarray:
        outs = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            enc = self.tok(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
                return_token_type_ids=False,
            ).to(self.device)
            with self.torch.no_grad():
                h = self.model(**enc).last_hidden_state[:, 0, :]  # CLS pooling
            outs.append(h.float().cpu().numpy())
        return _l2(np.vstack(outs)) if outs else np.zeros((0, 768), np.float32)


class SentenceEmbedder:
    def __init__(self, model: str, device: str | None = None, batch_size: int = 32) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model, device=device)
        self.prefix = QUERY_PREFIX.get(model, "")
        self.batch_size = batch_size
        self.name = model
        self.sep = " "

    def encode(self, texts: list[str], query: bool = False) -> np.ndarray:
        if query and self.prefix:
            texts = [self.prefix + t for t in texts]
        out: np.ndarray = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 1000,
        ).astype(np.float32)
        return out


def paper_embedder(cfg: Config, fake: bool = False) -> Embedder:
    return HashEmbedder() if fake else Specter2Embedder(cfg.paper_model, cfg.paper_adapter)


def chunk_embedder(cfg: Config, fake: bool = False) -> Embedder:
    return HashEmbedder() if fake else SentenceEmbedder(cfg.chunk_model)


def paper_texts(
    cfg: Config, papers: pd.DataFrame, sep: str = " [SEP] "
) -> tuple[list[str], list[str]]:
    """Build "title [SEP] body" per paper and record which body was used.

    Body preference: abstract, then the first zbMATH review, then the opening 250
    words of the full text. The source goes into papers_ids.text_source so the
    choice is visible downstream, not a silent fallback.
    """
    opening: dict[str, str] = {}
    if cfg.table("sections").exists():
        secs = pd.read_parquet(cfg.table("sections"))
        if not secs.empty:
            first = secs.sort_values("section_idx").groupby("paper_id")["text"].first()
            opening = {k: " ".join(v.split()[:250]) for k, v in first.items()}

    def s(x: object) -> str:  # NaN-safe: parquet stores missing strings as NaN
        return x if isinstance(x, str) else ""

    texts, sources = [], []
    for p in papers.itertuples():
        reviews = list(p.reviews) if p.reviews is not None else []
        candidates = [
            ("abstract", s(p.abstract)),
            ("review", s(reviews[0]) if reviews else ""),
            ("fulltext", opening.get(p.paper_id, "")),
        ]
        source, body = next(((k, v) for k, v in candidates if v), ("title_only", ""))
        texts.append(f"{s(p.title)}{sep}{body}")
        sources.append(source)
    return texts, sources


def embed_papers(cfg: Config, fake: bool = False) -> tuple[pd.DataFrame, np.ndarray]:
    cfg.ensure_dirs()
    papers = pd.read_parquet(cfg.table("papers"))
    emb = paper_embedder(cfg, fake)
    sep = emb.sep
    texts, sources = paper_texts(cfg, papers, sep)
    keep = [i for i, t in enumerate(texts) if len(t.strip()) > len(sep.strip()) + 5]
    X = emb.encode([texts[i] for i in keep])
    ids = papers.iloc[keep][["paper_id"]].reset_index(drop=True)
    ids["model"] = emb.name
    ids["text_source"] = [sources[i] for i in keep]
    params = {"model": emb.name}
    write_array(cfg, cfg.emb_dir / "papers.npy", X, inputs=["papers", "sections"], params=params)
    ids.to_parquet(cfg.emb_dir / "papers_ids.parquet", index=False)
    log.info("embedded %d papers with %s", len(ids), emb.name)
    return ids, X


def embed_chunks(cfg: Config, fake: bool = False) -> tuple[pd.DataFrame, np.ndarray]:
    cfg.ensure_dirs()
    chunks = pd.read_parquet(cfg.table("chunks"))
    emb = chunk_embedder(cfg, fake)
    X = emb.encode(chunks["text"].tolist()).astype(np.float16)  # halves disk/RAM
    ids = chunks[["chunk_id", "paper_id"]].copy()
    ids["model"] = emb.name
    write_array(cfg, cfg.emb_dir / "chunks.npy", X, inputs=["chunks"], params={"model": emb.name})
    ids.to_parquet(cfg.emb_dir / "chunks_ids.parquet", index=False)
    log.info("embedded %d chunks with %s", len(ids), emb.name)
    return ids, X
