"""Configure an Ubuntu server with a generated installer command."""
import re
import shlex

import asyncssh
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_USER
from .ssh import fetch_metrics_with_host_key

USERNAME = re.compile(r"^[a-z_][a-z0-9_-]{0,30}$")


class UbuntuLinuxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure an Ubuntu host via SSH."""

    VERSION = 1

    def __init__(self):
        self.details = {}
        self.private_key = ""
        self.public_key = ""

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            name = user_input["name"].strip()
            host = user_input["host"].strip()
            username = user_input["username"].strip()
            if (not name or not host or any(ch.isspace() for ch in host)
                    or not USERNAME.fullmatch(username)):
                errors["base"] = "invalid_input"
            else:
                await self.async_set_unique_id(f"{host.lower()}:{user_input['port']}")
                self._abort_if_unique_id_configured()
                self.details = {
                    "name": name, "host": host,
                    "port": user_input["port"], "username": username,
                }
                key = asyncssh.generate_private_key("ssh-ed25519")
                self.private_key = key.export_private_key().decode("utf-8")
                self.public_key = key.export_public_key().decode("utf-8").strip()
                return await self.async_step_install()
        schema = vol.Schema({
            vol.Required("name"): str,
            vol.Required("host"): str,
            vol.Required("port", default=DEFAULT_PORT): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required("username", default=DEFAULT_USER): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_install(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            try:
                _, fingerprint = await fetch_metrics_with_host_key(
                    self.details["host"], self.details["port"],
                    self.details["username"], self.private_key,
                )
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=self.details["name"],
                    data={**self.details, "private_key": self.private_key,
                          "fingerprint": fingerprint},
                )
        command = (
            "curl -fsSL https://raw.githubusercontent.com/ricobach/HA-UbuntuLinux/main/scripts/install.sh"
            " | sudo bash -s -- " + shlex.quote(self.public_key) + " " +
            shlex.quote(self.details["username"])
        )
        return self.async_show_form(
            step_id="install",
            data_schema=vol.Schema({
                vol.Optional("install_command", default=command): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True, read_only=True)
                ),
            }),
            errors=errors,
            description_placeholders={},
        )
