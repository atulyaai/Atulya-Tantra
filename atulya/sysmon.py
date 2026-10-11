"""Live host metrics for the status panel: CPU, memory, disk, network rate, uptime, battery."""
from __future__ import annotations

import time

import psutil

_last_net: tuple[float, int, int] | None = None


def _rate(now: float, sent: int, received: int) -> tuple[float, float]:
    """Bytes per second since the previous sample (0 on the first call)."""
    global _last_net
    previous, _last_net = _last_net, (now, sent, received)
    if previous is None or now <= previous[0]:
        return 0.0, 0.0
    elapsed = now - previous[0]
    return max(0.0, (sent - previous[1]) / elapsed), max(0.0, (received - previous[2]) / elapsed)


def snapshot(data_path: str = ".") -> dict[str, object]:
    now = time.monotonic()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(data_path)
    net = psutil.net_io_counters()
    up, down = _rate(now, net.bytes_sent, net.bytes_recv)
    battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    return {
        "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
        "cpu_count": psutil.cpu_count() or 0,
        "memory_percent": round(memory.percent, 1),
        "memory_used_gb": round(memory.used / 1024 ** 3, 1),
        "memory_total_gb": round(memory.total / 1024 ** 3, 1),
        "disk_percent": round(disk.percent, 1),
        "net_up_kbps": round(up * 8 / 1000, 1),
        "net_down_kbps": round(down * 8 / 1000, 1),
        "uptime_hours": round((time.time() - psutil.boot_time()) / 3600, 1),
        "battery_percent": None if battery is None else round(battery.percent),
        "on_power": None if battery is None else bool(battery.power_plugged),
    }
