"""Persistent local storage and medication calculations."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from uuid import uuid4

from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import STORAGE_KEY, STORAGE_VERSION


def _new_id() -> str:
    return uuid4().hex


class PillStore:
    """Store medication data in Home Assistant .storage."""

    def __init__(self, hass):
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data = {"medications": [], "intake": [], "reminder_marks": []}

    async def async_load(self):
        loaded = await self._store.async_load()
        if isinstance(loaded, dict):
            self.data.update(loaded)
        self.data.setdefault("medications", [])
        self.data.setdefault("intake", [])
        self.data.setdefault("reminder_marks", [])

    async def async_save(self):
        await self._store.async_save(self.data)

    def snapshot(self):
        return deepcopy(self.data)

    def save_medication(self, payload):
        med = dict(payload)
        med["id"] = med.get("id") or _new_id()
        med["name"] = str(med.get("name", "")).strip()
        med.setdefault("strengths", [])
        med.setdefault("schedules", [])
        existing = next((i for i, x in enumerate(self.data["medications"]) if x["id"] == med["id"]), None)
        if existing is None:
            self.data["medications"].append(med)
        else:
            self.data["medications"][existing] = med
        return med

    def delete_medication(self, med_id):
        self.data["medications"] = [m for m in self.data["medications"] if m["id"] != med_id]

    def _medication(self, med_id):
        return next((m for m in self.data["medications"] if m["id"] == med_id), None)

    def confirm_intake(self, med_id, doses, taken_at=None, note=""):
        med = self._medication(med_id)
        if med is None:
            raise ValueError("Medication not found")
        taken_at = taken_at or dt_util.now().isoformat()
        normalized = []
        for strength, amount in doses.items():
            amount = int(amount)
            if amount <= 0:
                continue
            stock = next((s for s in med["strengths"] if str(s["strength"]) == str(strength)), None)
            if stock is None or int(stock.get("quantity", 0)) < amount:
                raise ValueError(f"Insufficient stock for strength {strength}")
            normalized.append({"strength": str(strength), "quantity": amount})
        if not normalized:
            raise ValueError("No dose selected")
        for dose in normalized:
            stock = next(s for s in med["strengths"] if str(s["strength"]) == dose["strength"])
            stock["quantity"] = int(stock.get("quantity", 0)) - dose["quantity"]
        record = {"id": _new_id(), "medication_id": med_id, "taken_at": taken_at,
                  "doses": normalized, "note": str(note)}
        self.data["intake"].append(record)
        return record

    def update_intake(self, record_id, doses, taken_at=None, note=None):
        record = next((r for r in self.data["intake"] if r["id"] == record_id), None)
        if record is None:
            raise ValueError("Intake record not found")
        med = self._medication(record["medication_id"])
        if med is None:
            raise ValueError("Medication not found")
        old = {d["strength"]: int(d["quantity"]) for d in record["doses"]}
        new = {str(k): int(v) for k, v in doses.items() if int(v) > 0}
        # Calculate all resulting stock levels first; never partially apply a correction.
        changes = {}
        for strength in set(old) | set(new):
            stock = next((s for s in med["strengths"] if str(s["strength"]) == strength), None)
            if stock is None:
                raise ValueError(f"Strength {strength} no longer exists in inventory")
            resulting = int(stock.get("quantity", 0)) + old.get(strength, 0) - new.get(strength, 0)
            if resulting < 0:
                raise ValueError(f"Insufficient stock for strength {strength}")
            changes[strength] = resulting
        for strength, quantity in changes.items():
            next(s for s in med["strengths"] if str(s["strength"]) == strength)["quantity"] = quantity
        record["doses"] = [{"strength": k, "quantity": v} for k, v in new.items()]
        if taken_at:
            record["taken_at"] = taken_at
        if note is not None:
            record["note"] = str(note)
        return record

    def forecast(self, medication):
        """Return days until each strength is depleted, based on active schedules."""
        today = dt_util.now().date()
        result = []
        for stock in medication.get("strengths", []):
            strength = str(stock["strength"])
            daily = 0.0
            for schedule in medication.get("schedules", []):
                if strength not in schedule.get("doses", {}):
                    continue
                weekdays = schedule.get("weekdays", list(range(7)))
                start = date.fromisoformat(schedule.get("start_date", today.isoformat()))
                end = date.fromisoformat(schedule["end_date"]) if schedule.get("end_date") else None
                if start <= today and (end is None or today <= end):
                    daily += int(schedule["doses"][strength]) * len(weekdays) / 7
            qty = int(stock.get("quantity", 0))
            result.append({"strength": strength, "quantity": qty,
                           "days_remaining": None if daily <= 0 else round(qty / daily, 1)})
        return result
