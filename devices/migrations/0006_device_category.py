from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0005_device_check_port"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="category",
            field=models.CharField(
                choices=[
                    ("pc", "PC"),
                    ("printer", "Printer"),
                    ("centralized", "Centralized"),
                    ("access_point", "Access Point"),
                ],
                db_index=True,
                default="pc",
                help_text="Sheet / device type: PC, Printer, Centralized, Access Point",
                max_length=20,
            ),
        ),
    ]
