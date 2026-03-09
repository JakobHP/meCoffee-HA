from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .parser import parse_packet


class MeCoffeeCoordinator(DataUpdateCoordinator):

    def __init__(self, hass, ble):

        super().__init__(
            hass,
            logger=None,
            name="mecoffee"
        )

        self.ble = ble
        self.data = {}

    def handle_packet(self, packet):

        parsed = parse_packet(packet)

        if parsed:
            self.data.update(parsed)
            self.async_set_updated_data(self.data)
