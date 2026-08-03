# LAN Monitor — Django

A small Django app for a network admin to see, at a glance, which PCs on the
LAN are up or down. Dashboard shows each device as a card with its **name,
IP, MAC address, ping time, and last-checked time**. Cards go green when a
device is online and red when it isn't, and refresh automatically every 15
seconds (also refreshable on demand with "Check now").

## How status detection works

- **Up/Down** — the server pings each device's IP address (one ICMP echo,
  ~1.5s timeout) using the OS `ping` command. This works cross-platform
  (Linux/macOS/Windows).
- **MAC address** — after a successful ping, the app reads the local ARP
  table (`arp -n <ip>` / `arp -a`) to fetch/refresh the device's MAC. This
  only works for devices on the **same subnet** as the machine running
  Django (ARP doesn't cross routers), and only after that device has
  answered at least once. You can also just type the MAC in manually when
  adding a device — it isn't required to already know the current MAC to
  start tracking a device.

Because this relies on ICMP ping and ARP, **run this on a machine that's on
the same LAN** as the PCs you want to monitor (e.g. a small server, NAS, or
even your own workstation) — not on a cloud VM outside the network.

## Setup

```bash
# 1. Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply database migrations
python manage.py migrate

# 4. Create an admin account (used to log into the dashboard)
python manage.py createsuperuser

# 5. Run the dev server
python manage.py runserver 0.0.0.0:8000
```

Then open **http://localhost:8000/** (or `http://<server-ip>:8000/` from
another machine on the LAN) and log in with the superuser account you
created.

> On Windows, ping requires no special privileges. On Linux, the `ping`
> binary usually works out of the box for a single ICMP echo; if you get
> permission errors, either run as root or `sudo setcap cap_net_raw+p
> /bin/ping` once.

## Using it

- **Add device**: click "Add device" in the navbar — enter a name, IP, and
  optionally MAC/location/notes.
- **Dashboard**: every device shows as a card — green border/badge = up,
  red = down, with live ping time and last-checked timestamp.
- **Edit / delete**: pencil/trash icons on each card.
- **Admin panel**: `/admin/` also lets you manage devices via Django's
  built-in admin if you prefer a table view.

## Project layout

```
lanmonitor/
├── manage.py
├── requirements.txt
├── lanmonitor/          # project settings & root urls
├── devices/             # the app: models, views, ping/ARP utils
│   ├── models.py        # Device model (name, ip, mac, status fields)
│   ├── utils.py         # ping_host() / get_mac_from_arp() / check_device()
│   ├── views.py         # dashboard + CRUD + JSON status endpoints
│   ├── forms.py
│   └── urls.py
└── templates/           # Bootstrap-based UI (dashboard, forms, login)
```

## Notes / things you may want to extend

- Statuses are checked **on page load / refresh**, not on a background
  schedule. For continuous monitoring even with no browser open, add a
  periodic task (e.g. `django-crontab`, Celery beat, or a simple cron job
  calling `python manage.py shell -c "..."` or hitting `/api/check-all/`)
  that runs `check_device()` for every `Device` on an interval.
- Currently single-subnet oriented (ARP-based MAC lookup). For multi-VLAN
  environments you'd want SNMP or a dedicated network scanner instead.
- All dashboard/API routes require login (`@login_required`) so only your
  admin account(s) can see internal IPs/MACs.
