#!/usr/bin/env python3
"""Restricted Docker Compose gateway for Home Assistant Ubuntu SSH integration.

Only projects explicitly registered locally by an administrator are accessible.
The helper always executes an argv list (never a shell), never returns resolved
Compose configuration or environment variable values, and accepts fixed verbs.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REGISTRY = Path("/etc/ha-ubuntu-monitor/compose-projects.json")
SERVICE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root"}


def fatal(message):
    print(message, file=sys.stderr)
    sys.exit(2)


def registry():
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}


def store(data):
    REGISTRY.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(REGISTRY.parent, 0o700)
    fd = os.open(str(REGISTRY) + ".tmp", os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, sort_keys=True)
    os.replace(str(REGISTRY) + ".tmp", REGISTRY)
    os.chmod(REGISTRY, 0o600)


def compose(path, *args):
    command = ["docker", "compose", "--project-directory", str(path.parent), "-f", str(path), *args]
    result = subprocess.run(command, cwd=path.parent, env=ENV, capture_output=True,
                            text=True, timeout=90, check=False)
    if result.returncode:
        # Compose may echo interpolated values in error messages; do not send those to HA.
        fatal("Docker Compose failed; check Docker and Compose logs locally on Ubuntu")
    return result.stdout


def main():
    if os.geteuid() != 0:
        fatal("Root permissions required")
    if len(sys.argv) < 3:
        fatal("Usage: ha-ubuntu-compose <status|up|down|service-up|service-stop|register> <project-id> [service|compose-path]")
    verb, project = sys.argv[1:3]
    if not SERVICE.fullmatch(project):
        fatal("Invalid project identifier")
    data = registry()
    if verb == "register":
        # The SSH monitoring account must never be allowed to register a project.
        if os.environ.get("SUDO_USER") in ("ha-monitor",):
            fatal("Registration must be performed by an Ubuntu administrator")
        if len(sys.argv) != 4:
            fatal("Usage: sudo ha-ubuntu-compose register <project-id> /absolute/path/compose.yaml")
        requested = Path(sys.argv[3])
        if not requested.is_absolute() or not requested.is_file():
            fatal("Compose file must be an existing absolute file path")
        resolved = requested.resolve(strict=True)
        data[project] = str(resolved)
        store(data)
        print("Registered project:", project)
        return
    if verb not in ("status", "up", "down", "service-up", "service-stop"):
        fatal("Unsupported operation")
    expected = 4 if verb.startswith("service-") else 3
    if len(sys.argv) != expected:
        fatal("Invalid number of arguments")
    raw = data.get(project)
    if not raw:
        fatal("Project not registered; run sudo ha-ubuntu-compose register locally")
    path = Path(raw)
    if not path.is_file() or path.resolve(strict=True) != path:
        fatal("Registered Compose file missing or changed")
    service = sys.argv[3] if len(sys.argv) == 4 else None
    if service and not SERVICE.fullmatch(service):
        fatal("Invalid Compose service name")
    if verb == "status":
        services = compose(path, "config", "--services").splitlines()
        raw_ps = compose(path, "ps", "-a", "--format", "json")
        containers = []
        for line in raw_ps.strip().splitlines():
            try:
                row = json.loads(line)
                if isinstance(row, list):
                    elements = row
                else:
                    elements = [row]
                for item in elements:
                    if not isinstance(item, dict):
                        continue
                    containers.append({
                        "name": str(item.get("Name") or "")[:160],
                        "service": str(item.get("Service") or "")[:128],
                        "state": str(item.get("State") or "unknown")[:40],
                        "health": str(item.get("Health") or "")[:40],
                    })
            except (ValueError, TypeError):
                fatal("Unexpected docker compose ps output")
        print(json.dumps({"services": services, "containers": containers}))
        return
    if verb == "up":
        compose(path, "up", "-d")
    elif verb == "down":
        compose(path, "down")
    else:
        services = compose(path, "config", "--services").splitlines()
        if service not in services:
            fatal("Service not defined by this compose project")
        if verb == "service-up":
            compose(path, "up", "-d", service)
        else:
            compose(path, "stop", service)
    print(json.dumps({"ok": True, "operation": verb, "project": project}))


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired:
        fatal("Docker Compose command timed out")
