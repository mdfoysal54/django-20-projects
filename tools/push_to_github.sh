#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Push this monorepo to GitHub.
#
# 1) Create a fine-grained Personal Access Token (NOT your password):
#      GitHub → Settings → Developer settings → Personal access tokens
#           → Fine-grained tokens → Generate new token
#      • Repository access: "All repositories" (or pre-create the repo and pick it)
#      • Permissions → Repository permissions → Contents: Read and write
#      • Expiration: 7 days (revoke it right after the push)
#
# 2) Run (token is never written to any file in this repo):
#      export GITHUB_TOKEN=github_pat_xxxxxxxx
#      bash tools/push_to_github.sh <your-github-username> [repo-name]
#
#      # repo-name defaults to "django-20-projects".
#      # Creates the repo if it doesn't exist, then pushes main.
#
# 3) Revoke the token when done:
#      https://github.com/settings/tokens
# ---------------------------------------------------------------------------
set -euo pipefail

USERNAME="${1:-}"
REPO="${2:-django-20-projects}"
API="https://api.github.com"
TOKEN="${GITHUB_TOKEN:-}"

if [[ -z "$USERNAME" ]]; then
  echo "Usage: bash tools/push_to_github.sh <github-username> [repo-name]" >&2
  exit 1
fi
if [[ -z "$TOKEN" ]]; then
  echo "Error: export GITHUB_TOKEN first (see the header of this script)." >&2
  exit 1
fi

# Never let git prompt for credentials or cache them on disk.
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/true
GIT_SAFE=(git -c credential.helper= -c core.askpass=)

cd "$(dirname "$0")/.."
git rev-parse --git-dir >/dev/null 2>&1 || { echo "Error: not a git repository." >&2; exit 1; }

# --- 1. verify the token and identify the account --------------------------
echo "▶ Verifying token …"
WHOAMI=$(curl -s -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" "$API/user")
LOGIN=$(printf '%s' "$WHOAMI" | python3 -c "import json,sys; print(json.load(sys.stdin).get('login',''))" 2>/dev/null || true)
if [[ -z "$LOGIN" ]]; then
  echo "  ✗ The token was rejected by GitHub. Common causes:" >&2
  echo "    • token expired or copied incompletely" >&2
  echo "    • fine-grained token missing 'Contents: Read and write' permission" >&2
  echo "    • token not authorised for the target repository" >&2
  exit 1
fi
echo "  ✓ authenticated as @$LOGIN"

if [[ "$LOGIN" != "$USERNAME" ]]; then
  echo "  note: token belongs to @$LOGIN, not @$USERNAME — pushing to @$LOGIN/$REPO."
  USERNAME="$LOGIN"
fi

# --- 2. wire the CI badge + identity into the repo -------------------------
if [[ -z "$(git config user.email || true)" ]]; then
  git config user.name "django-20-projects"
  git config user.email "dev@django-20-projects.local"
fi
if grep -q "OWNER/django-20-projects" README.md 2>/dev/null && [[ "$USERNAME" != "OWNER" ]]; then
  sed -i.bak "s|OWNER/django-20-projects|$USERNAME/$REPO|g" README.md && rm -f README.md.bak
  git add README.md
  git commit -q -m "ci: point Actions badge at $USERNAME/$REPO" || true
  echo "▶ CI badge wired to $USERNAME/$REPO"
fi

# --- 3. create the repository if needed ------------------------------------
echo "▶ Checking repository $USERNAME/$REPO …"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
  "$API/repos/$USERNAME/$REPO")

if [[ "$STATUS" == "404" ]]; then
  echo "  doesn't exist yet — creating (public, issues enabled) …"
  CREATE=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -d "{\"name\":\"$REPO\",\"description\":\"Six flagship Django 5.2 projects — full-stack, tested, hardened.\",\"private\":false,\"has_issues\":true,\"has_wiki\":false}" \
    "$API/user/repos")
  printf '%s' "$CREATE" | grep -q '"full_name"' || { echo "  ✗ Could not create the repo:"; printf '%s\n' "$CREATE"; exit 1; }
  echo "  ✓ created"
elif [[ "$STATUS" == "200" ]]; then
  echo "  ✓ exists — pushing into it"
else
  echo "  ✗ GitHub API replied HTTP $STATUS. Check the token's 'Contents: Read and write' permission." >&2
  exit 1
fi

# --- 4. push ----------------------------------------------------------------
REMOTE_URL="https://x-access-token:${TOKEN}@github.com/${USERNAME}/${REPO}.git"
"${GIT_SAFE[@]}" remote remove origin >/dev/null 2>&1 || true
"${GIT_SAFE[@]}" remote add origin "https://github.com/${USERNAME}/${REPO}.git"

echo "▶ Pushing main …"
if "${GIT_SAFE[@]}" push --quiet "$REMOTE_URL" main 2>/tmp/gh_push_err; then
  :
elif [[ "${FORCE:-0}" == "1" ]]; then
  echo "  retrying with --force (FORCE=1 was set) …"
  "${GIT_SAFE[@]}" push --quiet --force "$REMOTE_URL" main
else
  echo "  ✗ Push rejected:" >&2
  sed 's/x-access-token:[^@]*@/x-access-token:***@/g' /tmp/gh_push_err >&2 || true
  echo >&2
  echo "  Most likely the repo was created WITH a README/license, so its history differs." >&2
  echo "  Fix A (safest): delete that repo on GitHub and re-run this script." >&2
  echo "  Fix B: keep the repo and re-run with:  FORCE=1 bash tools/push_to_github.sh $USERNAME $REPO" >&2
  exit 1
fi
rm -f /tmp/gh_push_err

# --- 5. summary --------------------------------------------------------------
echo "▶ Done ✅"
"${GIT_SAFE[@]}" remote -v | head -2
echo "  🌐 https://github.com/$USERNAME/$REPO"
echo
echo "  Next: revoke the token → https://github.com/settings/tokens"
