"""Offline tests for sharding, storage sync, Vectorize upload, and the CLI docs."""

import hashlib
import json
import math

import numpy as np
import pandas as pd
import pytest

from msp.config import Author, Config
from msp.harvest import merge_records
from msp.sources import empty_record


def _rec(sid, title, key, role, year=2020):
    r = empty_record("openalex", sid)
    r.update(
        title=title,
        year=year,
        author_keys={key} if key else set(),
        role=role,
        abstract="An abstract long enough to embed.",
    )
    return r


def test_shard_config_and_merge(tmp_path):
    from msp import shards

    base = Config(data_dir=tmp_path, authors=[Author("a", "A"), Author("b", "B")])
    for key, recs in {
        "a": [
            _rec("W1", "Paper one by A", "a", "own"),
            _rec("W9", "Shared citing paper", None, "citing"),
        ],
        "b": [
            _rec("W2", "Paper two by B", "b", "own"),
            _rec("W9", "Shared citing paper", None, "citing"),
            _rec("W1", "Paper one by A", "b", "own"),
        ],
    }.items():  # coauthored
        cfg = shards.shard_config(Config(data_dir=tmp_path, authors=list(base.authors)), key)
        assert cfg.data_dir == tmp_path / "shards" / key and [x.key for x in cfg.authors] == [key]
        cfg.ensure_dirs()
        pd.DataFrame(merge_records(recs)).to_parquet(cfg.table("papers"))
        pd.DataFrame(
            [
                {
                    "chunk_id": f"{r['source_id']}::0::0",
                    "paper_id": r["source_id"],
                    "section": None,
                    "text": "x",
                    "n_words": 1,
                }
                for r in recs
            ]
        ).to_parquet(cfg.table("chunks"))
    counts = shards.merge(base)
    papers = pd.read_parquet(base.table("papers")).set_index("paper_id")
    assert counts == {"papers": 3, "chunks": 3}
    assert list(papers.loc["W1", "author_keys"]) == ["a", "b"]
    assert papers.loc["W9", "role"] == "citing" and papers.loc["W2", "role"] == "own"
    with pytest.raises(SystemExit):
        shards.shard_config(Config(data_dir=tmp_path, authors=base.authors), "nobody")


class FakeS3:
    """In-memory stand-in for the boto3 S3 client calls R2 uses."""

    def __init__(self):
        self.objects = {}

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        start = int(ContinuationToken or 0)
        page = keys[start : start + 2]  # tiny pages exercise pagination
        out = {
            "Contents": [
                {
                    "Key": k,
                    "Size": len(self.objects[k]),
                    "ETag": f'"{hashlib.md5(self.objects[k]).hexdigest()}"',
                }
                for k in page
            ],
            "IsTruncated": start + 2 < len(keys),
        }
        if out["IsTruncated"]:
            out["NextContinuationToken"] = str(start + 2)
        return out

    def upload_file(self, path, bucket, key, Config=None):
        self.objects[key] = open(path, "rb").read()

    def download_file(self, bucket, key, path):
        open(path, "wb").write(self.objects[key])


def test_r2_push_pull_roundtrip(tmp_path):
    from msp.storage import R2

    src = tmp_path / "src"
    for rel, data in {
        "tables/papers.parquet": b"P" * 10,
        "pdf/W1.pdf": b"%PDF-" + b"x" * 50,
        "cache/http/ab/abc": b"{}",
        "pdf/W2.pdf.part": b"partial",
    }.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_bytes(data)
    r2 = R2("bucket", client=FakeS3())
    assert len(r2.push(src, "shards/a", dry_run=True)) == 3  # dry run plans, sends nothing
    assert r2.s3.objects == {}
    assert len(r2.push(src, "shards/a")) == 3  # .part files are skipped
    assert len(r2.push(src, "shards/a")) == 0  # unchanged → nothing re-uploaded
    (src / "tables/papers.parquet").write_bytes(b"P" * 11)  # changed file
    with pytest.raises(FileExistsError, match="overwrite"):
        r2.push(src, "shards/a")  # replacing needs the flag
    assert len(r2.push(src, "shards/a", overwrite=True).replace) == 1
    dst = tmp_path / "dst"
    assert len(r2.pull("shards", dst, include=("*/tables/*",))) == 1
    assert (dst / "a/tables/papers.parquet").read_bytes() == b"P" * 11
    assert not (dst / "a/pdf").exists()
    assert len(r2.pull("shards/a", tmp_path / "all")) == 3


