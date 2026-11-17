"""WebSocket API for the isolated v2 medication model."""
from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, EVENT_V2_UPDATED
from .models import validate_medication, empty_database
from .engine import forecast, active_phase, PillManagerError


def _store(hass: HomeAssistant):
    entries = hass.data.get(f"{DOMAIN}_v2", {})
    if not entries:
        raise HomeAssistantError("Pill Manager v2 is not loaded")
    return next(iter(entries.values()))


def async_setup_v2_websocket(hass: HomeAssistant) -> None:
    """Register v2 commands without changing legacy WebSocket endpoints."""

    @websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}_v2/get_data"})
    @websocket_api.async_response
    async def get_data(hass, connection, msg):
        store = _store(hass)
        data = store.snapshot()
        from homeassistant.util import dt as dt_util
        current_date = dt_util.now().date()
        for medication in data["medications"]:
            try:
                medication["current_phase"] = active_phase(medication.get("regimen", {}), current_date)
                medication["forecast"] = forecast(
                    medication.get("products", []),
                    medication.get("regimen", {}),
                    current_date,
                )
            except (PillManagerError, KeyError, ValueError) as err:
                medication["current_phase"] = None
                medication["forecast"] = {"error": str(err)}
        connection.send_result(msg["id"], data)

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}_v2/save_medication",
        vol.Required("medication"): dict,
    })
    @websocket_api.async_response
    async def save_medication(hass, connection, msg):
        store = _store(hass)
        medication = deepcopy(msg["medication"])
        medication["id"] = medication.get("id") or uuid4().hex
        try:
            validate_medication(medication)
        except PillManagerError as err:
            raise HomeAssistantError(str(err)) from err
        existing = next((i for i, item in enumerate(store.data["medications"])
                         if item["id"] == medication["id"]), None)
        if existing is None:
            store.data["medications"].append(medication)
        else:
            # A still-active intake may need to be undone later. Do not allow
            # editing away a product or batch referenced by its allocation.
            protected = {}
            for intake in store.data.get("intake", []):
                if intake.get("medication_id") == medication["id"] and intake.get("status") == "taken":
                    for allocation in intake.get("allocation", []):
                        key = (allocation.get("product_id"), allocation.get("batch_id"))
                        old_product = next((p for p in store.data["medications"][existing].get("products", [])
                                            if p.get("id") == key[0]), None)
                        old_batch = next((b for b in old_product.get("stock_batches", [])
                                          if b.get("id") == key[1]), None) if old_product else None
                        if old_product and old_batch:
                            protected[key] = (float(old_product["strength_mg"]),
                                              bool(old_product.get("splittable", False)),
                                              float(old_batch.get("quantity", 0)))
            new_products = {p.get("id"): p for p in medication.get("products", [])}
            for (product_id, batch_id), (old_strength, old_split, old_quantity) in protected.items():
                new_product = new_products.get(product_id)
                new_batch = next((b for b in new_product.get("stock_batches", [])
                                  if b.get("id") == batch_id), None) if new_product else None
                if (new_product is None or new_batch is None
                        or float(new_product.get("strength_mg", 0)) != old_strength
                        or bool(new_product.get("splittable", False)) != old_split
                        or float(new_batch.get("quantity", 0)) != old_quantity):
                    raise HomeAssistantError(
                        "A product or stock batch used by a confirmed intake cannot be changed or removed. Use stock adjustment for quantity corrections."
                    )
            store.data["medications"][existing] = medication
        await store.async_save()
        hass.bus.async_fire(EVENT_V2_UPDATED)
        connection.send_result(msg["id"], medication)

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}_v2/delete_medication",
        vol.Required("medication_id"): str,
    })
    @websocket_api.async_response
    async def delete_medication(hass, connection, msg):
        store = _store(hass)
        med_id = msg["medication_id"]
        if any(item.get("medication_id") == med_id
               for item in store.data.get("intake", [])):
            raise HomeAssistantError("Cannot delete a medication with intake history")
        store.data["medications"] = [
            item for item in store.data["medications"] if item["id"] != med_id
        ]
        await store.async_save()
        hass.bus.async_fire(EVENT_V2_UPDATED)
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}_v2/add_stock",
        vol.Required("medication_id"): str,
        vol.Required("product_id"): str,
        vol.Required("batch"): dict,
    })
    @websocket_api.async_response
    async def add_stock(hass, connection, msg):
        store = _store(hass)
        med = next((m for m in store.data["medications"]
                    if m["id"] == msg["medication_id"]), None)
        if med is None:
            raise HomeAssistantError("Medication not found")
        product = next((p for p in med.get("products", [])
                        if p["id"] == msg["product_id"]), None)
        if product is None:
            raise HomeAssistantError("Product not found")
        batch = deepcopy(msg["batch"])
        batch["id"] = batch.get("id") or uuid4().hex
        if any(b["id"] == batch["id"] for b in product.get("stock_batches", [])):
            raise HomeAssistantError("Batch ID already exists")
        if float(batch.get("quantity", 0)) <= 0:
            raise HomeAssistantError("Stock quantity must be positive")
        from copy import deepcopy
        working = deepcopy(store.data)
        working_med = next(m for m in working["medications"] if m["id"] == msg["medication_id"])
        working_product = next(p for p in working_med["products"] if p["id"] == msg["product_id"])
        working_product.setdefault("stock_batches", []).append(batch)
        try:
            validate_medication(working_med)
        except PillManagerError as err:
            raise HomeAssistantError(str(err)) from err
        previous_data = store.data
        store.data = working
        try:
            await store.async_save()
        except Exception:
            store.data = previous_data
            raise
        hass.bus.async_fire(EVENT_V2_UPDATED)
        connection.send_result(msg["id"], batch)

    for handler in (get_data, save_medication, delete_medication, add_stock):
        websocket_api.async_register_command(hass, handler)
