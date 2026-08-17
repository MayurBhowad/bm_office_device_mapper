from concurrent.futures import ThreadPoolExecutor
import ipaddress
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import DeviceForm
from .models import Department, Device
from .utils import (
    check_device,
    check_devices,
    devices_on_switch,
    find_switch_for_port,
    infer_switch_status,
    parse_desk_port,
)
from .xlsx_export import build_xlsx


def _ip_sort_key(device):
    """Numeric IP order so 192.168.1.2 comes before 192.168.1.100.
    Switches (no IP) sort after addressed devices, by port range then name.
    """
    if device.ip_address:
        try:
            return (0, int(ipaddress.ip_address(device.ip_address)), "")
        except ValueError:
            return (2, 0, device.ip_address)
    number = parse_desk_port(device.port_from if device.is_switch else device.port)
    return (1, number if number is not None else 10**9, device.employee or "")


def _map_switches(devices):
    """Attach mapped_switch_id / mapped_switch_name for dashboard filter/cards."""
    switches = [d for d in devices if d.is_switch]
    for device in devices:
        if device.is_switch:
            device.mapped_switch_id = device.id
            device.mapped_switch_name = device.employee
        else:
            switch = find_switch_for_port(device.port, switches)
            device.mapped_switch_id = switch.id if switch else ""
            device.mapped_switch_name = switch.employee if switch else ""
    return switches


@login_required
def dashboard(request):
    """Main dashboard: shows every device as a card. Cards are pre-rendered
    with whatever status is stored in the DB; the page then calls
    /api/check-all/ via JS to refresh statuses live without a full reload."""
    devices = list(Device.objects.select_related("department").all())
    devices.sort(key=_ip_sort_key)
    switches = _map_switches(devices)
    up_count = sum(1 for d in devices if d.is_up)
    total_count = len(devices)
    departments = list(Department.objects.order_by("name"))
    has_unassigned = any(d.department_id is None for d in devices)
    devices_json = [
        {
            "id": d.id,
            "ip": d.ip_address or "",
            "mac": d.mac_address or "",
            "host": d.host or "",
            "employee": d.employee,
            "port": d.port or "",
            "port_from": d.port_from or "",
            "port_to": d.port_to or "",
            "check_port": d.check_port,
            "department": d.department.name if d.department else "",
            "category": d.category,
            "category_label": d.get_category_display(),
            "is_switch": d.is_switch,
            "switch_id": d.mapped_switch_id or "",
            "switch_name": d.mapped_switch_name or "",
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
        "switches": switches,
        "up_count": up_count,
        "down_count": total_count - up_count,
        "total_count": total_count,
        "devices_json": devices_json,
        "departments": departments,
        "has_unassigned": has_unassigned,
    })


@login_required
def device_add(request):
    if request.method == "POST":
        form = DeviceForm(request.POST)
        if form.is_valid():
            device = form.save()
            messages.success(request, f"Added {device.employee}.")
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
            messages.success(request, f"Updated {device.employee}.")
            return redirect("dashboard")
    else:
        form = DeviceForm(instance=device)
    return render(request, "devices/device_form.html", {"form": form, "title": f"Edit {device.employee}"})


