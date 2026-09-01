from django.apps import AppConfig


class CoreConfig(AppConfig):
    default = True
    name = "core"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import core.signals  # noqa: F401
