"""
Networking helpers: check if a host is up via ICMP ping and/or TCP connect,
and try to resolve its MAC address from the local ARP table (works only for
hosts on the same LAN segment as the machine running Django).

Unmanaged switches have no IP, so their live status is inferred from devices
whose desk ports (D-1, D-2, …) fall in the switch's port range.
"""
from concurrent.futures import ThreadPoolExecutor
import platform
import re
import socket
import subprocess
import time

_DESK_PORT_RE = re.compile(r"^D-(\d+)$", re.IGNORECASE)


def parse_desk_port(value):
    """Return the integer in 'D-12' / 'd-12' / '12', or None if not a desk port."""
    if not value:
        return None
    text = str(value).strip()
    match = _DESK_PORT_RE.match(text)
    if match:
        return int(match.group(1))
    if text.isdigit():
        return int(text)
    return None


def normalize_desk_port(value):
    """Canonical 'D-12' when the value is a desk port; otherwise stripped original."""
    number = parse_desk_port(value)
    if number is None:
        return (value or "").strip()
    return f"D-{number}"


def switch_port_bounds(switch):
    """(low, high) inclusive port numbers for a switch, or None if unset/invalid."""
    low = parse_desk_port(getattr(switch, "port_from", None))
    high = parse_desk_port(getattr(switch, "port_to", None))
    if low is None or high is None:
        return None
    if low > high:
        low, high = high, low
    return low, high


def port_on_switch(port, switch):
    bounds = switch_port_bounds(switch)
    number = parse_desk_port(port)
    if bounds is None or number is None:
        return False
    low, high = bounds
    return low <= number <= high


def devices_on_switch(switch, candidates):
    """Endpoint devices whose port sits in this switch's D-n range."""
    return [
        device for device in candidates
        if getattr(device, "category", None) != getattr(device, "CATEGORY_SWITCH", "switch")
        and port_on_switch(device.port, switch)
    ]


def find_switch_for_port(port, switches):
    """First switch whose range contains this desk port, or None."""
    for switch in switches:
        if port_on_switch(port, switch):
            return switch
    return None


def infer_switch_status(switch, candidates):
    """
    Mark an unmanaged switch up if any device on its ports is currently up.
    Stores member counts on switch._probes for the API/UI.
    """
    members = devices_on_switch(switch, candidates)
    up_members = [m for m in members if m.is_up]
    is_up = bool(up_members)
    switch.mark_status(is_up, response_ms=None)
    switch._probes = {
        "ping": None,
        "tcp": None,
        "arp": None,
        "inferred": True,
        "members_up": len(up_members),
        "members_total": len(members),
    }
    return is_up, None


def ping_host(ip_address: str, timeout_seconds: float = 1.5):
    """
    Ping a single host once. Returns (is_up: bool, response_ms: float|None).
    Works on Linux, macOS and Windows by adjusting the ping command flags.
    """
    system = platform.system().lower()

    if system == "windows":
        # -n 1 = one echo request, -w timeout in ms
        cmd = ["ping", "-n", "1", "-w", str(int(timeout_seconds * 1000)), ip_address]
    else:
        # -c 1 = one echo request, -W timeout in seconds (Linux) / macOS uses -W ms but
        # -t for TTL; -W1 works fine across common distros for whole seconds.
        cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout_seconds))), ip_address]

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds + 2,
            text=True,
        )
        elapsed_ms = round((time.time() - start) * 1000, 1)
        is_up = result.returncode == 0
        return is_up, elapsed_ms if is_up else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False, None


def tcp_check(ip_address: str, port: int, timeout_seconds: float = 1.5):
    """
    Try a TCP connect to ip:port. Returns (is_up: bool, response_ms: float|None).
    Succeeds if the handshake completes (port open / accepting).
    """
    start = time.time()
    try:
        with socket.create_connection((ip_address, int(port)), timeout=timeout_seconds):
            elapsed_ms = round((time.time() - start) * 1000, 1)
            return True, elapsed_ms
    except (OSError, ValueError, TypeError):
        return False, None


