"""Offline tests: no network, no models. Run with `pytest -q`."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from msp.config import Author, Config
from msp.harvest import merge_records
from msp.parse import parse_pdf_plain, parse_tei
from msp.sources import empty_record
from msp.sources.arxiv import ArXiv
from msp.sources.openalex import OpenAlex, abstract_from_index
from msp.sources.zbmath import ZbMath

TEI = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
 <teiHeader><fileDesc><titleStmt><title>Applications of the prime gap method</title></titleStmt></fileDesc>
  <profileDesc><abstract><p><s>We extend a sieve bound.</s></p></abstract></profileDesc></teiHeader>
 <text><body>
  <div><head>Introduction</head>
   <p><s>The foundational result of <ref type="bibr" target="#b0">[1]</ref> resolved bounded gaps between primes for all sufficiently large integers.</s>
      <s>We use the bound <formula>p_{n+1}-p_n &lt; C</formula> throughout.</s></p>
  </div>
  <div><head>Method</head>
   <p><s>Unlike <ref type="bibr" target="#b1">[2]</ref>, our argument avoids the Elliott–Halberstam conjecture entirely and is effective.</s></p>
  </div>
 </body>
 <back><div><listBibl>
  <biblStruct xml:id="b0"><analytic><title>Bounded gaps between primes</title><author><persName><surname>Zhang</surname></persName></author></analytic>
   <monogr><title>Annals of Mathematics</title><imprint><date when="2014"/></imprint></monogr><idno type="DOI">10.4007/annals.2014.179.3.7</idno></biblStruct>
  <biblStruct xml:id="b1"><analytic><title>Small gaps between primes</title></analytic>
   <monogr><title>Annals of Mathematics</title><imprint><date when="2015"/></imprint></monogr></biblStruct>
 </listBibl></div></back>
 </text></TEI>"""

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
 <entry><id>http://arxiv.org/abs/1311.4600v3</id><published>2013-11-19T00:00:00Z</published>
  <title>Small gaps
   between primes</title><summary>We introduce a refinement of the GPY sieve.</summary>
  <author><name>James Maynard</name></author>
  <arxiv:doi>10.4007/annals.2015.181.1.7</arxiv:doi>
  <category term="math.NT"/></entry>
