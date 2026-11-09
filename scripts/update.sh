#!/usr/bin/env bash
# Update only the Home Assistant Ubuntu monitoring collector scripts.
# Run: curl -fsSL https://raw.githubusercontent.com/ricobach/HA-UbuntuLinux/main/scripts/update.sh | sudo bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run this updater with sudo." >&2
    exit 1
fi

for cmd in curl install python3 bash mktemp; do
    command -v "${cmd}" >/dev/null || { echo "Missing: ${cmd}" >&2; exit 1; }
done

# Read-only download stage; no changes until validation succeeds.
base="https://raw.githubusercontent.com/ricobach/HA-UbuntuLinux/main/scripts"
stage="$(mktemp -d)"
trap 'rm -rf "${stage}"' EXIT

curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    "${base}/monitor.py" -o "${stage}/monitor.py"
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    "${base}/monitor-root.sh" -o "${stage}/monitor-root.sh"

# Validate syntax without creating pycache in the target directory.
python3 - "${stage}/monitor.py" <<'PY'
import ast
import pathlib
import sys
ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
PY
bash -n "${stage}/monitor-root.sh"

# Preserve existing scripts as backups in case rollback is needed.
for spec in "monitor.py:/usr/local/bin/ha-ubuntu-monitor" \
            "monitor-root.sh:/usr/local/sbin/ha-ubuntu-monitor-root"; do
    source="${spec%%:*}"
    target="${spec#*:}"
    if [[ -f "${target}" ]]; then
        cp -p "${target}" "${target}.bak"
    fi
    install -o root -g root -m 755 "${stage}/${source}" "${target}"
done

echo "Updated Ubuntu monitoring scripts."
echo "Version: $(/usr/local/bin/ha-ubuntu-monitor | python3 -c 'import json,sys; print(json.load(sys.stdin).get("monitor_version", "unknown"))')"
echo "The SSH monitoring account, authorized_keys, and sudoers configuration were not modified."
