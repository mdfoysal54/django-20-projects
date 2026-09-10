"""Shared model helpers for LearnHub."""
from __future__ import annotations

from django.db import models
from django.utils.text import slugify


def unique_slug(model: type[models.Model], value: str, exclude_pk=None) -> str:
    """Return a URL-safe slug guaranteed unique across `model`."""
    base = slugify(value)[:50] or "item"
    slug, n = base, 1
    qs = model.objects.filter(slug=slug)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.exists():
        n += 1
        slug = f"{base}-{n}"
        qs = model.objects.filter(slug=slug)
    return slug
