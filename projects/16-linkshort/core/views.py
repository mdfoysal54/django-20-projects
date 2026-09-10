"""LinkShort views — the redirect endpoint, the dashboard and per-link analytics."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponseGone
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import LinkForm, QuickShortenForm
from .models import Click, ShortLink


def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    recent = ShortLink.objects.order_by("-created")[:3]
    return render(request, "linkshort/index.html", {
        "total_links": ShortLink.objects.count(),
        "total_clicks": ShortLink.objects.aggregate(n=Sum("click_count"))["n"] or 0,
        "sample": recent,
    })


# ------------------------------------------------------------------- redirect
def redirect_link(request, code):
    """The hot path: 302 to the target and count the click atomically."""
    link = get_object_or_404(ShortLink, code=code)
    if not link.can_redirect:
        return render(request, "linkshort/gone.html", {"link": link}, status=410)
    link.register_click(request)
    return redirect(link.target_url, permanent=False)


# ------------------------------------------------------------------ dashboard
@login_required
def dashboard(request):
    links = (ShortLink.objects.filter(owner=request.user)
             .annotate(unique=Count("clicks__ip_hash", distinct=True)))
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    tag = request.GET.get("tag", "").strip()
    if q:
        links = links.filter(Q(code__icontains=q) | Q(title__icontains=q)
                             | Q(target_url__icontains=q) | Q(tags__icontains=q))
    if status == "active":
        links = links.filter(active=True, expires_at__isnull=True) | links.filter(active=True, expires_at__gt=timezone.now())
    elif status == "disabled":
        links = links.filter(active=False)
    if tag:
        links = links.filter(tags__icontains=tag)

    qs = links.order_by("-created")
    paginator = Paginator(qs, 10)
    total_clicks = ShortLink.objects.filter(owner=request.user).aggregate(n=Sum("click_count"))["n"] or 0
    last_week = Click.objects.filter(link__owner=request.user,
                                     created__gte=timezone.now() - timedelta(days=7)).count()
    top = (ShortLink.objects.filter(owner=request.user).order_by("-click_count")[:5])
    return render(request, "linkshort/dashboard.html", {
        "page_obj": paginator.get_page(request.GET.get("page")), "q": q, "status": status, "tag": tag,
        "total_links": links.count(), "total_clicks": total_clicks, "last_week": last_week,
        "top": top, "quick_form": QuickShortenForm(),
    })


@login_required
def link_create(request):
    if request.method == "POST":
        form = LinkForm(request.POST)
        if form.is_valid():
            link = form.save(commit=False)
            link.owner = request.user
            link.save()
            messages.success(request, f"Short link ready: /s/{link.code}")
            return redirect(link)
        messages.error(request, "Please fix the highlighted fields.")
    else:
        form = LinkForm()
    return render(request, "linkshort/link_form.html", {"form": form, "mode": "create"})


@login_required
@require_POST
def quick_shorten(request):
    """Dashboard shortcut: paste a URL, get a link with a generated code."""
    form = QuickShortenForm(request.POST)
    if form.is_valid():
        link = ShortLink.objects.create(owner=request.user, target_url=form.cleaned_data["target_url"])
        messages.success(request, f"Created /s/{link.code} for {link.target_url[:50]}")
        return redirect(link)
    messages.error(request, "; ".join(e for errors in form.errors.values() for e in errors))
    return redirect("dashboard")


@login_required
def link_detail(request, code):
    link = get_object_or_404(ShortLink, code=code, owner=request.user)   # owner-scoped: 404 for others
    days = 14
    return render(request, "linkshort/link_detail.html", {
        "link": link,
        "stats": link.analytics(),
        "series": link.clicks_by_day(days),
        "max_day": max([row["count"] for row in link.clicks_by_day(days)], default=0) or 1,
        "clicks": link.clicks.all()[:25],
    })


@login_required
def link_edit(request, code):
    link = get_object_or_404(ShortLink, code=code, owner=request.user)
    if request.method == "POST":
        form = LinkForm(request.POST, instance=link)
        if form.is_valid():
            form.save()
            messages.success(request, "Link updated.")
            return redirect(link)
        messages.error(request, "Please fix the highlighted fields.")
    else:
        form = LinkForm(instance=link)
    return render(request, "linkshort/link_form.html", {"form": form, "link": link, "mode": "edit"})


@login_required
@require_POST
def link_toggle(request, code):
    link = get_object_or_404(ShortLink, code=code, owner=request.user)
    link.active = not link.active
    link.save(update_fields=["active"])
    messages.success(request, f"Link {'enabled' if link.active else 'disabled'}.")
    return redirect(link)


@login_required
@require_POST
def link_delete(request, code):
    link = get_object_or_404(ShortLink, code=code, owner=request.user)
    code_value = link.code
    link.delete()
    messages.success(request, f"/s/{code_value} deleted along with its click history.")
    return redirect("dashboard")


def link_preview(request, code):
    """Show where a short link goes before following it.

    Public on purpose: any cautious visitor can check the destination before
    they are sent to a third-party site.
    """
    link = get_object_or_404(ShortLink, code=code)
    return render(request, "linkshort/preview.html", {"link": link})


# ------------------------------------------------------------------ analytics
@login_required
def analytics(request):
    links = ShortLink.objects.filter(owner=request.user)
    clicks = Click.objects.filter(link__owner=request.user)
    window = timezone.now() - timedelta(days=30)
    recent = clicks.filter(created__gte=window)
    per_day = {}
    for offset in range(13, -1, -1):
        day = timezone.localdate() - timedelta(days=offset)
        per_day[day] = recent.filter(created__date=day).count()
    device_totals = {row["device"]: row["n"] for row in recent.values("device").annotate(n=Count("id"))}
    return render(request, "linkshort/analytics.html", {
        "total_links": links.count(),
        "total_clicks": clicks.count(),
        "clicks_30d": recent.count(),
        "unique_30d": recent.values("ip_hash").distinct().count(),
        "series": [{"date": day, "count": n} for day, n in sorted(per_day.items())],
        "max_day": max(per_day.values(), default=0) or 1,
        "devices": device_totals,
        "best_links": links.order_by("-click_count")[:8],
        "referrers": (recent.exclude(referrer="").values("referrer").annotate(n=Count("id")).order_by("-n")[:8]),
    })


@login_required
def profile(request):
    links = ShortLink.objects.filter(owner=request.user)
    return render(request, "account/profile.html", {
        "links": links.count(),
        "active_links": len([l for l in links if l.can_redirect]),
        "clicks": links.aggregate(n=Sum("click_count"))["n"] or 0,
        "best": links.order_by("-click_count").first(),
    })
