# ✅ TaskFlow — team projects & kanban task manager

> Flagship **#5** of the [django-20-projects](../../README.md) monorepo.
> Django 5.2 LTS · first-party HTML/CSS frontend · hardened security baseline ·
> **33 automated tests, all green.**

A Trello-style team workspace: five-column kanban boards per project,
role-based memberships (owner / admin / member / viewer), task assignment,
due-date intelligence, comments and an append-only activity feed.

---

## Feature tour

| Area | What's implemented |
|---|---|
| **Dashboard** | Your projects with live progress bars, tasks assigned to you, overdue counters, "new project" flow |
| **Kanban board** | Five columns (Backlog → To do → In progress → Review → Done), per-column ordering with up/down moves, move any task to any column via a no-JS control |
| **Roles** | **Owner** (everything incl. archive) · **Admin** (edit project, manage members, delete tasks) · **Member** (create/edit/move tasks, comment) · **Viewer** (read-only) — each boundary is individually tested |
| **Tasks** | Title/description, priority (low → urgent badges), assignee restricted to project participants, due dates with overdue/today/soon states, hour estimates, completed-at lifecycle |
| **Collaboration** | Comments on tasks, activity feed per project + global feed (created / moved / commented / membership changes) |
| **Members** | Add existing users by username with a role; remove with one POST; owner can never be added as a duplicate member |
| **Admin** | Inline memberships & tasks per project, list-editable status/priority/assignee, archive/restore actions |

## The access model (single source of truth)

```python
# core/access.py — every project view goes through these
projects_for(user)                  # only projects you own or belong to
get_project_for(user, slug)         # 404 (not 403) for non-participants
@require_project_role("member")     # viewer < member < admin < owner
```

Decorating views with a **minimum role** keeps the matrix readable and
prevents copy-paste permission bugs. `test_role_matrix` asserts the positive
*and* negative case for every role × every gated action.

## Page map

```
/                                      dashboard
/projects/new/                         create project
/projects/<slug>/                      kanban board + activity + team
/projects/<slug>/edit/                 settings (admin+)
/projects/<slug>/archive/              POST archive/restore (owner)
/projects/<slug>/members/              member management (admin+)
/projects/<slug>/members/<id>/remove/  POST remove
/projects/<slug>/tasks/new/            create task (member+)
/projects/<slug>/tasks/<id>/move/      POST move column / reorder
/projects/<slug>/tasks/<id>/edit/      edit task (member+)
/projects/<slug>/tasks/<id>/delete/    delete task (admin+)
/tasks/<id>/                           task detail + comments
/my-tasks/  /activity/                 personal views
/profile/  /accounts/*  /admin/        account & admin
```

## Data model

```
User ──< Project ──< Membership >── User        unique (project, user)
          │
          ├──< Task ──< Comment ──> User
          │     └── assignee >── User (participants only)
          └──< Activity >── User (append-only feed)
```

- `Task.set_status()` is the only status writer — it maintains `completed_at`
  and appends the activity entry, so board and feed can never disagree.
- Membership checks live in *one* module (`core/access.py`); views never
  hand-roll permission logic.
- Cross-project IDOR is impossible twice over: `task_edit`/`task_move` look up
  by `(pk, project=…)` **and** the project itself is membership-gated.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo            # 3 projects, 19 tasks, comments, activity
python manage.py runserver
```

**Demo accounts** (all `DemoPass123!`)

| Username | Role in demo data |
|---|---|
| `alice` | owner of *Website Redesign*, member of *Mobile App v2* |
| `bob` | owner of *Mobile App v2*, member of *Website Redesign* |
| `carol` | owner of *Q3 Security Hardening*, **admin** in *Website Redesign* |
| `dave` | **viewer** in *Website Redesign*, member of *Mobile App v2* |
| `admin` | superuser |

Try it: log in as `dave` (viewer) vs `carol` (admin) on *Website Redesign* and
watch the buttons change — the server enforces the same boundaries either way.

## Tests — 33 total

- `core/tests_security.py` — 12 canonical security tests
- `core/tests.py` — 21 domain tests: project isolation + 404-not-403 for
  strangers, the full role matrix (task creation, comments, member management,
  project edit, task delete — each with positive and negative cases), board
  moves with `completed_at` lifecycle, reordering, activity logging, invalid
  column rejection, cross-project task-pk rejection, progress maths,
  due-state/overdue logic, assignee participant restriction, seeder integrity

## Security notes

Beyond the [shared baseline](../../docs/SECURITY.md):

- **No existence leaks**: non-participants get 404 for projects, not 403 —
  outsiders can't enumerate project slugs.
- Every destructive action (archive, remove member, delete task, move task)
  is POST + CSRF and role-gated server-side; the UI hiding buttons is a
  convenience, never the control.
- Comment posting re-checks edit rights on POST; a viewer who forges the
  request gets a message, not a comment row.
