from django.db import models
from django.utils import timezone


class Device(models.Model):
    """A network device (PC, server, printer, etc.) tracked on the LAN."""

    name = models.CharField(max_length=100, help_text="Friendly name, e.g. 'Reception PC'")
    ip_address = models.GenericIPAddressField(unique=True, help_text="e.g. 192.168.1.25")
    mac_address = models.CharField(
        max_length=17,
        blank=True,
        help_text="e.g. AA:BB:CC:DD:EE:FF (optional, auto-detected via ARP when possible)",
    )
    location = models.CharField(max_length=100, blank=True, help_text="e.g. 'Office - Floor 2'")
    notes = models.CharField(max_length=255, blank=True)

    is_up = models.BooleanField(default=False)
    last_checked = models.DateTimeField(null=True, blank=True)
    last_response_ms = models.FloatField(null=True, blank=True)
    last_seen_up = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.ip_address})"

    def mark_status(self, is_up: bool, response_ms=None, mac_address=None):
        self.is_up = is_up
        self.last_checked = timezone.now()
        self.last_response_ms = response_ms
        if is_up:
            self.last_seen_up = self.last_checked
        if mac_address:
            self.mac_address = mac_address
        self.save(update_fields=[
            "is_up", "last_checked", "last_response_ms", "last_seen_up", "mac_address"
        ])
