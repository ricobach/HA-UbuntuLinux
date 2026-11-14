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
    if entry.options.get("compose_project"):
        async_add_entities([DockerComposeProjectSensor(coordinator)])
        discovered = set()
        discovered_containers = set()

        def add_services():
            response = coordinator.data.get("compose", {})
            services = set(response.get("services", []))
            new = sorted(services - discovered)
            if new:
                discovered.update(new)
                async_add_entities(
                    DockerComposeServiceSensor(coordinator, name) for name in new
                )
            containers = {
                (c.get("name"), c.get("service"))
                for c in response.get("containers", [])
                if c.get("name") and c.get("service")
            }
            new_containers = sorted(containers - discovered_containers)
            if new_containers:
                discovered_containers.update(new_containers)
                async_add_entities(
                    DockerComposeContainerSensor(coordinator, name, service)
                    for name, service in new_containers
                )

        add_services()
        entry.async_on_unload(coordinator.async_add_listener(add_services))


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

class DockerComposeServiceSensor(CoordinatorEntity, SensorEntity):
    """One entity per configured Compose service, including stopped services."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:docker"

    def __init__(self, coordinator, service):
        super().__init__(coordinator)
        self.service = service
        self._attr_name = f"Docker {service} status"
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_compose_"
            f"{coordinator.entry.options['compose_project']}_{service}"
        )

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=self.coordinator.entry.title,
            manufacturer="Ubuntu",
            model=self.coordinator.data.get("os", "Linux"),
        )

    @property
    def native_value(self):
        response = self.coordinator.data.get("compose", {})
        if response.get("error"):
            return None
        containers = [
            c for c in response.get("containers", [])
            if c.get("service") == self.service
        ]
        if not containers:
            return "not created"
        states = {c.get("state", "unknown").lower() for c in containers}
        if states == {"running"}:
            return "running"
        if len(states) == 1:
            return states.pop()
        return "mixed"

    @property
    def extra_state_attributes(self):
        response = self.coordinator.data.get("compose", {})
        containers = [
            {"name": c.get("name"), "state": c.get("state"), "health": c.get("health")}
            for c in response.get("containers", [])
            if c.get("service") == self.service
        ]
        return {
            "compose_project": self.coordinator.entry.options.get("compose_project"),
            "containers": containers,
            "error": response.get("error"),
        }

class DockerComposeProjectSensor(CoordinatorEntity, SensorEntity):
    """Project-level diagnostic showing whether the gateway can access Compose."""

    _attr_has_entity_name = True
    _attr_name = "Docker Compose project status"
    _attr_icon = "mdi:docker"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_compose_project_status"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=self.coordinator.entry.title,
            manufacturer="Ubuntu",
            model=self.coordinator.data.get("os", "Linux"),
        )

    @property
    def native_value(self):
        response = self.coordinator.data.get("compose", {})
        return "error" if response.get("error") else "ready"

    @property
    def extra_state_attributes(self):
        response = self.coordinator.data.get("compose", {})
        return {
            "project": self.coordinator.entry.options.get("compose_project"),
            "error": response.get("error"),
        }


class DockerComposeContainerSensor(CoordinatorEntity, SensorEntity):
    """Report each actual Docker Compose container, including replicas."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:docker"

    def __init__(self, coordinator, name, service):
        super().__init__(coordinator)
        self.container_name = name
        self.service = service
        self._attr_name = f"Docker container {name}"
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_container_"
            f"{coordinator.entry.options['compose_project']}_{name}"
        )

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=self.coordinator.entry.title,
            manufacturer="Ubuntu",
            model=self.coordinator.data.get("os", "Linux"),
        )

    @property
    def _container(self):
        for container in self.coordinator.data.get("compose", {}).get("containers", []):
            if container.get("name") == self.container_name:
                return container
        return None

    @property
    def native_value(self):
        if self.coordinator.data.get("compose", {}).get("error"):
            return None
        container = self._container
        return container.get("state", "unknown").lower() if container else "not created"

    @property
    def extra_state_attributes(self):
        container = self._container or {}
        return {"service": self.service, "health": container.get("health")}
