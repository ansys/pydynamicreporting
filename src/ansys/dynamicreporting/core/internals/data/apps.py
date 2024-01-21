from django.apps import AppConfig


class DataConfig(AppConfig):
    name = "ansys.dynamicreporting.core.internals.data"  # name of the application
    label = "data"

    def ready(self):
        from . import signals
