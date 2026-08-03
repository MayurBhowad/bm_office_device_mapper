from django import forms
from .models import Device


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ["name", "ip_address", "mac_address", "location", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Reception PC"}),
            "ip_address": forms.TextInput(attrs={"class": "form-control", "placeholder": "192.168.1.25"}),
            "mac_address": forms.TextInput(attrs={"class": "form-control", "placeholder": "AA:BB:CC:DD:EE:FF (optional)"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "Floor 2 - Office"}),
            "notes": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional notes"}),
        }
