#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Publish every project in this monorepo as its own GitHub repository.
#
#   GITHUB_TOKEN=github_pat_xxx bash tools/push_projects.sh <owner>
#   GITHUB_TOKEN=... bash tools/push_projects.sh <owner> 01-shopnest 16-linkshort
#   REPO_PREFIX=django- bash tools/push_projects.sh <owner>     # -> django-shopnest
#   DRYRUN=1 bash tools/push_projects.sh <owner>                # build trees only
#   FORCE=1  bash tools/push_projects.sh <owner>                # overwrite existing repos
#
# Each project becomes a repository named after the project ("shopnest",
# "blogpress", …) containing exactly the files tracked in the monorepo for that
# project — no local database, no __pycache__, no .env: those are git-ignored
# and therefore never part of the export.
#
# The token needs, on every target repository:
#   • Repository access : All repositories      (new repos cannot be pre-selected)
#   • Contents          : Read and write        (push the code)
#   • Administration    : Read and write        (create the repositories)
# ---------------------------------------------------------------------------
set -uo pipefail

API="https://api.github.com"
OWNER="${1:-}"
if [[ -z "$OWNER" ]]; then
  echo "Usage: GITHUB_TOKEN=... bash tools/push_projects.sh <owner> [project ...]" >&2
  exit 1
fi
shift || true

TOKEN="${GITHUB_TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
  echo "Error: export GITHUB_TOKEN first (see docs/PUSH-TO-GITHUB.md)." >&2
  exit 1
fi

PREFIX="${REPO_PREFIX:-}"
DRYRUN="${DRYRUN:-0}"
FORCE="${FORCE:-0}"

export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/true
GIT=(git -c credential.helper= -c core.askpass=)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

declare -A DESC=(
  [shopnest]="ShopNest — full-featured Django 5.2 e-commerce platform: catalogue, cart, checkout, stock control."
  [learnhub]="LearnHub — online learning platform: courses, lessons, enrolment and progress tracking."
  [stayhub]="StayHub — hotel and room booking engine with availability checks and date-range validation."
  [devjobs]="DevJobs — job board and recruitment portal: postings, applications, employer dashboard."
  [taskflow]="TaskFlow — team projects and kanban task manager with membership-gated boards."
  [fintrack]="FinTrack — personal finance and budget dashboard: transactions, categories, recurring rules."
  [blogpress]="BlogPress — blog and publishing platform with drafts, comments and moderation."
  [eventtix]="EventTix — ticketing with capacity control: tiers, inventory, check-in and refunds."
  [helpdesk]="HelpDesk — support ticket desk with agent queue, status rules and first-response metrics."
  [medcare]="MedCare — clinic appointments: doctor availability, slot booking and consultation notes."
  [fittrack]="FitTrack — workout tracker with sets, volume maths, streaks and personal records."
  [recipebox]="RecipeBox — recipes with ratings, favourites, collections and serving-size scaling."
  [invoicepro]="InvoicePro — freelancer invoicing: clients, invoices, payments, aging and expenses."
  [attendx]="AttendX — class attendance tracking with registers, statuses and attendance-rate reports."
  [quizmaster]="QuizMaster — quizzes with auto-grading, timed attempts, analytics and authoring studio."
  [linkshort]="LinkShort — URL shortener with atomic click analytics, expiry and click caps."
  [nexora]="Nexora — retail operating system: POS, stock, purchase, accounts, warranty, কিস্তি."
  [campusos]="CampusOS — school operating system: admissions, fees, exams, timetable, library."
  [aetherhr]="AetherHR — people operating system: HRIS, leave, Bangladesh payroll, recruiting."
  [tidetable]="TideTable — restaurant OS: floor, reservations, kitchen tickets."
  [parcelio]="Parcelio — courier OS: waybills, hub scans, last-mile, COD."
  [aurorarealty]="AuroraRealty — property OS: listings, viewings, offers."
  [salonova]="Salonova — salon OS: stylists, chairs, service menu."
  [vaultsign]="VaultSign — contract OS: rooms, envelopes, multi-party e-sign."
  [civicpulse]="CivicPulse — civic OS: wards, issues, work orders."
  [fleetnova]="FleetNova — fleet OS: vehicles, trips, odometer, fuel."
  [orbitpay]="OrbitPay — wallet OS: double-entry ledger, P2P transfers."
  [pulsegrid]="PulseGrid — SRE OS: sites, monitors, deduped incidents."
  [lexora]="Lexora — practice OS: matters, six-minute time, retainers, invoices."
)

