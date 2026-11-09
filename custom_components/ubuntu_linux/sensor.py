"""Ubuntu SSH metric sensors."""
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

DESCRIPTIONS = (
    SensorEntityDescription(key="monitor_version", name="Monitor script version"),
    SensorEntityDescription(key="cpu_percent", name="CPU usage", native_unit_of_measurement="%", state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="memory_percent", name="Memory usage", native_unit_of_measurement="%", state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="disk_percent", name="Root disk usage", native_unit_of_measurement="%", state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="disk_free_gb", name="Root disk free", native_unit_of_measurement="GB", state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="load_1", name="Load average (1 min)", state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="uptime_seconds", name="Uptime", native_unit_of_measurement="s", device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="updates_available", name="Updates available", state_class=SensorStateClass.MEASUREMENT),
    SensorEntityDescription(key="failed_services", name="Failed systemd units", state_class=SensorStateClass.MEASUREMENT),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(UbuntuSensor(coordinator, description) for description in DESCRIPTIONS)


class UbuntuSensor(CoordinatorEntity, SensorEntity):
    """One metric from the shared response."""

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
    def native_value(self):
        return self.coordinator.data.get(self.entity_description.key)
