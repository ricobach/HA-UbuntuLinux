# Ubuntu Linux SSH for Home Assistant

Custom Home Assistant integration that polls Ubuntu servers securely over SSH, without an agent daemon or inbound ports beyond SSH.

## Features

- One Home Assistant device per host; polls every 60 seconds.
- CPU %, memory %, root disk usage/free, load average, uptime, available apt upgrades, failed systemd services, reboot required.
- Dedicated SSH Ed25519 identity per integration entry (generated during setup).
- A copyable `curl | sudo bash` command installs/updates an Ubuntu monitoring account, root-owned collectors, and a narrowly scoped sudoers rule.
- Host key fingerprint pinning: configuration refuses to connect until the SSH server fingerprint is supplied and verified.
- No root SSH login, passwords, or broad `NOPASSWD: ALL` access.

## Installation

Copy `custom_components/ubuntu_linux` to `<config>/custom_components/ubuntu_linux` on Home Assistant. Restart Home Assistant. Go to **Settings → Devices & services → Add integration → Ubuntu Linux SSH**.

Enter the Ubuntu host and SSH port. The integration generates a dedicated private/public SSH key pair and displays a bootstrap command containing **only the public key**. Review [scripts/install.sh](scripts/install.sh) before executing the command on the Ubuntu server with sudo. The installer also downloads the two root-owned monitoring scripts from this repository. Run the bootstrap command again whenever you want to update those scripts or rotate the authorized key.

Get the **server's** SSH host fingerprint on Ubuntu with:

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

Enter the `SHA256:...` value (not the monitoring user key fingerprint) in the final setup step. The integration tests SSH authentication and the collector before creating the device.

### Permissions

The installer creates a system account (`ha-monitor` by default), an `authorized_keys` block with OpenSSH `restrict` restrictions, and the exact sudoers rule:

```text
ha-monitor ALL=(root) NOPASSWD: /usr/local/sbin/ha-ubuntu-monitor-root
```

Only the fixed root-owned helper can execute without a password, and it accepts no arguments. The main collector runs unprivileged. All file paths under `/usr/local` are owned by root. SSH access must be enabled, and the Home Assistant host must reach the Ubuntu machine over TCP 22 (or your configured SSH port).

### Security notes

- The private key is stored in the Home Assistant config entry database. Protect Home Assistant backups and `.storage`; do not commit them.
- The one-liner downloads executable code as root. Audit and pin the URL to a reviewed commit for high-assurance environments. Updating from `main` always executes its latest content.
- Verify the server fingerprint out of band. A changed server host key requires reconfiguration; do not disable verification.
- Protect the Home Assistant instance: anyone controlling this integration's private key can access the monitoring account.
- The monitor is **read-only**; it does not expose arbitrary command execution or systemd control.
- The first version is intended for Ubuntu with systemd, apt, Python 3, OpenSSH, and sudo.

## Development

Validate Python syntax with `python3 -m compileall custom_components/ubuntu_linux scripts/monitor.py` and shell syntax with `bash -n scripts/*.sh`. Test installation only on a non-production Ubuntu VM first.

Issues and contributions: https://github.com/ricobach/HA-UbuntuLinux/issues
