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
    
    # Agentes Credenciados CRUD
    path('agentes-credenciados/', views.agentes_credenciados_list, name='agentes_credenciados_list'),
    path('agentes-credenciados/create/', views.agente_credenciado_create, name='agente_credenciado_create'),
    path('agentes-credenciados/<int:pk>/', views.agente_credenciado_detail, name='agente_credenciado_detail'),
    path('agentes-credenciados/<int:pk>/edit/', views.agente_credenciado_edit, name='agente_credenciado_edit'),
    path('agentes-credenciados/<int:pk>/delete/', views.agente_credenciado_delete, name='agente_credenciado_delete'),
    
    # Agentes IA (visao global)
    path('agents/', views.agents_list, name='agents_list'),
    path('agents/<slug:slug>/', views.agent_detail, name='agent_detail'),
    
    # API Keys
    path('padarias/<slug:slug>/apikey/', views.padaria_apikey, name='padaria_apikey'),
    path('padarias/<slug:slug>/apikey/generate/', views.padaria_apikey_generate, name='padaria_apikey_generate'),
    
    # Users
    path('users/', views.users_list, name='users_list'),
    
    # Portal do Agente Credenciado
    path('meu-portal/', views.agente_minhas_padarias, name='agente_minhas_padarias'),
    path('meu-portal/padarias/create/', views.agente_padaria_create, name='agente_padaria_create'),
    path('meu-portal/padarias/<int:pk>/', views.agente_padaria_detail, name='agente_padaria_detail'),
    path('meu-portal/relatorio/', views.agente_relatorio, name='agente_relatorio'),
    
    # API Agente
    path('api/validate-cnpj/', views.api_validate_cnpj, name='api_validate_cnpj'),
    
    # Assinaturas
    path('assinaturas/', views.subscriptions_list, name='subscriptions_list'),
    
    # Ações de Assinatura (Admin e Agente Credenciado)
    path('assinatura/<int:subscription_id>/confirmar-pagamento/', views.confirm_subscription_payment, name='confirm_subscription_payment'),
    path('assinatura/<int:subscription_id>/pausar/', views.pause_subscription, name='pause_subscription'),
    path('assinatura/<int:subscription_id>/cancelar/', views.cancel_admin_subscription, name='cancel_admin_subscription'),
    path('assinatura/<int:subscription_id>/reativar/', views.reactivate_subscription, name='reactivate_subscription'),
]


