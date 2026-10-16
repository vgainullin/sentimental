"""Link citation contexts in citing papers back to each mathematician's own papers.

Output table `citation_contexts`: one row per sentence in which a citing paper
cites one of the author's works. This is the input for the reception/stance
(sentiment) model.

Matching: DOI first; otherwise fuzzy title match (token-sort ratio >= 90) with
both publication years known and within one year. Token-sort, not token-set:
token-set scores 100 whenever one title's words are a subset of the other's.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from .config import Config
from .harvest import norm_title
from .provenance import write_table

log = logging.getLogger(__name__)


def link(cfg: Config, min_score: int = 90) -> pd.DataFrame:
    papers = pd.read_parquet(cfg.table("papers"))
    refs = pd.read_parquet(cfg.table("references"))
    ctxs = pd.read_parquet(cfg.table("contexts"))
    if refs.empty or ctxs.empty:
        log.warning("no references/contexts parsed (is GROBID running?)")
        out = pd.DataFrame(
            columns=[
                "citing_paper_id",
                "cited_paper_id",
                "author_key",
                "sentence",
                "section",
                "match",
            ]
        )
        write_table(cfg, "citation_contexts", out, inputs=["papers", "references", "contexts"])
        return out

    own = papers[papers["role"] == "own"]
    # isinstance checks: parquet turns missing strings into NaN, which is truthy
    # and would otherwise match every other missing DOI.
    by_doi = {
        d: r for d, r in zip(own["doi"], own.itertuples(), strict=True) if isinstance(d, str) and d
    }
    rows = list(own.itertuples())
    own_titles = [(norm_title(t), r) for t, r in zip(own["title"], rows, strict=True)]
    own_titles = [(t, r) for t, r in own_titles if t]

    def resolve(ref: Any) -> tuple[Any, str] | tuple[None, None]:
        if isinstance(ref.doi, str) and ref.doi in by_doi:
            return by_doi[ref.doi], "doi"
        nt = norm_title(ref.title if isinstance(ref.title, str) else None)
        if not nt:
            return None, None
        best: Any = None
        score = 0.0
        for t, r in own_titles:
            s = float(fuzz.token_sort_ratio(nt, t or ""))
            if s > score:
                best, score = r, s
        if best is not None and score >= min_score:
            if pd.isna(ref.year) or pd.isna(best.year) or abs(int(ref.year) - int(best.year)) > 1:
                return None, None
            return best, f"title:{int(score)}"
        return None, None

    resolved = {}
    for ref in refs.itertuples():
        hit, how = resolve(ref)
        if hit is not None and hit.paper_id != ref.paper_id:  # skip self-matches
            resolved[(ref.paper_id, ref.ref_id)] = (hit, how)

    rows = []
    for c in ctxs.itertuples():
        hit = resolved.get((c.paper_id, c.ref_id))
        if not hit:
            continue
        target, how = hit
        for key in target.author_keys:
            rows.append(
                {
                    "citing_paper_id": c.paper_id,
                    "cited_paper_id": target.paper_id,
                    "author_key": key,
                    "sentence": c.sentence,
                    "section": c.section,
                    "match": how,
                }
            )
    out = (
        pd.DataFrame(rows).drop_duplicates()
        if rows
        else pd.DataFrame(
            columns=[
                "citing_paper_id",
                "cited_paper_id",
                "author_key",
                "sentence",
                "section",
                "match",
            ]
        )
    )
    write_table(
        cfg,
        "citation_contexts",
        out,
        inputs=["papers", "references", "contexts"],
        params={"min_score": min_score},
    )
    log.info("citation contexts linked: %d", len(out))
    return out
