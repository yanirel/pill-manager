"""WebSocket commands for the Pill Manager panel."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN, WS_GET_DATA, WS_SAVE_MEDICATION, WS_DELETE_MEDICATION,
    WS_CONFIRM_INTAKE, WS_UPDATE_INTAKE, WS_SAVE_SCHEDULE,
)


def _store(hass: HomeAssistant):
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise ValueError("Pill Manager is not loaded")
    return next(iter(entries.values()))


@callback
def async_setup_websocket(hass: HomeAssistant):
    """Register commands once."""

    @websocket_api.websocket_command({vol.Required("type"): WS_GET_DATA})
    @websocket_api.async_response
    async def get_data(hass, connection, msg):
        store = _store(hass)
        data = store.snapshot()
        for med in data["medications"]:
            med["forecast"] = store.forecast(med)
        connection.send_result(msg["id"], data)

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SAVE_MEDICATION,
        vol.Required("medication"): dict,
    })
    @websocket_api.async_response
    async def save_medication(hass, connection, msg):
        store = _store(hass)
        med = store.save_medication(msg["medication"])
        await store.async_save()
        connection.send_result(msg["id"], med)

    @websocket_api.websocket_command({
        vol.Required("type"): WS_DELETE_MEDICATION,
        vol.Required("medication_id"): str,
    })
    @websocket_api.async_response
    async def delete_medication(hass, connection, msg):
        store = _store(hass)
        store.delete_medication(msg["medication_id"])
        await store.async_save()
        connection.send_result(msg["id"], {})

    @websocket_api.websocket_command({
        vol.Required("type"): WS_CONFIRM_INTAKE,
        vol.Required("medication_id"): str,
        vol.Required("doses"): dict,
        vol.Optional("taken_at"): str,
        vol.Optional("note", default=""): str,
    })
    @websocket_api.async_response
    async def confirm_intake(hass, connection, msg):
        store = _store(hass)
        record = store.confirm_intake(msg["medication_id"], msg["doses"], msg.get("taken_at"), msg["note"])
        await store.async_save()
        connection.send_result(msg["id"], record)

    @websocket_api.websocket_command({
        vol.Required("type"): WS_UPDATE_INTAKE,
        vol.Required("record_id"): str,
        vol.Required("doses"): dict,
        vol.Optional("taken_at"): str,
        vol.Optional("note"): str,
    })
    @websocket_api.async_response
    async def update_intake(hass, connection, msg):
        store = _store(hass)
        record = store.update_intake(msg["record_id"], msg["doses"], msg.get("taken_at"), msg.get("note"))
        await store.async_save()
        connection.send_result(msg["id"], record)

    @websocket_api.websocket_command({
        vol.Required("type"): WS_SAVE_SCHEDULE,
        vol.Required("medication_id"): str,
        vol.Required("schedule"): dict,
    })
    @websocket_api.async_response
    async def save_schedule(hass, connection, msg):
        store = _store(hass)
        med = store._medication(msg["medication_id"])
        if med is None:
            raise ValueError("Medication not found")
        schedule = dict(msg["schedule"])
        schedule["id"] = schedule.get("id") or __import__("uuid").uuid4().hex
        schedules = med.setdefault("schedules", [])
        old = next((i for i, item in enumerate(schedules) if item["id"] == schedule["id"]), None)
        if old is None:
            schedules.append(schedule)
        else:
            schedules[old] = schedule
        await store.async_save()
        connection.send_result(msg["id"], schedule)

    for handler in (get_data, save_medication, delete_medication, confirm_intake, update_intake, save_schedule):
        websocket_api.async_register_command(hass, handler)