def test_r2_detects_same_size_changes(tmp_path):
    from msp.storage import R2

    f = tmp_path / "src/tables/papers.parquet.meta.json"
    f.parent.mkdir(parents=True)
    f.write_bytes(b'{"sha256": "aaaa"}')
    r2 = R2("bucket", client=FakeS3())
    r2.push(tmp_path / "src", "shards/a")
    f.write_bytes(b'{"sha256": "bbbb"}')  # same size, new content
    with pytest.raises(FileExistsError):
        r2.push(tmp_path / "src", "shards/a")
    assert len(r2.push(tmp_path / "src", "shards/a", new_only=True)) == 0  # failure path
    assert r2.s3.objects["shards/a/tables/papers.parquet.meta.json"] == b'{"sha256": "aaaa"}'
    assert len(r2.push(tmp_path / "src", "shards/a", overwrite=True).replace) == 1
    dst = tmp_path / "dst/tables/papers.parquet.meta.json"
    dst.parent.mkdir(parents=True)
    dst.write_bytes(b'{"sha256": "cccc"}')  # same size, stale local copy
    assert len(r2.pull("shards/a", tmp_path / "dst", overwrite=True).replace) == 1
    assert dst.read_bytes() == b'{"sha256": "bbbb"}'


def _embedded_cfg(tmp_path, model="BAAI/bge-base-en-v1.5"):
    cfg = Config(data_dir=tmp_path)
    cfg.ensure_dirs()
    pd.DataFrame(
        merge_records(
            [_rec("W1", "Own paper", "tao", "own"), _rec("W2", "Citing paper", None, "citing")]
        )
    ).to_parquet(cfg.table("papers"))
    long_id = "arxiv-math_0501001::" + "9" * 80
    chunks = pd.DataFrame(
        [
            {
                "chunk_id": long_id,
                "paper_id": "W1",
                "section": "Intro",
                "text": "τ" * 3000,
                "n_words": 1,
            },
            {"chunk_id": "W2::0::0", "paper_id": "W2", "section": None, "text": "c", "n_words": 1},
        ]
    )
    chunks.to_parquet(cfg.table("chunks"))
    ids = chunks[["chunk_id", "paper_id"]].assign(model=model)
    ids.to_parquet(cfg.emb_dir / "chunks_ids.parquet")
    np.save(cfg.emb_dir / "chunks.npy", np.eye(2, 768, dtype=np.float16))
    return cfg, long_id


def test_vectorize_records_respect_limits(tmp_path):
    from msp.cloudflare import build_vectors, vector_id

    cfg, long_id = _embedded_cfg(tmp_path)
    recs = list(build_vectors(cfg))
    assert len(recs) == 1  # citing papers excluded by default
    (r,) = recs
    assert r["id"] == vector_id(long_id) and len(r["id"].encode()) <= 64
    assert r["metadata"]["chunk_id"] == long_id and r["metadata"]["author"] == "tao"
    assert len(json.dumps(r["metadata"], ensure_ascii=False).encode()) < 10 * 1024  # as sent
    assert r["metadata"]["text"] == "τ" * 3000  # 6000 bytes
    assert len(r["values"]) == 768 and math.isclose(r["values"][0], 1.0)
    assert len(list(build_vectors(cfg, include_citing=True))) == 2


def test_vectorize_refuses_wrong_model(tmp_path):
    from msp.cloudflare import build_vectors

    cfg, _ = _embedded_cfg(tmp_path, model="hash-512")
    with pytest.raises(SystemExit, match="refusing"):
        list(build_vectors(cfg))


def test_upsert_batches_ndjson(tmp_path, monkeypatch):
    from msp import cloudflare

    cfg, _ = _embedded_cfg(tmp_path)
    sent = []

    class Resp:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = "{}"

        def json(self):
            return {"success": True, "result": {"mutationId": "m"}}

    def fake_post(url, data, headers, timeout):
        sent.append((url, headers, data.decode()))
        return Resp()

    monkeypatch.setenv("CF_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CF_API_TOKEN", "tok")
    monkeypatch.setattr(cloudflare.requests, "post", fake_post)
    assert cloudflare.upsert(cfg, "idx", batch=1, include_citing=True) == 2
    assert len(sent) == 2
    url, hdr, body = sent[0]
    assert url.endswith("/accounts/acct/vectorize/v2/indexes/idx/upsert")
    assert hdr["Content-Type"] == "application/x-ndjson" and hdr["Authorization"] == "Bearer tok"
    assert json.loads(body)["metadata"]["paper_id"] == "W1"


def test_parity_check(monkeypatch):
    from msp import cloudflare

    v = np.ones((3, 4), np.float32) / 2
    monkeypatch.setattr(cloudflare, "workers_ai_embed", lambda t: v)
    assert cloudflare.check_parity(["a", "b", "c"], lambda t: v) == pytest.approx(1.0)
    with pytest.raises(SystemExit, match="parity"):
        cloudflare.check_parity(["a", "b", "c"], lambda t: -v)


