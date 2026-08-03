from django import forms
from .models import Device


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ["ip_address", "mac_address", "host", "employee", "port", "department"]
        labels = {
            "ip_address": "IP",
            "mac_address": "MAC",
            "host": "Host",
            "employee": "Employee",
            "port": "Port",
            "department": "Department",
        }
        widgets = {
            "ip_address": forms.TextInput(attrs={"class": "form-control", "placeholder": "192.168.1.25"}),
            "mac_address": forms.TextInput(attrs={"class": "form-control", "placeholder": "AA:BB:CC:DD:EE:FF (optional)"}),
            "host": forms.TextInput(attrs={"class": "form-control", "placeholder": "Hostname (optional)"}),
            "employee": forms.TextInput(attrs={"class": "form-control", "placeholder": "Employee name"}),
            "port": forms.TextInput(attrs={"class": "form-control", "placeholder": "Gi0/12"}),
            "department": forms.Select(attrs={"class": "form-control"}),
        }
