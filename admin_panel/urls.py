from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Relatório de Clientes (Padarias)
    path('relatorio-clientes/', views.clientes_report, name='clientes_report'),
    path('relatorio-clientes/exportar/', views.clientes_export_excel, name='clientes_export_excel'),
    
    # Padarias CRUD
    path('padarias/', views.padarias_list, name='padarias_list'),
    path('padarias/create/', views.padaria_create, name='padaria_create'),
    path('padarias/<slug:slug>/', views.padaria_detail, name='padaria_detail'),
    path('padarias/<slug:slug>/edit/', views.padaria_edit, name='padaria_edit'),
    path('padarias/<slug:slug>/delete/', views.padaria_delete, name='padaria_delete'),
    
    # Agentes (visao global)
    path('agents/', views.agents_list, name='agents_list'),
    path('agents/<slug:slug>/', views.agent_detail, name='agent_detail'),
    
    # API Keys
    path('padarias/<slug:slug>/apikey/', views.padaria_apikey, name='padaria_apikey'),
    path('padarias/<slug:slug>/apikey/generate/', views.padaria_apikey_generate, name='padaria_apikey_generate'),
]


