import logging
from homeassistant.components.number import RestoreNumber
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Smart Boiler Threshold number."""
    async_add_entities([SmartBoilerThreshold(hass)])

class SmartBoilerThreshold(RestoreNumber):
    """Representation of the learning threshold."""

    def __init__(self, hass):
        self._hass = hass
        self._attr_name = "Smart Boiler Threshold"
        self._attr_unique_id = "smart_boiler_learning_threshold"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_mode = "box"
        self._attr_icon = "mdi:brain"
        self._attr_native_value = 50 # ברירת מחדל להתחלה

    async def async_added_to_hass(self) -> None:
        """Run when entity is about to be added to hass."""
        await super().async_added_to_hass()
        # שחזור הזיכרון מהפעלה קודמת
        last_state = await self.async_get_last_number_data()
        if last_state is not None and last_state.native_value is not None:
            self._attr_native_value = last_state.native_value

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()