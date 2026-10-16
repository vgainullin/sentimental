"""Split section text into overlapping word windows for retrieval embeddings."""

from __future__ import annotations

import pandas as pd

from .config import Config
from .provenance import write_table


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = max(1, size - overlap)
    out = []
    for start in range(0, len(words), step):
        out.append(" ".join(words[start : start + size]))
        if start + size >= len(words):
            break
    return out


def chunk_all(cfg: Config) -> pd.DataFrame:
    secs = pd.read_parquet(cfg.table("sections"))
    rows = []
    for s in secs.itertuples():
        for j, txt in enumerate(chunk_text(s.text, cfg.chunk_tokens, cfg.chunk_overlap)):
            if len(txt.split()) < 25:  # drop scraps (captions, stray lines)
                continue
            rows.append(
                {
                    "chunk_id": f"{s.paper_id}::{s.section_idx}::{j}",
                    "paper_id": s.paper_id,
                    "section": s.head,
                    "text": txt,
                    "n_words": len(txt.split()),
                }
            )
    df = pd.DataFrame(rows)
    write_table(
        cfg,
        "chunks",
        df,
        inputs=["sections"],
        params={"chunk_tokens": cfg.chunk_tokens, "chunk_overlap": cfg.chunk_overlap},
    )
    return df
