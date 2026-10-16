#!/usr/bin/env bash
# Set the repo's Actions secrets and variables from your own terminal (needs `gh auth login`).
# Values are read with hidden prompts and go straight to GitHub; nothing is written to disk.
#   scripts/bootstrap_secrets.sh owner/repo
# Leave a prompt empty to skip it (that integration's steps are then skipped in CI).
set -euo pipefail
repo="${1:?owner/repo}"

secret() {  # name, description
  local v
  read -r -s -p "$1 ($2): " v; echo
  if [[ -n "$v" ]]; then printf '%s' "$v" | gh secret set "$1" --repo "$repo"; echo "  set $1"; fi
}
var() {     # name, description, default
  local v
  read -r -p "$1 ($2) [$3]: " v
  v="${v:-$3}"
  if [[ -n "$v" ]]; then gh variable set "$1" --repo "$repo" --body "$v"; echo "  set $1=$v"; fi
}

echo "== Secrets =="
secret OPENALEX_API_KEY  "free key from openalex.org; raises the daily budget to \$1"
secret HF_TOKEN          "Hugging Face write token"
secret CF_ACCOUNT_ID     "Cloudflare account id"
secret CF_API_TOKEN      "Cloudflare token: Workers Scripts edit, Workers AI read, Vectorize edit"
secret R2_ACCESS_KEY_ID  "R2 S3 API access key id"
secret R2_SECRET_ACCESS_KEY "R2 S3 API secret"
secret SEARCH_TOKEN      "any long random string; clients send it as a Bearer token"
secret LAMBDA_API_KEY    "Lambda Cloud API key (optional)"
if [[ -f "${LAMBDA_SSH_KEY_FILE:-}" ]]; then
  gh secret set LAMBDA_SSH_PRIVATE_KEY --repo "$repo" < "$LAMBDA_SSH_KEY_FILE"; echo "  set LAMBDA_SSH_PRIVATE_KEY"
else
  echo "  (set LAMBDA_SSH_KEY_FILE=path/to/private_key to upload LAMBDA_SSH_PRIVATE_KEY)"
fi

echo "== Variables =="
var HF_DATASET           "Hugging Face dataset repo"        ""
var R2_BUCKET            "R2 bucket name"                   "math-style-data"
var VECTORIZE_INDEX      "Vectorize index name"             "math-style-chunks"
var MSP_MAILTO           "contact email in API User-Agent"  ""
var LAMBDA_SSH_KEY_NAME  "SSH key name registered in Lambda" "gh-actions"
var LAMBDA_INSTANCE_TYPES "preferred GPU types, comma-separated" "gpu_1x_a10,gpu_1x_a6000,gpu_1x_a100"
var EMBED_GPU_THRESHOLD  "chunks above which embedding moves to a GPU" "20000"
echo "done"
