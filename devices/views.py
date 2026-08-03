from concurrent.futures import ThreadPoolExecutor

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import DeviceForm
from .models import Device
from .utils import check_device


@login_required
def dashboard(request):
    """Main dashboard: shows every device as a card. Cards are pre-rendered
    with whatever status is stored in the DB; the page then calls
    /api/check-all/ via JS to refresh statuses live without a full reload."""
    devices = list(Device.objects.select_related("department").all())
    up_count = sum(1 for d in devices if d.is_up)
    total_count = len(devices)
    devices_json = [
        {
            "id": d.id,
            "name": d.name,
            "ip": d.ip_address,
            "mac": d.mac_address or "",
            "location": d.location or "",
            "port": d.port or "",
            "department": d.department.name if d.department else "",
            "notes": d.notes or "",
            "is_up": d.is_up,
            "response_ms": d.last_response_ms,
            "last_checked": d.last_checked.strftime("%H:%M:%S") if d.last_checked else "",
            "edit_url": reverse("device_edit", args=[d.id]),
            "delete_url": reverse("device_delete", args=[d.id]),
        }
        for d in devices
    ]
    return render(request, "devices/dashboard.html", {
        "devices": devices,
        "up_count": up_count,
        "down_count": total_count - up_count,
        "total_count": total_count,
        "devices_json": devices_json,
    })


@login_required
def device_add(request):
    if request.method == "POST":
        form = DeviceForm(request.POST)
        if form.is_valid():
            device = form.save()
            messages.success(request, f"Added {device.name}.")
            return redirect("dashboard")
    else:
        form = DeviceForm()
    return render(request, "devices/device_form.html", {"form": form, "title": "Add device"})


@login_required
def device_edit(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if request.method == "POST":
        form = DeviceForm(request.POST, instance=device)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {device.name}.")
            return redirect("dashboard")
    else:
        form = DeviceForm(instance=device)
    return render(request, "devices/device_form.html", {"form": form, "title": f"Edit {device.name}"})


@login_required
def device_delete(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if request.method == "POST":
        name = device.name
        device.delete()
        messages.success(request, f"Removed {name}.")
        return redirect("dashboard")
    return render(request, "devices/device_confirm_delete.html", {"device": device})


def _serialize(device):
    return {
        "id": device.id,
        "is_up": device.is_up,
        "response_ms": device.last_response_ms,
        "mac_address": device.mac_address or None,
        "last_checked": device.last_checked.strftime("%H:%M:%S") if device.last_checked else None,
        "last_seen_up": device.last_seen_up.strftime("%Y-%m-%d %H:%M:%S") if device.last_seen_up else None,
    }


@login_required
def check_one(request, pk):
    """Ping a single device on demand and return its fresh status as JSON."""
    device = get_object_or_404(Device, pk=pk)
    check_device(device)
    return JsonResponse(_serialize(device))


@login_required
def check_all(request):
    """Ping every device in parallel (thread pool, since ping is I/O bound)
    and return fresh statuses for all of them as JSON."""
    devices = list(Device.objects.all())

    if devices:
        with ThreadPoolExecutor(max_workers=min(32, len(devices))) as pool:
            list(pool.map(check_device, devices))

    return JsonResponse({"devices": [_serialize(d) for d in devices]})
