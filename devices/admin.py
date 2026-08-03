from django.contrib import admin
from .models import Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "ip_address", "mac_address", "location", "is_up", "last_checked")
    list_filter = ("is_up", "location")
    search_fields = ("name", "ip_address", "mac_address")
