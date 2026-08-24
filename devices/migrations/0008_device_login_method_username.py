# Generated manually for login method + username

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0007_device_switch_port_range"),
    ]

    operations = [
        migrations.AddField(
            model_name="device",
            name="login_method",
            field=models.CharField(
                choices=[
                    ("none", "None"),
                    ("ssh", "SSH"),
                    ("rdp", "RDP"),
                    ("http", "HTTP"),
                    ("https", "HTTPS"),
                    ("telnet", "Telnet"),
                ],
                db_index=True,
                default="ssh",
                help_text="How you connect to this device (e.g. SSH for PCs)",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="device",
            name="login_username",
            field=models.CharField(
                blank=True,
                help_text="Username for SSH/RDP/Telnet (optional for HTTP/HTTPS)",
                max_length=100,
            ),
        ),
    ]
