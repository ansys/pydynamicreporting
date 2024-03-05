from django.apps import AppConfig


class ReportsConfig(AppConfig):
    name = "ansys.dynamicreporting.core.internals.reports"
    label = "reports"

    def ready(self):
        from . import template_layouts, template_simple_layouts, template_pptx_layouts, template_generators
