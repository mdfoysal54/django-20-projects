# Pushing this repo to GitHub

Two supported routes — both end in the same place. **Never share your GitHub
password with anyone (including an AI).** If someone asks for it, it's a scam.

---

## Route A — let the agent push (you approve once with a temporary token)

1. Create a **fine-grained Personal Access Token**:
   GitHub → *Settings* → *Developer settings* → *Personal access tokens* →
   **Fine-grained tokens** → *Generate new token*
   - **Repository access:** All repositories (or pre-create `django-20-projects` and select just it)
   - **Permissions:** Repository permissions → **Contents: Read and write**
   - **Expiration:** 7 days (shortest available)
2. Paste the token when the agent asks. The push happens immediately.
3. **Revoke the token right after** — same settings page. It takes 10 seconds
   and makes the token worthless if it ever leaks.

> What the token can do: push code to repos you selected. What it cannot do:
> change your password, access billing, delete your account, or read private
> repos it wasn't granted.

---

## Route B — push it yourself (recommended if you're unsure)

Everything is already committed on branch `main`. On any machine with Git:

```bash
# 1. Get the code onto your machine (download the workspace, then:)
cd django-20-projects

# 2. Set your identity for this repo only
git config user.name  "Your Name"
git config user.email "you@example.com"

# 3. Create an EMPTY repo on github.com named django-20-projects
#    (no README, no .gitignore, no license — this repo already has them)

# 4. Point it at your new repo and push
git remote add origin https://github.com/<your-username>/django-20-projects.git
git branch -M main
git push -u origin main
```

That's it. GitHub will ask you to authenticate (browser or a token — either
works).

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

- **About panel:** description = *Six flagship Django 5.2 projects — full-stack, tested, hardened.*
  Topics: `django` `python` `full-stack` `postgresql` `security` `portfolio`
- **Pin** the repo to your profile.
- Each project README explains its own quickstart; the root README is the index.
- Optional: enable *Actions* later — `tools/verify_all.sh` is CI-ready
  (run tests for all six projects in one command).
