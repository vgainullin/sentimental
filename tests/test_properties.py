"""Property tests (hypothesis) for parsers and transforms."""

import string

from hypothesis import given
from hypothesis import strategies as st

from msp.chunk import chunk_text
from msp.harvest import norm_title
from msp.sources import arxiv_from_url, norm_doi
from msp.sources.openalex import abstract_from_index

words = st.lists(st.text(alphabet=string.ascii_letters, min_size=1, max_size=8), max_size=400)


@given(words, st.integers(5, 60), st.integers(0, 4))
def test_chunks_cover_every_word_in_order(ws, size, overlap):
    chunks = chunk_text(" ".join(ws), size, overlap)
    assert all(len(c.split()) <= size for c in chunks)
    # Dropping each chunk's overlap with the previous one rebuilds the text exactly.
    step = size - overlap
    rebuilt = [w for i, c in enumerate(chunks) for w in c.split()[(0 if i == 0 else size - step) :]]
    assert rebuilt == ws


@given(words)
def test_abstract_index_roundtrip(ws):
    inv: dict[str, list[int]] = {}
    for i, w in enumerate(ws):
        inv.setdefault(w, []).append(i)
    assert abstract_from_index(inv) == (" ".join(ws) or None)


@given(st.text())
def test_norm_doi_idempotent(s):
    d = norm_doi(s)
    assert d is None or (norm_doi(d) == d and d == d.lower())


@given(st.text())
def test_norm_title_idempotent_and_clean(s):
    t = norm_title(s)
    assert t is None or (
        norm_title(t) == t and set(t) <= set(string.ascii_lowercase + string.digits + " ")
    )


@given(
    st.from_regex(r"[0-9]{4}\.[0-9]{4,5}", fullmatch=True),
    st.integers(1, 9),
    st.sampled_from(["abs", "pdf"]),
)
def test_arxiv_url_strips_version(aid, v, kind):
    assert arxiv_from_url(f"https://arxiv.org/{kind}/{aid}v{v}") == aid
