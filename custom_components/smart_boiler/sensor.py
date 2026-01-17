import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    add_entities([SmartBoilerScoreSensor(hass)])

class SmartBoilerScoreSensor(SensorEntity):
    """Representation of the Boiler Urgency Score."""

    def __init__(self, hass):
        self._hass = hass
        self._attr_name = "Boiler Urgency Score"
        self._attr_unique_id = "boiler_urgency_score_ai"
        self._attr_native_unit_of_measurement = "%"
        self._attr_icon = "mdi:chart-line-variant"
        self._state = 0

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Fetch new state data for the sensor."""
        # 1. קריאת נתונים מהמערכת
        # יש לוודא שהישויות האלו קיימות אצלך (מה-Package הקודם או מחיישנים אחרים)
        history_state = self._hass.states.get("sensor.showers_last_7_days_evening")
        people_state = self._hass.states.get("input_number.number_of_shower_people")
        weather_state = self._hass.states.get("weather.home")

        # ערכי ברירת מחדל למקרה שמשהו לא זמין
        history = float(history_state.state) if history_state and history_state.state.replace('.','',1).isdigit() else 0
        people = float(people_state.state) if people_state and people_state.state.replace('.','',1).isdigit() else 0
        outside_temp = 20
        if weather_state and "temperature" in weather_state.attributes:
            outside_temp = float(weather_state.attributes["temperature"])

        # 2. הלוגיקה - הנוסחה החכמה
        score_history = history * 5
        score_people = people * 15
        score_weather = (20 - outside_temp) * 2

        total = score_history + score_people + score_weather
        
        # עדכון הציון הסופי (גבולות 0-100)
        self._state = max(0, min(100, int(total)))