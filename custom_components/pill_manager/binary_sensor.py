"""Binary sensor indicating an unconfirmed scheduled dose."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_V2_UPDATED
from .engine import active_phase


class PillManagerDueSensor(BinarySensorEntity):
    """Indicate whether a scheduled dose is currently awaiting confirmation."""

    _attr_has_entity_name = True

    def __init__(self, store, medication_id: str, name: str):
        self.store = store
        self.medication_id = medication_id
        self._attr_unique_id = f"{medication_id}_due"
        self._attr_name = "נדרשת נטילה"

    @property
    def medication(self):
        return next((m for m in self.store.data["medications"]
                     if m["id"] == self.medication_id), None)

    def _due_occurrence(self):
        medication = self.medication
        if medication is None:
            return None
        now = dt_util.now()
        phase = active_phase(medication.get("regimen", {}), now.date())
        if not phase:
            return None
        if now.weekday() not in phase.get("weekdays", list(range(7))):
            return None
        intake = self.store.data.get("intake", [])
        occurrences = self.store.data.get("occurrences", [])
        for time_text in sorted(phase.get("times", [])):
            try:
                scheduled = datetime.combine(now.date(), datetime.strptime(time_text, "%H:%M").time())
            except ValueError:
                continue
            if now.replace(tzinfo=None) < scheduled:
                continue
            occurrence_id = f"{self.medication_id}:{now.date().isoformat()}:{time_text}"
            taken = any(item.get("occurrence_id") == occurrence_id and item.get("status") == "taken"
                        for item in intake)
            handled = any(item.get("occurrence_id") == occurrence_id
                          and item.get("status") in ("skipped", "missed") for item in occurrences)
            if not taken and not handled:
                return {"occurrence_id": occurrence_id, "scheduled_time": time_text,
                        "dose_mg": phase.get("dose_mg")}
        return None

    @property
    def is_on(self):
        return self._due_occurrence() is not None

    @property
    def extra_state_attributes(self):
        return self._due_occurrence() or {}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Create due sensors and refresh them after data changes."""
    store = hass.data[f"{DOMAIN}_v2"][entry.entry_id]
    added: set[str] = set()
    entities = []

    @callback
    def add_missing():
        new_entities = []
        for medication in store.data["medications"]:
            key = medication["id"]
            if key in added:
                continue
            entity = PillManagerDueSensor(store, key, medication["name"])
            entities.append(entity)
            new_entities.append(entity)
            added.add(key)
        if new_entities:
            async_add_entities(new_entities)

    add_missing()

    @callback
    def handle_update(_event):
        add_missing()
        for entity in entities:
            entity.async_write_ha_state()

    unsub = hass.bus.async_listen(EVENT_V2_UPDATED, handle_update)
    hass.data.setdefault(f"{DOMAIN}_unsubscribers", {}).setdefault(entry.entry_id, []).append(unsub)
