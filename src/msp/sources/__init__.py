"""Clients for bibliographic sources. Each returns plain dicts in a shared shape:

{source, source_id, title, year, abstract, doi, arxiv_id, msc, arxiv_cats,
 reviews, cited_by_count, pdf_urls, openalex_content, raw_authors}
"""

import re
from typing import Any

ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:v\d+)?(?:\.pdf)?(?:[?#]|$)", re.I)


def norm_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi.strip(), flags=re.I)
    return d.lower() or None


def arxiv_from_url(url: str | None) -> str | None:
    if not url:
        return None
    m = ARXIV_RE.search(url)
    return m.group(1) if m else None


def empty_record(source: str, source_id: str) -> dict[str, Any]:
    return dict(
        source=source,
        source_id=source_id,
        title=None,
        year=None,
        abstract=None,
        doi=None,
        arxiv_id=None,
        msc=[],
        arxiv_cats=[],
        reviews=[],
        cited_by_count=None,
        pdf_urls=[],
        openalex_content=False,
        raw_authors=[],
    )
