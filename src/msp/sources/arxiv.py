"""arXiv API (Atom). Free PDFs for most mathematics since the 1990s.

Respect arXiv's guidance of one request every 3 seconds (set in rate_limits).
"""

from __future__ import annotations

import re
from typing import Any

from lxml import etree

from ..http import Http
from . import empty_record, norm_doi

API = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArXiv:
    def __init__(self, http: Http):
        self.http = http

    def search(self, query: str, limit: int = 2000, per_page: int = 100) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        start = 0
        while len(out) < limit:
            xml = self.http.get_text(
                API,
                {
                    "search_query": query,
                    "start": start,
                    "max_results": per_page,
                    "sortBy": "submittedDate",
                    "sortOrder": "ascending",
                },
            )
            batch = self.parse(xml)
            out.extend(batch)
            if len(batch) < per_page:
                break
            start += per_page
        return out[:limit]

    @staticmethod
    def parse(xml: str) -> list[dict[str, Any]]:
        root = etree.fromstring(xml.encode())
        recs: list[dict[str, Any]] = []
        for e in root.findall("a:entry", NS):
            aid = (e.findtext("a:id", "", NS) or "").rsplit("/abs/", 1)[-1]
            if not aid:
                raise ValueError("arXiv entry without an <id>")
            aid_base = re.sub(r"v\d+$", "", aid)
            r = empty_record("arxiv", aid_base)
            r["arxiv_id"] = aid_base
            r["title"] = " ".join(e.findtext("a:title", "", NS).split())
            r["abstract"] = " ".join(e.findtext("a:summary", "", NS).split())
            pub = e.findtext("a:published", "", NS)
            r["year"] = int(pub[:4]) if pub[:4].isdigit() else None
            r["doi"] = norm_doi(e.findtext("arxiv:doi", None, NS))
            r["arxiv_cats"] = [c.get("term") for c in e.findall("a:category", NS)]
            r["pdf_urls"] = [f"https://arxiv.org/pdf/{aid_base}"]
            r["raw_authors"] = [a.findtext("a:name", "", NS) for a in e.findall("a:author", NS)]
            recs.append(r)
        return recs