_MAC_RE = re.compile(r"([0-9A-Fa-f]{2}([:-])){5}[0-9A-Fa-f]{2}")
# Kernel neighbor states that mean the host answered ARP recently.
# STALE/FAILED/INCOMPLETE are excluded: STALE is an old cache, not a live check.
_NEIGH_UP_STATES = frozenset({"REACHABLE", "DELAY", "PROBE", "PERMANENT"})


def get_mac_from_arp(ip_address: str):
    """
    Best-effort MAC address lookup using the OS ARP table.
    Returns a normalized 'AA:BB:CC:DD:EE:FF' string, or None if not found.
    Note: the ARP entry only exists/updates after the host has been
    contacted (e.g. just pinged), and only for devices on the same subnet.
    """
    system = platform.system().lower()
    cmd = ["arp", "-a", ip_address] if system == "windows" else ["arp", "-n", ip_address]

    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3, text=True
        )
        match = _MAC_RE.search(result.stdout)
        if match:
            mac = match.group(0).replace("-", ":").upper()
            return mac
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass
    return None


def neigh_reachable(ip_address: str):
    """
    True if the kernel neighbor table says this IP answered ARP/ND recently.

    Ping already triggers ARP. Mesh APs (e.g. TP-Link Deco) often ignore ICMP
    and expose no TCP port, but they still reply to ARP, so they would look
    permanently down without this fallback. Linux only (`ip neigh`).
    """
    try:
        result = subprocess.run(
            ["ip", "neigh", "show", ip_address],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
            text=True,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False

    line = (result.stdout or "").strip()
    if not line:
        return False
    state = line.split()[-1].upper()
    return state in _NEIGH_UP_STATES


def check_device(device):
    """
    Run ICMP ping, optional TCP connect, and ARP neighbor checks independently.
    Mark a Device up if any of those succeed. Refresh MAC via ARP when up.
    Stores per-method results on device._probes for the API/UI.
    Returns the (is_up, response_ms) tuple.

    Unmanaged switches are not pinged here; use infer_switch_status() after
    endpoint devices have been checked.
    """
    if device.category == getattr(device, "CATEGORY_SWITCH", "switch"):
        from .models import Device as DeviceModel
        members = list(DeviceModel.objects.exclude(category=DeviceModel.CATEGORY_SWITCH))
        return infer_switch_status(device, members)

    if not device.ip_address:
        device.mark_status(False, response_ms=None)
        device._probes = {
            "ping": None,
            "tcp": None,
            "arp": False,
            "ping_ms": None,
            "tcp_ms": None,
        }
        return False, None

    ping_up, ping_ms = ping_host(device.ip_address)

    tcp_up = None
    tcp_ms = None
    if device.check_port:
        tcp_up, tcp_ms = tcp_check(device.ip_address, device.check_port)

    arp_up = neigh_reachable(device.ip_address)

    is_up = bool(ping_up or tcp_up or arp_up)
    response_ms = ping_ms if ping_up else (tcp_ms if tcp_up else None)

    mac = get_mac_from_arp(device.ip_address) if is_up else None
    device.mark_status(is_up, response_ms=response_ms, mac_address=mac)
    device._probes = {
        "ping": ping_up,
        "tcp": tcp_up,
        "arp": arp_up,
        "ping_ms": ping_ms,
        "tcp_ms": tcp_ms,
    }
    return is_up, response_ms


def check_devices(devices):
    """
    Ping/TCP/ARP all non-switch devices in parallel, then infer each switch
    from the devices on its port range.
    """
    endpoints = [d for d in devices if d.category != getattr(d, "CATEGORY_SWITCH", "switch")]
    switches = [d for d in devices if d.category == getattr(d, "CATEGORY_SWITCH", "switch")]

    if endpoints:
        workers = min(32, len(endpoints))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(check_device, endpoints))

    for switch in switches:
        infer_switch_status(switch, endpoints)
