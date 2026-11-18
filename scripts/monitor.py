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

MONITOR_VERSION = "0.5.0"
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


SIMULATED_INSTALL = re.compile(r"^Inst\s+(?P<package>\S+)")


def pending_updates():
    """Count only upgrades that APT would install on THIS Ubuntu machine.

    apt list --upgradable includes phased, held, and dependency-blocked items.
    APT's simulation uses the same machine-id and phasing policy as the actual
    apt-get upgrade action. Never force phased updates into the simulation.
    If the simulation fails, return unknown instead of a misleading zero.
    """
    listing = run(["apt", "list", "--upgradable"], 10)
    simulation = run(
        ["apt-get", "-s", "upgrade"], 14
    )
    if (listing is None or simulation is None
            or listing.returncode != 0 or simulation.returncode != 0):
        return None, [], None, [], None
    candidates = {}
    for line in listing.stdout.splitlines():
        match = UPGRADABLE.match(line.strip())
        if match is not None:
            candidates[match["package"]] = {
                "package": match["package"],
                "installed": match["installed"],
                "available": match["available"],
                "repository": match["repository"],
            }
    planned = set()
    for line in simulation.stdout.splitlines():
        match = SIMULATED_INSTALL.match(line)
        if match:
            planned.add(match["package"])
    # apt list and apt-get -s may render the architecture qualification
    # differently. Match exact names first, then the unambiguous base name.
    by_base = {}
    for name in candidates:
        by_base.setdefault(name.split(":", 1)[0], []).append(name)
    selected = set()
    for package in planned:
        if package in candidates:
            selected.add(package)
        elif ":" not in package:
            names = by_base.get(package, [])
            if len(names) == 1:
                selected.add(names[0])
    ready = [detail for name, detail in candidates.items() if name in selected]
    deferred = [detail for name, detail in candidates.items() if name not in selected]
    # Deferred can include phased rollouts, held packages and dependencies.
    # Do not label all deferred packages as phased.
    return (len(ready), ready[:MAX_UPDATE_DETAILS],
            len(deferred), deferred[:MAX_UPDATE_DETAILS], len(candidates))

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
    update_count, update_details, deferred_count, deferred_details, total_count = pending_updates()
    maintenance = None
    maintenance_result = run(
        ["sudo", "-n", "/usr/local/sbin/ha-ubuntu-maintenance", "status"], 8
    )
    if maintenance_result and maintenance_result.returncode == 0:
        try:
            value = json.loads(maintenance_result.stdout)
            if isinstance(value, dict):
                maintenance = value
        except ValueError:
            pass
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
        "updates_deferred": deferred_count,
        "deferred_packages": deferred_details,
        "updates_total": total_count,
        "maintenance": maintenance,
        "failed_services": failed,
        "reboot_required": os.path.exists("/var/run/reboot-required"),
    }))


if __name__ == "__main__":
    main()
