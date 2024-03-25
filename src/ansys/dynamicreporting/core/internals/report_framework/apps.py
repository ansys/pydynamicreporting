from django.contrib.staticfiles.apps import StaticFilesConfig


class ReportFrameworkConfig(StaticFilesConfig):
    # custom ignore list
    ignore_patterns = StaticFilesConfig.ignore_patterns + ["*.py", "*.md", "*.txt", "LICENSE*", "*.sh"]
