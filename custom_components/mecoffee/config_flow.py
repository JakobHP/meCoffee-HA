"""Config flow for meCoffee PID integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, MECOFFEE_DEVICE_NAME_PREFIX, MECOFFEE_SERVICE_UUID

_LOGGER = logging.getLogger(__name__)


class MeCoffeeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for meCoffee PID."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the Bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or "meCoffee",
        }

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery."""
        if self._discovery_info is None:
            return self.async_abort(reason="no_device")

        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name or "meCoffee",
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    "name": self._discovery_info.name or "meCoffee",
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or "meCoffee",
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step — pick from discovered meCoffee devices."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            info = self._discovered_devices.get(address)
            if info is None:
                return self.async_abort(reason="no_device")

            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=info.name or "meCoffee",
                data={
                    CONF_ADDRESS: address,
                    "name": info.name or "meCoffee",
                },
            )

        # Discover meCoffee devices
        self._discovered_devices = {}
        for info in async_discovered_service_info(self.hass):
            if (
                info.name
                and info.name.startswith(MECOFFEE_DEVICE_NAME_PREFIX)
            ):
                self._discovered_devices[info.address] = info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: f"{info.name} ({address})"
                            for address, info in self._discovered_devices.items()
                        }
                    ),
                }
            ),
        )
