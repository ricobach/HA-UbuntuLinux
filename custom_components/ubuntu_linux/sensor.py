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
    SensorEntityDescription(key="uptime_seconds", name="Uptime"),
    SensorEntityDescription(key="uptime_raw_seconds", name="Uptime seconds", native_unit_of_measurement="s", device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.MEASUREMENT, entity_registry_enabled_default=False),
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
        """Show a human-readable uptime while keeping raw seconds available."""
        key = self.entity_description.key
        if key in ("uptime_seconds", "uptime_raw_seconds"):
            seconds = self.coordinator.data.get("uptime_seconds")
            if seconds is None:
                return None
            if key == "uptime_raw_seconds":
                return seconds
            total = max(0, int(seconds))
            days, remainder = divmod(total, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds_part = divmod(remainder, 60)
            return f"{days}d {hours}h {minutes}m {seconds_part}s"
        return self.coordinator.data.get(key)

    @property
    def extra_state_attributes(self):
        """Retain precise uptime seconds on the visible Uptime sensor."""
        if self.entity_description.key == "uptime_seconds":
            return {"uptime_seconds": self.coordinator.data.get("uptime_seconds")}
        return None
