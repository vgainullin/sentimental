#!/usr/bin/env bash
# Read changed file paths on stdin; print the ones only a human may merge.
# Gate-defining files: workflows, agent config and skills, agent rules, lint/type/test config,
# and this list itself.
# Exit 0 either way; the caller decides on whether anything was printed.
grep -E '^(\.github/|\.claude/|AGENTS\.md$|CLAUDE\.md$|pyproject\.toml$|\.pre-commit-config\.yaml$|scripts/protected_paths\.sh$)' || true
