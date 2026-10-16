"""scripts/protected_paths.sh decides which PRs autopilot must leave for a human."""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "protected_paths.sh"


def held(*paths: str) -> list[str]:
    out = subprocess.run(
        ["bash", str(SCRIPT)],
        input="\n".join(paths) + "\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return out.split()


def test_gate_files_are_held():
    gate = [
        ".github/workflows/ponytail.yml",
        ".github/dependabot.yml",
        ".claude/skills/x/SKILL.md",
        ".claude/settings.json",
        "AGENTS.md",
        "CLAUDE.md",
        "pyproject.toml",
        ".pre-commit-config.yaml",
        "scripts/protected_paths.sh",
    ]
    assert held(*gate) == gate


def test_ordinary_files_merge():
    assert (
        held(
            "src/msp/cli.py",
            "README.md",
            "docs/AGENTS.md",
            "scripts/other.sh",
            "AGENTS.md.bak",
            "x/.github/y",
        )
        == []
    )


def test_rename_caught_by_old_name():
    # autopilot feeds both names of a renamed file; the old name alone must hold the PR
    assert held("docs/old/AGENTS.md", "AGENTS.md") == ["AGENTS.md"]


def test_empty_diff():
    assert held() == []
