from django import forms
from .models import Device
from .utils import normalize_desk_port, parse_desk_port, switch_port_bounds


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = [
            "category",
            "employee",
            "ip_address",
            "host",
            "port",
            "port_from",
            "port_to",
            "mac_address",
            "check_port",
            "department",
        ]
        labels = {
            "ip_address": "IP",
            "mac_address": "MAC",
            "host": "Host",
            "employee": "Name",
            "port": "Switch port",
            "port_from": "Ports from",
            "port_to": "Ports to",
            "check_port": "TCP check port",
            "department": "Department",
            "category": "Type",
        }
        widgets = {
            "ip_address": forms.TextInput(attrs={"class": "form-control", "placeholder": "192.168.1.25"}),
            "mac_address": forms.TextInput(attrs={"class": "form-control", "placeholder": "AA:BB:CC:DD:EE:FF (optional)"}),
            "host": forms.TextInput(attrs={"class": "form-control", "placeholder": "Hostname (optional)"}),
            "employee": forms.TextInput(attrs={"class": "form-control", "placeholder": "Employee or Switch-1"}),
            "port": forms.TextInput(attrs={"class": "form-control", "placeholder": "D-1"}),
            "port_from": forms.TextInput(attrs={"class": "form-control", "placeholder": "D-1"}),
            "port_to": forms.TextInput(attrs={"class": "form-control", "placeholder": "D-20"}),
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

    def clean_ip_address(self):
        return self.cleaned_data.get("ip_address") or None

    def clean(self):
        data = super().clean()
        category = data.get("category")

        if category == Device.CATEGORY_SWITCH:
            port_from = normalize_desk_port(data.get("port_from"))
            port_to = normalize_desk_port(data.get("port_to"))
            data["port_from"] = port_from
            data["port_to"] = port_to
            data["port"] = ""
            data["check_port"] = None

            if not port_from:
                self.add_error("port_from", "Set the first port (e.g. D-1).")
            elif parse_desk_port(port_from) is None:
                self.add_error("port_from", "Use D-1, D-2, … format.")

            if not port_to:
                self.add_error("port_to", "Set the last port (e.g. D-20).")
            elif parse_desk_port(port_to) is None:
                self.add_error("port_to", "Use D-1, D-2, … format.")

            self.instance.port_from = port_from
            self.instance.port_to = port_to
            bounds = switch_port_bounds(self.instance)
            if bounds:
                low, high = bounds
                others = Device.objects.filter(category=Device.CATEGORY_SWITCH)
                if self.instance.pk:
                    others = others.exclude(pk=self.instance.pk)
                for other in others:
                    other_bounds = switch_port_bounds(other)
                    if not other_bounds:
                        continue
                    other_low, other_high = other_bounds
                    if low <= other_high and other_low <= high:
                        self.add_error(
                            "port_from",
                            f"Overlaps {other.employee} ({other.port_from}–{other.port_to}).",
                        )
                        break
        else:
            data["port_from"] = ""
            data["port_to"] = ""
            if data.get("port"):
                normalized = normalize_desk_port(data["port"])
                data["port"] = normalized
            if not data.get("ip_address"):
                self.add_error("ip_address", "IP is required for this device type.")

        return data