TOKEN_LOGIN="$(curl -s -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
  "$API/user" | python3 -c "import json,sys; print(json.load(sys.stdin).get('login',''))" 2>/dev/null)"
if [[ -z "$TOKEN_LOGIN" ]]; then
  echo "✗ Token rejected by GitHub." >&2
  exit 1
fi
if [[ "$TOKEN_LOGIN" != "$OWNER" ]]; then
  echo "note: token belongs to @$TOKEN_LOGIN — publishing to @$TOKEN_LOGIN."
  OWNER="$TOKEN_LOGIN"
fi
echo "▶ Publishing projects to @$OWNER as individual repositories${PREFIX:+ (prefix: $PREFIX)}"
[[ "$DRYRUN" == "1" ]] && echo "  (dry run — nothing will be created or pushed)"

# Which projects? Everything by default, or just the names/numbers given.
declare -a SELECTED=()
if [[ $# -gt 0 ]]; then
  SELECTED=("$@")
else
  for d in projects/*/; do SELECTED+=("$(basename "$d")"); done
fi

created=0; pushed=0; failed=0; dry=0

for project in "${SELECTED[@]}"; do
  # Accept "07-blogpress", "blogpress" or "07".
  match=""
  for d in projects/*/; do
    base="$(basename "$d")"; slug="${base#*-}"
    if [[ "$project" == "$base" || "$project" == "$slug" || "$project" == "${base%%-*}" ]]; then match="$base"; fi
  done
  if [[ -z "$match" ]]; then echo "  ✗ $project: no such project directory"; failed=$((failed+1)); continue; fi

  slug="${match#*-}"
  repo="$PREFIX$slug"
  desc="${DESC[$slug]:-Django 5.2 project — see README for details.}"

  # ---- 1. build the standalone tree from the monorepo's tracked files -------
  tmp="$(mktemp -d)"
  if ! git archive "HEAD:projects/$match" 2>/dev/null | tar -x -C "$tmp"; then
    echo "  ✗ $match: not committed in the monorepo yet — commit first, then re-run"
    rm -rf "$tmp"; failed=$((failed+1)); continue
  fi
  if [[ ! -f "$tmp/manage.py" || ! -f "$tmp/requirements.txt" ]]; then
    echo "  ✗ $match: export is incomplete (missing manage.py/requirements.txt)"
    rm -rf "$tmp"; failed=$((failed+1)); continue
  fi

  # ---- 1b. give the standalone repo its own CI + badge ----------------------
  mkdir -p "$tmp/.github/workflows"
  cat > "$tmp/.github/workflows/tests.yml" <<'CI'
name: tests

on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Test-suite (security + domain)
        run: python manage.py test

      - name: Production deploy check (fails if hardening regressed)
        env:
          DJANGO_DEBUG: "False"
          DJANGO_SECRET_KEY: "ci-only-key-abcdefghijklmnopqrstuvwxyz-0123456789-ABCDEFGHIJ"
          DJANGO_ALLOWED_HOSTS: "example.com"
          DJANGO_CSRF_TRUSTED_ORIGINS: "https://example.com"
          DJANGO_SECURE_SSL_REDIRECT: "True"
          DJANGO_COOKIE_SECURE: "True"
          DJANGO_HSTS: "True"
        run: python manage.py check --deploy
CI
  BADGE="${BADGE:-1}" python3 - "$tmp/README.md" "$OWNER" "$repo" <<'PYEOF2'
import os, pathlib, sys
readme, owner, repo = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
if readme.exists() and os.environ.get("BADGE", "1") != "0":
    text = readme.read_text()
    if "actions/workflows/tests.yml" not in text:
        lines = text.splitlines()
        badge = (f"[![tests](https://github.com/{owner}/{repo}/actions/workflows/tests.yml/badge.svg)]"
                 f"(https://github.com/{owner}/{repo}/actions/workflows/tests.yml)")
        if lines and lines[0].startswith("# "):
            lines[1:1] = ["", badge, ""]
        else:
            lines[0:0] = [badge, ""]
        readme.write_text("\n".join(lines) + "\n")
PYEOF2
  files="$(find "$tmp" -type f | wc -l | tr -d ' ')"

  if [[ "$DRYRUN" == "1" ]]; then
    echo "  ✓ $match → $repo  ($files files ready)"
    rm -rf "$tmp"; dry=$((dry+1)); continue
  fi

  # ---- 2. create the repository if it does not exist ------------------------
  code="$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" "$API/repos/$OWNER/$repo")"
  if [[ "$code" == "404" ]]; then
    body="$(python3 - "$repo" "$desc" <<'PY'
import json, sys
print(json.dumps({"name": sys.argv[1], "description": sys.argv[2], "private": False,
                  "has_issues": True, "has_wiki": False, "has_projects": False,
                  "auto_init": False}))
PY
)"
    resp="$(curl -s -w "\n%{http_code}" -X POST -H "Authorization: Bearer $TOKEN" \
      -H "Accept: application/vnd.github+json" "$API/user/repos" -d "$body")"
    status="$(printf '%s' "$resp" | tail -1)"
    if [[ "$status" != "201" ]]; then
      msg="$(printf '%s' "$resp" | head -n -1 | python3 -c "import json,sys; print(json.load(sys.stdin).get('message',''))" 2>/dev/null)"
      echo "  ✗ $match: could not create $OWNER/$repo — HTTP $status ${msg:+(${msg})}"
      echo "      → the token needs 'Administration: Read and write' and access to All repositories"
      rm -rf "$tmp"; failed=$((failed+1)); continue
    fi
    echo "  + created $OWNER/$repo"
    created=$((created+1))
  elif [[ "$code" != "200" ]]; then
    echo "  ✗ $match: cannot read $OWNER/$repo (HTTP $code) — is the token authorised for it?"
    rm -rf "$tmp"; failed=$((failed+1)); continue
  fi

  # ---- 3. commit the standalone tree and push ------------------------------
  (
    cd "$tmp"
    "${GIT[@]}" init -q -b main
    "${GIT[@]}" config user.name  "django-20-projects"
    "${GIT[@]}" config user.email "dev@django-20-projects.local"
    "${GIT[@]}" add -A
    "${GIT[@]}" commit -q -m "$match — standalone repository

Published from the django-20-projects monorepo.
Quickstart: python -m venv .venv && pip install -r requirements.txt
            python manage.py migrate && python manage.py seed_demo
            python manage.py runserver"
    "${GIT[@]}" remote add origin "https://x-access-token:${TOKEN}@github.com/$OWNER/$repo.git"
    if "${GIT[@]}" push -q -u origin main 2>/tmp/push_err; then
      exit 0
    fi
    if [[ "$FORCE" == "1" ]] && "${GIT[@]}" push -q --force -u origin main 2>>/tmp/push_err; then
      exit 0
    fi
    exit 1
  )
  if [[ $? -eq 0 ]]; then
    echo "  ✓ $match → https://github.com/$OWNER/$repo  ($files files)"
    pushed=$((pushed+1))
  else
    echo "  ✗ $match: push to $OWNER/$repo failed — $(tail -1 /tmp/push_err 2>/dev/null)"
    failed=$((failed+1))
  fi
  rm -rf "$tmp"
done

echo
if [[ "$DRYRUN" == "1" ]]; then
  echo "Dry run: $dry project tree(s) ready to publish."
else
  echo "Done — created $created, pushed $pushed, failed $failed."
  [[ "$failed" -gt 0 ]] && echo "Tip: the token must have Contents: Read and write and Administration: Read and write."
fi
exit 0
