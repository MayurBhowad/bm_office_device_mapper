from django.contrib import admin
from .models import Department, Device


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "ip_address", "mac_address", "location", "port", "department", "is_up", "last_checked")
    list_filter = ("is_up", "location", "department")
    search_fields = ("name", "ip_address", "mac_address", "port", "department__name")
    autocomplete_fields = ("department",)
