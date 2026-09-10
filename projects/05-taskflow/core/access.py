"""TaskFlow access helpers — the single place membership is enforced.

Every project-scoped view goes through one of these so the rules live in one
file instead of being re-implemented (and mis-implemented) per view.
"""
from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Project


def projects_for(user):
    """Projects the user owns or is a member of (never others')."""
    if not user.is_authenticated:
        return Project.objects.none()
    return Project.objects.filter(Q(owner=user) | Q(memberships__user=user)).distinct()


def get_project_for(user, slug) -> Project:
    """Project by slug, but only if `user` can see it — otherwise 404.

    Returning 404 (not 403) avoids leaking which project slugs exist.
    """
    return get_object_or_404(projects_for(user), slug=slug)


def require_project_role(min_role: str):
    """Decorator for function views taking a `slug` kwarg.

    min_role: one of "viewer" < "member" < "admin" < "owner".
    """
    order = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            project = get_project_for(request.user, kwargs["slug"])
            role = project.role_of(request.user) or "viewer"
            if order.get(role, -1) < order[min_role]:
                messages.error(request, "You do not have permission to do that in this project.")
                raise PermissionDenied("Insufficient project role.")
            kwargs["project"] = project
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
