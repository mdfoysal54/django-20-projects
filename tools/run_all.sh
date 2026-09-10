#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Start all six flagship dev servers at once (local development).
#
#   bash tools/run_all.sh          # serve on ports 8000–8005
#   Ctrl+C                          # stop everything
#
# Each project keeps its own SQLite database. If a project has never been
# migrated/seeded on this machine, run its quickstart first:
#   cd projects/<name> && python manage.py migrate && python manage.py seed_demo
# ---------------------------------------------------------------------------
set -uo pipefail

cd "$(dirname "$0")/.."

PROJECTS=(
  "01-shopnest:8000:🛍️  ShopNest"
  "02-learnhub:8001:🎓  LearnHub"
  "03-stayhub:8002:🛎️  StayHub"
  "04-devjobs:8003:💼  DevJobs"
  "05-taskflow:8004:✅  TaskFlow"
  "06-fintrack:8005:💹  FinTrack"
)

PIDS=()
trap 'echo; echo "Stopping all servers…"; kill "${PIDS[@]}" 2>/dev/null; exit 0' INT TERM

for entry in "${PROJECTS[@]}"; do
  IFS=":" read -r dir port label <<< "$entry"
  project="projects/$dir"
  if [[ ! -f "$project/manage.py" ]]; then
    echo "skip: $project not found"; continue
  fi
  if [[ ! -f "$project/db.sqlite3" ]]; then
    echo "note: $project has no database — running migrate + seed_demo"
    (cd "$project" && python manage.py migrate -v 0 && python manage.py seed_demo -v 0) \
      || { echo "  ✗ setup failed for $dir"; continue; }
  fi
  # `exec` makes the recorded PID the Python process itself, so the Ctrl+C
  # trap below reliably stops the actual servers (not just the wrapper).
  (cd "$project" && DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1" \
      exec python manage.py runserver "0.0.0.0:$port" --noreload >/dev/null 2>&1) &
  PIDS+=($!)
  printf "%-14s %-6s http://127.0.0.1:%s\n" "$label" ":$port" "$port"
done

echo
echo "All servers running. Demo logins: alice / DemoPass123!  (admin / DemoPass123! for /admin/)"
echo "Press Ctrl+C to stop."
wait
