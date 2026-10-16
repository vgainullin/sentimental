"""Lambda Cloud helper against a fake API (no network, no spend)."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "lambda_gpu", Path(__file__).parents[1] / "scripts" / "lambda_gpu.py"
)
lg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lg)


class Resp:
    def __init__(self, data, status=200):
        self._d, self.status_code, self.text = data, status, str(data)

    def json(self):
        return self._d


class FakeSession:
    def __init__(self):
        self.auth, self.calls, self.polls = None, [], 0
        self.instances = {
            "i-old": {"id": "i-old", "name": "msp-embed-111", "status": "active"},
            "i-mine": {"id": "i-mine", "name": "msp-embed-222", "status": "active"},
            "i-other": {"id": "i-other", "name": "someone-else", "status": "active"},
        }

    def request(self, method, url, timeout, json=None):
        path = url.split("/api/v1")[1]
        self.calls.append((method, path, json))
        if path == "/instance-types":
            return Resp(
                {
                    "data": {
                        "gpu_1x_a10": {"regions_with_capacity_available": []},
                        "gpu_1x_a100": {
                            "regions_with_capacity_available": [
                                {"name": "us-west-2"},
                                {"name": "us-east-1"},
                            ]
                        },
                    }
                }
            )
        if path == "/instance-operations/launch":
            return Resp({"data": {"instance_ids": ["i-new"]}})
        if path == "/instances/i-new":
            self.polls += 1
            st = {"status": "booting"} if self.polls < 3 else {"status": "active", "ip": "1.2.3.4"}
            return Resp({"data": st})
        if path == "/instances":
            return Resp({"data": list(self.instances.values())})
        if path == "/instance-operations/terminate":
            return Resp({"data": {"terminated_instances": json["instance_ids"]}})
        return Resp({"error": "nope"}, 404)


def test_pick_launch_wait():
    s = FakeSession()
    lam = lg.Lambda("key", base="https://x/api/v1", session=s)
    assert s.auth == ("key", "")
    assert lam.pick(["gpu_1x_a10", "gpu_1x_a100"]) == ("gpu_1x_a100", "us-west-2")
    assert lam.pick(["gpu_1x_a100"], regions=["us-east-1"]) == ("gpu_1x_a100", "us-east-1")
    iid = lam.launch("msp-embed-5", "gh", "gpu_1x_a100", "us-west-2")
    body = s.calls[-1][2]
    assert iid == "i-new" and body["ssh_key_names"] == ["gh"] and body["quantity"] == 1
    assert lam.wait_active(iid, poll=0)["ip"] == "1.2.3.4"


def test_no_capacity_exits():
    lam = lg.Lambda("key", base="https://x/api/v1", session=FakeSession())
    with pytest.raises(SystemExit):
        lam.pick(["gpu_1x_a10"])


def test_reap_only_finished_runs(monkeypatch):
    s = FakeSession()
    real = lg.Lambda("key", base="https://x/api/v1", session=s)
    monkeypatch.setattr(lg, "Lambda", lambda: real)
    monkeypatch.setattr(lg, "run_in_progress", lambda repo, rid: rid == "222")
    lg.main(["reap", "--repo", "o/r"])
    term = [c for c in s.calls if c[1] == "/instance-operations/terminate"]
    assert term[0][2] == {"instance_ids": ["i-old"]}  # 222 still running; other prefix ignored


def test_api_error_exits():
    lam = lg.Lambda("key", base="https://x/api/v1", session=FakeSession())
    with pytest.raises(SystemExit, match="404"):
        lam.get("missing")


def _reap(monkeypatch, instances, in_progress, *args):
    s = FakeSession()
    s.instances = {i["id"]: i for i in instances}
    real = lg.Lambda("key", base="https://x/api/v1", session=s)
    monkeypatch.setattr(lg, "Lambda", lambda: real)
    monkeypatch.setattr(lg, "run_in_progress", in_progress)
    exit_code = None
    try:
        lg.main(["reap", "--repo", "o/r", *args])
    except SystemExit as e:
        exit_code = e.code
    term = [c[2]["instance_ids"] for c in s.calls if c[1] == "/instance-operations/terminate"]
    return (term[0] if term else []), exit_code


def test_reap_age_cap_beats_running_status(monkeypatch):
    old = int(lg.time.time()) - 5 * 3600
    fresh = int(lg.time.time()) - 60
    insts = [
        {"id": "i-stale", "name": f"msp-embed-1-{old}", "status": "active"},
        {"id": "i-fresh", "name": f"msp-embed-2-{fresh}", "status": "active"},
    ]
    term, code = _reap(monkeypatch, insts, lambda repo, rid: True)
    assert term == ["i-stale"] and code is None


def test_reap_unknown_status_reaps_others_and_fails(monkeypatch):
    insts = [
        {"id": "i-done", "name": "msp-embed-1", "status": "active"},
        {"id": "i-?", "name": "msp-embed-2", "status": "active"},
    ]

    def status(repo, rid):
        if rid == "2":
            raise LookupError("rate limited")
        return False

    term, code = _reap(monkeypatch, insts, status)
    assert term == ["i-done"]
    assert "i-?" in str(code) and "rate limited" in str(code)  # non-zero exit names it


def test_reap_finished_run_flag_reaps_own_run(monkeypatch):
    insts = [{"id": "i-own", "name": f"msp-embed-77-{int(lg.time.time())}", "status": "active"}]
    term, _ = _reap(monkeypatch, insts, lambda repo, rid: True, "--finished-run", "77")
    assert term == ["i-own"]


def test_reap_malformed_prefixed_name_is_reaped(monkeypatch):
    insts = [{"id": "i-bad", "name": "msp-embed-oops", "status": "active"}]
    term, code = _reap(monkeypatch, insts, lambda repo, rid: True)
    assert term == ["i-bad"] and code is None


class Done:
    def __init__(self, rc, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def test_run_in_progress_outcomes(monkeypatch):
    def fake(result):
        monkeypatch.setattr(lg.subprocess, "run", lambda *a, **k: result)

    fake(Done(0, '{"status": "in_progress"}'))
    assert lg.run_in_progress("o/r", "1") is True
    fake(Done(0, '{"status": "completed"}'))
    assert lg.run_in_progress("o/r", "1") is False
    fake(Done(1, err="could not find any workflow run with ID: 1"))
    assert lg.run_in_progress("o/r", "1") is False  # deleted run = finished
    fake(Done(1, err="HTTP 403: API rate limit exceeded"))
    with pytest.raises(LookupError, match="rate limit"):
        lg.run_in_progress("o/r", "1")

    def missing(*a, **k):
        raise FileNotFoundError("gh")

    monkeypatch.setattr(lg.subprocess, "run", missing)
    with pytest.raises(LookupError):
        lg.run_in_progress("o/r", "1")


def test_parse_name():
    assert lg.parse_name("msp-embed-12-1700", "msp-embed-") == ("12", 1700)
    assert lg.parse_name("msp-embed-12", "msp-embed-") == ("12", None)
    assert lg.parse_name("msp-embed-x-1", "msp-embed-") is None
    assert lg.parse_name("other-12", "msp-embed-") is None
