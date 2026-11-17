"""Sensors exposing the v2 medication status."""
from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_V2_UPDATED
from .engine import active_phase, forecast, PillManagerError


class PillManagerSensor(SensorEntity):
    """A read-only status sensor for one medication."""

    _attr_has_entity_name = True

    def __init__(self, store, medication_id: str, kind: str, name: str):
        self.store = store
        self.medication_id = medication_id
        self.kind = kind
        self._attr_unique_id = f"{medication_id}_{kind}"
        self._attr_name = name

    @property
    def medication(self):
        return next((m for m in self.store.data["medications"]
                     if m["id"] == self.medication_id), None)

    @property
    def native_value(self):
        medication = self.medication
        if medication is None:
            return None
        if self.kind == "current_dose":
            phase = active_phase(medication.get("regimen", {}), dt_util.now().date())
            return phase.get("dose_mg") if phase else None
        try:
            result = forecast(medication.get("products", []),
                              medication.get("regimen", {}), dt_util.now().date())
        except (PillManagerError, KeyError, ValueError):
            return None
        if self.kind == "remaining_days":
            return result.get("days_remaining")
        if self.kind == "depletion_date":
            value = result.get("depletion_date")
            return date.fromisoformat(value) if value else None
        return None

    @property
    def extra_state_attributes(self):
        medication = self.medication
        if medication is None:
            return {}
        if self.kind == "depletion_date":
            try:
                return forecast(medication.get("products", []),
                                medication.get("regimen", {}), dt_util.now().date())
            except (PillManagerError, KeyError, ValueError) as err:
                return {"forecast_error": str(err)}
        return {"medication_id": self.medication_id, "medication": medication["name"]}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Create and dynamically add medication sensors."""
    store = hass.data[f"{DOMAIN}_v2"][entry.entry_id]
    added: set[str] = set()

    @callback
    def add_missing():
        entities = []
        for medication in store.data["medications"]:
            med_id = medication["id"]
            for kind, name, unit, device_class in (
                ("remaining_days", "ימים שנותרו במלאי", "d", None),
                ("depletion_date", "תאריך אזילת מלאי", None, SensorDeviceClass.DATE),
                ("current_dose", "מינון נוכחי", "mg", None),
            ):
                key = f"{med_id}_{kind}"
                if key in added:
                    continue
                entity = PillManagerSensor(store, med_id, kind, name)
                entity._attr_native_unit_of_measurement = unit
                entity._attr_device_class = device_class
                if kind in ("remaining_days", "current_dose"):
                    entity._attr_state_class = "measurement"
                entities.append(entity)
                added.add(key)
        if entities:
            async_add_entities(entities)

    add_missing()

    @callback
    def handle_update(_event):
        add_missing()
        for entity in getattr(hass, "data", {}).get(f"{DOMAIN}_sensor_entities_{entry.entry_id}", []):
            entity.async_write_ha_state()

    # Keep entity references so updates can refresh them after stock or regimen changes.
    # async_add_entities owns entity lifecycle; we register the listener in the entry data.
    hass.data.setdefault(f"{DOMAIN}_sensor_entities_{entry.entry_id}", [])
    original_add = async_add_entities

    def add_and_track(entities):
        entities = list(entities)
        hass.data[f"{DOMAIN}_sensor_entities_{entry.entry_id}"].extend(entities)
        original_add(entities)

    # Initial entities were already submitted above; subsequent ones are tracked.
    unsub = hass.bus.async_listen(EVENT_V2_UPDATED, handle_update)
    hass.data.setdefault(f"{DOMAIN}_unsubscribers", {})[entry.entry_id] = [unsub]
