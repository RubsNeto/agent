from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    """Inline para editar o perfil diretamente na página do usuário."""
    model = UserProfile
    can_delete = False
    verbose_name = "Perfil"
    verbose_name_plural = "Perfil"
    fields = ('role', 'phone', 'cep', 'birth_date')


class UserAdmin(BaseUserAdmin):
    """Admin customizado para User com perfil inline."""
    inlines = [UserProfileInline]
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_active')
    list_filter = ('is_active', 'is_superuser', 'profile__role')
    
    def get_role(self, obj):
        if obj.is_superuser:
            return "SuperAdmin"
        if hasattr(obj, 'profile'):
            return obj.profile.get_role_display()
        return "-"
    get_role.short_description = "Papel"


# Desregistrar o User padrão e registrar o customizado
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin para visualização/edição direta de perfis."""
    list_display = ("user", "role", "phone", "cep", "created_at")
    search_fields = ("user__username", "user__email", "phone", "cep")
    list_filter = ("role", "created_at")
    readonly_fields = ("user", "created_at", "updated_at")
    
    def has_add_permission(self, request):
        """Desabilita criação manual - perfis são criados automaticamente."""
        return False
