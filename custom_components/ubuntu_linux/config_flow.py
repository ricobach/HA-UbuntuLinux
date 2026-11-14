"""Configure an Ubuntu server with a generated installer command."""
import re
import shlex

import asyncssh
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.network import get_url
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_USER
from .ssh import fetch_metrics_with_host_key
from .install_page import create_install_page, remove_install_page, register_install_view

USERNAME = re.compile(r"^[a-z_][a-z0-9_-]{0,30}$")


class UbuntuLinuxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure an Ubuntu host via SSH."""

    VERSION = 1

    def __init__(self):
        self.details = {}
        self.private_key = ""
        self.public_key = ""
        self.install_url = None
        self.install_token = None

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
                if self.install_token:
                    remove_install_page(self.hass, self.install_token)
                return self.async_create_entry(
                    title=self.details["name"],
                    data={**self.details, "private_key": self.private_key,
                          "fingerprint": fingerprint},
                )
        if self.install_url is None:
            register_install_view(self.hass)
            self.install_url, self.install_token, self.install_command = (
                create_install_page(
                    self.hass, self.public_key, self.details["username"],
                    get_url(self.hass, prefer_external=False),
                )
            )
        command = self.install_command
        return self.async_show_form(
            step_id="install",
            data_schema=vol.Schema({
                vol.Optional("install_command", default=command): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True, read_only=True)
                ),
            }),
            errors=errors,
            description_placeholders={"copy_url": self.install_url},
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return UbuntuComposeOptionsFlow()


class UbuntuComposeOptionsFlow(config_entries.OptionsFlow):
    """Authorize one Docker Compose file through an administrator on Ubuntu."""

    def __init__(self):
        self.values = {}

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            project = user_input["compose_project"].strip()
            path = user_input["compose_file"].strip()
            if not project and not path:
                return self.async_create_entry(
                    title="", data={"compose_project": "", "compose_file": ""}
                )
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", project):
                errors["base"] = "invalid_project"
            elif not path.startswith("/") or "\\x00" in path or "\\n" in path:
                errors["base"] = "invalid_path"
            else:
                self.values = {"compose_project": project, "compose_file": path}
                return await self.async_step_register()
        schema = vol.Schema({
            vol.Optional(
                "compose_project",
                default=self.config_entry.options.get("compose_project", ""),
            ): str,
            vol.Optional(
                "compose_file",
                default=self.config_entry.options.get("compose_file", ""),
            ): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def async_step_register(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=self.values)
        command = (
            "sudo /usr/local/sbin/ha-ubuntu-compose register "
            + shlex.quote(self.values["compose_project"]) + " "
            + shlex.quote(self.values["compose_file"])
        )
        return self.async_show_form(
            step_id="register",
            data_schema=vol.Schema({
                vol.Optional("registration_command", default=command): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True, read_only=True)
                ),
            }),
        )
