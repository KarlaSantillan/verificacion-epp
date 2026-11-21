from django.db import migrations, models


class Migration(migrations.Migration):
    """Agrega el correo institucional (opcional) del estudiante para notificar el llamado de atención (HU16)."""

    dependencies = [
        ("estudiantes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="estudiante",
            name="correo",
            field=models.EmailField(blank=True, max_length=120, null=True),
        ),
    ]
