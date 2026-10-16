"""OpenAlex: author resolution, works, citing works, and paid full-text content.

Pricing (checked Oct 2026): list/filter calls ~$0.10 per 1k, search ~$1 per 1k,
content downloads $0.01 per file. A free key gives a $1/day budget.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..http import Http
from . import arxiv_from_url, empty_record, norm_doi

API = "https://api.openalex.org"
CONTENT = "https://content.openalex.org/works"
WORK_FIELDS = (
    "id,doi,title,publication_year,abstract_inverted_index,locations,"
    "best_oa_location,authorships,cited_by_count,type,ids,has_content"
)


def short_id(oa_id: str | None) -> str | None:
    return oa_id.rsplit("/", 1)[-1] if oa_id else None


def abstract_from_index(inv: dict[str, Any] | None) -> str | None:
    if not inv:
        return None
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos)) or None


class OpenAlex:
    def __init__(self, http: Http, api_key: str | None = None):
        self.http = http
        self.secret = {"api_key": api_key} if api_key else None

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        return self.http.get_json(f"{API}/{path}", params, secret_params=self.secret)

    def search_authors(self, name: str, n: int = 10) -> list[dict[str, Any]]:
        res = self._get("authors", {"search": name, "per_page": n})["results"]
        out = []
        for a in res:
            years = [c["year"] for c in a.get("counts_by_year", []) if c.get("works_count")]
            inst = a.get("last_known_institutions") or []
            out.append(
                {
                    "openalex_id": short_id(a["id"]),
                    "name": a.get("display_name"),
                    "works": a.get("works_count"),
                    "cited_by": a.get("cited_by_count"),
                    "institution": inst[0].get("display_name") if inst else None,
                    "recent_years": f"{min(years)}-{max(years)}" if years else None,
                    "top_topics": [t.get("display_name") for t in (a.get("topics") or [])[:3]],
                }
            )
        return out

    def _paged(self, filt: str, limit: int, per_page: int = 100) -> Iterator[dict[str, Any]]:
        cursor, got = "*", 0
        while cursor and got < limit:
            page = self._get(
                "works",
                {"filter": filt, "per_page": per_page, "cursor": cursor, "select": WORK_FIELDS},
            )
            for w in page["results"]:
                yield w
                got += 1
                if got >= limit:
                    return
            cursor = page.get("meta", {}).get("next_cursor")

    def works_by_author(self, author_id: str, limit: int = 2000) -> list[dict[str, Any]]:
        return [self.to_record(w) for w in self._paged(f"authorships.author.id:{author_id}", limit)]

    def citing_works(self, work_id: str, n: int) -> list[dict[str, Any]]:
        """Most-cited papers that cite `work_id` (a stable, reproducible sample)."""
        page = self._get(
            "works",
            {
                "filter": f"cites:{work_id}",
                "per_page": min(n, 100),
                "sort": "cited_by_count:desc",
                "select": WORK_FIELDS,
            },
        )
        return [self.to_record(w) for w in page["results"][:n]]

    @staticmethod
    def to_record(w: dict[str, Any]) -> dict[str, Any]:
        r = empty_record("openalex", w["id"].rsplit("/", 1)[-1])
        r.update(
            title=w.get("title"),
            year=w.get("publication_year"),
            abstract=abstract_from_index(w.get("abstract_inverted_index")),
            doi=norm_doi(w.get("doi")),
            cited_by_count=w.get("cited_by_count"),
        )
        urls = []
        for loc in [w.get("best_oa_location")] + (w.get("locations") or []):
            if not loc:
                continue
            for u in (loc.get("pdf_url"), loc.get("landing_page_url")):
                r["arxiv_id"] = r["arxiv_id"] or arxiv_from_url(u)
            if loc.get("pdf_url") and loc["pdf_url"] not in urls:
                urls.append(loc["pdf_url"])
        r["pdf_urls"] = urls
        r["openalex_content"] = bool((w.get("has_content") or {}).get("pdf"))
        r["openalex_tei"] = bool((w.get("has_content") or {}).get("grobid_xml"))
        r["raw_authors"] = [
            a.get("author", {}).get("display_name") for a in (w.get("authorships") or [])
        ]
        return r

    def content_url(self, work_id: str, kind: str = "pdf") -> tuple[str, dict[str, Any] | None]:
        """kind: 'pdf' or 'grobid-xml'. Paid ($0.01/file)."""
        return f"{CONTENT}/{work_id}.{kind}", self.secret
