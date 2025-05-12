from django.apps import AppConfig


class ControlebiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'controleBI'

    def ready(self):
        import controleBI.signals
