#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Push this monorepo to GitHub.
#
# 1) Create a fine-grained Personal Access Token (NOT your password):
#      GitHub → Settings → Developer settings → Personal access tokens
#           → Fine-grained tokens → Generate new token
#      • Repository access: "All repositories" (or pre-create the repo and pick it)
#      • Permissions → Repository permissions → Contents: Read and write
#      • Expiration: 7 days (you can revoke it right after the push)
#
# 2) Run (token is never written to any file):
#      export GITHUB_TOKEN=github_pat_xxxxxxxx
#      bash tools/push_to_github.sh <your-github-username> [repo-name]
#
#      # repo-name defaults to "django-20-projects".
#      # The script creates the repo if it does not exist yet, then pushes main.
#
# 3) Revoke the token at the same settings page when the push is done.
# ---------------------------------------------------------------------------
set -euo pipefail

USERNAME="${1:-}"
REPO="${2:-django-20-projects}"
API="https://api.github.com"

if [[ -z "$USERNAME" ]]; then
  echo "Usage: bash tools/push_to_github.sh <github-username> [repo-name]" >&2
  exit 1
fi
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "Error: export GITHUB_TOKEN first (see the header of this script)." >&2
  exit 1
fi

cd "$(dirname "$0")/.."

echo "▶ Checking repository $USERNAME/$REPO …"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "$API/repos/$USERNAME/$REPO")

if [[ "$STATUS" == "404" ]]; then
  echo "  Creating it …"
  CREATE=$(curl -s -X POST -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -d "{\"name\":\"$REPO\",\"description\":\"Six flagship Django 5.2 projects — full-stack, tested, hardened.\",\"private\":false,\"has_issues\":true}" \
    "$API/user/repos")
  echo "$CREATE" | grep -q '"full_name"' || { echo "  ✗ Could not create the repo:"; echo "$CREATE"; exit 1; }
  echo "  ✓ created"
elif [[ "$STATUS" == "200" ]]; then
  echo "  ✓ exists — pushing to it"
else
  echo "  ✗ GitHub API replied HTTP $STATUS. Check the token's permissions (Contents: read & write)." >&2
  exit 1
fi

echo "▶ Pushing main (token used inline; never stored in .git/config) …"
git push -q "https://x-access-token:${GITHUB_TOKEN}@github.com/${USERNAME}/${REPO}.git" main

echo "▶ Done."
echo "  🌐 https://github.com/${USERNAME}/${REPO}"
echo
echo "  Next: revoke the token at https://github.com/settings/tokens"
