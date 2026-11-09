"""Shared poller for one Ubuntu host."""
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, SCAN_INTERVAL
from .ssh import fetch_metrics


class UbuntuCoordinator(DataUpdateCoordinator):
    """Poll remote monitor once for all entities."""

    def __init__(self, hass, entry):
        super().__init__(hass, logger=__import__("logging").getLogger(__name__),
                         name=f"{DOMAIN}_{entry.entry_id}", update_interval=SCAN_INTERVAL)
        self.entry = entry

    async def _async_update_data(self):
        try:
            return await fetch_metrics(
                self.entry.data["host"], self.entry.data["port"],
                self.entry.data["username"], self.entry.data["private_key"],
                self.entry.data["fingerprint"],
            )
        except Exception as exc:
            raise UpdateFailed(f"SSH monitoring failed: {exc}") from exc