@login_required
def device_delete(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if request.method == "POST":
        employee = device.employee
        device.delete()
        messages.success(request, f"Removed {employee}.")
        return redirect("dashboard")
    return render(request, "devices/device_confirm_delete.html", {"device": device})


def _serialize(device):
    probes = getattr(device, "_probes", None) or {}
    return {
        "id": device.id,
        "is_up": device.is_up,
        "is_switch": device.is_switch,
        "response_ms": device.last_response_ms,
        "mac_address": device.mac_address or None,
        "last_checked": device.last_checked.strftime("%H:%M:%S") if device.last_checked else None,
        "last_seen_up": device.last_seen_up.strftime("%Y-%m-%d %H:%M:%S") if device.last_seen_up else None,
        "probes": {
            "ping": probes.get("ping"),
            "tcp": probes.get("tcp"),
            "arp": probes.get("arp"),
            "ping_ms": probes.get("ping_ms"),
            "tcp_ms": probes.get("tcp_ms"),
            "inferred": probes.get("inferred"),
            "members_up": probes.get("members_up"),
            "members_total": probes.get("members_total"),
        },
    }


@login_required
def check_one(request, pk):
    """Check a single device (ping, then optional TCP) and return fresh status.
    For a switch, re-check devices on its ports and infer live/down from those.
    """
    device = get_object_or_404(Device, pk=pk)
    related = []

    if device.is_switch:
        endpoints = list(Device.objects.exclude(category=Device.CATEGORY_SWITCH))
        members = devices_on_switch(device, endpoints)
        if members:
            workers = min(32, len(members))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(check_device, members))
        infer_switch_status(device, endpoints)
        related = [_serialize(m) for m in members]
    else:
        check_device(device)
        switches = list(Device.objects.filter(category=Device.CATEGORY_SWITCH))
        parent = find_switch_for_port(device.port, switches)
        if parent:
            endpoints = list(Device.objects.exclude(category=Device.CATEGORY_SWITCH))
            infer_switch_status(parent, endpoints)
            related = [_serialize(parent)]

    payload = _serialize(device)
    payload["related"] = related
    return JsonResponse(payload)


@login_required
def check_all(request):
    """Ping/TCP/ARP endpoints in parallel, then infer unmanaged switch status
    from devices on each switch's port range. Returns JSON for all devices."""
    devices = list(Device.objects.all())
    if devices:
        check_devices(devices)
    return JsonResponse({"devices": [_serialize(d) for d in devices]})


_EXPORT_MAX_IDS = 5000
_EXPORT_HEADERS = [
    "Name",
    "Type",
    "IP",
    "MAC",
    "Host",
    "Port",
    "Switch",
    "Department",
    "Status",
    "Response (ms)",
    "Last checked",
]


def _export_row(device, switches):
    if device.is_switch:
        port = device.port_range_label or ""
        switch_name = device.employee
        status = "Live" if device.is_up else "No path"
        response = ""
    else:
        port = device.port or ""
        parent = find_switch_for_port(device.port, switches)
        switch_name = parent.employee if parent else ""
        status = "Online" if device.is_up else "Offline"
        response = (
            str(int(round(device.last_response_ms)))
            if device.last_response_ms is not None
            else ""
        )
    last_checked = ""
    if device.last_checked:
        last_checked = timezone.localtime(device.last_checked).strftime("%Y-%m-%d %H:%M:%S")
    return [
        device.employee,
        device.get_category_display(),
        device.ip_address or "",
        device.mac_address or "",
        device.host or "",
        port,
        switch_name,
        device.department.name if device.department else "",
        status,
        response,
        last_checked,
    ]


@login_required
@require_POST
def export_devices(request):
    """Excel download of the devices currently visible after search/filters."""
    try:
        payload = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request."}, status=400)

    raw_ids = payload.get("ids") or []
    if not isinstance(raw_ids, list) or not raw_ids:
        return JsonResponse({"error": "No devices to export."}, status=400)
    if len(raw_ids) > _EXPORT_MAX_IDS:
        return JsonResponse({"error": "Too many devices to export."}, status=400)

    ids = []
    seen = set()
    for value in raw_ids:
        try:
            pk = int(value)
        except (TypeError, ValueError):
            continue
        if pk > 0 and pk not in seen:
            seen.add(pk)
            ids.append(pk)
    if not ids:
        return JsonResponse({"error": "No devices to export."}, status=400)

    devices_by_id = {
        d.id: d
        for d in Device.objects.select_related("department").filter(id__in=ids)
    }
    ordered = [devices_by_id[pk] for pk in ids if pk in devices_by_id]
    if not ordered:
        return JsonResponse({"error": "No devices to export."}, status=400)

    switches = list(Device.objects.filter(category=Device.CATEGORY_SWITCH))
    rows = [_export_row(device, switches) for device in ordered]
    content = build_xlsx(_EXPORT_HEADERS, rows)
    stamp = timezone.localdate().isoformat()
    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="devices-{stamp}.xlsx"'
    return response
