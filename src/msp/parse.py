"""Turn PDFs/TEI into sentences, sections, references, and citation contexts.

Primary path: GROBID (run locally: `docker run --rm -p 8070:8070 grobid/grobid:<tag>`)
with sentence segmentation, so every in-text citation <ref type="bibr"> sits
inside an <s> sentence; that sentence is the citation context.
Fallback: PyMuPDF plain text (no references, no contexts).

Formulas become the token ⟨math⟩. PDF-extracted math is mostly noise for text
embeddings; a LaTeX-aware OCR model (e.g. Nougat or Marker) is the upgrade path.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from lxml import etree

from .config import Config
from .provenance import write_table

log = logging.getLogger(__name__)
T = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
MATH = "⟨math⟩"
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")


# ---------------------------------------------------------------- GROBID
def grobid_pdf_to_tei(pdf: Path, tei: Path, grobid_url: str, timeout: int = 300) -> bool:
    """PDF -> TEI via GROBID. False (and logged) on any per-paper failure, so one slow
    or broken PDF cannot stop the shard."""
    try:
        with pdf.open("rb") as f:
            r = requests.post(
                f"{grobid_url.rstrip('/')}/api/processFulltextDocument",
                files={"input": f},
                data={
                    "segmentSentences": "1",
                    "consolidateHeader": "0",
                    "consolidateCitations": "0",
                    "includeRawCitations": "1",
                },
                timeout=timeout,
            )
    except requests.RequestException as e:
        log.warning("GROBID failed on %s: %s", pdf.name, type(e).__name__)
        return False
    if r.status_code != 200:
        log.warning("GROBID %s on %s", r.status_code, pdf.name)
        return False
    tmp = tei.with_name(tei.name + ".part")
    tmp.write_text(r.text)
    tmp.replace(tei)  # a killed job never leaves a truncated TEI to be reused
    return True


def _text(el: etree._Element) -> str:
    """Flatten an element, replacing formulas with ⟨math⟩."""
    parts: list[str] = []

    def rec(e: etree._Element) -> None:
        tag = etree.QName(e).localname if isinstance(e.tag, str) else None
        if tag == "formula":
            parts.append(f" {MATH} ")
        else:
            if e.text:
                parts.append(e.text)
            for c in e:
                rec(c)
        if e.tail and e is not el:
            parts.append(e.tail)

    rec(el)
    return " ".join("".join(parts).split())


def parse_tei(xml: str | bytes) -> dict[str, Any]:
    root = etree.fromstring(xml if isinstance(xml, bytes) else xml.encode())
    title = root.findtext(f".//{T}titleStmt/{T}title") or None
    abs_el = root.find(f".//{T}profileDesc/{T}abstract")
    abstract = _text(abs_el) if abs_el is not None else None

    refs = []
    for b in root.iterfind(f".//{T}back//{T}listBibl/{T}biblStruct"):
        rid = b.get(XML_ID)
        t = b.findtext(f"{T}analytic/{T}title") or b.findtext(f"{T}monogr/{T}title")
        doi = b.findtext(f".//{T}idno[@type='DOI']")
        date = b.find(f".//{T}imprint/{T}date")
        when = (date.get("when") or "") if date is not None else ""
        surnames = [s.text for s in b.iterfind(f".//{T}author//{T}surname") if s.text]
        refs.append(
            {
                "ref_id": rid,
                "title": " ".join(t.split()) if t else None,
                "doi": doi.lower() if doi else None,
                "year": int(when[:4]) if when[:4].isdigit() else None,
                "first_author": surnames[0] if surnames else None,
            }
        )

    sections, contexts = [], []
    body = root.find(f".//{T}text/{T}body")
    for div in body.iterfind(f"{T}div") if body is not None else []:
        head_el = div.find(f"{T}head")
        head = _text(head_el) if head_el is not None else None
        sents = []
        for p in div.iterfind(f"{T}p"):
            s_els = p.findall(f"{T}s")
            if s_els:
                for s in s_els:
                    txt = _text(s)
                    sents.append(txt)
                    for ref in s.iterfind(f".//{T}ref[@type='bibr']"):
                        for tgt in (ref.get("target") or "").split():
                            contexts.append(
                                {"ref_id": tgt.lstrip("#"), "sentence": txt, "section": head}
                            )
            else:  # GROBID run without segmentation: split ourselves, context = paragraph
                ptxt = _text(p)
                sents += SENT_SPLIT.split(ptxt)
                for ref in p.iterfind(f".//{T}ref[@type='bibr']"):
                    for tgt in (ref.get("target") or "").split():
                        contexts.append(
                            {"ref_id": tgt.lstrip("#"), "sentence": ptxt[:1000], "section": head}
                        )
        if sents:
            sections.append({"head": head, "sentences": sents})
    return {
        "title": title,
        "abstract": abstract,
        "sections": sections,
        "references": refs,
        "contexts": contexts,
    }


# ---------------------------------------------------------------- PDF fallback
REF_HEAD = re.compile(r"^\s*(references|bibliography|literatur|literature cited)\s*$", re.I | re.M)


def parse_pdf_plain(pdf: Path) -> dict[str, Any]:
    import pymupdf

    with pymupdf.Document(pdf) as doc:  # type: ignore[no-untyped-call]
        text = "\n".join(page.get_text("text") for page in doc)
    matches = list(REF_HEAD.finditer(text))
    m = matches[-1] if matches else None  # the last heading is the real bibliography
    if m and m.start() > len(text) * 0.5:
        text = text[: m.start()]
    text = re.sub(r"-\n(?=[a-z])", "", text)  # de-hyphenate line breaks
    text = " ".join(text.split())
    return {
        "title": None,
        "abstract": None,
        "sections": [{"head": None, "sentences": SENT_SPLIT.split(text)}],
        "references": [],
        "contexts": [],
    }


# ---------------------------------------------------------------- stage
def parse_all(cfg: Config, use_grobid: bool = True) -> dict[str, pd.DataFrame]:
    status = pd.read_parquet(cfg.table("fetch_status"))
    secs, refs, ctxs, log_rows = [], [], [], []
    # Fail loudly: silently parsing without GROBID would drop every citation context.
    if use_grobid and not (cfg.grobid_url and _grobid_alive(cfg.grobid_url)):
        raise RuntimeError(
            f"GROBID not reachable at {cfg.grobid_url!r}; start it or pass --no-grobid"
        )
    grobid_ok = use_grobid

    def _path(x: object) -> Path | None:  # parquet turns None into NaN
        return Path(x) if isinstance(x, str) and x else None

    for s in status.itertuples():
        pid, parsed, parser = s.paper_id, None, None
        tei, pdf = _path(s.tei_path), _path(s.pdf_path)
        if tei is None and pdf and grobid_ok:
            cand = cfg.tei_dir / (pdf.stem + ".tei.xml")
            assert cfg.grobid_url is not None  # checked above when use_grobid
            if cand.exists() or grobid_pdf_to_tei(pdf, cand, cfg.grobid_url):
                tei = cand
        try:
            if tei is not None and tei.exists():
                parsed, parser = parse_tei(tei.read_bytes()), "grobid"
            elif pdf:
                parsed, parser = parse_pdf_plain(pdf), "pymupdf"
        except Exception as e:  # noqa: BLE001
            log.warning("parse failed for %s: %s", pid, e)
        log_rows.append({"paper_id": pid, "parser": parser})
        if not parsed:
            continue
        for i, sec in enumerate(parsed["sections"]):
            secs.append(
                {
                    "paper_id": pid,
                    "section_idx": i,
                    "head": sec["head"],
                    "text": " ".join(sec["sentences"]),
                    "parser": parser,
                }
            )
        refs += [{"paper_id": pid, **r} for r in parsed["references"]]
        ctxs += [{"paper_id": pid, **c} for c in parsed["contexts"]]
    out = {
        "sections": pd.DataFrame(secs),
        "references": pd.DataFrame(refs),
        "contexts": pd.DataFrame(ctxs),
        "parse_status": pd.DataFrame(log_rows),
    }
    for name, df in out.items():
        write_table(cfg, name, df, inputs=["fetch_status"], params={"use_grobid": use_grobid})
    return out


def _grobid_alive(url: str) -> bool:
    try:
        return requests.get(f"{url.rstrip('/')}/api/isalive", timeout=5).status_code == 200
    except requests.RequestException:
        return False
