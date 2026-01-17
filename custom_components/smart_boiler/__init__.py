"""The Smart Boiler AI integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant, Event
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.util import dt as dt_util
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "smart_boiler"

# --- הגדרות בדיקה ---
# True = מצב בטוח: רק כותב לוגים, לא משנה כלום במערכת
# False = מצב חי: המערכת עובדת מלא
DRY_RUN = True 

# --- ישויות ---
BOILER_SWITCH_ENTITY = "switch.shelly_shsw_1_8caab54b957d"
TEMP_RATE_ENTITY = "sensor.water_temp_change_rate"
PEOPLE_COUNTER_ENTITY = "input_number.number_of_shower_people"
THRESHOLD_ENTITY = "number.smart_boiler_threshold"

last_shower_time = None

def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Smart Boiler AI component."""
    if DRY_RUN:
        _LOGGER.warning("⚠️ Smart Boiler AI started in DRY RUN mode! No actions will be taken.")
    else:
        _LOGGER.info("Smart Boiler AI started in ACTIVE mode.")

    hass.helpers.discovery.load_platform(hass, "sensor", DOMAIN, {}, config)
    hass.helpers.discovery.load_platform(hass, "number", DOMAIN, {}, config)

    # --- 1. לוגיקת תיקון עצמי ---
    async def handle_boiler_state_change(event: Event):
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if entity_id != BOILER_SWITCH_ENTITY or new_state is None or old_state is None:
            return

        # זיהוי הדלקה ידנית
        if new_state.state == STATE_ON and old_state.state == STATE_OFF:
            user_id = new_state.context.user_id
            if user_id: 
                _LOGGER.info("🔍 Detection: Manual boost detected.")
                await adjust_threshold(hass, decrease=True)

    # --- 2. לוגיקת זיהוי מקלחות ---
    async def handle_temp_rate_change(event: Event):
        global last_shower_time
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")

        if entity_id != TEMP_RATE_ENTITY or new_state is None or new_state.state in ["unknown", "unavailable"]:
            return

        try:
            rate = float(new_state.state)
        except ValueError:
            return

        now = dt_util.now()
        if last_shower_time and (now - last_shower_time) < timedelta(minutes=15):
            return

        boiler_state = hass.states.get(BOILER_SWITCH_ENTITY)
        is_heating = boiler_state and boiler_state.state == STATE_ON
        
        people_state = hass.states.get(PEOPLE_COUNTER_ENTITY)
        people_count = int(float(people_state.state)) if people_state else 0

        if people_count <= 0:
            return

        shower_detected = False
        detection_method = ""

        if rate < -1.5:
            shower_detected = True
            detection_method = "Strong Drop"
        elif rate < -0.3 and is_heating:
            shower_detected = True
            detection_method = "Heating Drop"

        if shower_detected:
            msg = f"🚿 Shower detected via {detection_method}!"
            
            if DRY_RUN:
                _LOGGER.info(f"[DRY RUN] Would have decremented counter. {msg}")
            else:
                _LOGGER.info(f"{msg} Decrementing counter.")
                last_shower_time = now
                await hass.services.async_call(
                    "input_number", "decrement",
                    {"entity_id": PEOPLE_COUNTER_ENTITY}
                )

    hass.bus.listen("state_changed", handle_boiler_state_change)
    hass.bus.listen("state_changed", handle_temp_rate_change)
    return True

async def adjust_threshold(hass: HomeAssistant, decrease: bool):
    """Adjust the sensitivity threshold dynamically."""
    threshold_state = hass.states.get(THRESHOLD_ENTITY)
    if threshold_state is None:
        return

    current_value = float(threshold_state.state)
    
    if decrease:
        new_value = max(0, current_value - 5)
        log_msg = f"Learning: Decreasing threshold from {current_value} to {new_value}"
    else:
        new_value = min(100, current_value + 2)
        log_msg = f"Learning: Increasing threshold from {current_value} to {new_value}"

    if DRY_RUN:
        _LOGGER.info(f"[DRY RUN] Would have updated threshold: {log_msg}")
    else:
        _LOGGER.info(log_msg)
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": THRESHOLD_ENTITY, "value": new_value}
        )