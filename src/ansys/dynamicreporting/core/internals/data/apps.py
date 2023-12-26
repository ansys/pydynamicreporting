from django.apps import AppConfig


class DataConfig(AppConfig):
    name = 'data'  # name of the application

    def ready(self):
        from . import signals
