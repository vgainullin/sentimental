"""Per-author shards and merging them.

CI runs one job per author, each with its own data dir (data/shards/<key>), so
jobs never write the same files. `merge` combines every shard's tables into
data/tables for the cross-author stages (embed, profile, index).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .config import Config
from .provenance import write_table

log = logging.getLogger(__name__)

# table -> columns that identify a row (for de-duplication across shards)
KEYS = {
    "papers": ["paper_id"],
    "fetch_status": ["paper_id"],
    "parse_status": ["paper_id"],
    "sections": ["paper_id", "section_idx"],
    "references": ["paper_id", "ref_id"],
    "contexts": ["paper_id", "ref_id", "sentence"],
    "citation_contexts": ["citing_paper_id", "cited_paper_id", "author_key", "sentence"],
    "chunks": ["chunk_id"],
    "cite_edges": ["citing_openalex_id", "cited_openalex_id", "author_key"],
}


def shard_config(cfg: Config, key: str) -> Config:
    """Restrict cfg to one author and give it a private data dir."""
    match = [a for a in cfg.authors if a.key == key]
    if not match:
        raise SystemExit(f"unknown author key {key!r}; known: {[a.key for a in cfg.authors]}")
    cfg.authors = match
    cfg.root_dir = Path(cfg.data_dir)
    cfg.data_dir = cfg.root_dir / "shards" / key
    return cfg


def _merge_papers(df: pd.DataFrame) -> pd.DataFrame:
    """One row per paper_id: union author_keys, 'own' wins over 'citing'."""
    df = df.copy()
    df["author_keys"] = df["author_keys"].apply(lambda x: sorted(set(x)) if x is not None else [])
    keys = df.groupby("paper_id")["author_keys"].apply(lambda s: sorted(set().union(*map(set, s))))
    own = df.groupby("paper_id")["role"].apply(lambda s: "own" if (s == "own").any() else "citing")
    first = df.sort_values("role", key=lambda s: s.ne("own")).drop_duplicates("paper_id")
    first = first.set_index("paper_id")
    first["author_keys"], first["role"] = keys, own
    return first.reset_index()


def merge(cfg: Config) -> dict[str, int]:
    root = Path(cfg.data_dir)
    shard_dirs = sorted(p for p in (root / "shards").glob("*") if (p / "tables").is_dir())
    if not shard_dirs:
        raise SystemExit(f"no shards under {root / 'shards'}")
    cfg.ensure_dirs()
    counts = {}
    for name, key in KEYS.items():
        parts = [
            pd.read_parquet(f)
            for d in shard_dirs
            if (f := d / "tables" / f"{name}.parquet").exists()
        ]
        parts = [p for p in parts if not p.empty]
        if not parts:
            continue
        df = pd.concat(parts, ignore_index=True)
        df = _merge_papers(df) if name == "papers" else df.drop_duplicates(subset=key)
        write_table(cfg, name, df, params={"shards": [d.name for d in shard_dirs]})
        counts[name] = len(df)
    log.info("merged %d shards: %s", len(shard_dirs), counts)
    return counts
