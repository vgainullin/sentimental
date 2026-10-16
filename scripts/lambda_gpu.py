#!/usr/bin/env python3
"""Lambda Cloud GPU instances for embedding jobs: launch, wait, terminate, reap.

Every instance is named msp-embed-<github run id>-<launch epoch s> so `reap` can
kill instances whose workflow run is no longer in progress, or that are older than
--max-age regardless of what GitHub says (the cost backstop if a runner dies before
its terminate step). A run GitHub cannot find counts as finished; any other lookup
failure makes `reap` exit non-zero so the failure is visible.

Env: LAMBDA_API_KEY; optional LAMBDA_API_BASE (default below; Lambda has been
moving domains, so this is configurable).

  lambda_gpu.py launch --name msp-embed-123-1760000000 --ssh-key gh-actions --types gpu_1x_a10
  lambda_gpu.py terminate --id <instance id>
  lambda_gpu.py reap --repo owner/name [--finished-run ID] [--max-age S]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

BASE = os.environ.get("LAMBDA_API_BASE", "https://cloud.lambdalabs.com/api/v1")


class Lambda:
    def __init__(self, key: str | None = None, base: str = BASE, session=None):
        key = key or os.environ.get("LAMBDA_API_KEY")
        if not key:
            sys.exit("LAMBDA_API_KEY is not set")
        self.base = base.rstrip("/")
        self.s = session or requests.Session()
        self.s.auth = (key, "")  # basic auth: key as user, empty password

    def _req(self, method: str, path: str, **kw) -> dict:
        r = self.s.request(method, f"{self.base}{path}", timeout=60, **kw)
        if r.status_code >= 400:
            sys.exit(f"Lambda API {method} {path} -> {r.status_code}: {r.text[:400]}")
        return r.json()

    def pick(self, preferred: list[str], regions: list[str] | None = None) -> tuple[str, str]:
        """First preferred instance type with capacity, and a region that has it."""
        types = self._req("GET", "/instance-types")["data"]
        for t in preferred:
            avail = [r["name"] for r in types.get(t, {}).get("regions_with_capacity_available", [])]
            if regions:
                avail = [r for r in avail if r in regions]
            if avail:
                return t, avail[0]
        sys.exit(f"no capacity for any of {preferred}")

    def launch(self, name: str, ssh_key: str, itype: str, region: str) -> str:
        body = {
            "region_name": region,
            "instance_type_name": itype,
            "ssh_key_names": [ssh_key],
            "quantity": 1,
            "name": name,
        }
        return self._req("POST", "/instance-operations/launch", json=body)["data"]["instance_ids"][
            0
        ]

    def get(self, iid: str) -> dict:
        return self._req("GET", f"/instances/{iid}")["data"]

    def list(self) -> list[dict]:
        return self._req("GET", "/instances")["data"]

    def terminate(self, ids: list[str]) -> None:
        if ids:
            self._req("POST", "/instance-operations/terminate", json={"instance_ids": ids})

    def wait_active(self, iid: str, timeout: int = 900, poll: float = 15) -> dict:
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            inst = self.get(iid)
            if inst.get("status") == "active" and inst.get("ip"):
                return inst
            if inst.get("status") in ("terminated", "unhealthy"):
                sys.exit(f"instance {iid} is {inst['status']}")
            time.sleep(poll)
        self.terminate([iid])
        sys.exit(f"instance {iid} not active after {timeout}s; terminated")


def _output(**kv) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"{k}={v}")
        if path:
            with Path(path).open("a") as f:
                f.write(f"{k}={v}\n")


def run_in_progress(repo: str, run_id: str) -> bool:
    """Whether the GitHub run is still going. A run GitHub cannot find is finished.

    Raises LookupError when GitHub cannot answer (auth, rate limit, no gh), so the
    caller can fail loudly instead of keeping a GPU alive forever.
    """
    try:
        out = subprocess.run(
            ["gh", "run", "view", run_id, "--repo", repo, "--json", "status"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise LookupError(f"gh run view {run_id}: {e}") from e
    if out.returncode != 0:
        err = out.stderr.lower()
        if "could not find" in err or "not found" in err or "404" in err:
            return False
        raise LookupError(f"gh run view {run_id}: {out.stderr.strip()[:300]}")
    try:
        return json.loads(out.stdout)["status"] != "completed"
    except (ValueError, KeyError) as e:
        raise LookupError(f"gh run view {run_id}: unreadable output") from e


def parse_name(name: str, prefix: str) -> tuple[str, int | None] | None:
    """(run id, launch epoch or None) from prefix + '<run id>[-<epoch>]'; None if not ours."""
    if not name.startswith(prefix):
        return None
    run_id, _, epoch = name[len(prefix) :].partition("-")
    if not run_id.isdigit() or (epoch and not epoch.isdigit()):
        return None
    return run_id, int(epoch) if epoch else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("launch")
    s.add_argument("--name", required=True)
    s.add_argument("--ssh-key", required=True, help="name of an SSH key registered in Lambda")
    s.add_argument("--types", default="gpu_1x_a10,gpu_1x_a6000,gpu_1x_a100,gpu_1x_h100_pcie")
    s.add_argument("--regions", default="")
    s = sub.add_parser("terminate")
    s.add_argument("--id", required=True)
    s = sub.add_parser("reap")
    s.add_argument("--prefix", default="msp-embed-")
    s.add_argument("--repo", required=True)
    s.add_argument(
        "--finished-run", action="append", default=[], help="run id to treat as finished"
    )
    s.add_argument("--max-age", type=int, default=4 * 3600, help="reap anything older (s)")
    a = ap.parse_args(argv)

    lam = Lambda()
    if a.cmd == "launch":
        itype, region = lam.pick(a.types.split(","), [r for r in a.regions.split(",") if r] or None)
        iid = lam.launch(a.name, a.ssh_key, itype, region)
        _output(instance_id=iid)  # emitted first so teardown can find it
        inst = lam.wait_active(iid)
        _output(ip=inst["ip"], instance_type=itype, region=region)
    elif a.cmd == "terminate":
        lam.terminate([a.id])
        print(f"terminated {a.id}")
    elif a.cmd == "reap":
        doomed, unknown = [], []
        now = time.time()
        for inst in lam.list():
            if inst.get("status") == "terminated":
                continue
            name = inst.get("name") or ""
            if not name.startswith(a.prefix):
                continue
            parsed = parse_name(name, a.prefix)
            if parsed is None:  # ours by prefix but malformed: nothing can claim it
                doomed.append(inst["id"])
                continue
            run_id, epoch = parsed
            if epoch is not None and now - epoch > a.max_age:
                doomed.append(inst["id"])
                continue
            if run_id in a.finished_run:
                doomed.append(inst["id"])
                continue
            try:
                if not run_in_progress(a.repo, run_id):
                    doomed.append(inst["id"])
            except LookupError as e:
                unknown.append(f"{inst['id']}: {e}")
        lam.terminate(doomed)
        print(f"reaped {len(doomed)} instance(s): {doomed}")
        if unknown:
            sys.exit("could not decide on instance(s), check by hand:\n" + "\n".join(unknown))


if __name__ == "__main__":
    main()
