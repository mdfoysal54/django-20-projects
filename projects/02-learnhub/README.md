# 🎓 LearnHub — online learning platform (LMS)

> Flagship **#2** of the [django-20-projects](../../README.md) monorepo.
> Django 5.2 LTS · first-party HTML/CSS frontend · hardened security baseline ·
> **29 automated tests, all green.**

A complete LMS: course catalogue with search & level filters, gated lesson
content, one-click enrolment, per-lesson progress tracking with automatic
"next lesson" flow, an instructor authoring area (create → add lessons →
publish) and enrolment dashboards.

---

## Feature tour

| Area | What's implemented |
|---|---|
| **Catalogue** | Published-only listing, keyword search across title/summary/description, level filter (beginner → advanced), per-course lesson counts + total duration |
| **Course pages** | Curriculum list with durations, instructor card, "includes" panel, draft/archived badges, related enrolment state |
| **Enrolment** | One-click POST enrolment (CSRF-protected), duplicate-proof via `unique_together`, instructors auto-redirected |
| **Gated lessons** | Lesson bodies visible **only** to enrolled students, the course instructor or staff — everyone else is bounced back to the course page |
| **Progress** | Per-lesson completion records, live percentage, "next incomplete lesson" continue-button, completion celebration at 100%, idempotent marking |
| **Instructor area** | `/teach/` dashboard with per-course lesson/student counts, create course (draft by default), add lessons with collision-checked positions, **publish blocked until ≥1 lesson exists** |
| **Accounts** | Register, login throttle, password change, profile with progress digest |
| **Admin** | Course inline lesson editing, publish/unpublish/archive bulk actions, enrolment progress columns |

## Page map

```
/                                    home (hero, continue-learning, featured, how-it-works)
/courses/                            catalogue (search + level filter)
/courses/<slug>/                     course detail + curriculum
/courses/<slug>/enroll/              POST enrolment
/my-learning/                        enrolled courses with progress bars
/courses/<slug>/lessons/<id>/        lesson player (gated)
/courses/<slug>/lessons/<id>/complete/  POST mark-complete → next lesson
/teach/                              instructor dashboard
/teach/new/                          create course
/teach/<slug>/edit/                  edit + publish course
/teach/<slug>/lessons/new/           add lesson
/profile/                            account
/admin/                              Django admin
```

## Data model

```
User ──< Course ──< Lesson
  │         │           │
  │         │           └──< LessonProgress >── Enrollment
  │         └──< Enrollment >── User (unique student×course)
  └── courses_taught
```

- `Course.lesson_count`, `total_minutes`, `student_count`, `is_free` are derived, never stored twice.
- `Enrollment.progress_percent` is computed from completed `LessonProgress` rows — impossible to desync.
- `unique_together` guards: one enrolment per student per course, one progress row per lesson, unique lesson positions.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo          # 2 instructors, 6 courses, 35 lessons, 2 students
python manage.py runserver
```

**Demo accounts**

| Username | Password | Role |
|---|---|---|
| `sara` | `DemoPass123!` | instructor (4 courses) |
| `rafiq` | `DemoPass123!` | instructor (2 courses) |
| `alice` | `DemoPass123!` | student — enrolled, 3/6 lessons done |
| `bob` | `DemoPass123!` | student — enrolled in 2 courses |
| `admin` | `DemoPass123!` | superuser |

## Tests — 29 total

- `core/tests_security.py` — 12 canonical security tests
- `core/tests.py` — 17 domain tests: draft visibility rules, search & level
  filters, enrolment gating (unauthenticated *and* unenrolled), instructor
  preview rights, progress maths, idempotent completion, authoring permissions
  (404 for non-instructors), publish-without-lessons block, lesson-order
  collision rejection, seeder integrity

## Security notes

Beyond the [shared baseline](../../docs/SECURITY.md):

- Lesson content is **authorisation-gated server-side**, not hidden with CSS —
  the test suite proves an unenrolled user cannot read a lesson body even when
  they know the URL.
- Authoring views are scoped with `get_object_or_404(Course, slug=…, instructor=request.user)`,
  so guessing a slug gives a 404, never an edit form.
- Course status transitions (draft → published) are server-side state checks;
  the publish button is disabled *and* the POST is re-validated.
