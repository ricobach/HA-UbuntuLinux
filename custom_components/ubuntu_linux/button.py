"""Explicit Docker Compose action buttons: no switches or automatic toggles."""
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if not entry.options.get("compose_project"):
        return
    project = entry.options["compose_project"]
    async_add_entities([
        DockerComposeActionButton(coordinator, "up", None),
        DockerComposeActionButton(coordinator, "down", None),
    ])
    discovered = set()

    def add_services():
        services = set(coordinator.data.get("compose", {}).get("services", []))
        new = sorted(services - discovered)
        if new:
            discovered.update(new)
            async_add_entities(
                DockerComposeActionButton(coordinator, action, service)
                for service in new for action in ("service-up", "service-stop")
            )

    add_services()
    entry.async_on_unload(coordinator.async_add_listener(add_services))


class DockerComposeActionButton(CoordinatorEntity, ButtonEntity):
    """One deliberate control; Compose manages the dependencies."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, action, service):
        super().__init__(coordinator)
        self.action = action
        self.service = service
        self._attr_name = (
            f"Docker {service} {'Up' if action == 'service-up' else 'Stop'}"
            if service else f"Docker project {'Up' if action == 'up' else 'Down'}"
        )
        self._attr_icon = "mdi:play-circle" if action.endswith("up") else "mdi:stop-circle"
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_compose_"
            f"{coordinator.entry.options['compose_project']}_{service or 'project'}_{action}"
        )

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=self.coordinator.entry.title,
            manufacturer="Ubuntu",
            model=self.coordinator.data.get("os", "Linux"),
        )

    async def async_press(self):
        """Execute a requested action only when a button is pressed."""
        await self.coordinator.async_compose_action(self.action, self.service)
