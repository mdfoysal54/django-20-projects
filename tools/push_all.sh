#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Publish everything to GitHub in one shot:
#   1. the monorepo            → <owner>/django-20-projects
#   2. every project, one repo → <owner>/shopnest, <owner>/blogpress, …
#
#   export GITHUB_TOKEN=github_pat_xxx      # see docs/PUSH-TO-GITHUB.md
#   bash tools/push_all.sh mdfoysal54
#
#   DRYRUN=1 bash tools/push_all.sh mdfoysal54      # build trees, no network writes
#   FORCE=1  bash tools/push_all.sh mdfoysal54      # overwrite existing repos
#
# The token needs: Repository access = All repositories,
# and the permissions Contents, Administration and Workflows all set to
# Read and write. Revoke it when the push is done.
# ---------------------------------------------------------------------------
set -uo pipefail
cd "$(dirname "$0")"

OWNER="${1:-mdfoysal54}"
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "Error: export GITHUB_TOKEN first (see docs/PUSH-TO-GITHUB.md)." >&2
  exit 1
fi

fail=0
echo "════ 1/2  monorepo ════"
if bash push_to_github.sh "$OWNER" django-20-projects; then :; else
  echo "  ✗ monorepo push failed"; fail=1
fi

echo
echo "════ 2/2  one repository per project ════"
if bash push_projects.sh "$OWNER"; then :; else
  echo "  ✗ some project repos failed"; fail=1
fi

exit "$fail"
