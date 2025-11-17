from django.apps import AppConfig
from django.core.signals import setting_changed


class Tracet2AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'TraceT2App'

    def ready(self):
        from . import signals