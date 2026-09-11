from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Agent, Listing, Offer
from .services import DomainError, accept_offer, book_viewing, place_offer

NAV = [("Desk", [("dashboard", "Pipeline"), ("listing_list", "Listings"), ("listing_new", "New listing")]),
       ("Deals", [("offer_list", "Offers")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    qs = Listing.objects.select_related("agent")
    return render(request, "app/dashboard.html", _ctx(request, rows=qs,
        live=qs.filter(status="live").count(), hold=qs.filter(status="hold").count(),
        sold=qs.filter(status="sold").count()))

@login_required
def listing_list(request):
    return render(request, "app/list.html", _ctx(request, title="Listings", rows=Listing.objects.all(), kind="lst"))

@login_required
def listing_detail(request, code):
    listing = get_object_or_404(Listing, code=code)
    if request.method == "POST":
        act = request.POST.get("act")
        try:
            if act == "view":
                when = parse_datetime(request.POST.get("when") or "") or timezone.now()
                if timezone.is_naive(when):
                    when = timezone.make_aware(when)
                book_viewing(listing, when, request.POST.get("visitor") or request.user.get_full_name() or "Visitor")
                messages.success(request, "Viewing booked.")
            elif act == "offer":
                place_offer(listing, request.POST.get("buyer") or "Buyer", float(request.POST.get("amount") or 0))
                messages.success(request, "Offer lodged.")
            elif act == "accept":
                offer = get_object_or_404(Offer, pk=request.POST.get("offer"), listing=listing)
                accept_offer(offer)
                messages.success(request, "Sold.")
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(listing)
    return render(request, "app/detail.html", _ctx(request, listing=listing))

@login_required
def listing_new(request):
    if request.method == "POST":
        agent = get_object_or_404(Agent, pk=request.POST.get("agent"))
        listing = Listing.objects.create(title=request.POST.get("title") or "Home",
            suburb=request.POST.get("suburb") or "Gulshan",
            price=request.POST.get("price") or 10000000, beds=int(request.POST.get("beds") or 3), agent=agent)
        return redirect(listing)
    return render(request, "app/form.html", _ctx(request, agents=Agent.objects.all()))

@login_required
def offer_list(request):
    return render(request, "app/list.html", _ctx(request, title="Offers", rows=Offer.objects.select_related("listing"), kind="off"))

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