</feed>"""


def test_abstract_inversion():
    assert (
        abstract_from_index({"gaps": [1], "Small": [0], "primes": [3], "between": [2]})
        == "Small gaps between primes"
    )


def test_openalex_record_extracts_arxiv_and_pdf():
    w = {
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1/ABC",
        "title": "T",
        "publication_year": 2015,
        "cited_by_count": 9,
        "locations": [
            {
                "landing_page_url": "https://arxiv.org/abs/1311.4600v2",
                "pdf_url": "https://arxiv.org/pdf/1311.4600v2",
            }
        ],
        "has_content": {"pdf": True, "grobid_xml": False},
    }
    r = OpenAlex.to_record(w)
    assert r["source_id"] == "W1" and r["doi"] == "10.1/abc"
    assert r["arxiv_id"] == "1311.4600" and r["openalex_content"] and not r["openalex_tei"]


def test_arxiv_parse():
    (r,) = ArXiv.parse(ATOM)
    assert r["arxiv_id"] == "1311.4600" and r["title"] == "Small gaps between primes"
    assert r["doi"] == "10.4007/annals.2015.181.1.7" and r["arxiv_cats"] == ["math.NT"]


def test_zbmath_record_defensive():
    d = {
        "id": 6383670,
        "identifier": "1306.11073",
        "title": {"title": "Small gaps between primes"},
        "year": "2015",
        "msc": [{"code": "11N05", "scheme": "msc2010"}, {"code": "11N36"}],
        "links": [
            {"type": "doi", "identifier": "10.4007/annals.2015.181.1.7"},
            {"type": "arxiv", "identifier": "1311.4600"},
        ],
        "editorial_contributions": [
            {"contribution_type": "review", "text": "The author proves..."}
        ],
    }
    r = ZbMath.to_record(d)
    assert r["msc"] == ["11N05", "11N36"] and r["year"] == 2015
    assert r["doi"] == "10.4007/annals.2015.181.1.7" and r["reviews"] == ["The author proves..."]


def test_merge_links_three_sources():
    oa = OpenAlex.to_record(
        {
            "id": "W2",
            "doi": "10.4007/annals.2015.181.1.7",
            "title": "Small gaps between primes",
            "publication_year": 2015,
        }
    )
    zb = ZbMath.to_record(
        {
            "id": 1,
            "title": "Small gaps between primes",
            "year": 2015,
            "msc": [{"code": "11N05"}],
            "links": [{"type": "doi", "identifier": "10.4007/ANNALS.2015.181.1.7"}],
        }
    )
    (ax,) = ArXiv.parse(ATOM)
    for r in (oa, zb, ax):
        r["author_keys"], r["role"] = {"maynard"}, "own"
    other = empty_record("arxiv", "9999.0001")
    other.update(title="An unrelated paper on knots", year=2015, author_keys={"x"}, role="own")
    merged = merge_records([oa, zb, ax, other])
    assert len(merged) == 2
    m = next(p for p in merged if p["paper_id"] == "W2")
    assert m["sources"] == ["arxiv", "openalex", "zbmath"] and m["msc"] == ["11N05"]
    assert m["abstract"].startswith("We introduce") and m["pdf_urls"][0].startswith(
        "https://arxiv.org"
    )


def test_tei_contexts_and_math():
    d = parse_tei(TEI)
    assert [s["head"] for s in d["sections"]] == ["Introduction", "Method"]
    assert "⟨math⟩" in d["sections"][0]["sentences"][1]
    assert {c["ref_id"] for c in d["contexts"]} == {"b0", "b1"}
    b0 = next(r for r in d["references"] if r["ref_id"] == "b0")
    assert b0["doi"] == "10.4007/annals.2014.179.3.7" and b0["year"] == 2014


def _make_pdf(path: Path, body: str, refs: str):
    import pymupdf

    doc = pymupdf.open()
    for text in (body, "References\n" + refs):
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=10)
    doc.save(path)


def test_pdf_fallback_drops_bibliography(tmp_path):
    p = tmp_path / "x.pdf"
    _make_pdf(
        p, "We prove that bounded gaps occur infinitely often. " * 20, "[1] Zhang, Bounded gaps."
    )
    d = parse_pdf_plain(p)
    text = " ".join(d["sections"][0]["sentences"])
    assert "bounded gaps occur" in text and "Zhang" not in text


def test_end_to_end_offline(tmp_path, monkeypatch):
    from msp import chunk, citations, embed, fetch, index, parse, profile

    cfg = Config(
        data_dir=tmp_path / "data",
        grobid_url=None,
        chunk_tokens=60,
        chunk_overlap=10,
        authors=[
            Author(key="zhang", name="Yitang Zhang"),
            Author(key="maynard", name="James Maynard"),
        ],
    )
    cfg.ensure_dirs()

    def rec(src, sid, title, year, key, role, doi=None):
        r = empty_record(src, sid)
        r.update(
            title=title,
            year=year,
            doi=doi,
            author_keys={key} if key else set(),
            role=role,
            abstract=f"{title}. A study in analytic number theory and sieve methods.",
        )
        return r

    recs = [
        rec(
            "openalex",
            "W10",
            "Bounded gaps between primes",
            2014,
            "zhang",
            "own",
            "10.4007/annals.2014.179.3.7",
        ),
        rec("openalex", "W11", "On the zeros of Dirichlet L-functions", 2016, "zhang", "own"),
        rec("openalex", "W20", "Small gaps between primes", 2015, "maynard", "own"),
        rec("openalex", "W30", "Applications of the prime gap method", 2019, None, "citing"),
    ]
    pd.DataFrame(merge_records(recs)).to_parquet(cfg.table("papers"), index=False)

    _make_pdf(
        cfg.pdf_dir / "W10.pdf",
        "Introduction. We prove that there are infinitely many pairs of primes that differ "
        "by at most seventy million, using a refined sieve and equidistribution estimates. " * 6,
        "[1] Goldston, Pintz, Yildirim.",
    )
    _make_pdf(
        cfg.pdf_dir / "W20.pdf",
        "We introduce a multidimensional sieve weight and show bounded gaps between primes "
        "with a short combinatorial argument and no equidistribution beyond Bombieri. " * 6,
        "[1] Zhang.",
    )
    (cfg.tei_dir / "W30.tei.xml").write_text(TEI)
    monkeypatch.setattr(fetch.Http, "download", lambda *a, **k: False)  # no network

    st = fetch.fetch(cfg)
    assert set(st.dropna(subset=["via"])["paper_id"]) == {"W10", "W20", "W30"}
    out = parse.parse_all(cfg, use_grobid=False)
    assert len(out["contexts"]) == 2

    ctx = citations.link(cfg)
    by = dict(zip(ctx["cited_paper_id"], ctx["match"], strict=True))
    assert by == {"W10": "doi", "W20": "title:100"}
    assert set(ctx["author_key"]) == {"zhang", "maynard"}

    chunks = chunk.chunk_all(cfg)
    assert len(chunks) >= 4 and chunks["n_words"].max() <= 60

    embed.embed_papers(cfg, fake=True)
    _, X = embed.embed_chunks(cfg, fake=True)
    assert X.dtype == np.float16 and X.shape[0] == len(chunks)

    feats = profile.author_features(cfg, min_papers=2)
    z = feats.set_index("author_key").loc["zhang"]
    assert z.n_papers == 2 and 0 <= z.dispersion <= 2

    hits = index.search(cfg, "multidimensional sieve weight", k=3, fake=True)
    assert hits.iloc[0]["paper_id"] == "W20"
    only_zhang = index.search(cfg, "sieve", k=5, author="zhang", fake=True)
    assert set(only_zhang["paper_id"]) == {"W10"}


def test_paper_texts_nan_safe(tmp_path):
    from msp.embed import paper_texts

    cfg = Config(data_dir=tmp_path / "d")
    cfg.ensure_dirs()
    r = empty_record("zbmath", "1")
    r.update(title="Über die Theorie", reviews=["Reviewer summary."], author_keys={"h"}, role="own")
    df = pd.DataFrame(merge_records([r]))
    df.to_parquet(cfg.table("papers"))
    (t,), (src,) = paper_texts(cfg, pd.read_parquet(cfg.table("papers")))
    assert t == "Über die Theorie [SEP] Reviewer summary." and "nan" not in t
    assert src == "review"


def test_http_cache_retry_and_secret(tmp_path):
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from msp.http import Http

    hits = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            if len(hits) == 1:
                self.send_response(429)
                self.send_header("Retry-After", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": 1}')

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/works"
    h = Http(tmp_path / "c")
    assert h.get_json(url, {"q": "x"}, secret_params={"api_key": "SECRET"}) == {"ok": 1}
    assert h.get_json(url, {"q": "x"}, secret_params={"api_key": "SECRET"}) == {"ok": 1}
    assert len(hits) == 2 and "api_key=SECRET" in hits[-1]  # retried once, then cached
    cached = list((tmp_path / "c").rglob("*"))
    assert not any("SECRET" in p.read_text() for p in cached if p.is_file())
    srv.shutdown()


def test_parse_fails_loudly_without_grobid(tmp_path):
    from msp import parse

    cfg = Config(data_dir=tmp_path, grobid_url="http://127.0.0.1:9")  # nothing listens on 9
    cfg.ensure_dirs()
    pd.DataFrame([{"paper_id": "W1", "pdf_path": None, "tei_path": None, "via": None}]).to_parquet(
        cfg.table("fetch_status")
    )
    with pytest.raises(RuntimeError, match="--no-grobid"):
        parse.parse_all(cfg, use_grobid=True)


def test_empty_and_malformed_inputs():
    from lxml import etree

    assert ArXiv.parse('<feed xmlns="http://www.w3.org/2005/Atom"/>') == []
    assert merge_records([]) == []
    with pytest.raises(etree.XMLSyntaxError):
        parse_tei("<TEI><unclosed>")
    r = ZbMath.to_record(
        {
            "id": 5,
            "msc": ["11A", {"code": 3}, None],
            "year": "n.d.",
            "links": ["junk", {"type": "doi"}],
        }
    )
    assert r["msc"] == ["11A"] and r["year"] is None and r["doi"] is None
