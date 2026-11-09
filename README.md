# Ubuntu Linux SSH for Home Assistant

Custom Home Assistant integration that polls Ubuntu servers securely over SSH, without an agent daemon or inbound ports beyond SSH.

## Features

- One Home Assistant device per host; polls every 60 seconds.
- CPU %, memory %, root disk usage/free, load average, uptime, available apt upgrades, failed systemd services, reboot required, and installed monitor script version.
- Dedicated SSH Ed25519 identity per integration entry (generated during setup).
- A copyable `curl | sudo bash` command installs/updates an Ubuntu monitoring account, root-owned collectors, and a narrowly scoped sudoers rule.
- No fingerprint entry in the setup flow: the first successful SSH connection pins the observed host key (trust on first use); subsequent connections reject host-key changes.
- No root SSH login, passwords, or broad `NOPASSWD: ALL` access.

## Installation

Copy `custom_components/ubuntu_linux` to `<config>/custom_components/ubuntu_linux` on Home Assistant. Restart Home Assistant. Go to **Settings → Devices & services → Add integration → Ubuntu Linux SSH**.

Enter a **Server Name**, Ubuntu hostname or IP, SSH port, and monitoring account. The Server Name is used for the Home Assistant device. The integration generates a dedicated private/public SSH key pair and displays a bootstrap command containing **only the public key**. Review [scripts/install.sh](scripts/install.sh) before executing the command on the Ubuntu server with sudo. The installer also downloads the two root-owned monitoring scripts from this repository. Run the bootstrap command again whenever you want to update those scripts or rotate the authorized key.

Copy the generated command from the read-only **Installation command** field (select the text and use Ctrl+C / Cmd+C), execute it on Ubuntu, then click **Submit** in Home Assistant. The integration tests SSH access and discovers the server's host key automatically. No fingerprint needs to be entered.\n\n### Ubuntu updates and reboot monitoring

The **Updates available** sensor counts packages in the local APT cache (`apt list --upgradable`). It does not refresh APT indexes automatically; use Ubuntu's regular background APT updates or run `sudo apt update` to refresh those indexes. The **Reboot required** binary sensor checks for `/var/run/reboot-required`. Neither sensor installs packages nor reboots the server.

### Updating the Ubuntu monitoring scripts

Run this on the monitored Ubuntu server:

```bash
curl -fsSL https://raw.githubusercontent.com/ricobach/HA-UbuntuLinux/main/scripts/update.sh | sudo bash
```

This replaces only `/usr/local/bin/ha-ubuntu-monitor` and `/usr/local/sbin/ha-ubuntu-monitor-root`. It does **not** replace SSH keys, modify the monitoring account, or rewrite sudoers. It downloads both files, validates Python and Bash syntax, and saves previous versions with `.bak` suffixes before installation. The **Monitor script version** sensor reports the version installed on each machine after the next poll.

**Security:** Running the updater as root trusts the current contents of the repository's `main` branch. Review the changes before updating and pin the download to a reviewed commit for stronger supply-chain guarantees.

### Permissions

The installer creates a system account (`ha-monitor` by default), an `authorized_keys` block with OpenSSH `restrict` restrictions, and the exact sudoers rule:

```text
ha-monitor ALL=(root) NOPASSWD: /usr/local/sbin/ha-ubuntu-monitor-root
```

Only the fixed root-owned helper can execute without a password, and it accepts no arguments. The main collector runs unprivileged. All file paths under `/usr/local` are owned by root. SSH access must be enabled, and the Home Assistant host must reach the Ubuntu machine over TCP 22 (or your configured SSH port).

### Security notes

- The private key is stored in the Home Assistant config entry database. Protect Home Assistant backups and `.storage`; do not commit them.
- The one-liner downloads executable code as root. Audit and pin the URL to a reviewed commit for high-assurance environments. Updating from `main` always executes its latest content.
- **Trust on first use (TOFU):** the first SSH connection pins the key that the remote host presents; later key changes are rejected. The first connection is susceptible to a man-in-the-middle attack if the network is compromised. For high-assurance environments verify the observed key separately.
- Protect the Home Assistant instance: anyone controlling this integration's private key can access the monitoring account.
- The monitor is **read-only**; it does not expose arbitrary command execution or systemd control.
- The first version is intended for Ubuntu with systemd, apt, Python 3, OpenSSH, and sudo.

## Development

Validate Python syntax with `python3 -m compileall custom_components/ubuntu_linux scripts/monitor.py` and shell syntax with `bash -n scripts/*.sh`. Test installation only on a non-production Ubuntu VM first.

Issues and contributions: https://github.com/ricobach/HA-UbuntuLinux/issues
