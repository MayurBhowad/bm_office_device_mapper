from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Department(models.Model):
    """Organizational department that devices can belong to."""

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Device(models.Model):
    """A network device (PC, server, printer, etc.) tracked on the LAN."""

    CATEGORY_PC = "pc"
    CATEGORY_PRINTER = "printer"
    CATEGORY_CENTRALIZED = "centralized"
    CATEGORY_ACCESS_POINT = "access_point"
    CATEGORY_CHOICES = [
        (CATEGORY_PC, "PC"),
        (CATEGORY_PRINTER, "Printer"),
        (CATEGORY_CENTRALIZED, "Centralized"),
        (CATEGORY_ACCESS_POINT, "Access Point"),
    ]

    ip_address = models.GenericIPAddressField(unique=True, help_text="e.g. 192.168.1.25")
    mac_address = models.CharField(
        max_length=17,
        blank=True,
        help_text="e.g. AA:BB:CC:DD:EE:FF (optional, auto-detected via ARP when possible)",
    )
    host = models.CharField(
        max_length=100,
        blank=True,
        help_text="Hostname (optional), e.g. 'PC-RECEPTION-01'",
    )
    employee = models.CharField(max_length=100, help_text="Employee name (required)")
    port = models.CharField(max_length=50, blank=True, help_text="e.g. switch port 'Gi0/12' or '24'")
    check_port = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text="Optional TCP port for up/down when ping is blocked (e.g. 445, 22, 3389, 80)",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="devices",
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_PC,
        db_index=True,
        help_text="Sheet / device type: PC, Printer, Centralized, Access Point",
    )

    is_up = models.BooleanField(default=False)
    last_checked = models.DateTimeField(null=True, blank=True)
    last_response_ms = models.FloatField(null=True, blank=True)
    last_seen_up = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ip_address"]

    def __str__(self):
        return f"{self.employee} ({self.ip_address})"

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
