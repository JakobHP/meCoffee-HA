from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class BoilerTemperatureSensor(CoordinatorEntity, SensorEntity):

    _attr_name = "Boiler Temperature"
    _attr_native_unit_of_measurement = "°C"

    @property
    def native_value(self):

        return self.coordinator.data.get("temperature")
