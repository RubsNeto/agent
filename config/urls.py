"""
URL configuration for SaaS Agentes de IA project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("ui.urls")),
    path("accounts/", include("accounts.urls")),
    path("agents/", include("agents.urls")),
    path("organizations/", include("organizations.urls")),
    path("api/", include("api.urls")),
    path("webhooks/", include("webhooks.urls")),
]

# Servir arquivos de media em desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
