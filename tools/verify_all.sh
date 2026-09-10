#!/usr/bin/env bash
# Run the full test-suite (security + domain) for every flagship project.
# Usage:  bash tools/verify_all.sh   (from the repo root)
set -u
PASS=0
FAIL=0
for project in projects/*/; do
  name=$(basename "$project")
  if [ ! -f "$project/manage.py" ]; then continue; fi
  echo "──────────────────────────────────────────────────"
  echo "▶ $name"
  output=$(cd "$project" && python manage.py test 2>&1)
  line=$(echo "$output" | grep -E "^(Ran|OK|FAILED)" | tr '\n' ' ')
  if echo "$output" | grep -q "^OK"; then
    echo "  ✅ $line"
    PASS=$((PASS+1))
  else
    echo "  ❌ $line"
    echo "$output" | grep -E "^(FAIL|ERROR):" | head -10
    FAIL=$((FAIL+1))
  fi
done
echo "──────────────────────────────────────────────────"
echo "Projects green: $PASS · failing: $FAIL"
[ "$FAIL" -eq 0 ]
