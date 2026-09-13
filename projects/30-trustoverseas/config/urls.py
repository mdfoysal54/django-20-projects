"""Trust Overseas Ltd — root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Trust Overseas Ltd Admin"
admin.site.site_title = "Trust Overseas Ltd administration"
admin.site.index_title = "Manage Trust Overseas Ltd"

# Branded, first-party error pages (403 / 404 / 429 / 500).
handler400 = "core.views_errors.bad_request"
handler403 = "core.views_errors.permission_denied"
handler404 = "core.views_errors.page_not_found"
handler500 = "core.views_errors.server_error"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
