# Generated manually to rename Legajo.titulo to Legajo.nombre
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('expediente', '0003_actualiza_estado_prestamo'),
    ]

    operations = [
        migrations.RenameField(
            model_name='legajo',
            old_name='titulo',
            new_name='nombre',
        ),
    ]
