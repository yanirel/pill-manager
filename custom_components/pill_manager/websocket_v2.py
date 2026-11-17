"""WebSocket API for the isolated v2 medication model."""
from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, EVENT_V2_UPDATED
from .models import validate_medication, empty_database
from .engine import forecast, active_phase, PillManagerError


def _store(hass: HomeAssistant):
    entries = hass.data.get(f"{DOMAIN}_v2", {})
    if not entries:
        raise ValueError("Pill Manager v2 is not loaded")
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
        validate_medication(medication)
        existing = next((i for i, item in enumerate(store.data["medications"])
                         if item["id"] == medication["id"]), None)
        if existing is None:
            store.data["medications"].append(medication)
        else:
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
            raise ValueError("Cannot delete a medication with intake history")
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
            raise ValueError("Medication not found")
        product = next((p for p in med.get("products", [])
                        if p["id"] == msg["product_id"]), None)
        if product is None:
            raise ValueError("Product not found")
        batch = deepcopy(msg["batch"])
        batch["id"] = batch.get("id") or uuid4().hex
        if any(b["id"] == batch["id"] for b in product.get("stock_batches", [])):
            raise ValueError("Batch ID already exists")
        if float(batch.get("quantity", 0)) <= 0:
            raise ValueError("Stock quantity must be positive")
        product.setdefault("stock_batches", []).append(batch)
        validate_medication(med)
        await store.async_save()
        hass.bus.async_fire(EVENT_V2_UPDATED)
        connection.send_result(msg["id"], batch)

    for handler in (get_data, save_medication, delete_medication, add_stock):
        websocket_api.async_register_command(hass, handler)
