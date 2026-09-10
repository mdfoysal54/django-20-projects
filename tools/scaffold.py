#!/usr/bin/env python3
"""Scaffold the django-20-projects monorepo.

Generates the full skeleton of every flagship project from one canonical source
so settings, middleware, auth plumbing and security templates are identical
across projects (and stay consistent when fixes are applied).
"""
from __future__ import annotations

import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import canonical          # noqa: E402  (python code templates)
import canonical_assets   # noqa: E402  (templates / css / assets)


def render(text: str, slug: str, title: str, tag: str) -> str:
    return (text.replace("__SLUG__", slug)
                .replace("__TITLE__", title)
                .replace("__TAG__", tag))


def write(rel_path: pathlib.Path, content: str, slug: str, title: str, tag: str) -> None:
    rel_path.parent.mkdir(parents=True, exist_ok=True)
    rel_path.write_text(render(content, slug, title, tag), encoding="utf-8")


def make_project(meta: dict) -> None:
    slug, title, tag = meta["dir"], meta["title"], meta["tag"]
    base = ROOT / "projects" / slug
    files = [
        ("manage.py", canonical.MANAGE),
        ("config/__init__.py", "# Django project package.\n"),
        ("config/settings.py", canonical.SETTINGS),
        ("config/urls.py", canonical.CONFIG_URLS),
        ("config/wsgi.py", canonical.WSGI),
        ("config/asgi.py", canonical.ASGI),
        ("core/__init__.py", ""),
        ("core/apps.py", canonical.APPS),
        ("core/middleware.py", canonical.MIDDLEWARE),
        ("core/auth_views.py", canonical.AUTH_VIEWS),
        ("core/models.py", canonical.MODELS_STUB),
        ("core/forms.py", canonical.FORMS_STUB),
        ("core/admin.py", canonical.ADMIN_STUB),
        ("core/views.py", canonical.VIEWS_STUB),
        ("core/views_errors.py", canonical.VIEWS_ERRORS),
        ("core/urls.py", canonical.CORE_URLS),
        ("core/tests.py", canonical.TESTS_STUB),
        ("core/tests_security.py", canonical.TESTS_SECURITY),
        ("core/migrations/__init__.py", ""),
        ("static/css/style.css", canonical_assets.CSS_STUB),
        (".env.example", canonical_assets.ENV),
        ("README.md", canonical_assets.PROJECT_README),
    ]
    for rel, content in files:
        write(base / rel, content, slug, title, tag)
    for rel, content in canonical_assets.TEMPLATES.items():
        write(base / rel, content, slug, title, tag)
    print(f"[ok] {slug}  ({title})")


def main() -> None:
    print(f"Scaffolding {len(canonical.PROJECTS)} projects under {ROOT / 'projects'}")
    for meta in canonical.PROJECTS:
        make_project(meta)
    print("Done.")


if __name__ == "__main__":
    main()
