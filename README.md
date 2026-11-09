# Ubuntu Linux SSH for Home Assistant

Custom Home Assistant integration that polls Ubuntu servers securely over SSH, without an agent daemon or inbound ports beyond SSH.

## Features

- One Home Assistant device per host; polls every 60 seconds.
- CPU %, memory %, root disk usage/free, load average, uptime, available apt upgrades (count and alert binary sensor), failed systemd services, reboot required, and installed monitor script version.
- Dedicated SSH Ed25519 identity per integration entry (generated during setup).
- A copyable `curl | sudo bash` command fetched **directly from Home Assistant** installs the Ubuntu monitoring account, root-owned collectors, and narrowly scoped sudoers rule without contacting GitHub.
- No fingerprint entry in the setup flow: the first successful SSH connection pins the observed host key (trust on first use); subsequent connections reject host-key changes.
- No root SSH login, passwords, or broad `NOPASSWD: ALL` access.

## Home Assistant-hosted installer

During setup, Home Assistant generates a temporary **30-minute**, 256-bit random enrollment token and serves a self-contained installer at:

```text
http(s)://YOUR-HA-SERVER:8123/api/ubuntu_linux/bootstrap/TOKEN
```

The copyable one-line command shown during setup is:

```bash
curl -fsSL 'http(s)://YOUR-HA-SERVER:8123/api/ubuntu_linux/bootstrap/TOKEN' | sudo bash
```

The URL is generated with Home Assistant's configured **internal URL** (Settings → System → Network). The Ubuntu host must be able to resolve and connect to that URL. Configure a suitable reachable HA internal URL before adding a host. The endpoint bundles the public SSH key and the monitoring scripts from the installed HA integration; it makes no calls to GitHub or other external servers on Ubuntu. The private SSH key is never served.

Anyone with the URL can download and inspect the installer until it expires or setup succeeds. Treat it as a short-lived secret. **Prefer HTTPS with a trusted certificate**; running a root-level installer fetched over plain HTTP exposes you to script tampering by an on-path attacker. No permanent unauthenticated `/install.sh` endpoint is provided. Review the generated script before running it as root.

The integrated copy page is still available as a link in the installation dialog. Existing monitored hosts are unaffected. To refresh the Ubuntu-side script later, use the separate updater in the section below.

## Human-readable uptime

The **Uptime** sensor displays elapsed time as `70d 0h 35m 19s` instead of a numeric seconds value. The original raw value remains available as the `uptime_seconds` state attribute on that sensor. An additional **Uptime seconds** numeric sensor is created but disabled by default; enable it in entity settings if you need a numeric state for time-series statistics or automations. No Ubuntu-side script update is necessary for this change.

## Integration logo

Home Assistant 2026.3+ reads the Ubuntu icon and logo from `custom_components/ubuntu_linux/brand/`.
The source is [Ubuntu logoib.svg on Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Ubuntu_logoib.svg) (Bear17, CC BY-SA 4.0). See [branding attribution](custom_components/ubuntu_linux/brand/ATTRIBUTION.md). The image files are generated and committed by the [brand assets workflow](.github/workflows/build-brand.yml).

## Installation

Copy `custom_components/ubuntu_linux` to `<config>/custom_components/ubuntu_linux` on Home Assistant. Restart Home Assistant. Go to **Settings → Devices & services → Add integration → Ubuntu Linux SSH**.

Enter a **Server Name**, Ubuntu hostname or IP, SSH port, and monitoring account. The Server Name is used for the Home Assistant device. The integration generates a dedicated private/public SSH key pair and displays a bootstrap command containing **only the public key**. Review [scripts/install.sh](scripts/install.sh) before executing the command on the Ubuntu server with sudo. The installer also includes the two root-owned monitoring scripts bundled within the installed Home Assistant integration. Run the bootstrap command again whenever you want to update those scripts or rotate the authorized key.

Open the **installation command with Copy button** link in the setup dialog to copy the exact one-line command with one click (requires browser clipboard permissions and HTTPS or localhost). A read-only selectable command field remains available as a fallback. The page is served by Home Assistant behind a random 30-minute link and contains only the generated public SSH key, never the private key. Run the command, on Ubuntu, then click **Submit** in Home Assistant. The integration tests SSH access and discovers the server's host key automatically. No fingerprint needs to be entered.\n\n### Ubuntu updates and reboot monitoring

The **Updates available** sensor counts packages in the local APT cache (`apt list --upgradable`). Monitor script v0.3.0 also returns package names, installed versions, available versions and the Ubuntu release to Home Assistant. It does not refresh APT indexes automatically; use Ubuntu's regular background APT updates or run `sudo apt update` to refresh those indexes. The **Reboot required** binary sensor checks for `/var/run/reboot-required`. Neither sensor installs packages nor reboots the server.

### System update alert in Home Assistant

The integration provides three update-related entities (the update dialog's package list requires Ubuntu monitor script **0.3.0 or newer**):

- **Updates available** (numeric sensor): number of upgradable APT packages.
- **Ubuntu system updates** (read-only Update entity): appears in Home Assistant's update interface when upgrades are pending. Its installed version identifies the Ubuntu release and its latest-version label indicates how many package updates are pending. **Release notes** shows the list of upgradable packages with installed and candidate versions. No remote installation feature is enabled.\n- **System updates available** (binary sensor): `on` when the package count is greater than zero, `off` when zero, and `unknown` when the count cannot be read. Its `package_count` attribute contains the count.

To notify when updates first become available, create an automation using your actual entity ID and mobile notification service:

```yaml
alias: Ubuntu system updates available
description: Notify when an Ubuntu server has upgradable packages
triggers:
  - trigger: state
    entity_id: binary_sensor.ubuntu_production_system_updates_available
    to: "on"
conditions: []
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: "Ubuntu updates available"
      message: >-
        {{ state_attr('binary_sensor.ubuntu_production_system_updates_available',
                      'package_count') }} packages can be upgraded on Ubuntu Production.
mode: single
```

You can alternatively create an automation triggered by the state of `update.<your_server>_ubuntu_system_updates` changing to `on`. Home Assistant's Update entity has no install action for this integration.\n\nThis alerts when the sensor transitions to `on`, including after an unavailable or unknown state. It does not automatically upgrade the system. APT indexes must still be refreshed regularly for fresh update counts.

### Updating the Ubuntu monitoring scripts

Run this on the monitored Ubuntu server:

```bash
curl -fsSL https://raw.githubusercontent.com/ricobach/HA-UbuntuLinux/main/scripts/update.sh | sudo bash
```

This replaces only `/usr/local/bin/ha-ubuntu-monitor` and `/usr/local/sbin/ha-ubuntu-monitor-root`. It does **not** replace SSH keys, modify the monitoring account, or rewrite sudoers. It downloads both files, validates Python and Bash syntax, and saves previous versions with `.bak` suffixes before installation. The **Monitor script version** sensor reports the version installed on each machine after the next poll. **Run the command above on every existing monitored Ubuntu server** to upgrade its collector to v0.3.0 and enable detailed APT package lists in the Home Assistant Update entity. The Home Assistant integration itself must also be updated through HACS.

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
