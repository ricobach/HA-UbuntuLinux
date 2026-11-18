#!/usr/bin/env python3
"""Fixed-command, root-owned Ubuntu APT maintenance helper.

Public commands: status, check, install, reboot.  The worker verb is executed
only by a transient systemd service.  Never accept package names, shell input,
arbitrary commands, or APT options from Home Assistant.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

STATE_DIR = Path("/var/lib/ha-ubuntu-monitor")
STATE_FILE = STATE_DIR / "maintenance.json"
LOCK_FILE = STATE_DIR / "maintenance.lock"
HELPER = "/usr/local/sbin/ha-ubuntu-maintenance"
VALID_UNIT = re.compile(r"^ha-ubuntu-apt-[0-9]+-[0-9]+\.service$")


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_directory():
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE_DIR, 0o700)


def read_state():
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def save_state(state):
    ensure_directory()
    temp = STATE_DIR / ("maintenance-" + str(os.getpid()) + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(state, stream, sort_keys=True)
        stream.write("\n")
    os.chmod(temp, 0o600)
    os.replace(temp, STATE_FILE)


def active(unit):
    if not isinstance(unit, str) or not VALID_UNIT.fullmatch(unit):
        return False
    result = subprocess.run(
        ["/usr/bin/systemctl", "is-active", "--quiet", unit],
        check=False, timeout=10,
    )
    return result.returncode == 0


def sanitized_status():
    state = read_state()
    if not state:
        return {"state": "idle", "operation": None, "phase": None,
                "started_at": None, "finished_at": None, "result": None}
    if state.get("state") in ("queued", "running"):
        unit = state.get("unit")
        if active(unit):
            return state
        # systemd-run can take a moment to activate a newly queued service.
        if state.get("state") == "queued" and time.time() - state.get("queued_epoch", 0) < 15:
            return state
        if state.get("state") == "running":
            # The worker might have just written completion state.
            recent = read_state()
            if recent.get("state") not in ("queued", "running"):
                return recent
        state = {**state, "state": "failed", "phase": "interrupted",
                 "result": "Maintenance job stopped unexpectedly",
                 "finished_at": stamp()}
        save_state(state)
    state.pop("queued_epoch", None)
    return state


def execute_worker(operation, unit):
    """Run APT in the background under systemd, even if SSH disconnects."""
    if operation not in ("check", "install") or not VALID_UNIT.fullmatch(unit):
        raise ValueError("Invalid worker arguments")
    with (LOCK_FILE).open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = read_state()
        if state.get("unit") != unit or state.get("operation") != operation:
            raise ValueError("Worker was not scheduled")
        state.update(state="running", phase="refreshing", started_at=stamp())
        save_state(state)
    commands = [["/usr/bin/apt-get", "update"]]
    if operation == "install":
        commands.append([
            "/usr/bin/apt-get", "-y", "-o", "Dpkg::Options::=--force-confold",
            "upgrade",
        ])
    result = "Updates checked" if operation == "check" else "Updates installed"
    success = True
    for index, command in enumerate(commands):
        if index:
            state.update(phase="installing")
            save_state(state)
        try:
            process = subprocess.run(
                command,
                env={**os.environ, "DEBIAN_FRONTEND": "noninteractive",
                     "APT_LISTCHANGES_FRONTEND": "none"},
                check=False, timeout=7200,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if process.returncode != 0:
                success = False
                result = f"APT command failed (exit code {process.returncode}); inspect journalctl -u {unit}"
                break
        except (OSError, subprocess.TimeoutExpired):
            success = False
            result = f"APT command could not complete; inspect journalctl -u {unit}"
            break
    state.update(
        state="success" if success else "failed",
        phase="complete" if success else "error",
        finished_at=stamp(), result=result,
    )
    save_state(state)


def start_job(operation):
    ensure_directory()
    with LOCK_FILE.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = sanitized_status()
        if previous.get("state") in ("queued", "running"):
            raise ValueError("A maintenance job is already active")
        unit = f"ha-ubuntu-apt-{int(time.time())}-{os.getpid()}.service"
        new = {
            "state": "queued", "phase": "scheduled", "operation": operation,
            "unit": unit, "started_at": None, "finished_at": None,
            "result": None, "queued_epoch": time.time(),
        }
        save_state(new)
        try:
            cmd = [
                "/usr/bin/systemd-run", "--quiet", "--collect",
                "--unit", unit[:-8], "--property=Type=exec",
                HELPER, "worker", operation, unit,
            ]
            completed = subprocess.run(
                cmd, check=False, timeout=25,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if completed.returncode:
                raise RuntimeError("Could not start transient systemd maintenance unit")
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            new.update(state="failed", phase="error", finished_at=stamp(),
                       result="Could not schedule the maintenance job")
            save_state(new)
            raise
    return {"accepted": True, "operation": operation, "unit": unit}


def reboot():
    state = sanitized_status()
    if state.get("state") in ("queued", "running"):
        raise ValueError("Reboot blocked while maintenance is running")
    completed = subprocess.run(
        ["/usr/bin/systemd-run", "--quiet", "--collect", "--on-active=5s",
         "--unit=ha-ubuntu-requested-reboot", "/usr/bin/systemctl", "reboot"],
        check=False, timeout=20,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if completed.returncode:
        raise RuntimeError("Could not schedule a reboot")
    return {"accepted": True, "operation": "reboot", "message": "Reboot scheduled in five seconds"}


def main():
    if os.geteuid() != 0:
        raise ValueError("Root permissions are required")
    arguments = sys.argv[1:]
    if arguments == ["status"]:
        print(json.dumps(sanitized_status()))
    elif arguments == ["check"]:
        print(json.dumps(start_job("check")))
    elif arguments == ["install"]:
        print(json.dumps(start_job("install")))
    elif arguments == ["reboot"]:
        print(json.dumps(reboot()))
    elif len(arguments) == 3 and arguments[0] == "worker":
        execute_worker(arguments[1], arguments[2])
    else:
        raise ValueError("Unsupported maintenance command")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
