"""Public Home Assistant services for medication inventory and intake."""
from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_V2_UPDATED
from .engine import allocate_dose, consume_allocation, PillManagerError


def _parse_iso_datetime(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as err:
        raise HomeAssistantError("Datetime values must be ISO 8601") from err
    if parsed.tzinfo is None:
        raise HomeAssistantError("Datetime values must include a timezone")
    return parsed.isoformat()


def _parse_received_at(value: str) -> str:
    # Inventory batches may be recorded with a date only or a full zoned timestamp.
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        return _parse_iso_datetime(value)


async def async_setup_services(hass: HomeAssistant):
    """Register services against the isolated v2 store."""
    def get_store():
        entries = hass.data.get(f"{DOMAIN}_v2", {})
        if not entries:
            raise HomeAssistantError("Pill Manager v2 storage is not loaded")
        return next(iter(entries.values()))

    async def take_dose(call: ServiceCall):
        store = get_store()
        from copy import deepcopy
        working = deepcopy(store.data)
        occurrence_id = call.data.get("occurrence_id")
        existing_intake = next((x for x in working["intake"] if x.get("id") == call.data["intake_id"]), None)
        if existing_intake and existing_intake.get("status") != "undone":
            return
        intake_id = uuid4().hex if existing_intake else call.data["intake_id"]
        if occurrence_id:
            if any(x.get("occurrence_id") == occurrence_id and x.get("status") == "taken"
                   for x in working["intake"]):
                return
            if any(x.get("occurrence_id") == occurrence_id and x.get("status") in ("skipped", "missed")
                   for x in working["occurrences"]):
                raise HomeAssistantError("This dose was already skipped or marked missed")
        medication = next((m for m in working["medications"]
                           if m["id"] == call.data["medication_id"]), None)
        if medication is None:
            raise HomeAssistantError("Medication not found")
        try:
            taken_at = _parse_iso_datetime(call.data["taken_at"])
            taken_on = date.fromisoformat(taken_at[:10])
            dose = float(call.data["actual_dose_mg"])
            allocation = allocate_dose(medication["products"], dose, taken_on)
            # Validate and consume on a working copy so a failed operation cannot
            # leave a partially changed in-memory inventory.
            updated_products = deepcopy(medication["products"])
            consume_allocation(updated_products, allocation)
            medication["products"] = updated_products
            working["intake"].append({
                "id": intake_id,
                "medication_id": medication["id"],
                "occurrence_id": occurrence_id,
                "actual_dose_mg": dose,
                "scheduled_dose_mg": call.data.get("scheduled_dose_mg"),
                "taken_at": taken_at,
                "allocation": allocation,
                "status": "taken",
                "source": call.data.get("source", "manual"),
            })
            if occurrence_id:
                occurrence = next((item for item in working["occurrences"]
                                   if item.get("occurrence_id") == occurrence_id), None)
                if occurrence:
                    occurrence["status"] = "taken"
                    occurrence["updated_at"] = taken_at
            previous_data = store.data
            store.data = working
            try:
                await store.async_save()
            except Exception:
                store.data = previous_data
                raise
            hass.bus.async_fire(EVENT_V2_UPDATED)
        except (KeyError, TypeError, ValueError, PillManagerError) as err:
            raise HomeAssistantError(str(err)) from err

    async def skip_dose(call: ServiceCall):
        store = get_store()
        occurrence_id = call.data["occurrence_id"]
        if any(x.get("occurrence_id") == occurrence_id and x.get("status") == "taken"
               for x in store.data["intake"]):
            raise HomeAssistantError("A confirmed intake cannot be marked skipped")
        existing = next((x for x in store.data["occurrences"]
                         if x.get("occurrence_id") == occurrence_id), None)
        if existing:
            existing["status"] = "skipped"
            existing["updated_at"] = _parse_iso_datetime(call.data["updated_at"])
        else:
            store.data["occurrences"].append({
                "occurrence_id": occurrence_id,
                "medication_id": call.data["medication_id"],
                "status": "skipped",
                "updated_at": _parse_iso_datetime(call.data["updated_at"]),
            })
        await store.async_save()
        hass.bus.async_fire(EVENT_V2_UPDATED)

    async def undo_dose(call: ServiceCall):
        store = get_store()
        from copy import deepcopy
        working = deepcopy(store.data)
        record = next((x for x in working["intake"] if x["id"] == call.data["intake_id"]), None)
        if record is None:
            raise HomeAssistantError("Intake record not found")
        if record.get("status") == "undone":
            return
        if record.get("source") == "legacy_import" or not record.get("allocation"):
            raise HomeAssistantError("Imported historical records cannot be undone because their original batch allocation is unknown")
        medication = next((m for m in working["medications"]
                           if m["id"] == record["medication_id"]), None)
        if medication is None:
            raise HomeAssistantError("Medication not found")
        consume_allocation(medication["products"], record["allocation"], sign=1)
        record["status"] = "undone"
        occurrence_id = record.get("occurrence_id")
        if occurrence_id:
            occurrence = next((item for item in working["occurrences"]
                               if item.get("occurrence_id") == occurrence_id), None)
            if occurrence:
                occurrence["status"] = "pending"
                occurrence["updated_at"] = dt_util.now().isoformat()
        previous_data = store.data
        store.data = working
        try:
            await store.async_save()
        except Exception:
            store.data = previous_data
            raise
        hass.bus.async_fire(EVENT_V2_UPDATED)

    async def add_stock(call: ServiceCall):
        store = get_store()
        medication = next((m for m in store.data["medications"]
                           if m["id"] == call.data["medication_id"]), None)
        if medication is None:
            raise HomeAssistantError("Medication not found")
        product = next((p for p in medication["products"]
                        if p["id"] == call.data["product_id"]), None)
        if product is None:
            raise HomeAssistantError("Product not found")
        if any(b.get("id") == call.data["batch_id"] for b in product.get("stock_batches", [])):
            raise HomeAssistantError("Stock batch ID already exists for this product")
        quantity = float(call.data["quantity"])
        if quantity <= 0:
            raise HomeAssistantError("Stock quantity must be positive")
        if product.get("splittable", False):
            if abs(quantity * 2 - round(quantity * 2)) > 1e-7:
                raise HomeAssistantError("Splittable stock must use 0.5 tablet increments")
        elif not quantity.is_integer():
            raise HomeAssistantError("Non-splittable stock must be a whole number")
        if call.data.get("expires_on"):
            try:
                date.fromisoformat(call.data["expires_on"])
            except ValueError as err:
                raise HomeAssistantError("Expiry date must use YYYY-MM-DD") from err
        product.setdefault("stock_batches", []).append({
            "id": call.data["batch_id"],
            "quantity": quantity,
            "expires_on": call.data.get("expires_on"),
            "received_at": _parse_received_at(call.data["received_at"]),
        })
        await store.async_save()
        hass.bus.async_fire(EVENT_V2_UPDATED)

    async def adjust_stock(call: ServiceCall):
        store = get_store()
        medication = next((m for m in store.data["medications"]
                           if m["id"] == call.data["medication_id"]), None)
        if medication is None:
            raise HomeAssistantError("Medication not found")
        product = next((p for p in medication["products"]
                        if p["id"] == call.data["product_id"]), None)
        if product is None:
            raise HomeAssistantError("Product not found")
        batch = next((b for b in product.get("stock_batches", [])
                      if b["id"] == call.data["batch_id"]), None)
        if batch is None:
            raise HomeAssistantError("Stock batch not found")
        new_quantity = float(call.data["quantity"])
        if product.get("splittable", False):
            if abs(new_quantity * 2 - round(new_quantity * 2)) > 1e-7:
                raise HomeAssistantError("Splittable stock must use 0.5 tablet increments")
        elif not new_quantity.is_integer():
            raise HomeAssistantError("Non-splittable stock must be a whole number")
        if any(event.get("id") == call.data["event_id"]
               for event in store.data.get("stock_events", [])):
            raise HomeAssistantError("Stock event ID has already been used")
        before = float(batch.get("quantity", 0))
        batch["quantity"] = new_quantity
        store.data.setdefault("stock_events", []).append({
            "id": call.data["event_id"],
            "medication_id": medication["id"],
            "product_id": product["id"],
            "batch_id": batch["id"],
            "before": before,
            "after": new_quantity,
            "reason": call.data["reason"],
            "created_at": _parse_iso_datetime(call.data["created_at"]),
        })
        await store.async_save()
        hass.bus.async_fire(EVENT_V2_UPDATED)

    schemas = {
        "take_dose": vol.Schema({
            vol.Required("medication_id"): str, vol.Required("intake_id"): str,
            vol.Optional("occurrence_id"): str, vol.Required("actual_dose_mg"): vol.Coerce(float),
            vol.Optional("scheduled_dose_mg"): vol.Coerce(float), vol.Required("taken_at"): str,
            vol.Optional("source", default="manual"): str,
        }),
        "skip_dose": vol.Schema({
            vol.Required("medication_id"): str, vol.Required("occurrence_id"): str,
            vol.Required("updated_at"): str,
        }),
        "undo_dose": vol.Schema({vol.Required("intake_id"): str}),
        "add_stock": vol.Schema({
            vol.Required("medication_id"): str, vol.Required("product_id"): str,
            vol.Required("batch_id"): str, vol.Required("quantity"): vol.Coerce(float),
            vol.Optional("expires_on"): str, vol.Required("received_at"): str,
        }),
        "adjust_stock": vol.Schema({
            vol.Required("medication_id"): str, vol.Required("product_id"): str,
            vol.Required("batch_id"): str, vol.Required("quantity"): vol.Coerce(float),
            vol.Required("reason"): str, vol.Required("event_id"): str,
            vol.Required("created_at"): str,
        }),
    }
    handlers = {
        "take_dose": take_dose,
        "skip_dose": skip_dose,
        "undo_dose": undo_dose,
        "add_stock": add_stock,
        "adjust_stock": adjust_stock,
    }
    for name, handler in handlers.items():
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)
        hass.services.async_register(DOMAIN, name, handler, schema=schemas[name])
