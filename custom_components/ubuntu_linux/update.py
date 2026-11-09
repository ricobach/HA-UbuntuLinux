"""Read-only Ubuntu APT update entity.

APT does not provide one installed/latest OS version for a set of pending
package upgrades. The version fields deliberately represent pending *counts*
rather than Ubuntu release versions.
"""
from homeassistant.components.update import UpdateEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Add an update entity for each Ubuntu server."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([UbuntuSystemUpdate(coordinator)])


class UbuntuSystemUpdate(CoordinatorEntity, UpdateEntity):
    """Report pending package updates without installing them."""

    _attr_has_entity_name = True
    _attr_name = "Ubuntu system updates"
    _attr_title = "Ubuntu APT package updates"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_supported_features = 0

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
    def installed_version(self):
        """Baseline count, not an Ubuntu OS version."""
        if not self._valid_count:
            return None
        return "0 pending"

    @property
    def latest_version(self):
        """Current number of pending packages, not an Ubuntu OS version."""
        if not self._valid_count:
            return None
        return f"{self.coordinator.data['updates_available']} pending"

    @property
    def _valid_count(self):
        count = self.coordinator.data.get("updates_available")
        return isinstance(count, int) and not isinstance(count, bool) and count >= 0

    @property
    def has_update(self):
        """Ubuntu Core 2026.11+: use explicit count rather than version ordering."""
        return self._valid_count and self.coordinator.data["updates_available"] > 0

    def version_is_newer(self, latest_version, installed_version):
        """Support HA versions before Core 2026.11 too."""
        return self._valid_count and self.coordinator.data["updates_available"] > 0

    @property
    def release_summary(self):
        if not self._valid_count:
            return None
        count = self.coordinator.data["updates_available"]
        return (
            f"{count} APT package upgrade(s) available in the local package cache. "
            "Refresh apt indexes on Ubuntu to discover newly released updates. "
            "Installation from Home Assistant is intentionally disabled."
        )

    @property
    def extra_state_attributes(self):
        return {"package_count": self.coordinator.data.get("updates_available")}
