# Generated manually for the Server device category

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0008_device_login_method_username"),
    ]

    operations = [
        migrations.AlterField(
            model_name="device",
            name="category",
            field=models.CharField(
                choices=[
                    ("pc", "PC"),
                    ("printer", "Printer"),
                    ("centralized", "Centralized"),
                    ("server", "Server"),
                    ("access_point", "Access Point"),
                    ("switch", "Switch"),
                ],
                db_index=True,
                default="pc",
                help_text="Device type: PC, Printer, Centralized, Server, Access Point, Switch",
                max_length=20,
            ),
        ),
    ]
