from django.contrib import admin
from .models import Department, Device


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "ip_address",
        "mac_address",
        "host",
        "employee",
        "port",
        "check_port",
        "department",
        "is_up",
        "last_checked",
    )
    list_filter = ("is_up", "department")
    search_fields = ("ip_address", "mac_address", "host", "employee", "port", "department__name")
    autocomplete_fields = ("department",)
