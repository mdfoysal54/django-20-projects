"""Canonical non-Python assets shared by every flagship project:
templates, base stylesheet, .env.example and the README skeleton.
"""
from __future__ import annotations

ENV = """# __TITLE__ — environment configuration
# Copy this file to ".env" and edit the values. NEVER commit a real .env.
# Everything here is read by config/settings.py.

# 1) Generate with: python -c "import secrets; print(secrets.token_urlsafe(64))"
DJANGO_SECRET_KEY=

# Development only — MUST be false (and DJANGO_SECRET_KEY set) in production.
DJANGO_DEBUG=True

DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
# Comma-separated https origins when behind HTTPS, e.g.
DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.example

# Set all three to true after HTTPS is live (they flip cookie+redirect+HSTS hardening).
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_COOKIE_SECURE=False
DJANGO_HSTS=False
DJANGO_BEHIND_PROXY=False

DJANGO_TIME_ZONE=Asia/Dhaka
DJANGO_FROM_EMAIL=noreply@example.com

# Brute-force protection on the login form.
DJANGO_LOGIN_MAX_ATTEMPTS=5
DJANGO_LOGIN_WINDOW_SECONDS=60
"""

PROJECT_README = """# __TITLE__

> **__TAG__** — flagship Django project in the **django-20-projects** monorepo.

*Status: scaffolded — this page will be replaced by the project walkthrough
as the app is built out.*

---

## Quickstart (needs Python 3.10+)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt

cp .env.example .env             # then fill in DJANGO_SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver       # http://127.0.0.1:8000
```

Run the test-suite (43 canonical security + domain tests):

```bash
python manage.py test
```

## Tech stack

- **Django 5.2 LTS** (Python 3.10–3.13), SQLite out of the box, PostgreSQL-ready
- First-party HTML/CSS frontend, no CDN, no build step
- Argon2 password hashing, CSP + nonce, HSTS/secure-cookie flags via `.env`,
  login brute-force throttling, CSRF everywhere

## Repository layout

```
__SLUG__/
├── manage.py
├── config/            settings · root urls · wsgi/asgi
├── core/              models · views · forms · admin · middleware · tests
├── templates/         first-party pages
├── static/css/        first-party stylesheet
├── tests/             security + domain tests live in core/tests*.py
└── docs/              SECURITY.md — hardening checklist
```

## Security checklist

See **[/docs/SECURITY.md](../docs/SECURITY.md)** (monorepo-wide) and
`config/settings.py` for exactly which flags this project sets.
"""

