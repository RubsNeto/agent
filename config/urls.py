"""
URL configuration for SaaS Agentes de IA project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("admin-panel/", include("admin_panel.urls")),
    path("", include("ui.urls")),
    path("accounts/", include("accounts.urls")),
    path("agents/", include("agents.urls")),
    path("organizations/", include("organizations.urls")),
    path("api/", include("api.urls")),
    path("webhooks/", include("webhooks.urls")),
    path("audit/", include("audit.urls")),
    path("payments/", include("payments.urls")),  # Asaas + Mercado Pago
]

# Servir arquivos de media em desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Em produção, também servir media files via Django
    # Nota: Para alta performance, configure o Traefik/nginx para servir /media/ diretamente
    from django.views.static import serve
    from django.urls import re_path
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
