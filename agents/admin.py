from django.contrib import admin
from .models import Agent


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "padaria", "role", "status", "personality", "created_at")
    search_fields = ("name", "slug", "padaria__name", "role", "sector")
    list_filter = ("status", "personality", "role", "sector", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("knowledge_updated_at", "created_at", "updated_at")
    autocomplete_fields = ()  # Padaria removida do admin
    
    fieldsets = (
        ("Informações Básicas", {
            "fields": ("padaria", "name", "slug", "role", "sector", "language", "status")
        }),
        ("Personalidade e Mensagens", {
            "fields": ("personality", "greeting", "out_of_hours_message", "max_response_time")
        }),
        ("Transferência para Humano", {
            "fields": ("transfer_keywords",),
            "description": "Configure quando o agente deve transferir para um atendente humano"
        }),
        ("Horários de Atendimento", {
            "fields": ("business_hours",)
        }),
        ("Base de Conhecimento", {
            "fields": (
                "knowledge_base", 
                "knowledge_pdf", 
                "knowledge_pdf_category",
                "knowledge_pdf_text",
                "knowledge_updated_at"
            ),
            "description": "Gerencie o conhecimento do agente através de texto ou PDF"
        }),
        ("Comportamento Avançado (Legacy)", {
            "fields": ("tone", "style_guidelines", "fallback_message", "escalation_rule", "is_active"),
            "classes": ("collapse",)
        }),
        ("Integração N8N", {
            "fields": ("n8n_webhook_url",),
            "classes": ("collapse",)
        }),
        ("Metadados", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
