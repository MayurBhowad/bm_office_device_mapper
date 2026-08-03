# Generated manually for host/employee field reshape

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0002_device_department_device_port"),
    ]

    operations = [
        migrations.RenameField(
            model_name="device",
            old_name="name",
            new_name="employee",
        ),
        migrations.AlterField(
            model_name="device",
            name="employee",
            field=models.CharField(help_text="Employee name (required)", max_length=100),
        ),
        migrations.AddField(
            model_name="device",
            name="host",
            field=models.CharField(
                blank=True,
                help_text="Hostname (optional), e.g. 'PC-RECEPTION-01'",
                max_length=100,
            ),
        ),
        migrations.RemoveField(
            model_name="device",
            name="location",
        ),
        migrations.RemoveField(
            model_name="device",
            name="notes",
        ),
        migrations.AlterModelOptions(
            name="device",
            options={"ordering": ["employee"]},
        ),
    ]
