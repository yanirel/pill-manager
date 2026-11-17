"""Sensors exposing the v2 medication status."""
from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_V2_UPDATED
from .engine import active_phase, forecast, PillManagerError


def _get_forecast(store, medication):
    """Cache the comparatively expensive forecast until data changes or the date rolls over."""
    today = dt_util.now().date()
    cache = getattr(store, "_pill_manager_forecast_cache", {})
    key = (medication["id"], today)
    if key not in cache:
        try:
            cache[key] = forecast(medication.get("products", []), medication.get("regimen", {}), today)
        except (PillManagerError, KeyError, ValueError) as err:
            cache[key] = {"error": str(err)}
        store._pill_manager_forecast_cache = cache
    return cache[key]


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
        result = _get_forecast(self.store, medication)
        if result.get("error"):
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
            return _get_forecast(self.store, medication)
        return {"medication_id": self.medication_id, "medication": medication["name"]}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Create and dynamically add medication sensors."""
    store = hass.data[f"{DOMAIN}_v2"][entry.entry_id]
    added: set[str] = set()
    all_entities = []

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
                    entity._attr_state_class = SensorStateClass.MEASUREMENT
                entities.append(entity)
                all_entities.append(entity)
                added.add(key)
        if entities:
            async_add_entities(entities)

    add_missing()

    @callback
    def handle_update(_event):
        store._pill_manager_forecast_cache = {}
        add_missing()
        for entity in all_entities:
            entity.async_write_ha_state()

    unsub = hass.bus.async_listen(EVENT_V2_UPDATED, handle_update)
    hass.data.setdefault(f"{DOMAIN}_unsubscribers", {})[entry.entry_id] = [unsub]
