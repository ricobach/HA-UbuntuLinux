#!/usr/bin/env python3
"""Collect safe, bounded Ubuntu metrics as the unprivileged monitor account."""
import json
import os
import platform
import shutil
import socket
import subprocess
import time


def run(args, seconds=8):
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              timeout=seconds, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def cpu_read():
    with open("/proc/stat", encoding="ascii") as f:
        values = [int(x) for x in f.readline().split()[1:]]
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
    with open("/proc/meminfo", encoding="ascii") as f:
        for line in f:
            key, val = line.split(":", 1)
            mem[key] = int(val.strip().split()[0])
    return round(100 * (1 - mem["MemAvailable"] / mem["MemTotal"]), 1)


def update_count():
    result = run(["apt", "list", "--upgradable"], 8)
    if result is None or result.returncode != 0:
        return None
    return sum(1 for line in result.stdout.splitlines() if "/" in line and "[upgradable" in line)


def main():
    disk = shutil.disk_usage("/")
    with open("/proc/uptime", encoding="ascii") as f:
        uptime = int(float(f.read().split()[0]))
    root = run(["sudo", "-n", "/usr/local/sbin/ha-ubuntu-monitor-root"], 8)
    failed = None
    if root and root.returncode == 0:
        try:
            failed = int(root.stdout.strip())
        except ValueError:
            pass
    print(json.dumps({
        "schema": 1,
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "cpu_percent": cpu_percent(),
        "memory_percent": mem_percent(),
        "disk_percent": round(100 * disk.used / disk.total, 1),
        "disk_free_gb": round(disk.free / 1_000_000_000, 2),
        "load_1": round(os.getloadavg()[0], 2),
        "uptime_seconds": uptime,
        "updates_available": update_count(),
        "failed_services": failed,
        "reboot_required": os.path.exists("/var/run/reboot-required"),
    }))


if __name__ == "__main__":
    main()
