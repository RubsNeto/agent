from django.apps import AppConfig


class AgentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "agents"
    
    def ready(self):
        """Importar signals quando o app estiver pronto."""
        import agents.signals