def test_cli_docs_and_report(tmp_path, capsys):
    from msp.cli import build_parser, cli_markdown, report_markdown

    md = cli_markdown(build_parser())
    for name in ("harvest", "merge", "sync", "vectorize-upsert", "parity-check"):
        assert f"## `msp {name}`" in md
    cfg, _ = _embedded_cfg(tmp_path)
    rep = report_markdown(cfg)
    assert "| `papers` | 2 |" in rep and "| tao | 1 |" in rep


def test_cli_sync_mirrors_data_dir(tmp_path, monkeypatch):
    """Shard data/shards/a ↔ r2 shards/a; merge job pulls every shard's tables only."""
    import yaml

    from msp import cli, storage

    fake = FakeS3()
    real_init = storage.R2.__init__

    class R2Fake(storage.R2):
        def __init__(self):
            real_init(self, "b", client=fake)

    monkeypatch.setattr(storage, "R2", R2Fake)
    data = tmp_path / "data"
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({"data_dir": str(data)}))
    (tmp_path / "authors.yaml").write_text(yaml.safe_dump([{"key": "a", "name": "A"}]))
    shard = data / "shards" / "a"
    for rel in ("tables/papers.parquet", "pdf/x.pdf", "cache/http/0/1"):
        (shard / rel).parent.mkdir(parents=True, exist_ok=True)
        (shard / rel).write_bytes(b"123")
    args = ["--config", str(tmp_path / "config.yaml"), "--authors", str(tmp_path / "authors.yaml")]
    cli.main(args + ["--shard", "a", "sync", "r2-push"])
    assert set(fake.objects) == {
        "shards/a/tables/papers.parquet",
        "shards/a/pdf/x.pdf",
        "shards/a/cache/http/0/1",
    }
    import shutil

    shutil.rmtree(data)
    cli.main(args + ["sync", "r2-pull", "--prefix", "shards", "--include", "*/tables/*"])
    assert (data / "shards/a/tables/papers.parquet").exists() and not (
        data / "shards/a/pdf"
    ).exists()


def test_vectorize_cli_requires_explicit_flag(tmp_path):
    import yaml

    from msp import cli

    (tmp_path / "c.yaml").write_text(yaml.safe_dump({"data_dir": str(tmp_path / "d")}))
    with pytest.raises(SystemExit, match="--overwrite"):
        cli.main(["--config", str(tmp_path / "c.yaml"), "vectorize-upsert", "--index", "i"])


def test_vectorize_dry_run_sends_nothing(tmp_path, monkeypatch):
    from msp import cloudflare

    cfg, _ = _embedded_cfg(tmp_path)
    monkeypatch.setattr(cloudflare.requests, "post", lambda *a, **k: pytest.fail("network call"))
    assert cloudflare.upsert(cfg, "idx", dry_run=True) == 1


def test_provenance_sidecar(tmp_path):
    from msp.provenance import file_sha256, write_table

    cfg = Config(data_dir=tmp_path, seed=7)
    cfg.ensure_dirs()
    write_table(cfg, "papers", pd.DataFrame({"paper_id": ["W1"]}))
    path = write_table(
        cfg,
        "chunks",
        pd.DataFrame({"chunk_id": ["c"]}),
        inputs=["papers", "nope"],
        params={"chunk_tokens": 250},
    )
    meta = json.loads(path.with_name("chunks.parquet.meta.json").read_text())
    assert meta["sha256"] == file_sha256(path) and meta["rows"] == 1 and meta["seed"] == 7
    assert meta["inputs"] == {"papers": file_sha256(cfg.table("papers")), "nope": None}
    assert meta["params"] == {"chunk_tokens": 250} and meta["git_sha"]


def test_write_table_is_atomic(tmp_path, monkeypatch):
    from msp.provenance import write_table

    cfg = Config(data_dir=tmp_path)
    cfg.ensure_dirs()
    good = write_table(cfg, "papers", pd.DataFrame({"paper_id": ["W1"]}))
    before = good.read_bytes()

    def killed(self, f, **kw):
        f.write(b"PAR1 half a table")
        raise KeyboardInterrupt  # job cancelled mid-write

    monkeypatch.setattr(pd.DataFrame, "to_parquet", killed)
    with pytest.raises(KeyboardInterrupt):
        write_table(cfg, "papers", pd.DataFrame({"paper_id": ["W2"]}))
    assert good.read_bytes() == before  # old table intact
    assert not list(good.parent.glob("*.part"))  # no stray temp file
