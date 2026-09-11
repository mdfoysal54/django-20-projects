from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Envelope, Room, Signer
from .services import DomainError, send, sign, void

NAV = [("Vault", [("dashboard", "Rooms"), ("envelope_list", "Envelopes"), ("envelope_new", "New")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    qs = Envelope.objects.all()
    return render(request, "app/dashboard.html", _ctx(request, rows=qs.order_by("-id")[:30],
        sent=qs.filter(status="sent").count(), signed=qs.filter(status="signed").count()))

@login_required
def envelope_list(request):
    return render(request, "app/list.html", _ctx(request, title="Envelopes", rows=Envelope.objects.all(), kind="env"))

@login_required
def envelope_detail(request, number):
    env = get_object_or_404(Envelope, number=number)
    if request.method == "POST":
        act = request.POST.get("act")
        try:
            if act == "add":
                Signer.objects.create(envelope=env, name=request.POST.get("name") or "Signer",
                                      email=request.POST.get("email") or "s@demo.dev")
            elif act == "send":
                send(env)
            elif act == "sign":
                sign(env, request.POST.get("email") or request.user.email)
            elif act == "void":
                void(env)
            messages.success(request, "Updated.")
        except DomainError as exc:
            messages.error(request, str(exc))
        return redirect(env)
    return render(request, "app/detail.html", _ctx(request, env=env))

@login_required
def envelope_new(request):
    if request.method == "POST":
        room, _ = Room.objects.get_or_create(name=request.POST.get("room") or "General")
        env = Envelope.objects.create(title=request.POST.get("title") or "Agreement", room=room, owner=request.user)
        return redirect(env)
    return render(request, "app/form.html", _ctx(request, rooms=Room.objects.all()))

@login_required
def profile(request):
    if request.method == "POST":
        u = request.user
        u.first_name = request.POST.get("first_name") or u.first_name
        u.email = request.POST.get("email") or u.email
        u.save()
        messages.success(request, "Profile updated.")
        return redirect("profile")
    return render(request, "account/profile.html", _ctx(request))
