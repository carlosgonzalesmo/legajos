from django.apps import AppConfig
from django.db.models.signals import post_migrate


def ensure_default_groups(sender, **kwargs):
    from django.contrib.auth.models import Group  # import inside for app registry readiness
    from .permissions import ADMIN_GROUP_NAME, USERS_GROUP_NAME

    for name in (ADMIN_GROUP_NAME, USERS_GROUP_NAME):
        Group.objects.get_or_create(name=name)


class ExpedienteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'expediente'

    def ready(self):
        post_migrate.connect(ensure_default_groups, sender=self)
