from homeassistant.components.binary_sensor import BinarySensorEntity


class HeaterBinarySensor(BinarySensorEntity):

    @property
    def is_on(self):

        return self.coordinator.data.get("heater")
