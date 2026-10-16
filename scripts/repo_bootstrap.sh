#!/usr/bin/env bash
# One-command setup of agent automation for a GitHub repo, run from your own terminal
# (needs `gh auth login` as a repo admin). Portable: works on any repo with these workflows.
#
#   scripts/repo_bootstrap.sh owner/repo            # dry run: print what would change
#   scripts/repo_bootstrap.sh owner/repo --apply    # do it
#
# Sets, when the variable is in your environment (values are piped, never put in argv):
#   AUTOPILOT_TOKEN     fine-grained PAT: Contents, Pull requests, Workflows = read & write.
#                       Stored in the `autopilot` environment, usable only from main-context
#                       jobs, so a workflow added on a branch can't read it.
#   OPENROUTER_API_KEY  repo secret, for the Ponytail review
# Then enables auto-merge and branch deletion, and protects the default branch with the
# required checks in REQUIRED_CHECKS (comma-separated job names). Admins can still push.
# --apply overwrites existing secrets and branch protection (AGENTS.md §7: explicit flag).
set -euo pipefail
repo="${1:?usage: repo_bootstrap.sh owner/repo [--apply]}"
apply="${2:-}"
checks="${REQUIRED_CHECKS:-python (3.12),python (3.13),worker,workflows,review}"
branch="${BRANCH:-main}"

run() {  # print, and execute only with --apply
  if [[ "$apply" == --apply ]]; then "$@"; else echo "would run: $*"; fi
}
run_in() {  # like run, but feeds $1 on stdin; a dry run never opens the pipe (no SIGPIPE race)
  local data="$1"; shift
  if [[ "$apply" == --apply ]]; then printf '%s' "$data" | "$@"; else echo "would run: $*"; fi
}

env_policy='{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}'
run_in "$env_policy" gh api -X PUT "repos/$repo/environments/autopilot" --input - --silent
policies="repos/$repo/environments/autopilot/deployment-branch-policies"
if [[ "$apply" != --apply ]] || ! gh api "$policies" -q '.branch_policies[].name' | grep -qx "$branch"; then
  run gh api -X POST "$policies" -f name="$branch" -f type=branch --silent
fi

secret() {  # name, extra gh args
  local name="$1"; shift
  if [[ -n "${!name:-}" ]]; then
    run_in "${!name}" gh secret set "$name" --repo "$repo" "$@"
  else
    echo "skip secret $name (not in environment)"
  fi
}
secret AUTOPILOT_TOKEN --env autopilot
secret OPENROUTER_API_KEY

run gh api -X PATCH "repos/$repo" -F allow_auto_merge=true -F delete_branch_on_merge=true \
  -F allow_merge_commit=true --silent

protection="$(CHECKS="$checks" python3 -c '
import json, os
contexts = [c.strip() for c in os.environ["CHECKS"].split(",") if c.strip()]
print(json.dumps({"required_status_checks": {"strict": False, "contexts": contexts},
                  "enforce_admins": False, "required_pull_request_reviews": None,
                  "restrictions": None}))')"
echo "branch protection for $branch: $protection"
run_in "$protection" gh api -X PUT "repos/$repo/branches/$branch/protection" --input - --silent

if [[ "$apply" != --apply ]]; then echo "dry run only; re-run with --apply"; fi
