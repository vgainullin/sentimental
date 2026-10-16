"""Configuration and on-disk data layout."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Author:
    """One mathematician, with identifiers in each source.

    Fill identifiers after confirming them with `msp resolve`; never trust a
    name match alone, since common names collide across eras.
    """

    key: str  # stable slug, e.g. "hilbert"
    name: str
    birth_year: int | None = None
    openalex_id: str | None = None  # e.g. "A5023888391"
    zbmath_code: str | None = None  # e.g. "hilbert.david"
    arxiv_query: str | None = None  # e.g. 'au:"Tao, Terence"'


@dataclass
class Config:
    data_dir: Path = Path("data")
    seed: int = 0  # the one seed for every RNG in a run
    mailto: str | None = None  # sent as User-Agent contact
    openalex_api_key: str | None = None  # or env OPENALEX_API_KEY
    use_openalex_content: bool = False  # paid: ~$0.01 per PDF/TEI file
    grobid_url: str | None = "http://localhost:8070"
    paper_model: str = "allenai/specter2_base"
    paper_adapter: str | None = "allenai/specter2"
    chunk_model: str = "BAAI/bge-base-en-v1.5"
    chunk_tokens: int = 250  # words; ~350-400 tokens, under BGE's 512 limit
    chunk_overlap: int = 40
    max_works_per_author: int = 2000
    citing_sample_per_work: int = 0  # >0 harvests citing papers for citation contexts
    rate_limits: dict[str, Any] = field(
        default_factory=lambda: {
            "api.openalex.org": 0.12,
            "content.openalex.org": 0.12,
            "api.zbmath.org": 0.5,
            "export.arxiv.org": 3.1,
            "arxiv.org": 3.1,
        }
    )
    authors: list[Author] = field(default_factory=list)
    root_dir: Path | None = None  # top data dir when data_dir points at a shard

    # ---- layout ----
    @property
    def root(self) -> Path:
        """The top data dir; R2 mirrors this layout exactly (shards/<key>/..., tables/...)."""
        return Path(self.root_dir or self.data_dir)

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def pdf_dir(self) -> Path:
        return self.data_dir / "pdf"

    @property
    def tei_dir(self) -> Path:
        return self.data_dir / "tei"

    @property
    def table_dir(self) -> Path:
        return self.data_dir / "tables"

    @property
    def emb_dir(self) -> Path:
        return self.data_dir / "emb"

    def ensure_dirs(self) -> None:
        for d in (self.cache_dir, self.pdf_dir, self.tei_dir, self.table_dir, self.emb_dir):
            d.mkdir(parents=True, exist_ok=True)

    def table(self, name: str) -> Path:
        return self.table_dir / f"{name}.parquet"


def load_config(path: str | Path = "config.yaml", authors_path: str | Path | None = None) -> Config:
    raw: dict[str, Any] = {}
    p = Path(path)
    if p.exists():
        raw = yaml.safe_load(p.read_text()) or {}
    authors_file = authors_path or raw.pop("authors_file", "authors.yaml")
    raw.pop("authors_file", None)
    cfg = Config(**{k: v for k, v in raw.items() if k != "authors"})
    cfg.data_dir = Path(cfg.data_dir)
    # Environment overrides, used by CI so config.yaml can stay generic.
    cfg.openalex_api_key = cfg.openalex_api_key or os.environ.get("OPENALEX_API_KEY") or None
    cfg.mailto = os.environ.get("MSP_MAILTO") or cfg.mailto
    if os.environ.get("MSP_GROBID_URL"):
        cfg.grobid_url = os.environ["MSP_GROBID_URL"]
    if os.environ.get("MSP_USE_OPENALEX_CONTENT"):
        cfg.use_openalex_content = os.environ["MSP_USE_OPENALEX_CONTENT"].lower() == "true"
    if os.environ.get("MSP_CITING_SAMPLE"):
        cfg.citing_sample_per_work = int(os.environ["MSP_CITING_SAMPLE"])
    ap = Path(authors_file)
    if ap.exists():
        cfg.authors = [Author(**a) for a in (yaml.safe_load(ap.read_text()) or [])]
    return cfg
