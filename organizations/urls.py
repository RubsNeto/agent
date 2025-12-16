from django.urls import path
from . import views

app_name = "organizations"

urlpatterns = [
    path("", views.organization_list, name="list"),
    path("create/", views.organization_create, name="create"),
    path("apikeys/", views.apikey_list, name="apikeys"),
    path("apikeys/create/", views.apikey_create, name="apikey_create"),
    path("apikeys/<int:pk>/delete/", views.apikey_delete, name="apikey_delete"),
    path("<slug:slug>/", views.organization_detail, name="detail"),
    path("<slug:slug>/edit/", views.organization_edit, name="edit"),
    path("<slug:slug>/delete/", views.organization_delete, name="delete"),
    path("<slug:slug>/whatsapp/", views.whatsapp_connect, name="whatsapp_connect"),
]
