from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'semanticiq.core'

    def ready(self):
        import semanticiq.core.signals

