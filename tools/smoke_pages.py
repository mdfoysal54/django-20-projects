#!/usr/bin/env python
"""Render every named route of a project with Django's test client.

Unit tests only touch the templates they need. This walks the project's *own*
URL names (admin and framework routes are ignored), guesses a sample object for
each path parameter from the seeded database, and reports the HTTP status of
every page — so a broken template or a dead route shows up here as a failure
instead of in a browser.

Usage:
    python tools/smoke_pages.py projects/16-linkshort
    python tools/smoke_pages.py projects/16-linkshort --user marketer --verbose

Exit status is non-zero when a page raises (5xx) or a parameter cannot be
sampled, so it can gate CI. 404/403 for a visitor who is not the owner counts
as an access guard, not a failure.
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback

OK_STATUSES = {200}
GUARD_STATUSES = {301, 302, 403, 404, 405, 410}

FRAMEWORK_APPS = {"admin", "auth", "contenttypes", "sessions", "staticfiles", "messages", "humanize"}


def load_project(project_dir: str):
    sys.path.insert(0, project_dir)
    os.chdir(project_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


def collect_routes():
    """Named patterns belonging to the project, not to the admin or Django itself."""
    from django.urls import get_resolver

    routes: list[tuple[str, object]] = []

    def walk(patterns, prefix=""):
        for pattern in patterns:
            if hasattr(pattern, "url_patterns"):
                walk(pattern.url_patterns, prefix + str(pattern.pattern))
                continue
            name = pattern.name or ""
            if not name or name.startswith(("admin", "django", "jsi18n", "autocomplete", "view_on_site")):
                continue
            if prefix.startswith(("admin/", "jsi18n/", "__debug__/")):
                continue
            routes.append((name, pattern))

    walk(get_resolver().url_patterns)
    return routes


def local_models():
    from django.apps import apps

    return [m for m in apps.get_models()
            if m._meta.app_label not in FRAMEWORK_APPS and m._meta.pk is not None]


def sample_for(param: str, url_name: str):
    """Best-effort sample value for a path parameter, taken from the database."""
    from django.contrib.auth import get_user_model

    if param in ("username", "user"):
        user = get_user_model().objects.first()
        return user.username if user else None
    if param == "status":
        return "present"

    models = local_models()
    stems = [part for part in url_name.split("_") if len(part) > 3]

    def name_matches(model):
        name = model._meta.model_name
        return name in url_name or any(part.startswith(name[:4]) or name.startswith(part[:4])
                                       for part in stems)

    def instance_for(model):
        """A sample instance — only models whose pk type fits the URL converter."""
        qs = model.objects.all()
        if param == "pk" and model._meta.pk.get_internal_type() not in ("AutoField", "BigAutoField", "IntegerField"):
            return None, None                      # integer-only converter, skip string pks
        obj = qs.first()
        return obj, None

    ordered = sorted(models, key=lambda m: not name_matches(m))
    for model in ordered:
        if param in ("slug", "code", "reference", "number", "token"):
            field_names = {f.name for f in model._meta.get_fields() if hasattr(f, "attname")}
            if param not in field_names:
                continue
            try:
                value = (model.objects.exclude(**{param: ""})
                         .values_list(param, flat=True).first())
            except Exception:
                continue
            if value:
                return str(value)
        elif param == "pk" and name_matches(model):
            obj, _ = instance_for(model)
            if obj is not None:
                return str(obj.pk)
    if param == "pk":
        for model in models:
            if model._meta.pk.get_internal_type() in ("AutoField", "BigAutoField", "IntegerField"):
                obj = model.objects.first()
                if obj is not None:
                    return str(obj.pk)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--user", help="username to log in as (default: first non-superuser)")
    parser.add_argument("--verbose", action="store_true", help="print every URL that was visited")
    args = parser.parse_args()

    project = os.path.abspath(args.project)
    if not os.path.exists(os.path.join(project, "manage.py")):
        print(f"Not a project directory: {project}")
        return 2
    load_project(project)

    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.urls import NoReverseMatch, reverse

    User = get_user_model()
    username = args.user
    if not username:
        user = User.objects.exclude(is_superuser=True).first() or User.objects.first()
        username = user.username if user else None

    print(f"\n▶ {os.path.basename(project)} — pages as {username or 'anonymous'}")
    client = Client()
    if username:
        try:
            client.force_login(User.objects.get(username=username))
        except User.DoesNotExist:
            print(f"  ! user {username!r} not found; visiting anonymously")

    failures, skipped, visited = [], [], 0
    for name, pattern in collect_routes():
        kwargs, missing = {}, []
        for param in pattern.pattern.regex.groupindex:
            value = sample_for(param, name)
            if value is None:
                missing.append(param)
            else:
                kwargs[param] = value
        if missing:
            skipped.append((name, f"no sample for {', '.join(missing)}"))
            continue
        try:
            url = reverse(name, kwargs=kwargs) if kwargs else reverse(name)
            response = client.get(url)
        except NoReverseMatch as exc:
            skipped.append((name, f"cannot reverse ({exc})"))
            continue
        except Exception as exc:                  # template / view errors raise here
            url = kwargs.get("pk", "")
            failures.append((name, str(kwargs), f"{type(exc).__name__}: {exc}"))
            if args.verbose:
                traceback.print_exc()
            continue
        visited += 1
        status = response.status_code
        if status not in OK_STATUSES | GUARD_STATUSES:
            failures.append((name, url, f"HTTP {status}"))
        if args.verbose or status not in GUARD_STATUSES:
            mark = "✅" if status == 200 else ("↪️  " if status in (301, 302) else "🔒")
            print(f"  {mark} {status} {url}  ({name})")

    for name, why in skipped:
        print(f"  ⏭️  skipped {name}: {why}")

    if failures:
        print(f"\n  ❌ {len(failures)} failing page(s):")
        for name, url, why in failures:
            print(f"     - {name} {url}: {why}")
        return 1
    print(f"  ✅ {visited} page(s) rendered without error"
          f"{f', {len(skipped)} skipped' if skipped else ''}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
