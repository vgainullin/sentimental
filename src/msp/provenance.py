"""Write derived artifacts with a provenance sidecar (`<file>.meta.json`).

Each sidecar records the artifact's sha256, the git commit, parameters, and the
sha256 of every input table, so any table or embedding can be traced back to
exactly what produced it.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import BinaryIO

    import pandas as pd

    from .config import Config


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_sha() -> str:
    """Commit of the running code: GITHUB_SHA in CI, else `git rev-parse`, else 'unknown'."""
    if sha := os.environ.get("GITHUB_SHA"):
        return sha
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip()


def _write_meta(
    path: Path, cfg: Config, inputs: list[str], params: dict[str, Any] | None, extra: dict[str, Any]
) -> None:
    meta: dict[str, Any] = {
        "artifact": path.name,
        "sha256": file_sha256(path),
        "git_sha": git_sha(),
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "seed": cfg.seed,
        "params": params or {},
        "inputs": {
            name: file_sha256(cfg.table(name)) if cfg.table(name).exists() else None
            for name in inputs
        },
        **extra,
    }
    meta_path = path.with_name(path.name + ".meta.json")
    _atomic(
        meta_path, lambda f: f.write((json.dumps(meta, indent=2, sort_keys=True) + "\n").encode())
    )


def _atomic(path: Path, write: Callable[[BinaryIO], object]) -> None:
    """Write via a temp file and rename, so a killed job never leaves a partial file."""
    tmp = path.with_name(path.name + ".part")  # R2 push skips .part files
    try:
        with tmp.open("wb") as f:
            write(f)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(path)


def write_table(
    cfg: Config,
    name: str,
    df: pd.DataFrame,
    inputs: list[str] | None = None,
    params: dict[str, Any] | None = None,
) -> Path:
    path = cfg.table(name)
    _atomic(path, lambda f: df.to_parquet(f, index=False))
    _write_meta(path, cfg, inputs or [], params, {"rows": len(df), "columns": list(df.columns)})
    return path


def write_array(
    cfg: Config,
    path: Path,
    arr: np.ndarray,
    inputs: list[str] | None = None,
    params: dict[str, Any] | None = None,
) -> Path:
    _atomic(path, lambda f: np.save(f, arr))
    _write_meta(
        path, cfg, inputs or [], params, {"shape": list(arr.shape), "dtype": str(arr.dtype)}
    )
    return path
