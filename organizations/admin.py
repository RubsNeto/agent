from django.contrib import admin
from .models import Padaria, PadariaUser, ApiKey, Promocao, Produto, Cliente, CampanhaWhatsApp, MensagemCampanha


class PadariaUserInline(admin.TabularInline):
    model = PadariaUser
    extra = 1
    autocomplete_fields = ['user']


class ApiKeyInline(admin.TabularInline):
    model = ApiKey
    extra = 0
    readonly_fields = ['key', 'created_at', 'last_used_at']
    fields = ['key', 'agent', 'name', 'is_active', 'created_at', 'last_used_at']
    autocomplete_fields = ['agent']



# Padaria removida do admin - gerenciada pelo admin_panel customizado
# @admin.register(Padaria)
# class PadariaAdmin(admin.ModelAdmin):
#     list_display = ['name', 'owner', 'is_active', 'created_at']
#     list_filter = ['is_active', 'created_at']
#     search_fields = ['name', 'slug', 'owner__username', 'email']
#     prepopulated_fields = {'slug': ('name',)}
#     inlines = [PadariaUserInline, ApiKeyInline]
#     readonly_fields = ['created_at', 'updated_at']
#     
#     fieldsets = (
#         (None, {
#             'fields': ('name', 'slug', 'owner', 'is_active')
#         }),
#         ('Contato', {
#             'fields': ('phone', 'email', 'address'),
#             'classes': ('collapse',)
#         }),
#         ('Datas', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )


@admin.register(PadariaUser)
class PadariaUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'padaria', 'role', 'created_at']
    list_filter = ['role', 'padaria']
    search_fields = ['user__username', 'user__email', 'padaria__name']
    autocomplete_fields = ['user']  # Padaria removida do admin


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ['padaria', 'agent', 'name', 'key_preview', 'is_active', 'last_used_at']
    list_filter = ['is_active', 'padaria', 'agent']
    search_fields = ['padaria__name', 'agent__name', 'name']
    readonly_fields = ['key', 'created_at', 'last_used_at']
    autocomplete_fields = ['agent']
    
    def key_preview(self, obj):
        return f"{obj.key[:12]}..."
    key_preview.short_description = "Chave"


@admin.register(Promocao)
class PromocaoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'padaria', 'preco', 'is_active', 'data_inicio', 'data_fim']
    list_filter = ['is_active', 'padaria', 'created_at']
    search_fields = ['titulo', 'descricao', 'padaria__name']
    date_hierarchy = 'created_at'


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'padaria', 'categoria', 'preco', 'ativo', 'created_at']
    list_filter = ['ativo', 'categoria', 'padaria', 'created_at']
    search_fields = ['nome', 'descricao', 'categoria', 'padaria__name']
    date_hierarchy = 'created_at'


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nome', 'telefone', 'padaria', 'aceita_promocoes', 'is_active', 'created_at']
    list_filter = ['is_active', 'aceita_promocoes', 'padaria']
    search_fields = ['nome', 'telefone', 'email', 'padaria__name']
    date_hierarchy = 'created_at'


class MensagemCampanhaInline(admin.TabularInline):
    model = MensagemCampanha
    extra = 0
    readonly_fields = ['cliente', 'status', 'enviado_em', 'erro_mensagem']
    can_delete = False


@admin.register(CampanhaWhatsApp)
class CampanhaWhatsAppAdmin(admin.ModelAdmin):
    list_display = ['nome', 'padaria', 'status', 'total_destinatarios', 'enviados', 'falhas', 'created_at']
    list_filter = ['status', 'padaria', 'created_at']
    search_fields = ['nome', 'padaria__name', 'mensagem']
    readonly_fields = ['total_destinatarios', 'enviados', 'falhas', 'iniciado_em', 'concluido_em']
    inlines = [MensagemCampanhaInline]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('padaria', 'nome', 'promocao', 'status')
        }),
        ('Mensagem', {
            'fields': ('mensagem', 'imagem')
        }),
        ('Configurações Anti-Ban', {
            'fields': ('delay_minimo', 'delay_maximo', 'lote_tamanho', 'pausa_entre_lotes'),
            'classes': ('collapse',)
        }),
        ('Estatísticas', {
            'fields': ('total_destinatarios', 'enviados', 'falhas', 'iniciado_em', 'concluido_em'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MensagemCampanha)
class MensagemCampanhaAdmin(admin.ModelAdmin):
    list_display = ['campanha', 'cliente', 'status', 'enviado_em']
    list_filter = ['status', 'campanha', 'enviado_em']
    search_fields = ['campanha__nome', 'cliente__nome', 'cliente__telefone']
    readonly_fields = ['campanha', 'cliente', 'enviado_em']
