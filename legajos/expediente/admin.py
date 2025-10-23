from django.contrib import admin
# ...existing code...
from django.apps import apps
from django.contrib.admin.sites import AlreadyRegistered

app_config = apps.get_app_config("expediente")

for model in app_config.get_models():
    try:
        admin.site.register(model)
    except AlreadyRegistered:
        continue