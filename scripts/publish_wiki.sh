#!/usr/bin/env bash
# Copy markdown pages into the repo's GitHub wiki and push.
#   scripts/publish_wiki.sh <dir with .md pages> "<commit message>"
# Needs GH_TOKEN (GITHUB_TOKEN with contents: write is enough) and GITHUB_REPOSITORY.
# Pages are added or updated, never deleted, so generated pages from other
# workflows (Data-Status, CLI-Reference) survive.
set -euo pipefail
src="${1:?page dir}"; msg="${2:-docs: update wiki}"
repo="${GITHUB_REPOSITORY:?}"
# WIKI_REMOTE lets tests point at a local bare repo.
remote="${WIKI_REMOTE:-https://x-access-token:${GH_TOKEN:?}@github.com/${repo}.wiki.git}"
tmp="$(mktemp -d)"
if ! git clone -q --depth 1 "$remote" "$tmp/wiki" 2>/dev/null; then
  echo "::error::Wiki repo not found. Enable Wiki in Settings → Features and create any first page once; GitHub only creates the wiki's git repo after that."
  exit 1
fi
cp "$src"/*.md "$tmp/wiki/"
cd "$tmp/wiki"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A
if git diff --cached --quiet; then
  echo "wiki already up to date"
  exit 0
fi
git commit -q -m "$msg"
git push -q
echo "published $(find "$src" -maxdepth 1 -name "*.md" | wc -l) page(s) to the wiki"
