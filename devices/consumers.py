"""In-browser SSH terminal over WebSocket (paramiko + xterm.js)."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import socket

import paramiko
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Device

logger = logging.getLogger(__name__)

_SSH_USER_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SSH_TIMEOUT = 12


class SSHConsumer(AsyncWebsocketConsumer):
    """Authenticated WebSocket that proxies an interactive SSH shell."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.device_id = None
        self.client = None
        self.channel = None
        self._reader_task = None
        self._connected_ssh = False

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.device_id = int(self.scope["url_route"]["kwargs"]["pk"])
        device = await self._get_device(self.device_id)
        if not device:
            await self.close(code=4404)
            return
        if device.is_switch or not device.ip_address or device.login_method != Device.LOGIN_SSH:
            await self.close(code=4400)
            return

        await self.accept()
        await self._send_json({
            "type": "ready",
            "host": device.ip_address,
            "user": (device.login_username or "").strip(),
            "label": device.employee,
        })

    async def disconnect(self, close_code):
        await self._cleanup_ssh()

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data is not None:
            if self.channel and self._connected_ssh:
                await asyncio.to_thread(self.channel.send, bytes_data)
            return

        if not text_data:
            return

        try:
            msg = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type")
        if msg_type == "start":
            await self._start_ssh(msg)
        elif msg_type == "input":
            data = msg.get("data")
            if data and self.channel and self._connected_ssh:
                await asyncio.to_thread(self.channel.send, data)
        elif msg_type == "resize":
            await self._resize(msg)

    async def _start_ssh(self, msg):
        if self._connected_ssh:
            return

        device = await self._get_device(self.device_id)
        if not device or not device.ip_address:
            await self._send_json({"type": "error", "message": "Device not found."})
            await self.close()
            return

        host = device.ip_address
        user = (device.login_username or "").strip()
        if user and not _SSH_USER_RE.match(user):
            await self._send_json({"type": "error", "message": "Invalid SSH username."})
            return

        password = msg.get("password") or None
        if password is not None and not isinstance(password, str):
            password = None
        if password == "":
            password = None

        cols = max(20, min(int(msg.get("cols") or 80), 500))
        rows = max(5, min(int(msg.get("rows") or 24), 200))

        await self._send_json({
            "type": "status",
            "message": f"Connecting to {user + '@' if user else ''}{host}…",
        })

        try:
            client, channel = await asyncio.to_thread(
                self._open_ssh,
                host,
                user,
                password,
                cols,
                rows,
            )
        except paramiko.AuthenticationException:
            await self._send_json({
                "type": "auth_required",
                "message": "Authentication failed. Enter the SSH password and connect again.",
            })
            return
        except (paramiko.SSHException, socket.error, OSError, TimeoutError, ValueError) as exc:
            logger.info("SSH connect failed for device %s: %s", self.device_id, exc)
            await self._send_json({"type": "error", "message": f"SSH failed: {exc}"})
            return

        self.client = client
        self.channel = channel
        self._connected_ssh = True
        await self._send_json({"type": "connected", "message": "Connected."})
        self._reader_task = asyncio.create_task(self._read_loop())

    def _open_ssh(self, host, user, password, cols, rows):
        client = paramiko.SSHClient()
        # LAN devices often rotate keys; known_hosts is not managed here.
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs = {
            "hostname": host,
            "port": 22,
            "username": user or None,
            "timeout": _SSH_TIMEOUT,
            "allow_agent": True,
            "look_for_keys": True,
            "banner_timeout": _SSH_TIMEOUT,
            "auth_timeout": _SSH_TIMEOUT,
        }
        if password is not None:
            connect_kwargs["password"] = password
            connect_kwargs["look_for_keys"] = False
            connect_kwargs["allow_agent"] = False

        try:
            client.connect(**connect_kwargs)
        except Exception:
            client.close()
            raise

        channel = client.invoke_shell(term="xterm-256color", width=cols, height=rows)
        channel.settimeout(0.0)
        return client, channel

    async def _read_loop(self):
        try:
            while self.channel and not self.channel.closed:
                data = await asyncio.to_thread(self._recv_chunk)
                if data is None:
                    await asyncio.sleep(0.02)
                    continue
                if data == b"":
                    break
                await self.send(bytes_data=data)
        except Exception as exc:
            logger.debug("SSH read loop ended: %s", exc)
        finally:
            await self._send_json({"type": "closed", "message": "Session ended."})
            await self._cleanup_ssh()
            try:
                await self.close()
            except Exception:
                pass

    def _recv_chunk(self):
        if not self.channel:
            return b""
        if self.channel.recv_ready():
            return self.channel.recv(8192)
        if self.channel.recv_stderr_ready():
            return self.channel.recv_stderr(8192)
        if self.channel.exit_status_ready():
            return b""
        return None

    async def _resize(self, msg):
        if not self.channel or not self._connected_ssh:
            return
        cols = max(20, min(int(msg.get("cols") or 80), 500))
        rows = max(5, min(int(msg.get("rows") or 24), 200))
        try:
            await asyncio.to_thread(self.channel.resize_pty, width=cols, height=rows)
        except Exception:
            pass

    async def _cleanup_ssh(self):
        self._connected_ssh = False
        task = self._reader_task
        self._reader_task = None
        current = asyncio.current_task()
        if task and not task.done() and task is not current:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        channel = self.channel
        client = self.client
        self.channel = None
        self.client = None
        if channel is not None:
            try:
                await asyncio.to_thread(channel.close)
            except Exception:
                pass
        if client is not None:
            try:
                await asyncio.to_thread(client.close)
            except Exception:
                pass

    async def _send_json(self, payload):
        await self.send(text_data=json.dumps(payload))

    @database_sync_to_async
    def _get_device(self, pk):
        try:
            return Device.objects.get(pk=pk)
        except Device.DoesNotExist:
            return None
