from django.urls import path
from . import views

app_name = "organizations"

urlpatterns = [
    path("", views.organization_list, name="list"),
    path("create/", views.organization_create, name="create"),
    path("apikeys/", views.apikey_list, name="apikeys"),
    path("apikeys/create/", views.apikey_create, name="apikey_create"),
    path("apikeys/<int:pk>/delete/", views.apikey_delete, name="apikey_delete"),
    
    # Promoções
    path("promocoes/", views.promocao_list, name="promocao_list"),
    path("promocoes/create/", views.promocao_create, name="promocao_create"),
    path("promocoes/<int:pk>/edit/", views.promocao_edit, name="promocao_edit"),
    path("promocoes/<int:pk>/delete/", views.promocao_delete, name="promocao_delete"),
    path("promocoes/<int:promocao_pk>/criar-campanha/", views.campanha_criar_de_promocao, name="campanha_criar_de_promocao"),
    
    # Produtos
    path("produtos/", views.produto_list, name="produto_list"),
    path("produtos/create/", views.produto_create, name="produto_create"),
    path("produtos/import/", views.produto_import, name="produto_import"),
    path("produtos/import-excel/", views.produto_import_excel, name="produto_import_excel"),
    path("produtos/<int:pk>/edit/", views.produto_edit, name="produto_edit"),
    path("produtos/<int:pk>/delete/", views.produto_delete, name="produto_delete"),
    
    # Clientes
    path("clientes/", views.cliente_list, name="cliente_list"),
    path("clientes/create/", views.cliente_create, name="cliente_create"),
    path("clientes/<int:pk>/edit/", views.cliente_edit, name="cliente_edit"),
    path("clientes/<int:pk>/delete/", views.cliente_delete, name="cliente_delete"),
    path("clientes/import/", views.cliente_import, name="cliente_import"),
    
    # Campanhas WhatsApp
    path("campanhas/", views.campanha_list, name="campanha_list"),
    path("campanhas/create/", views.campanha_create, name="campanha_create"),
    path("campanhas/<int:pk>/", views.campanha_detail, name="campanha_detail"),
    path("campanhas/<int:pk>/iniciar/", views.campanha_iniciar, name="campanha_iniciar"),
    path("campanhas/<int:pk>/pausar/", views.campanha_pausar, name="campanha_pausar"),
    path("campanhas/<int:pk>/status/", views.campanha_status_ajax, name="campanha_status_ajax"),
    path("campanhas/<int:pk>/delete/", views.campanha_delete, name="campanha_delete"),
    
    # Organization detail routes (must come after static routes)
    path("<slug:slug>/", views.organization_detail, name="detail"),
    path("<slug:slug>/edit/", views.organization_edit, name="edit"),
    path("<slug:slug>/delete/", views.organization_delete, name="delete"),
    path("<slug:slug>/whatsapp/", views.whatsapp_connect, name="whatsapp_connect"),
]

