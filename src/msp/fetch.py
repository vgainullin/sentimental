"""Download full text for each paper.

Order of attempts: free PDFs (arXiv first, then open-access links), then, if
`use_openalex_content` is on, OpenAlex's ready-made GROBID TEI (skips local
parsing), then OpenAlex's PDF copy. Paid steps cost ~$0.01 per file.
"""

from __future__ import annotations

import logging

import pandas as pd

from .config import Config
from .http import Http
from .provenance import write_table
from .sources.openalex import OpenAlex

log = logging.getLogger(__name__)


def safe_name(pid: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in pid)


def fetch(
    cfg: Config, roles: tuple[str, ...] = ("own", "citing"), limit: int | None = None
) -> pd.DataFrame:
    cfg.ensure_dirs()
    http = Http(cfg.cache_dir / "http", cfg.rate_limits, cfg.mailto)
    oa = OpenAlex(http, cfg.openalex_api_key)
    papers = pd.read_parquet(cfg.table("papers"))
    papers = papers[papers["role"].isin(roles)]
    if limit:
        papers = papers.head(limit)
    rows = []
    for p in papers.itertuples():
        name = safe_name(p.paper_id)
        pdf, tei = cfg.pdf_dir / f"{name}.pdf", cfg.tei_dir / f"{name}.tei.xml"
        row = {"paper_id": p.paper_id, "pdf_path": None, "tei_path": None, "via": None}
        if tei.exists():
            row.update(tei_path=str(tei), via="cached-tei")
        elif pdf.exists():
            row.update(pdf_path=str(pdf), via="cached-pdf")
        else:
            for url in list(p.pdf_urls):
                if http.download(url, pdf, expect_pdf=True):
                    row.update(pdf_path=str(pdf), via=url.split("/")[2])
                    break
            if not row["via"] and cfg.use_openalex_content and isinstance(p.openalex_id, str):
                if p.openalex_tei:
                    url, sec = oa.content_url(p.openalex_id, "grobid-xml")
                    if http.download(url, tei, secret_params=sec):
                        row.update(tei_path=str(tei), via="openalex-tei")
                if not row["via"] and p.openalex_content:
                    url, sec = oa.content_url(p.openalex_id, "pdf")
                    if http.download(url, pdf, expect_pdf=True, secret_params=sec):
                        row.update(pdf_path=str(pdf), via="openalex-pdf")
        rows.append(row)
    status = pd.DataFrame(rows)
    write_table(
        cfg,
        "fetch_status",
        status,
        inputs=["papers"],
        params={
            "roles": list(roles),
            "limit": limit,
            "use_openalex_content": cfg.use_openalex_content,
        },
    )
    got = status["via"].notna().sum()
    log.info("full text for %d / %d papers", got, len(status))
    return status
