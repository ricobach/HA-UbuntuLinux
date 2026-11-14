"""Shared poller for one Ubuntu host."""
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, SCAN_INTERVAL
from .ssh import fetch_metrics, compose_command


class UbuntuCoordinator(DataUpdateCoordinator):
    """Poll remote monitor once for all entities."""

    def __init__(self, hass, entry):
        super().__init__(hass, logger=__import__("logging").getLogger(__name__),
                         name=f"{DOMAIN}_{entry.entry_id}", update_interval=SCAN_INTERVAL)
        self.entry = entry

    async def _async_update_data(self):
        try:
            data = await fetch_metrics(
                self.entry.data["host"], self.entry.data["port"],
                self.entry.data["username"], self.entry.data["private_key"],
                self.entry.data["fingerprint"],
            )
            project = self.entry.options.get("compose_project")
            if project:
                try:
                    data["compose"] = await compose_command(
                        self.entry, "status", project
                    )
                except Exception as exc:
                    data["compose"] = {"services": [], "containers": [], "error": str(exc)}
            return data
        except Exception as exc:
            raise UpdateFailed(f"SSH monitoring failed: {exc}") from exc

    async def async_compose_action(self, action, service=None):
        """Execute an explicit action and immediately refresh the entities."""
        project = self.entry.options.get("compose_project")
        if not project:
            raise ValueError("No Docker Compose project configured")
        result = await compose_command(self.entry, action, project, service)
        await self.async_request_refresh()
        return result
