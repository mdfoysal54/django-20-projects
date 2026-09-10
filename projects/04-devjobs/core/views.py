"""DevJobs — views (authored with the project)."""
from django.shortcuts import render


def index(request):
    return render(request, "construction.html", {"page_title": "DevJobs"})
