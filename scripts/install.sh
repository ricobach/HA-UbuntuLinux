#!/usr/bin/env bash
# Idempotent installer for Ubuntu Linux SSH monitoring.
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then echo "Run via sudo bash" >&2; exit 1; fi
PUBLIC_KEY="${1:-}"
MONITOR_USER="${2:-ha-monitor}"
if [[ ! "${PUBLIC_KEY}" =~ ^ssh-ed25519[[:space:]][A-Za-z0-9+/=]+([[:space:]].*)?$ ]]; then
  echo "Expected an SSH Ed25519 public key" >&2; exit 2
fi
if [[ ! "${MONITOR_USER}" =~ ^[a-z_][a-z0-9_-]{0,30}$ ]]; then
  echo "Invalid account name" >&2; exit 2
fi
if ! grep -qi '^ID=ubuntu' /etc/os-release; then
  echo "This installer supports Ubuntu only" >&2; exit 2
fi
for executable in python3 sshd sudo curl ssh-keygen visudo; do
  if ! command -v "${executable}" >/dev/null; then
    echo "Missing ${executable}. Install python3, openssh-server, curl and sudo first." >&2
    exit 2
  fi
done
if ! id "${MONITOR_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /bin/bash "${MONITOR_USER}"
fi
HOME_DIR="$(getent passwd "${MONITOR_USER}" | cut -d: -f6)"
install -d -m 700 -o "${MONITOR_USER}" -g "${MONITOR_USER}" "${HOME_DIR}/.ssh"
AUTH="${HOME_DIR}/.ssh/authorized_keys"
touch "${AUTH}"
chown "${MONITOR_USER}:${MONITOR_USER}" "${AUTH}"
chmod 600 "${AUTH}"
# Only replace this installer's managed key; preserve unrelated authorized keys.
TMP="$(mktemp)"
trap 'rm -f "${TMP}"' EXIT
awk '/^# BEGIN HA-UBUNTU-MONITOR$/ {skip=1; next} /^# END HA-UBUNTU-MONITOR$/ {skip=0; next} !skip {print}' "${AUTH}" > "${TMP}"
{
  cat "${TMP}"
  echo '# BEGIN HA-UBUNTU-MONITOR'
  echo "restrict ${PUBLIC_KEY}"
  echo '# END HA-UBUNTU-MONITOR'
} > "${AUTH}"
chown "${MONITOR_USER}:${MONITOR_USER}" "${AUTH}"
chmod 600 "${AUTH}"
# Download companion scripts from the same repository. HTTPS and root-owned install.
BASE="https://raw.githubusercontent.com/ricobach/HA-UbuntuLinux/main/scripts"
for name in monitor.py monitor-root.sh; do
  target="/usr/local/bin/ha-ubuntu-monitor"
  [[ "${name}" == monitor-root.sh ]] && target="/usr/local/sbin/ha-ubuntu-monitor-root"
  tmpfile="$(mktemp)"
  curl -fsSL --proto '=https' --tlsv1.2 "${BASE}/${name}" -o "${tmpfile}"
  install -o root -g root -m 755 "${tmpfile}" "${target}"
  rm -f "${tmpfile}"
done
tmpfile="$(mktemp)"
curl -fsSL --proto '=https' --tlsv1.2 "${BASE}/compose_helper.py" -o "${tmpfile}"
install -o root -g root -m 755 "${tmpfile}" /usr/local/sbin/ha-ubuntu-compose
rm -f "${tmpfile}"
SUDO_FILE="/etc/sudoers.d/ha-ubuntu-monitor"
printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/ha-ubuntu-monitor-root\n' "${MONITOR_USER}" > "${SUDO_FILE}"
printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/ha-ubuntu-compose status *, /usr/local/sbin/ha-ubuntu-compose up *, /usr/local/sbin/ha-ubuntu-compose down *, /usr/local/sbin/ha-ubuntu-compose service-up *, /usr/local/sbin/ha-ubuntu-compose service-stop *\n' "${MONITOR_USER}" >> "${SUDO_FILE}"
chmod 440 "${SUDO_FILE}"
visudo -cf "${SUDO_FILE}"
echo "Monitoring installed for user: ${MONITOR_USER}"
echo "Server SSH Ed25519 fingerprint (verify out of band):"
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
echo "Test: sudo -u ${MONITOR_USER} /usr/local/bin/ha-ubuntu-monitor"
