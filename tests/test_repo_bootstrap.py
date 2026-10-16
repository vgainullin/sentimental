"""repo_bootstrap.sh against a fake `gh` that records its arguments and stdin."""

import json
import os
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "repo_bootstrap.sh"


def _run(tmp_path: Path, *args: str, **env: str) -> tuple[str, list[dict]]:
    log = tmp_path / "calls.jsonl"
    fake = tmp_path / "gh"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(log)!r}, 'a').write(json.dumps("
        "{'argv': sys.argv[1:], 'stdin': sys.stdin.read()}) + '\\n')\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    base = {"PATH": f"{tmp_path}:{os.environ['PATH']}", "HOME": str(tmp_path)}
    out = subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env={**base, **env},
        check=True,
    ).stdout
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return out, calls


def test_dry_run_changes_nothing(tmp_path):
    out, calls = _run(tmp_path, "o/r", AUTOPILOT_TOKEN="ghp_secret")
    assert calls == []
    assert "would run: gh secret set AUTOPILOT_TOKEN --repo o/r --env autopilot" in out
    assert (
        "would run: gh api -X POST repos/o/r/environments/autopilot/deployment-branch-policies"
        in out
    )
    assert "skip secret OPENROUTER_API_KEY" in out
    assert "ghp_secret" not in out  # secret never printed
    assert "re-run with --apply" in out


def test_apply_sets_secrets_settings_and_protection(tmp_path):
    _, calls = _run(
        tmp_path,
        "o/r",
        "--apply",
        AUTOPILOT_TOKEN="ghp_secret",
        OPENROUTER_API_KEY="sk-or-x",
        REQUIRED_CHECKS="ci, review ,",
    )
    secret = {c["argv"][2]: c for c in calls if c["argv"][:2] == ["secret", "set"]}
    assert secret["AUTOPILOT_TOKEN"]["stdin"] == "ghp_secret"
    assert secret["AUTOPILOT_TOKEN"]["argv"][-2:] == ["--env", "autopilot"]  # env, not repo
    assert secret["OPENROUTER_API_KEY"]["stdin"] == "sk-or-x"
    assert "--env" not in secret["OPENROUTER_API_KEY"]["argv"]
    env = next(c for c in calls if c["argv"][3:4] == ["repos/o/r/environments/autopilot"])
    assert json.loads(env["stdin"])["deployment_branch_policy"]["custom_branch_policies"] is True
    post = next(c for c in calls if c["argv"][:3] == ["api", "-X", "POST"])
    assert "name=main" in post["argv"]  # only main may use the environment
    assert all("ghp_secret" not in a and "sk-or-x" not in a for c in calls for a in c["argv"])
    patch = next(c for c in calls if c["argv"][:3] == ["api", "-X", "PATCH"])
    assert (
        "allow_auto_merge=true" in patch["argv"] and "delete_branch_on_merge=true" in patch["argv"]
    )
    put = next(c for c in calls if c["argv"][3:4] == ["repos/o/r/branches/main/protection"])
    assert put["argv"][:3] == ["api", "-X", "PUT"]
    body = json.loads(put["stdin"])
    assert body["required_status_checks"] == {"strict": False, "contexts": ["ci", "review"]}
    assert body["enforce_admins"] is False and body["required_pull_request_reviews"] is None
