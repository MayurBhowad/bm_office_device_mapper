from django import forms
from .models import Device


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = [
            "ip_address",
            "mac_address",
            "host",
            "employee",
            "port",
            "check_port",
            "department",
            "category",
        ]
        labels = {
            "ip_address": "IP",
            "mac_address": "MAC",
            "host": "Host",
            "employee": "Employee",
            "port": "Switch port",
            "check_port": "TCP check port",
            "department": "Department",
            "category": "Type",
        }
        widgets = {
            "ip_address": forms.TextInput(attrs={"class": "form-control", "placeholder": "192.168.1.25"}),
            "mac_address": forms.TextInput(attrs={"class": "form-control", "placeholder": "AA:BB:CC:DD:EE:FF (optional)"}),
            "host": forms.TextInput(attrs={"class": "form-control", "placeholder": "Hostname (optional)"}),
            "employee": forms.TextInput(attrs={"class": "form-control", "placeholder": "Employee name"}),
            "port": forms.TextInput(attrs={"class": "form-control", "placeholder": "Gi0/12"}),
            "check_port": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. 445, 22, 3389 (optional)",
                    "min": 1,
                    "max": 65535,
                }
            ),
            "department": forms.Select(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
        }

    def clean_check_port(self):
        value = self.cleaned_data.get("check_port")
        if value is None:
            return value
        if not 1 <= value <= 65535:
            raise forms.ValidationError("Enter a TCP port between 1 and 65535.")
        return value