CSS_STUB = """
/* =====================================================================
   __TITLE__ — first-party stylesheet (no CDN, no build step).
   Loaded only via staticfiles; CSP nonce is never needed for CSS here.
   ===================================================================== */

:root {
  --bg: #f4f6fb;
  --surface: #ffffff;
  --ink: #171c28;
  --muted: #5b6472;
  --line: #e3e8f0;
  --brand: #4f46e5;
  --brand-2: #7c3aed;
  --brand-ink: #ffffff;
  --ok: #059669;
  --warn: #d97706;
  --bad: #dc2626;
  --info: #0284c7;
  --radius: 14px;
  --shadow: 0 10px 30px rgba(23, 28, 40, .08);
  --shadow-sm: 0 2px 8px rgba(23, 28, 40, .06);
  --font: "Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, "Cascadia Code", "JetBrains Mono", Consolas, monospace;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: var(--font);
  background: var(--bg);
  color: var(--ink);
  line-height: 1.55;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

a { color: var(--brand); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ------------------------------------------------ layout shells */
.site-header {
  position: sticky; top: 0; z-index: 50;
  background: rgba(255, 255, 255, .92);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
}
.nav {
  max-width: 1140px; margin: 0 auto; padding: .7rem 1.25rem;
  display: flex; align-items: center; gap: 1.4rem; flex-wrap: wrap;
}
.brand {
  display: flex; align-items: center; gap: .6rem;
  font-weight: 800; font-size: 1.12rem; color: var(--ink);
}
.brand:hover { text-decoration: none; }
.brand-badge {
  width: 34px; height: 34px; border-radius: 10px;
  display: grid; place-items: center;
  background: linear-gradient(135deg, var(--brand), var(--brand-2));
  color: var(--brand-ink); font-weight: 800;
  box-shadow: 0 4px 10px rgba(79, 70, 229, .35);
}
.nav-links { display: flex; gap: .3rem; flex-wrap: wrap; }
.nav-links a {
  color: var(--muted); padding: .45rem .8rem; border-radius: 10px;
  font-weight: 600; font-size: .95rem;
}
.nav-links a:hover { background: #eef0f8; color: var(--ink); text-decoration: none; }
.nav-links a.active { color: var(--brand); background: #eef0fe; }
.nav-right { margin-left: auto; display: flex; align-items: center; gap: .6rem; flex-wrap: wrap; }
.avatar { width: 30px; height: 30px; border-radius: 50%; background: linear-gradient(135deg, var(--brand), var(--brand-2)); color: #fff; display: inline-grid; place-items: center; font-size: .8rem; font-weight: 700; }

.site-main { flex: 1; width: 100%; max-width: 1140px; margin: 0 auto; padding: 1.75rem 1.25rem 3rem; }
.container { width: 100%; max-width: 1140px; margin: 0 auto; padding: 0 1.25rem; }
.container-narrow { max-width: 760px; }
.container-tight  { max-width: 480px; }

.site-footer {
  border-top: 1px solid var(--line);
  background: var(--surface);
  color: var(--muted); font-size: .9rem;
}
.footer-inner {
  max-width: 1140px; margin: 0 auto; padding: 1.1rem 1.25rem;
  display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
}

/* ------------------------------------------------ typography */
h1, h2, h3, h4 { line-height: 1.22; margin: 0 0 .6rem; font-weight: 800; }
.page-title { margin-bottom: .25rem; }
.lede { color: var(--muted); font-size: 1.05rem; margin-top: 0; }
.muted { color: var(--muted); }
.small { font-size: .85rem; }
.mono { font-family: var(--mono); font-size: .92em; }
.mt-0 { margin-top: 0; } .mb-0 { margin-bottom: 0; }
.mt-1 { margin-top: .5rem; } .mt-2 { margin-top: 1rem; } .mt-3 { margin-top: 1.6rem; }
.mb-1 { margin-bottom: .5rem; } .mb-2 { margin-bottom: 1rem; } .mb-3 { margin-bottom: 1.6rem; }
.text-center { text-align: center; }
.text-right { text-align: right; }

/* ------------------------------------------------ buttons */
.btn {
  display: inline-flex; align-items: center; gap: .45rem;
  border: 1px solid transparent; cursor: pointer;
  padding: .55rem 1.05rem; border-radius: 10px;
  font-weight: 700; font-size: .93rem; font-family: inherit;
  transition: transform .05s ease, filter .15s ease, background .15s ease;
}
.btn:active { transform: translateY(1px); }
.btn-primary { background: linear-gradient(135deg, var(--brand), var(--brand-2)); color: #fff; box-shadow: 0 6px 16px rgba(79,70,229,.3); }
.btn-primary:hover { filter: brightness(1.07); text-decoration: none; }
.btn-secondary { background: var(--surface); color: var(--ink); border-color: var(--line); }
.btn-secondary:hover { background: #f0f2f8; text-decoration: none; }
.btn-ghost { background: transparent; color: var(--muted); }
.btn-ghost:hover { background: #eef0f8; color: var(--ink); text-decoration: none; }
.btn-danger { background: #fef2f2; color: var(--bad); border-color: #fecaca; }
.btn-danger:hover { background: #fee2e2; text-decoration: none; }
.btn-sm { padding: .3rem .7rem; font-size: .84rem; border-radius: 8px; }
.btn-lg { padding: .75rem 1.5rem; font-size: 1rem; border-radius: 12px; }
.btn-block { display: flex; width: 100%; justify-content: center; }
.btn[disabled] { opacity: .55; cursor: not-allowed; }

/* ------------------------------------------------ cards & panels */
.card {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: var(--shadow-sm);
  padding: 1.25rem; margin-bottom: 1.1rem;
}
.card-hover { transition: transform .12s ease, box-shadow .12s ease; }
.card-hover:hover { transform: translateY(-3px); box-shadow: var(--shadow); }
.card-title { font-weight: 800; margin-bottom: .35rem; }
.grid { display: grid; gap: 1.1rem; }
.grid-2 { grid-template-columns: repeat(2, 1fr); }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-4 { grid-template-columns: repeat(4, 1fr); }
@media (max-width: 960px)  { .grid-4 { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 860px)  { .grid-3 { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 620px)  { .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; } }

.stat { text-align: left; }
.stat .stat-value { font-size: 1.7rem; font-weight: 800; }
.stat .stat-label { color: var(--muted); font-size: .86rem; }

/* ------------------------------------------------ tables */
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); }
table.tbl { width: 100%; border-collapse: collapse; font-size: .94rem; }
.tbl th, .tbl td { padding: .7rem .9rem; text-align: left; border-bottom: 1px solid var(--line); vertical-align: middle; }
.tbl thead th { background: #f8f9fd; font-size: .78rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }
.tbl tbody tr:last-child td { border-bottom: none; }
.tbl tbody tr:hover { background: #fafbff; }
.tbl .num { font-variant-numeric: tabular-nums; text-align: right; }

/* ------------------------------------------------ forms */
.form-group { margin-bottom: 1rem; }
.form-label { display: block; font-weight: 700; font-size: .9rem; margin-bottom: .35rem; }
.form-control {
  width: 100%; padding: .6rem .8rem; border-radius: 10px;
  border: 1.5px solid var(--line); background: #fff; color: var(--ink);
  font: inherit; font-size: .95rem;
}
.form-control:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px rgba(79,70,229,.15); }
textarea.form-control { resize: vertical; min-height: 96px; }
select.form-control { appearance: none; }
.form-hint { font-size: .82rem; color: var(--muted); margin-top: .3rem; }
.form-error { font-size: .85rem; color: var(--bad); margin-top: .3rem; }
.field-errors { list-style: none; margin: .25rem 0 0; padding: 0; }
.field-errors li { color: var(--bad); font-size: .85rem; }
.form-check { display: flex; align-items: center; gap: .5rem; font-size: .92rem; }
.input-group { display: flex; gap: .5rem; }

/* ------------------------------------------------ badges & tags */
.badge {
  display: inline-flex; align-items: center; gap: .3rem;
  padding: .18rem .6rem; border-radius: 999px;
  font-size: .76rem; font-weight: 800; letter-spacing: .02em;
  background: #eef0f8; color: var(--muted); white-space: nowrap;
}
.badge-ok   { background: #e7f7f0; color: var(--ok); }
.badge-warn { background: #fdf1e1; color: var(--warn); }
.badge-bad  { background: #fdecec; color: var(--bad); }
.badge-info { background: #e5f3fb; color: var(--info); }
.badge-brand{ background: #eeedfd; color: var(--brand); }
.tag { display: inline-block; padding: .14rem .55rem; margin: .12rem .18rem .12rem 0; border-radius: 8px; background: #f1f3fa; color: var(--muted); font-size: .8rem; font-weight: 600; }

/* ------------------------------------------------ hero / page head */
.hero {
  padding: 2.4rem 0 .6rem;
}
.hero h1 { font-size: clamp(1.7rem, 4vw, 2.6rem); letter-spacing: -.02em; }
.hero .lede { font-size: 1.12rem; }
.page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.2rem; }
.page-head h1 { margin-bottom: .2rem; }

/* ------------------------------------------------ alerts & messages */
.alert {
  padding: .8rem 1rem; border-radius: 12px; font-weight: 600; font-size: .93rem;
  margin-bottom: 1rem; border: 1px solid transparent;
}
.alert-success { background: #e7f7f0; color: #065f46; border-color: #a7e3cd; }
.alert-error   { background: #fdecec; color: #991b1b; border-color: #f5c2c2; }
.alert-warning { background: #fdf1e1; color: #92400e; border-color: #f3d9ae; }
.alert-info    { background: #e5f3fb; color: #075985; border-color: #b4ddf3; }

/* ------------------------------------------------ auth pages */
.auth-card { max-width: 460px; margin: 3vh auto 1rem; }
.auth-card .card { padding: 2rem 2.2rem; }
.auth-heading { text-align: center; margin-bottom: 1.4rem; }
.auth-heading .brand { justify-content: center; margin-bottom: .4rem; }

/* ------------------------------------------------ misc helpers */
.empty-state {
  text-align: center; padding: 3.2rem 1.5rem; color: var(--muted);
  border: 1.5px dashed var(--line); border-radius: var(--radius);
  background: var(--surface);
}
.empty-state .big { font-size: 2.6rem; margin-bottom: .4rem; }
.section-title { font-size: 1.05rem; font-weight: 800; margin: 1.5rem 0 .8rem; }
.divider { border: none; border-top: 1px solid var(--line); margin: 1.4rem 0; }
.pill-row { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
.thumb {
  width: 64px; height: 64px; border-radius: 12px; object-fit: cover;
  background: #eef0f8; border: 1px solid var(--line);
}
.list-plain { list-style: none; padding: 0; margin: 0; }
.list-plain li { padding: .55rem 0; border-bottom: 1px solid var(--line); }
.list-plain li:last-child { border-bottom: none; }
.progress { height: 8px; background: #e8ebf3; border-radius: 999px; overflow: hidden; }
.progress > span { display: block; height: 100%; background: linear-gradient(90deg, var(--brand), var(--brand-2)); border-radius: 999px; }
.flag { font-size: 2.4rem; line-height: 1; }

footer .heart { color: var(--bad); }

@media (max-width: 720px) {
  .nav-right { margin-left: 0; width: 100%; }
  .site-main { padding-top: 1.1rem; }
  .hide-sm { display: none !important; }
}
"""

