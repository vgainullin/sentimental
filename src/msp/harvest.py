"""Harvest records per author from all sources and merge them into one papers table.

Records are linked when they share a DOI, an arXiv id, or a normalized title
with publication years within one year. Linking uses union-find so a zbMATH
record (DOI) and an arXiv record (arXiv id) join through an OpenAlex record
that carries both.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any

import pandas as pd

from .config import Config
from .http import Http
from .provenance import write_table
from .sources.arxiv import ArXiv
from .sources.openalex import OpenAlex
from .sources.zbmath import ZbMath

log = logging.getLogger(__name__)


def norm_title(t: str | None) -> str | None:
    if not t:
        return None
    t = re.sub(r"<[^>]+>|\$[^$]*\$", " ", t.lower())  # tags, inline TeX
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return t if len(t) >= 12 else None  # too short to link on safely


class _UF:
    def __init__(self, n: int) -> None:
        self.p = list(range(n))

    def find(self, i: int) -> int:
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, a: int, b: int) -> None:
        self.p[self.find(a)] = self.find(b)


def merge_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """records: source records, each carrying author_keys (set) and role."""
    uf = _UF(len(records))
    seen: dict[tuple[str, str], int] = {}
    by_title: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(records):
        link_keys = (
            ("doi", r.get("doi")),
            ("arxiv", r.get("arxiv_id")),
            (str(r["source"]), r.get("source_id")),
        )
        for k in link_keys:
            if isinstance(k[1], str) and k[1]:
                kk = (k[0], k[1])
                if kk in seen:
                    uf.union(i, seen[kk])
                else:
                    seen[kk] = i
        nt = norm_title(r.get("title"))
        if nt:
            for j in by_title[nt]:
                yi, yj = r.get("year"), records[j].get("year")
                if yi is None or yj is None or abs(yi - yj) <= 1:
                    uf.union(i, j)
            by_title[nt].append(i)

    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for i, r in enumerate(records):
        groups[uf.find(i)].append(r)

    priority = {"openalex": 0, "zbmath": 1, "arxiv": 2}
    out = []
    for grp in groups.values():
        grp.sort(key=lambda r: priority.get(r["source"], 9))
        ids = {r["source"]: r["source_id"] for r in reversed(grp)}

        def pick(f: str, grp: list[dict[str, Any]] = grp) -> Any:
            return next((r.get(f) for r in grp if r.get(f)), None)

        # Prefer arXiv abstracts (author-written) over OpenAlex reconstructions.
        abstract = next(
            (r["abstract"] for r in grp if r["source"] == "arxiv" and r["abstract"]),
            pick("abstract"),
        )
        urls = []
        for r in sorted(grp, key=lambda r: 0 if r["source"] == "arxiv" else 1):
            urls += [u for u in r.get("pdf_urls", []) if u not in urls]
        keys = set().union(*(r.get("author_keys", set()) for r in grp))
        roles = {r.get("role", "own") for r in grp}
        if "openalex" in ids:
            pid = ids["openalex"]
        elif "zbmath" in ids:
            pid = f"zbl-{ids['zbmath']}"
        else:
            pid = f"arxiv-{ids['arxiv'].replace('/', '_')}"
        out.append(
            {
                "paper_id": pid,
                "title": pick("title"),
                "year": pick("year"),
                "abstract": abstract,
                "doi": pick("doi"),
                "arxiv_id": pick("arxiv_id"),
                "openalex_id": ids.get("openalex"),
                "zbmath_id": ids.get("zbmath"),
                "zbl": pick("zbl"),
                "msc": sorted({m for r in grp for m in r.get("msc", [])}),
                "arxiv_cats": sorted({c for r in grp for c in r.get("arxiv_cats", [])}),
                "reviews": [t for r in grp for t in r.get("reviews", [])],
                "cited_by_count": pick("cited_by_count"),
                "pdf_urls": urls,
                "openalex_content": any(r.get("openalex_content") for r in grp),
                "openalex_tei": any(r.get("openalex_tei") for r in grp),
                "author_keys": sorted(keys),
                "role": "own" if "own" in roles else "citing",
                "sources": sorted(ids),
            }
        )
    return out


def harvest(cfg: Config, author_keys: list[str] | None = None) -> pd.DataFrame:
    cfg.ensure_dirs()
    http = Http(cfg.cache_dir / "http", cfg.rate_limits, cfg.mailto)
    oa, zb, ax = OpenAlex(http, cfg.openalex_api_key), ZbMath(http), ArXiv(http)
    records, cite_edges = [], []
    for a in cfg.authors:
        if author_keys and a.key not in author_keys:
            continue
        mine = []
        if a.openalex_id:
            mine += oa.works_by_author(a.openalex_id, cfg.max_works_per_author)
        if a.zbmath_code:
            mine += zb.works_by_author(a.zbmath_code, cfg.max_works_per_author)
        if a.arxiv_query:
            mine += ax.search(a.arxiv_query, cfg.max_works_per_author)
        for r in mine:
            r["author_keys"], r["role"] = {a.key}, "own"
        log.info("%s: %d source records", a.key, len(mine))
        records += mine
        if cfg.citing_sample_per_work and a.openalex_id:
            for r in mine:
                if r["source"] == "openalex" and (r.get("cited_by_count") or 0) > 0:
                    for c in oa.citing_works(r["source_id"], cfg.citing_sample_per_work):
                        c["author_keys"], c["role"] = set(), "citing"
                        records.append(c)
                        cite_edges.append(
                            {
                                "citing_openalex_id": c["source_id"],
                                "cited_openalex_id": r["source_id"],
                                "author_key": a.key,
                            }
                        )
    papers = pd.DataFrame(merge_records(records))
    params = {
        "authors": [a.key for a in cfg.authors if not author_keys or a.key in author_keys],
        "max_works_per_author": cfg.max_works_per_author,
        "citing_sample_per_work": cfg.citing_sample_per_work,
    }
    write_table(cfg, "papers", papers, params=params)
    if cite_edges:
        write_table(cfg, "cite_edges", pd.DataFrame(cite_edges).drop_duplicates(), params=params)
    log.info("papers table: %d rows (%d own)", len(papers), (papers["role"] == "own").sum())
    return papers
