from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payments'
    verbose_name = 'Pagamentos'

    def ready(self):
        # Importar signals para registrá-los
        import payments.signals  # noqa