TEMPLATES = {
    # ----------------------------------------------------------------- base
    "templates/base.html": """
{% load static %}
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}{{ APP_NAME }}{% endblock %} · {{ APP_NAME }}</title>
<meta name="description" content="{% block meta_description %}{{ APP_TAGLINE }}{% endblock %}">
<meta name="color-scheme" content="light">
<link rel="stylesheet" href="{% static 'css/style.css' %}">
{% block extra_head %}{% endblock %}
</head>
<body>
<header class="site-header">
  <nav class="nav" aria-label="Main navigation">
    <a class="brand" href="{% url 'home' %}">
      <span class="brand-badge">{{ APP_NAME|slice:":1" }}</span>
      <span>{{ APP_NAME }}</span>
    </a>
    <div class="nav-links">
      {% block nav_links %}
      {% endblock %}
    </div>
    <div class="nav-right">
      {% block nav_right %}
      {% if user.is_authenticated %}
        {% url 'profile' as profile_url %}
        <span class="small muted hide-sm">Hi, <strong>{{ user.username }}</strong></span>
        {% if profile_url %}
        <a class="btn btn-sm btn-ghost" href="{{ profile_url }}">My profile</a>
        {% endif %}
        <form method="post" action="{% url 'logout' %}">
          {% csrf_token %}
          <button class="btn btn-sm btn-secondary" type="submit">Log out</button>
        </form>
      {% else %}
        <a class="btn btn-sm btn-ghost" href="{% url 'login' %}">Log in</a>
        <a class="btn btn-sm btn-primary" href="{% url 'register' %}">Sign up</a>
      {% endif %}
      {% endblock %}
    </div>
  </nav>
</header>

<main class="site-main">
  {% if messages %}
    {% for message in messages %}
      <div class="alert alert-{{ message.tags|default:'info' }}" role="status">{{ message }}</div>
    {% endfor %}
  {% endif %}

  {% block content %}{% endblock %}
</main>

<footer class="site-footer">
  <div class="footer-inner">
    <div>&copy; {% now "Y" %} {{ APP_NAME }} — {{ APP_TAGLINE }}</div>
    <div><span class="heart">&#9829;</span> Built with Django 5.2</div>
  </div>
</footer>
{% block extra_script %}{% endblock %}
</body>
</html>
""",

    # ------------------------------------------------------------- auth pages
    "templates/registration/login.html": """
{% extends "base.html" %}
{% block title %}Log in{% endblock %}
{% block content %}
<div class="auth-card">
  <div class="card">
    <div class="auth-heading">
      <div class="brand"><span class="brand-badge">{{ APP_NAME|slice:":1" }}</span><span>{{ APP_NAME }}</span></div>
      <h1 class="mt-2 mb-0">Welcome back</h1>
      <p class="muted mb-0">Log in to continue</p>
    </div>

    {% if form.non_field_errors %}
      <div class="alert alert-error">{{ form.non_field_errors }}</div>
    {% endif %}

    <form method="post" action="{% url 'login' %}" novalidate>
      {% csrf_token %}
      <input type="hidden" name="next" value="{{ next }}">
      <div class="form-group">
        <label class="form-label" for="id_username">Username</label>
        <input class="form-control" type="text" name="username" id="id_username"
               autocomplete="username" required autofocus value="{{ form.username.value|default_if_none:'' }}">
      </div>
      <div class="form-group">
        <label class="form-label" for="id_password">Password</label>
        <input class="form-control" type="password" name="password" id="id_password"
               autocomplete="current-password" required>
        {% if form.password.errors %}
          <ul class="field-errors">{% for e in form.password.errors %}<li>{{ e }}</li>{% endfor %}</ul>
        {% endif %}
      </div>
      <button class="btn btn-primary btn-block btn-lg" type="submit">Log in</button>
    </form>

    <p class="small muted text-center mb-0 mt-2">
      New here? <a href="{% url 'register' %}">Create an account</a>
    </p>
  </div>
</div>
{% endblock %}
""",

    "templates/registration/register.html": """
{% extends "base.html" %}
{% block title %}Create an account{% endblock %}
{% block content %}
<div class="auth-card">
  <div class="card">
    <div class="auth-heading">
      <div class="brand"><span class="brand-badge">{{ APP_NAME|slice:":1" }}</span><span>{{ APP_NAME }}</span></div>
      <h1 class="mt-2 mb-0">Create your account</h1>
      <p class="muted mb-0">Join {{ APP_NAME }}</p>
    </div>

    {% if form.non_field_errors %}
      <div class="alert alert-error">{{ form.non_field_errors }}</div>
    {% endif %}

    <form method="post" action="{% url 'register' %}" novalidate>
      {% csrf_token %}
      {% for field in form %}
      <div class="form-group">
        <label class="form-label" for="{{ field.id_for_label }}">{{ field.label }}</label>
        {{ field }}
        {% if field.errors %}
          <ul class="field-errors">{% for e in field.errors %}<li>{{ e }}</li>{% endfor %}</ul>
        {% endif %}
        {% if field.help_text and not field.errors %}
          <div class="form-hint">{{ field.help_text|safe }}</div>
        {% endif %}
      </div>
      {% endfor %}
      <button class="btn btn-primary btn-block btn-lg" type="submit">Create account</button>
    </form>

    <p class="small muted text-center mb-0 mt-2">
      Already have an account? <a href="{% url 'login' %}">Log in</a>
    </p>
  </div>
</div>
{% endblock %}
""",

    "templates/registration/password_change_form.html": """
{% extends "base.html" %}
{% block title %}Change password{% endblock %}
{% block content %}
<div class="auth-card">
  <div class="card">
    <div class="auth-heading">
      <h1 class="mb-0">Change your password</h1>
    </div>
    {% if form.non_field_errors %}<div class="alert alert-error">{{ form.non_field_errors }}</div>{% endif %}
    <form method="post" novalidate>
      {% csrf_token %}
      {% for field in form %}
      <div class="form-group">
        <label class="form-label" for="{{ field.id_for_label }}">{{ field.label }}</label>
        {{ field }}
        {% if field.errors %}<ul class="field-errors">{% for e in field.errors %}<li>{{ e }}</li>{% endfor %}</ul>{% endif %}
        {% if field.help_text and not field.errors %}<div class="form-hint">{{ field.help_text|safe }}</div>{% endif %}
      </div>
      {% endfor %}
      <button class="btn btn-primary btn-block" type="submit">Update password</button>
    </form>
  </div>
</div>
{% endblock %}
""",

    "templates/registration/password_change_done.html": """
{% extends "base.html" %}
{% block title %}Password changed{% endblock %}
{% block content %}
<div class="empty-state container-narrow" style="margin:4rem auto">
  <div class="big">&#128274;</div>
  <h2>Password updated</h2>
  <p>Your password was changed successfully.</p>
  <a class="btn btn-primary" href="{% url 'home' %}">Back to {{ APP_NAME }}</a>
</div>
{% endblock %}
""",

    "templates/registration/logged_out.html": """
{% extends "base.html" %}
{% block title %}Logged out{% endblock %}
{% block content %}
<div class="empty-state container-narrow" style="margin:4rem auto">
  <div class="big">&#128075;</div>
  <h2>You have been logged out</h2>
  <p>Thanks for visiting {{ APP_NAME }}. See you soon!</p>
  <a class="btn btn-primary" href="{% url 'home' %}">Back to home</a>
</div>
{% endblock %}
""",

    # ------------------------------------------------------------- error pages
    "templates/errors/404.html": """
{% extends "base.html" %}
{% block title %}Page not found{% endblock %}
{% block content %}
<div class="empty-state container-narrow" style="margin:4rem auto">
  <div class="big">&#128269;</div>
  <h1 class="h1">404 — page not found</h1>
  <p>The page you are looking for does not exist or has moved.</p>
  <a class="btn btn-primary" href="{% url 'home' %}">Go back home</a>
</div>
{% endblock %}
""",

    "templates/errors/400.html": """
{% extends "base.html" %}
{% block title %}Bad request{% endblock %}
{% block content %}
<div class="empty-state container-narrow" style="margin:4rem auto">
  <div class="big">&#128683;</div>
  <h1>400 — bad request</h1>
  <p>The request could not be understood — it may have been malformed or blocked for your safety.</p>
  <a class="btn btn-primary" href="{% url 'home' %}">Go back home</a>
</div>
{% endblock %}
""",

    "templates/errors/403.html": """
{% extends "base.html" %}
{% block title %}Access denied{% endblock %}
{% block content %}
<div class="empty-state container-narrow" style="margin:4rem auto">
  <div class="big">&#128683;</div>
  <h1>403 — access denied</h1>
  <p>You do not have permission to view this page.</p>
  <a class="btn btn-primary" href="{% url 'home' %}">Go back home</a>
</div>
{% endblock %}
""",

    "templates/errors/429.html": """
{% extends "base.html" %}
{% block title %}Too many attempts{% endblock %}
{% block content %}
<div class="empty-state container-narrow" style="margin:4rem auto">
  <div class="big">&#9203;</div>
  <h1>429 — too many attempts</h1>
  <p>Too many failed login attempts. Please wait <strong>{{ window_seconds }} seconds</strong>
     before trying again.</p>
  <a class="btn btn-primary" href="{% url 'login' %}">Try again</a>
</div>
{% endblock %}
""",

    "templates/errors/500.html": """
{% extends "base.html" %}
{% block title %}Server error{% endblock %}
{% block content %}
<div class="empty-state container-narrow" style="margin:4rem auto">
  <div class="big">&#128295;</div>
  <h1>500 — something went wrong</h1>
  <p>The server hit an unexpected error. The team has been notified — please try again shortly.</p>
  <a class="btn btn-primary" href="{% url 'home' %}">Go back home</a>
</div>
{% endblock %}
""",

    # ------------------------------------------- temporary under-construction
    "templates/construction.html": """
{% extends "base.html" %}
{% block title %}{{ page_title }}{% endblock %}
{% block content %}
<div class="hero text-center container-narrow" style="margin:6vh auto 0">
  <div class="flag">&#128736;</div>
  <h1>{{ page_title }}</h1>
  <p class="lede">This flagship project is scaffolded with its hardened baseline
     and is being built out module by module.</p>
  <p><a class="btn btn-secondary" href="/admin/">Admin panel</a>
     <a class="btn btn-ghost" href="https://docs.djangoproject.com/en/5.2/" target="_blank" rel="noopener">Django 5.2 docs</a></p>
</div>
{% endblock %}
""",
}
