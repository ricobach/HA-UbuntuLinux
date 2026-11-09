#!/usr/bin/env python3
"""Collect bounded read-only Ubuntu metrics as an unprivileged SSH account."""
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import time

MONITOR_VERSION = "0.3.0"
MAX_UPDATE_DETAILS = 150
UPGRADABLE = re.compile(
    r"^(?P<package>[^/\s]+)/(?P<repository>\S+)\s+"
    r"(?P<available>\S+)\s+\S+\s+"
    r"\[upgradable from: (?P<installed>[^\]]+)\]$"
)


def run(args, seconds=8):
    try:
        return subprocess.run(
            args, capture_output=True, text=True,
            timeout=seconds, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def cpu_read():
    with open("/proc/stat", encoding="ascii") as handle:
        values = [int(x) for x in handle.readline().split()[1:]]
    idle = values[3] + values[4]
    return sum(values), idle


def cpu_percent():
    before, before_idle = cpu_read()
    time.sleep(0.15)
    after, after_idle = cpu_read()
    delta = after - before
    return round(100 * (1 - (after_idle - before_idle) / delta), 1) if delta else 0


def mem_percent():
    mem = {}
    with open("/proc/meminfo", encoding="ascii") as handle:
        for line in handle:
            key, val = line.split(":", 1)
            mem[key] = int(val.strip().split()[0])
    return round(100 * (1 - mem["MemAvailable"] / mem["MemTotal"]), 1)


def ubuntu_version():
    """Read Ubuntu's reported OS version without launching an external process."""
    with open("/etc/os-release", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("VERSION_ID="):
                return line.split("=", 1)[1].strip().strip('"')
    return "unknown"


def pending_updates():
    """Read cached APT candidates without refreshing indexes or changing packages.

    Return (count, details). APT output may include repositories and versions;
    preserve exact package versions without inferring security origin.
    """
    result = run(["apt", "list", "--upgradable"], 12)
    if result is None or result.returncode != 0:
        return None, []
    count = 0
    details = []
    for line in result.stdout.splitlines():
        match = UPGRADABLE.match(line.strip())
        if match is None:
            continue
        count += 1
        if len(details) < MAX_UPDATE_DETAILS:
            details.append({
                "package": match["package"],
                "installed": match["installed"],
                "available": match["available"],
                "repository": match["repository"],
            })
    return count, details


def main():
    disk = shutil.disk_usage("/")
    with open("/proc/uptime", encoding="ascii") as handle:
        uptime = int(float(handle.read().split()[0]))
    root = run(["sudo", "-n", "/usr/local/sbin/ha-ubuntu-monitor-root"], 8)
    failed = None
    if root and root.returncode == 0:
        try:
            failed = int(root.stdout.strip())
        except ValueError:
            pass
    update_count, update_details = pending_updates()
    print(json.dumps({
        "schema": 1,
        "monitor_version": MONITOR_VERSION,
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "ubuntu_version": ubuntu_version(),
        "cpu_percent": cpu_percent(),
        "memory_percent": mem_percent(),
        "disk_percent": round(100 * disk.used / disk.total, 1),
        "disk_free_gb": round(disk.free / 1_000_000_000, 2),
        "load_1": round(os.getloadavg()[0], 2),
        "uptime_seconds": uptime,
        "updates_available": update_count,
        "update_packages": update_details,
        "failed_services": failed,
        "reboot_required": os.path.exists("/var/run/reboot-required"),
    }))


if __name__ == "__main__":
    main()
