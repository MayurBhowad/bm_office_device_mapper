from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0003_device_host_employee_remove_location_notes"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="device",
            options={"ordering": ["ip_address"]},
        ),
    ]
