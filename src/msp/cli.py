"""Command line: msp [--shard KEY] <command> [options].

Stages read and write parquet tables under the data dir. With --shard KEY a
command works on one author in data/shards/KEY (how CI parallelizes).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from .config import Config, load_config


def _show(df: pd.DataFrame, cols: list[str] | None = None) -> None:
    print((df[cols] if cols else df).to_string(max_colwidth=90))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="msp", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--authors", default=None, help="authors YAML (default from config)")
    ap.add_argument("--shard", metavar="KEY", help="work on one author in data/shards/KEY")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="command")

    def cmd(name: str, help_: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=help_, description=help_)

    s = cmd("resolve", "find candidate OpenAlex ids and zbMATH codes for a name")
    s.add_argument("name")
    s.add_argument("--zbmath-name", help='zbMATH author query, e.g. "Hilbert, David"')

    s = cmd("debug-zbmath", "print one raw zbMATH record (check field names)")
    s.add_argument("query", help="e.g. ai:hilbert.david")

    s = cmd("harvest", "pull metadata from OpenAlex, zbMATH, arXiv into papers")
    s.add_argument("--only", nargs="*", help="author keys")

    s = cmd("fetch", "download PDFs / TEI for papers")
    s.add_argument("--own-only", action="store_true")
    s.add_argument("--limit", type=int)

    s = cmd("parse", "PDF/TEI → sections, references, citation contexts")
    s.add_argument("--no-grobid", action="store_true")

    cmd("link", "link citation sentences to the cited own papers")
    cmd("chunk", "split full text into word windows")

    s = cmd("embed", "embed papers (SPECTER2) and/or chunks (BGE)")
    s.add_argument("--level", choices=["paper", "chunk", "both"], default="both")
    s.add_argument("--fake", action="store_true", help="hash embedder (testing only)")

    s = cmd("profile", "per-author dispersion and coherence")
    s.add_argument("--min-papers", type=int, default=5)

    s = cmd("search", "local semantic search over papers or chunks")
    s.add_argument("query")
    s.add_argument("-k", type=int, default=10)
    s.add_argument("--level", choices=["paper", "chunk"], default="chunk")
    s.add_argument("--author")
    s.add_argument("--fake", action="store_true")

    cmd("merge", "combine every data/shards/* into data/tables")
    cmd("status", "row counts per table")

    s = cmd("report", "markdown summary of the data (for the wiki)")
    s.add_argument("--out")

    s = cmd("sync", "move data between the local data dir and R2 / Hugging Face")
    s.add_argument("action", choices=["r2-pull", "r2-push", "hf-pull", "hf-push"])
    s.add_argument(
        "--prefix",
        help="R2 prefix, mirrored under the data dir "
        "(default: shards/KEY with --shard, else the whole data dir)",
    )
    s.add_argument("--include", nargs="*", default=[], help="fnmatch patterns for r2-pull")
    s.add_argument("--what", nargs="*", default=["tables", "emb"], help="hf-*: tables and/or emb")
    s.add_argument(
        "--overwrite", action="store_true", help="allow replacing existing R2/local files"
    )
    s.add_argument(
        "--dry-run", action="store_true", help="show what would transfer; change nothing"
    )

    s = cmd("vectorize-upsert", "upload chunk vectors to a Cloudflare Vectorize index")
    s.add_argument("--index", required=True)
    s.add_argument("--include-citing", action="store_true")
    s.add_argument(
        "--overwrite",
        action="store_true",
        help="required: upsert replaces vectors that share an id",
    )
    s.add_argument("--dry-run", action="store_true", help="build and count vectors; send nothing")

    s = cmd("parity-check", "Workers AI vs local BGE embeddings must agree")
    s.add_argument("--n", type=int, default=16)

    s = cmd("cli-docs", "print this CLI's reference as markdown")
    s.add_argument("--out")

    s = cmd("run", "harvest → fetch → parse → link → chunk → embed → profile")
    s.add_argument("--no-grobid", action="store_true")
    s.add_argument("--fake", action="store_true")
    return ap


def cli_markdown(ap: argparse.ArgumentParser) -> str:
    lines = [
        "# CLI reference",
        "",
        "_Generated from `msp cli-docs` on every push to main. Do not edit by hand._",
        "",
        "```",
        ap.format_help().rstrip(),
        "```",
        "",
    ]
    sub = next(a for a in ap._actions if isinstance(a, argparse._SubParsersAction))
    for name, p in sub.choices.items():
        lines += [f"## `msp {name}`", "", "```", p.format_help().rstrip(), "```", ""]
    return "\n".join(lines)


def _fmt(v: object) -> str:
    return "—" if pd.isna(v) else f"{float(v):.3f}"  # type: ignore[arg-type]


def report_markdown(cfg: Config) -> str:
    out = [
        "# Data status",
        "",
        "_Generated by the pipeline after each run._",
        "",
        "| Table | Rows |",
        "|---|---|",
    ]
    for p in sorted(cfg.table_dir.glob("*.parquet")):
        out.append(f"| `{p.stem}` | {len(pd.read_parquet(p)):,} |")
    papers_f = cfg.table("papers")
    if papers_f.exists():
        papers = pd.read_parquet(papers_f)
        own = papers[papers["role"] == "own"].explode("author_keys")
        status = (
            pd.read_parquet(cfg.table("fetch_status"))
            if cfg.table("fetch_status").exists()
            else None
        )
        out += [
            "",
            "| Author | Own papers | With MSC | With abstract | With full text |",
            "|---|---|---|---|---|",
        ]
        for key, g in own.groupby("author_keys"):
            ft = (
                status[status["paper_id"].isin(g["paper_id"])]["via"].notna().sum()
                if status is not None
                else 0
            )
            out.append(
                f"| {key} | {len(g)} | {(g['msc'].apply(len) > 0).sum()} | "
                f"{g['abstract'].notna().sum()} | {ft} |"
            )
    sim = cfg.table("author_similarity")
    if sim.exists():
        df = pd.read_parquet(sim)
        out += ["", "| Author | Papers embedded | Dispersion | Coherence |", "|---|---|---|---|"]
        for r in df.itertuples():
            out.append(
                f"| {r.author_key} | {r.n_papers} | {_fmt(r.dispersion)} | {_fmt(r.coherence)} |"
            )
    return "\n".join(out) + "\n"


def _write_or_print(text: str, path: str | None) -> None:
    if path:
        Path(path).write_text(text)
    else:
        print(text)


def main(argv: list[str] | None = None) -> None:
    ap = build_parser()
    a = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if a.cmd == "cli-docs":
        return _write_or_print(cli_markdown(ap), a.out)

    cfg = load_config(a.config, a.authors)
    if a.shard:
        from .shards import shard_config

        cfg = shard_config(cfg, a.shard)

    if a.cmd == "resolve":
        from .http import Http
        from .sources.openalex import OpenAlex
        from .sources.zbmath import ZbMath

        cfg.ensure_dirs()
        http = Http(cfg.cache_dir / "http", cfg.rate_limits, cfg.mailto)
        print("OpenAlex candidates (check works, years, topics before choosing):")
        _show(pd.DataFrame(OpenAlex(http, cfg.openalex_api_key).search_authors(a.name)))
        zq = a.zbmath_name or a.name
        print(f"\nzbMATH author codes on documents matching '{zq}':")
        for code, n in ZbMath(http).candidate_codes(zq):
            print(f"  {code:30s} {n} docs")
    elif a.cmd == "debug-zbmath":
        from .http import Http
        from .sources.zbmath import ZbMath

        cfg.ensure_dirs()
        docs = ZbMath(Http(cfg.cache_dir / "http", cfg.rate_limits, cfg.mailto)).search(a.query, 1)
        print(json.dumps(docs[0] if docs else {}, indent=2)[:6000])
    elif a.cmd == "status":
        for p in sorted(cfg.table_dir.glob("*.parquet")):
            print(f"{p.stem:22s} {len(pd.read_parquet(p)):>8d} rows")
    elif a.cmd == "report":
        _write_or_print(report_markdown(cfg), a.out)
    elif a.cmd == "harvest":
        from .harvest import harvest

        harvest(cfg, a.only)
    elif a.cmd == "fetch":
        from .fetch import fetch

        fetch(cfg, ("own",) if a.own_only else ("own", "citing"), a.limit)
    elif a.cmd == "parse":
        from .parse import parse_all

        parse_all(cfg, not a.no_grobid)
    elif a.cmd == "link":
        from .citations import link

        link(cfg)
    elif a.cmd == "chunk":
        from .chunk import chunk_all

        chunk_all(cfg)
    elif a.cmd == "embed":
        from .embed import embed_chunks, embed_papers

        if a.level in ("paper", "both"):
            embed_papers(cfg, a.fake)
        if a.level in ("chunk", "both"):
            embed_chunks(cfg, a.fake)
    elif a.cmd == "profile":
        from .profile import author_features

        _show(author_features(cfg, a.min_papers))
    elif a.cmd == "search":
        from .index import search

        cols = ["score", "title", "year", "author_keys"] + (
            ["section", "text"] if a.level == "chunk" else []
        )
        _show(search(cfg, a.query, a.k, a.level, a.author, a.fake), cols)
    elif a.cmd == "merge":
        from .shards import merge

        merge(cfg)
    elif a.cmd == "sync":
        from . import storage

        prefix = (a.prefix or (f"shards/{a.shard}" if a.shard else "")).strip("/")
        local = cfg.root / prefix  # R2 keys mirror the data dir
        if a.action == "r2-pull":
            storage.R2().pull(prefix, local, tuple(a.include), a.overwrite, a.dry_run)
        elif a.action == "r2-push":
            storage.R2().push(local, prefix, overwrite=a.overwrite, dry_run=a.dry_run)
        elif a.action == "hf-push":
            for w in a.what:
                src = cfg.table_dir if w == "tables" else cfg.emb_dir
                if src.exists():
                    storage.hf_push(src, w, f"pipeline: update {w}")
        else:
            storage.hf_pull(cfg.data_dir, [f"{w}/*" for w in a.what])
    elif a.cmd == "vectorize-upsert":
        from .cloudflare import upsert

        if not (a.overwrite or a.dry_run):
            raise SystemExit(
                "vectorize-upsert replaces existing vectors: pass --overwrite or --dry-run"
            )
        upsert(cfg, a.index, include_citing=a.include_citing, dry_run=a.dry_run)
    elif a.cmd == "parity-check":
        from .cloudflare import LOCAL_MODEL, check_parity
        from .embed import SentenceEmbedder

        chunks = pd.read_parquet(cfg.table("chunks"))
        texts = chunks.sample(min(a.n, len(chunks)), random_state=cfg.seed)["text"].tolist()
        texts = [" ".join(t.split()[:150]) for t in texts]  # well under 512 tokens on both sides
        check_parity(texts, SentenceEmbedder(LOCAL_MODEL).encode)
    elif a.cmd == "run":
        from .chunk import chunk_all
        from .citations import link
        from .embed import embed_chunks, embed_papers
        from .fetch import fetch
        from .harvest import harvest
        from .parse import parse_all
        from .profile import author_features

        harvest(cfg)
        fetch(cfg)
        parse_all(cfg, not a.no_grobid)
        link(cfg)
        chunk_all(cfg)
        embed_papers(cfg, a.fake)
        embed_chunks(cfg, a.fake)
        _show(author_features(cfg))


if __name__ == "__main__":
    main(sys.argv[1:])
