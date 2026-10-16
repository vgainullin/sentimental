"""HTTP client with per-host rate limiting, retries, and a disk cache.

Every JSON/XML response is cached by URL, so re-running a stage costs nothing
and paid OpenAlex calls are never repeated by accident.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import requests

log = logging.getLogger(__name__)


class Http:
    def __init__(
        self,
        cache_dir: Path,
        rate_limits: dict[str, float] | None = None,
        mailto: str | None = None,
        max_retries: int = 5,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limits = rate_limits or {}
        self.max_retries = max_retries
        self._last: dict[str, float] = {}
        self.session = requests.Session()
        ua = "math-style-pipeline/0.1"
        if mailto:
            ua += f" (mailto:{mailto})"
        self.session.headers["User-Agent"] = ua

    # ---- internals ----
    def _wait(self, host: str) -> None:
        gap = self.rate_limits.get(host, 0.0)
        dt = time.monotonic() - self._last.get(host, 0.0)
        if dt < gap:
            time.sleep(gap - dt)
        self._last[host] = time.monotonic()

    def _key(self, url: str) -> Path:
        h = hashlib.sha1(url.encode()).hexdigest()
        return self.cache_dir / h[:2] / h

    @staticmethod
    def build(url: str, params: dict[str, Any] | None) -> str:
        if not params:
            return url
        clean = {k: v for k, v in params.items() if v is not None}
        return f"{url}?{urlencode(clean)}"

    def _request(self, url: str, stream: bool = False) -> requests.Response:
        host = urlparse(url).netloc
        delay = 2.0
        for attempt in range(self.max_retries):
            self._wait(host)
            try:
                r = self.session.get(url, timeout=60, stream=stream)
            except requests.RequestException as e:
                log.warning("network error %s (%s), retry %d", url, e, attempt + 1)
            else:
                if r.status_code == 200:
                    return r
                if r.status_code in (429, 500, 502, 503, 504):
                    ra = r.headers.get("Retry-After")
                    wait = float(ra) if ra and ra.replace(".", "").isdigit() else delay
                    log.warning("HTTP %s on %s, waiting %.1fs", r.status_code, host, wait)
                    time.sleep(wait)
                else:
                    r.raise_for_status()
            delay = min(delay * 2, 60)
        raise RuntimeError(f"giving up on {url}")

    # ---- public ----
    def get_text(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        cache: bool = True,
        cache_key_url: str | None = None,
    ) -> str:
        """GET text. `cache_key_url` lets callers keep secrets (API keys) out of the key."""
        full = self.build(url, params)
        key = self._key(cache_key_url or full)
        if cache and key.exists():
            return key.read_text()
        text = self._request(full).text
        if cache:
            key.parent.mkdir(parents=True, exist_ok=True)
            key.write_text(text)
        return text

    def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        secret_params: dict[str, Any] | None = None,
        cache: bool = True,
    ) -> dict[str, Any]:
        all_params = {**(params or {}), **(secret_params or {})}
        data: dict[str, Any] = json.loads(
            self.get_text(url, all_params, cache=cache, cache_key_url=self.build(url, params))
        )
        return data

    def download(
        self,
        url: str,
        dest: Path,
        min_bytes: int = 1000,
        expect_pdf: bool = False,
        secret_params: dict[str, Any] | None = None,
    ) -> bool:
        """Stream a file to dest atomically. Returns False if it looks wrong.

        `secret_params` (e.g. an API key) are added to the request but kept out of logs.
        """
        if dest.exists() and dest.stat().st_size >= min_bytes:
            return True
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            r = self._request(self.build(url, secret_params), stream=True)
        except Exception as e:  # noqa: BLE001
            log.warning("download failed %s: %s", url, str(e).split("?")[0])
            return False
        with tmp.open("wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        head = tmp.read_bytes()[:5]
        if tmp.stat().st_size < min_bytes or (expect_pdf and head != b"%PDF-"):
            log.warning("rejecting %s (size %d, head %r)", url, tmp.stat().st_size, head)
            tmp.unlink(missing_ok=True)
            return False
        tmp.replace(dest)
        return True
