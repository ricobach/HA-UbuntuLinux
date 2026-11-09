"""Read-only Ubuntu APT package updates shown through Home Assistant's Update UI."""
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

MAX_RELEASE_NOTES_CHARS = 15000


async def async_setup_entry(hass, entry, async_add_entities):
    """Register one update entity for each monitored Ubuntu server."""
    async_add_entities([UbuntuSystemUpdate(hass.data[DOMAIN][entry.entry_id])])


class UbuntuSystemUpdate(CoordinatorEntity, UpdateEntity):
    """Expose pending APT packages without offering remote installation."""

    _attr_has_entity_name = True
    _attr_name = "Ubuntu system updates"
    _attr_title = "Ubuntu package updates"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_ubuntu_system_updates"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=self.coordinator.entry.title,
            manufacturer="Ubuntu",
            model=self.coordinator.data.get("os", "Linux"),
        )

    @property
    def _count(self):
        value = self.coordinator.data.get("updates_available")
        return value if type(value) is int and value >= 0 else None

    @property
    def _ubuntu_label(self):
        release = self.coordinator.data.get("ubuntu_version")
        return f"Ubuntu {release}" if release else "Ubuntu (version unknown)"

    @property
    def installed_version(self):
        """Ubuntu version is unchanged by routine APT package upgrades."""
        return self._ubuntu_label if self._count is not None else None

    @property
    def latest_version(self):
        """Describe pending package upgrades without inventing an Ubuntu release."""
        count = self._count
        if count is None:
            return None
        if count == 0:
            return self._ubuntu_label
        return f"{self._ubuntu_label} · {count} updates"

    @property
    def has_update(self):
        """Compare package counts instead of comparing OS release numbers."""
        return self._count is not None and self._count > 0

    def version_is_newer(self, latest_version, installed_version):
        """Keep compatibility with Home Assistant's update comparison methods."""
        return self.has_update

    @property
    def release_summary(self):
        count = self._count
        if count is None:
            return "APT package update information is unavailable."
        if count == 0:
            return "No APT package upgrades are pending in the local package cache."
        packages = self.coordinator.data.get("update_packages") or []
        preview = ", ".join(str(p.get("package", "")) for p in packages[:5])
        intro = f"{count} Ubuntu package update(s) pending."
        if preview:
            intro += f" Including: {preview}."
        if len(packages) > 5:
            intro += " Open release notes for all packages and versions."
        if self.coordinator.data.get("reboot_required"):
            intro += " Reboot required."
        return intro[:255]

    async def async_release_notes(self):
        """Provide Home Assistant's release-notes dialog with a Markdown list."""
        count = self._count
        if count is None:
            return "Ubuntu package information is currently unavailable."
        if count == 0:
            return "No package upgrades are pending in the local APT cache."
        packages = self.coordinator.data.get("update_packages") or []
        lines = [
            f"## Ubuntu {self.coordinator.data.get('ubuntu_version', '')} package updates",
            "",
            f"**{count} package update(s) pending.**",
            "",
            "APT uses locally cached package indexes; run `sudo apt update` on the server to refresh them.",
            "This integration does not install updates.",
            "",
        ]
        if self.coordinator.data.get("reboot_required"):
            lines.extend(["**A system reboot is required.**", ""])
        if packages:
            lines.extend(["### Pending packages", ""])
            for package in packages:
                # Markdown code spans prevent package versions being interpreted as formatting.
                name = str(package.get("package", "")).replace("`", "")
                installed = str(package.get("installed", "?")).replace("`", "")
                available = str(package.get("available", "?")).replace("`", "")
                lines.append(f"- **{name}**: `{installed}` → `{available}`")
            if count > len(packages):
                lines.extend(["", f"_Showing {len(packages)} of {count} updates._"])
        else:
            lines.append("The server is running an older monitoring script that does not return package details. Update its monitoring scripts to see the complete list.")
        return "\n".join(lines)[:MAX_RELEASE_NOTES_CHARS]

    @property
    def extra_state_attributes(self):
        """Keep entity state small; detailed package lists belong in release notes."""
        return {
            "package_count": self._count,
            "reboot_required": self.coordinator.data.get("reboot_required"),
        }
