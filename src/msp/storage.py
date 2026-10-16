"""Sync the local data dir with cloud storage.

* Cloudflare R2 (S3 API): raw and per-shard state. PDFs, TEI, the HTTP cache
  (so paid API calls are never repeated), and shard tables. Private.
* Hugging Face dataset repo: merged tables and embeddings, versioned. Private.

Credentials come from the environment only:
  R2: CF_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET
  HF: HF_TOKEN, HF_DATASET (e.g. "you/math-style-data")
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"missing environment variable {name}")
    return v


# ------------------------------------------------------------------ R2
@dataclass
class SyncPlan:
    new: list[tuple[Any, Any]] = field(default_factory=list)
    replace: list[tuple[Any, Any]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.new) + len(self.replace)


class R2:
    def __init__(self, bucket: str | None = None, client: Any = None) -> None:
        self.bucket = bucket or _env("R2_BUCKET")
        if client is None:
            import boto3

            client = boto3.client(
                "s3",
                region_name="auto",
                endpoint_url=f"https://{_env('CF_ACCOUNT_ID')}.r2.cloudflarestorage.com",
                aws_access_key_id=_env("R2_ACCESS_KEY_ID"),
                aws_secret_access_key=_env("R2_SECRET_ACCESS_KEY"),
            )
        self.s3 = client

    def list(self, prefix: str) -> dict[str, int]:
        out, token = {}, None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": prefix}
            if token:
                kw["ContinuationToken"] = token
            page = self.s3.list_objects_v2(**kw)
            for o in page.get("Contents", []):
                out[o["Key"]] = o["Size"]
            if not page.get("IsTruncated"):
                return out
            token = page["NextContinuationToken"]

    def _run(
        self,
        plan: SyncPlan,
        fn: Callable[[tuple[Any, Any]], None],
        overwrite: bool,
        dry_run: bool,
        what: str,
    ) -> SyncPlan:
        if plan.replace and not overwrite:
            sample = ", ".join(str(x[-1]) for x in plan.replace[:3])
            raise FileExistsError(
                f"{what} would replace {len(plan.replace)} existing file(s) ({sample}, ...); "
                "pass overwrite=True (--overwrite) to allow it"
            )
        log.info(
            "%s: %d new, %d replace%s",
            what,
            len(plan.new),
            len(plan.replace),
            " (dry run)" if dry_run else "",
        )
        if not dry_run:
            with ThreadPoolExecutor(16) as ex:
                list(ex.map(fn, plan.new + plan.replace))
        return plan

    def pull(
        self,
        prefix: str,
        local: Path,
        include: tuple[str, ...] = (),
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> SyncPlan:
        """Download objects under prefix that are missing locally or differ in size.

        `include` holds fnmatch patterns relative to prefix, e.g. ("*/tables/*",)
        to fetch every shard's tables but no PDFs. Replacing a local file needs `overwrite`.
        """
        prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        plan = SyncPlan()
        for key, size in self.list(prefix).items():
            rel = key[len(prefix) :]
            if include and not any(fnmatch(rel, pat) for pat in include):
                continue
            dest = Path(local) / rel
            if not dest.exists():
                plan.new.append((key, dest))
            elif dest.stat().st_size != size:
                plan.replace.append((key, dest))

        def get(item: tuple[Any, Any]) -> None:
            key, dest = item
            dest.parent.mkdir(parents=True, exist_ok=True)
            self.s3.download_file(self.bucket, key, str(dest))

        return self._run(plan, get, overwrite, dry_run, f"pull r2://{self.bucket}/{prefix}")

    def push(
        self,
        local: Path,
        prefix: str,
        exclude_suffixes: tuple[str, ...] = (".part",),
        exclude_dirs: tuple[str, ...] = (),
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> SyncPlan:
        """Upload files that are missing remotely or differ in size. Replacing needs `overwrite`."""
        prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        remote = self.list(prefix)
        plan = SyncPlan()
        for f in Path(local).rglob("*"):
            if not f.is_file() or f.name.endswith(exclude_suffixes):
                continue
            if exclude_dirs and f.relative_to(local).parts[0] in exclude_dirs:
                continue
            key = prefix + f.relative_to(local).as_posix()
            if key not in remote:
                plan.new.append((f, key))
            elif remote[key] != f.stat().st_size:
                plan.replace.append((f, key))

        def put(item: tuple[Any, Any]) -> None:
            f, key = item
            self.s3.upload_file(str(f), self.bucket, key)

        return self._run(plan, put, overwrite, dry_run, f"push r2://{self.bucket}/{prefix}")


# ------------------------------------------------------------------ Hugging Face
def hf_push(local: Path, path_in_repo: str, message: str) -> None:
    from huggingface_hub import HfApi

    api, repo = HfApi(token=_env("HF_TOKEN")), _env("HF_DATASET")
    api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
    api.upload_folder(
        folder_path=str(local),
        path_in_repo=path_in_repo,
        repo_id=repo,
        repo_type="dataset",
        commit_message=message,
    )
    log.info("uploaded %s to hf://datasets/%s/%s", local, repo, path_in_repo)


def hf_pull(local: Path, patterns: list[str]) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=_env("HF_DATASET"),
        repo_type="dataset",
        token=_env("HF_TOKEN"),
        local_dir=str(local),
        allow_patterns=patterns,
    )
