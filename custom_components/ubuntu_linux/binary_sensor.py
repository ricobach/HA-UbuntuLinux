"""Ubuntu SSH status sensors."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

DESCRIPTIONS = (
    BinarySensorEntityDescription(key="reboot_required", name="Reboot required"),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(UbuntuBinarySensor(coordinator, desc) for desc in DESCRIPTIONS)


class UbuntuBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
                          name=self.coordinator.entry.title,
                          manufacturer="Ubuntu", model=self.coordinator.data.get("os", "Linux"))

    @property
    def is_on(self):
        value = self.coordinator.data.get(self.entity_description.key)
        return bool(value) if value is not None else None
