"""Cloudflare: push chunk vectors to Vectorize and check embedding parity with Workers AI.

The search Worker embeds queries with Workers AI `@cf/baai/bge-base-en-v1.5`
using `pooling: "cls"`, while chunks are embedded offline with
sentence-transformers' BAAI/bge-base-en-v1.5 (CLS pooling). `check_parity`
proves the two agree before any vectors are uploaded; Workers AI's default
pooling is mean, which would silently degrade search.

Env: CF_ACCOUNT_ID, CF_API_TOKEN.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Callable, Iterator
from typing import Any

import numpy as np
import pandas as pd
import requests

from .config import Config

log = logging.getLogger(__name__)
API = "https://api.cloudflare.com/client/v4/accounts/{acct}"
WORKERS_AI_MODEL = "@cf/baai/bge-base-en-v1.5"
LOCAL_MODEL = "BAAI/bge-base-en-v1.5"


def _auth() -> tuple[str, dict[str, Any]]:
    acct, tok = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
    if not (acct and tok):
        raise SystemExit("CF_ACCOUNT_ID and CF_API_TOKEN must be set")
    return API.format(acct=acct), {"Authorization": f"Bearer {tok}"}


def vector_id(chunk_id: str) -> str:
    """Vectorize ids are capped at 64 bytes; chunk ids are not."""
    return hashlib.sha1(chunk_id.encode()).hexdigest()


def build_vectors(cfg: Config, include_citing: bool = False) -> Iterator[dict[str, Any]]:
    """Yield Vectorize records for every chunk of the mathematicians' own papers."""
    chunks = pd.read_parquet(cfg.table("chunks"))
    ids = pd.read_parquet(cfg.emb_dir / "chunks_ids.parquet")
    X = np.load(cfg.emb_dir / "chunks.npy")
    if (
        len(ids) != len(X)
        or not (ids["chunk_id"].to_numpy() == chunks["chunk_id"].to_numpy()).all()
    ):
        raise SystemExit(
            "chunks.npy is out of date with chunks table; rerun `msp embed --level chunk`"
        )
    if ids["model"].iloc[0] != LOCAL_MODEL:
        raise SystemExit(
            f"chunk embeddings came from {ids['model'].iloc[0]!r}, but the "
            f"Worker queries with {WORKERS_AI_MODEL}; refusing to upload"
        )
    papers = {p.paper_id: p for p in pd.read_parquet(cfg.table("papers")).itertuples()}

    def s(
        x: object, max_bytes: int
    ) -> str:  # clip by UTF-8 bytes: metadata is capped at 10 KiB per vector
        return x.encode()[:max_bytes].decode(errors="ignore") if isinstance(x, str) else ""

    for i, c in enumerate(chunks.itertuples()):
        p = papers.get(c.paper_id)
        if p is None or (p.role != "own" and not include_citing):
            continue
        keys = list(p.author_keys)
        meta = {
            "chunk_id": c.chunk_id,
            "paper_id": c.paper_id,
            "author": keys[0] if keys else "",
            "authors": s(",".join(keys), 256),
            "title": s(p.title, 600),
            "year": int(p.year) if pd.notna(p.year) else 0,
            "section": s(c.section, 240),
            "text": s(c.text, 6000),
        }
        yield {
            "id": vector_id(c.chunk_id),
            "values": [round(float(v), 6) for v in X[i].astype(np.float32)],
            "metadata": meta,
        }


def upsert(
    cfg: Config, index: str, batch: int = 5000, include_citing: bool = False, dry_run: bool = False
) -> int:
    if dry_run:
        n = sum(1 for _ in build_vectors(cfg, include_citing))
        log.info("dry run: would upsert %d vectors into %s", n, index)
        return n
    base, hdr = _auth()
    url = f"{base}/vectorize/v2/indexes/{index}/upsert"
    buf: list[str] = []
    n = 0

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        r = requests.post(
            url,
            data="\n".join(buf).encode(),
            headers={**hdr, "Content-Type": "application/x-ndjson"},
            timeout=300,
        )
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200 or not body.get("success", False):
            raise SystemExit(f"Vectorize upsert failed ({r.status_code}): {r.text[:500]}")
        buf = []

    for rec in build_vectors(cfg, include_citing):
        buf.append(json.dumps(rec, ensure_ascii=False))
        n += 1
        if len(buf) >= batch:
            flush()
    flush()
    log.info("upserted %d vectors into %s", n, index)
    return n


def workers_ai_embed(texts: list[str]) -> np.ndarray:
    base, hdr = _auth()
    r = requests.post(
        f"{base}/ai/run/{WORKERS_AI_MODEL}",
        headers=hdr,
        json={"text": texts, "pooling": "cls"},
        timeout=120,
    )
    r.raise_for_status()
    X = np.asarray(r.json()["result"]["data"], dtype=np.float32)
    out: np.ndarray = X / np.linalg.norm(X, axis=1, keepdims=True)
    return out


def check_parity(
    texts: list[str], local_encode: Callable[[list[str]], np.ndarray], min_cos: float = 0.98
) -> float:
    """Mean cosine between local and Workers AI embeddings of the same texts."""
    A = workers_ai_embed(texts)
    B = local_encode(texts)
    cos = float(np.mean(np.sum(A * B, axis=1)))
    log.info("Workers AI vs local %s: mean cosine %.4f over %d texts", LOCAL_MODEL, cos, len(texts))
    if cos < min_cos:
        raise SystemExit(f"embedding parity check failed: mean cosine {cos:.4f} < {min_cos}")
    return cos
