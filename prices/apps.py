from django.apps import AppConfig


class PricesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "prices"

    def ready(self):
        from . import signals  # noqa: F401
