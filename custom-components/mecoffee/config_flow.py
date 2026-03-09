from homeassistant import config_entries
from .const import DOMAIN


class MeCoffeeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    async def async_step_bluetooth(self, discovery_info):

        address = discovery_info.address

        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="meCoffee PID",
            data={"address": address},
        )
