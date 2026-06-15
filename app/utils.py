from __future__ import annotations

import ipaddress
import socket
from datetime import datetime, timezone


def local_hosts() -> set[str]:
    hosts = {"127.0.0.1", "::1", "localhost"}
    try:
        hostname = socket.gethostname()
        hosts.update(socket.gethostbyname_ex(hostname)[2])
    except OSError:
        pass
    return hosts


LOCAL_HOSTS = local_hosts()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_host(host: str | None) -> str:
    if not host:
        return "unknown"

    normalized = host.removeprefix("::ffff:")

    try:
        if ipaddress.ip_address(normalized).is_loopback:
            return "server-local"
    except ValueError:
        pass

    if normalized in LOCAL_HOSTS:
        return "server-local"

    return normalized
