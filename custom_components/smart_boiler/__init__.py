"""The Smart Boiler AI integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant, Event
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.util import dt as dt_util
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import discovery

_LOGGER = logging.getLogger(__name__)

DOMAIN = "smart_boiler"
DRY_RUN = True 

# ודא שזה השם הנכון של הדוד שלך!
BOILER_SWITCH_ENTITY = "switch.shelly_shsw_1_8caab54b957d"
TEMP_RATE_ENTITY = "sensor.water_temp_change_rate"
PEOPLE_COUNTER_ENTITY = "input_number.number_of_shower_people"
THRESHOLD_ENTITY = "number.smart_boiler_threshold"

last_shower_time = None

def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Smart Boiler AI component."""
    _LOGGER.warning("⚠️ Smart Boiler AI: DEBUG MODE STARTED (Dry Run: %s)", DRY_RUN)

    discovery.load_platform(hass, "sensor", DOMAIN, {}, config)
    discovery.load_platform(hass, "number", DOMAIN, {}, config)

    # --- מאזין לשינויים בדוד (לוגיקה מורחבת לדיבוג) ---
    async def handle_boiler_state_change(event: Event):
        entity_id = event.data.get("entity_id")
        
        # אנחנו מסננים רק את הדוד
        if entity_id != BOILER_SWITCH_ENTITY:
            return

        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        
        if new_state is None or old_state is None:
            return

        # --- הדפסת דיבוג: מה המערכת רואה? ---
        user_id = new_state.context.user_id
        parent_id = new_state.context.parent_id
        
        _LOGGER.warning(
            "🕵️ DEBUG: Boiler changed! %s -> %s | User ID: %s | Context ID: %s",
            old_state.state,
            new_state.state,
            user_id,
            new_state.context.id
        )

        # הלוגיקה המקורית (זיהוי הדלקה ידנית)
        if new_state.state == STATE_ON and old_state.state == STATE_OFF:
            if user_id: 
                _LOGGER.warning("✅ MATCH: Manual boost detected! Triggering learning.")
                await adjust_threshold(hass, decrease=True)
            else:
                _LOGGER.warning("❌ IGNORED: Switch turned on, but no User ID found (Automatic?).")

    # --- מאזין למקלחות ---
    async def handle_temp_rate_change(event: Event):
        # (אותו קוד כמו מקודם, השארתי נקי)
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
        method = ""

        if rate < -1.5:
            shower_detected = True
            method = "Strong Drop"
        elif rate < -0.3 and is_heating:
            shower_detected = True
            method = "Heating Drop"

        if shower_detected:
            msg = f"🚿 Shower detected ({method})!"
            if DRY_RUN:
                _LOGGER.warning("[DRY RUN] %s (Would decrement counter)", msg)
            else:
                _LOGGER.warning("%s Decrementing counter.", msg)
                last_shower_time = now
                await hass.services.async_call(
                    "input_number", "decrement", {"entity_id": PEOPLE_COUNTER_ENTITY}
                )

    hass.bus.listen("state_changed", handle_boiler_state_change)
    hass.bus.listen("state_changed", handle_temp_rate_change)
    return True

async def adjust_threshold(hass: HomeAssistant, decrease: bool):
    """Adjust the sensitivity threshold dynamically."""
    threshold_state = hass.states.get(THRESHOLD_ENTITY)
    if threshold_state is None:
        _LOGGER.error("Cannot find threshold entity %s", THRESHOLD_ENTITY)
        return

    current = float(threshold_state.state)
    if decrease:
        new_val = max(0, current - 5)
        log = f"📉 LEARNING: Decreasing threshold {current} -> {new_val}"
    else:
        new_val = min(100, current + 2)
        log = f"📈 LEARNING: Increasing threshold {current} -> {new_val}"

    if DRY_RUN:
        _LOGGER.warning("[DRY RUN] %s", log)
    else:
        _LOGGER.warning(log)
        await hass.services.async_call(
            "number", "set_value", {"entity_id": THRESHOLD_ENTITY, "value": new_val}
        )