"""Ubuntu Linux SSH integration."""
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady
from .const import DOMAIN
from .coordinator import UbuntuCoordinator
from .install_page import register_install_view

async def _async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.UPDATE, Platform.BUTTON]


async def async_setup(hass, config):
    """Expose the installer copy page before configuring servers."""
    register_install_view(hass)
    return True


async def async_setup_entry(hass, entry):
    """Start polling an Ubuntu host."""
    register_install_view(hass)
    coordinator = UbuntuCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as exc:
        raise ConfigEntryNotReady(str(exc)) from exc
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload entities without deleting keys."""
    success = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if success:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return success
