# Publishing this repo to GitHub

Two things get published:

1. **The monorepo** → `django-20-projects` (all 16 projects, tooling, docs).
2. **One repository per project** → named after the project: `shopnest`,
   `learnhub`, `stayhub`, `devjobs`, `taskflow`, `fintrack`, `blogpress`,
   `eventtix`, `helpdesk`, `medcare`, `fittrack`, `recipebox`, `invoicepro`,
   `attendx`, `quizmaster`, `linkshort`, `nexora`, `campusos`, `aetherhr`.

Each project repository is built from the files the monorepo tracks for that
project only (no local database, no `__pycache__`, no `.env`), gets its own
`requirements.txt`, its own GitHub Actions workflow running `manage.py test`
plus `check --deploy`, and a CI badge wired to its own name.

**Never share your GitHub password with anyone (including an AI).** If someone
asks for it, it's a scam. Tokens only.

---

## Route A — one command (recommended)

### 1. Create a fine-grained token with exactly these settings

GitHub → *Settings* → *Developer settings* → *Personal access tokens* →
**Fine-grained tokens** → *Generate new token*

| Setting | Value | Why |
|---|---|---|
| **Repository access** | **All repositories** | a brand-new repository can't be pre-selected |
| **Permissions ▸ Contents** | **Read and write** | push the code |
| **Permissions ▸ Administration** | **Read and write** | create the 16 new repositories |
| **Permissions ▸ Workflows** | **Read and write** | the repos ship `.github/workflows/tests.yml` |
| **Expiration** | 7 days (shortest available) | blast radius stays tiny |

A token with only *Contents: read* can log in and list repositories, but every
push and every `POST /user/repos` comes back `403 Resource not accessible by
personal access token` — that is a permissions error, not a git error.

### 2. Run it

```bash
export GITHUB_TOKEN=github_pat_xxxxxxxx
bash tools/push_all.sh mdfoysal54
```

That pushes the monorepo first, then creates and pushes the 16 project
repositories one by one, printing a line per repository:

```
════ 1/2  monorepo ════
  ✓ pushed main → https://github.com/mdfoysal54/django-20-projects
════ 2/2  one repository per project ════
  + created mdfoysal54/shopnest
  ✓ 01-shopnest → https://github.com/mdfoysal54/shopnest  (48 files)
  …
Done — created 16, pushed 16, failed 0.
```

Useful flags and switches:

```bash
DRYRUN=1 bash tools/push_projects.sh mdfoysal54          # build every tree, push nothing
FORCE=1  bash tools/push_all.sh mdfoysal54               # overwrite existing repos
REPO_PREFIX=django- bash tools/push_projects.sh mdfoysal54   # → django-shopnest, …
bash tools/push_projects.sh mdfoysal54 01-shopnest 16-linkshort   # just these two
```

Pushing only the monorepo (what `tools/push_to_github.sh` does on its own):

```bash
export GITHUB_TOKEN=github_pat_xxxxxxxx
bash tools/push_to_github.sh mdfoysal54 django-20-projects
```

### 3. Revoke the token right after

Same settings page — 10 seconds, and the token is worthless if it ever leaks.

---

## Route B — push it yourself

Everything is already committed on branch `main`.

```bash
cd django-20-projects

git config user.name  "Your Name"
git config user.email "you@example.com"

# Create an EMPTY repo named django-20-projects on github.com
# (no README, no .gitignore, no license — this repo already has them)

git remote add origin https://github.com/<your-username>/django-20-projects.git
git branch -M main
git push -u origin main
```

For a single project as its own repository, export it and push:

```bash
mkdir -p /tmp/shopnest && git archive HEAD:projects/01-shopnest | tar -x -C /tmp/shopnest
cd /tmp/shopnest && git init -b main && git add -A \
  && git commit -m "ShopNest — standalone Django 5.2 e-commerce project" \
  && git remote add origin https://github.com/<your-username>/shopnest.git \
  && git push -u origin main
```

---

## What gets pushed, and what never will

Tracked: source code, migrations, templates, static CSS, tests, docs, and the
tooling in `tools/`.

Never tracked (see `.gitignore`):

| Item | Why |
|---|---|
| `.env` | real secrets — only `.env.example` is committed |
| `db.sqlite3` | local database; regenerated with `migrate` + `seed_demo` |
| `media/` | uploaded/generated user files |
| `staticfiles/` | collected output; regenerated with `collectstatic` |
| `__pycache__/`, `.venv/` | machine-local build artefacts |

Before any public push, confirm:

```bash
git ls-files | grep -E "\.env$|sqlite3$"      # should print nothing
```

---

## After the push — quick repository setup

- **Monorepo About panel:** description = *Sixteen deep Django 5.2 flagship
  projects — full-stack, tested, hardened.* Topics: `django` `python`
  `full-stack` `security` `portfolio` `django-projects`.
- **Each project repo:** the workflow badge is already in its README; add
  topics like `django` `python` `web-app`.
- **Pin** the monorepo and your favourite three projects to your profile.
- CI runs on every push: `manage.py test`, the page smoke-render, and
  `check --deploy` in production mode.
