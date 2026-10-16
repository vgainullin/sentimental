"""zbMATH Open REST API: MSC codes and reviews, back to the 1868 Jahrbuch.

Endpoint: https://api.zbmath.org/v1/document/_search?search_string=...
Search prefixes: ai: (author code, e.g. ai:hilbert.david), au:, ti:, py:, cc: (MSC).

Field names are parsed defensively because responses vary by record and some
fields are redacted by publisher agreement. Inspect one live response
(`msp debug-zbmath ai:hilbert.david`) before a large run and adjust if needed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from typing import Any

from ..http import Http
from . import arxiv_from_url, empty_record, norm_doi

API = "https://api.zbmath.org/v1/document/_search"


def _first_str(x: object) -> str | None:
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        for k in ("title", "text", "value", "name"):
            v = x.get(k)
            if isinstance(v, str):
                return v
    if isinstance(x, list) and x:
        return _first_str(x[0])
    return None


def _walk(obj: object) -> Iterator[dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


class ZbMath:
    def __init__(self, http: Http):
        self.http = http

    def search(self, query: str, limit: int = 2000, per_page: int = 100) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        page = 0
        while len(out) < limit:
            res = self.http.get_json(
                API, {"search_string": query, "page": page, "results_per_page": per_page}
            )
            batch = res.get("result") or []
            out.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        return out[:limit]

    def works_by_author(self, code: str, limit: int = 2000) -> list[dict[str, Any]]:
        return [self.to_record(d) for d in self.search(f"ai:{code}", limit)]

    def candidate_codes(self, name: str, n_docs: int = 100) -> list[tuple[str, int]]:
        """Author codes seen on documents matching a name, with counts."""
        docs = self.search(f"au:{name}", n_docs)
        c: Counter[str] = Counter()
        for d in docs:
            for node in _walk(d.get("contributors", d)):
                codes = node.get("codes")
                if isinstance(codes, list):
                    c.update(x for x in codes if isinstance(x, str))
        return c.most_common(10)

    @staticmethod
    def to_record(d: dict[str, Any]) -> dict[str, Any]:
        r = empty_record("zbmath", str(d.get("id") or d.get("identifier")))
        r["zbl"] = d.get("identifier")
        r["title"] = _first_str(d.get("title"))
        y = d.get("year")
        r["year"] = int(y) if isinstance(y, (int, str)) and str(y)[:4].isdigit() else None
        msc = []
        for m in d.get("msc") or []:
            code = m.get("code") if isinstance(m, dict) else m
            if isinstance(code, str) and code not in msc:
                msc.append(code)
        r["msc"] = msc
        for link in d.get("links") or []:
            if not isinstance(link, dict):
                continue
            t, ident = (link.get("type") or "").lower(), link.get("identifier") or link.get("url")
            if t == "doi":
                r["doi"] = r["doi"] or norm_doi(ident)
            elif t == "arxiv":
                r["arxiv_id"] = r["arxiv_id"] or ident
            else:
                r["arxiv_id"] = r["arxiv_id"] or arxiv_from_url(ident)
        reviews = []
        for ec in d.get("editorial_contributions") or []:
            if isinstance(ec, dict) and ec.get("text"):
                reviews.append(ec["text"])
        r["reviews"] = reviews
        r["abstract"] = None  # zbMATH reviews are kept separate from abstracts
        r["raw_authors"] = [
            _first_str(a) for a in ((d.get("contributors") or {}).get("authors") or [])
        ]
        return r
