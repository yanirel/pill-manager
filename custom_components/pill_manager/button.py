"""Buttons for explicit medication intake confirmation."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .engine import active_phase


class PillManagerTakenButton(ButtonEntity):
    """Confirm the current planned dose for one medication."""

    _attr_has_entity_name = True
    _attr_name = "אישור נטילה"

    def __init__(self, hass, store, medication_id: str):
        self.hass = hass
        self.store = store
        self.medication_id = medication_id
        self._attr_unique_id = f"{medication_id}_taken"

    async def async_press(self) -> None:
        medication = next((m for m in self.store.data["medications"]
                           if m["id"] == self.medication_id), None)
        if medication is None:
            return
        now = dt_util.now()
        phase = active_phase(medication.get("regimen", {}), now.date())
        if not phase:
            return
        date_key = now.date().isoformat()
        clock = now.strftime("%H:%M")
        due_times = [value for value in phase.get("times", []) if value <= clock]
        due_time = sorted(due_times)[-1] if due_times else None
        occurrence_id = (
            f"{self.medication_id}:{date_key}:{due_time}" if due_time
            else f"button:{self.medication_id}:{now.strftime('%Y%m%d%H%M')}"
        )
        await self.hass.services.async_call(DOMAIN, "take_dose", {
            "medication_id": self.medication_id,
            "intake_id": occurrence_id,
            "occurrence_id": occurrence_id,
            "actual_dose_mg": float(phase["dose_mg"]),
            "scheduled_dose_mg": float(phase["dose_mg"]),
            "taken_at": now.isoformat(),
            "source": "button",
        })


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Create one intake confirmation button per medication."""
    store = hass.data[f"{DOMAIN}_v2"][entry.entry_id]
    added = set()

    def add_missing():
        entities = []
        for medication in store.data["medications"]:
            med_id = medication["id"]
            if med_id in added:
                continue
            entities.append(PillManagerTakenButton(hass, store, med_id))
            added.add(med_id)
        if entities:
            async_add_entities(entities)

    add_missing()

    from homeassistant.core import callback

    @callback
    def handle_update(_event):
        add_missing()

    unsub = hass.bus.async_listen(f"{DOMAIN}_v2_updated", handle_update)
    hass.data.setdefault(f"{DOMAIN}_unsubscribers", {}).setdefault(entry.entry_id, []).append(unsub)
