"""
Networking helpers: ping a host to see if it's up, and try to resolve its
MAC address from the local ARP table (works only for hosts on the same
LAN segment as the machine running Django).
"""
import platform
import re
import subprocess
import time


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


_MAC_RE = re.compile(r"([0-9A-Fa-f]{2}([:-])){5}[0-9A-Fa-f]{2}")


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


def check_device(device):
    """
    Ping a Device instance, try to refresh its MAC via ARP, and persist
    the result on the model. Returns the (is_up, response_ms) tuple.
    """
    is_up, response_ms = ping_host(device.ip_address)
    mac = get_mac_from_arp(device.ip_address) if is_up else None
    device.mark_status(is_up, response_ms=response_ms, mac_address=mac)
    return is_up, response_ms
