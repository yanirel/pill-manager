"""Config and options flows for Pill Manager."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


DEFAULT_OPTIONS = {
    "reminder_repeat_minutes": 30,
    "missed_after_minutes": 120,
    "missed_dose_action": "ask",
    "auto_deduct_stock": False,
    "notify_service": "",
}


class PillManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up Pill Manager."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Create the single local instance."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        if user_input is not None:
            return self.async_create_entry(title="Pill Manager", data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    def async_get_options_flow(config_entry):
        return PillManagerOptionsFlow(config_entry)


class PillManagerOptionsFlow(config_entries.OptionsFlow):
    """Configure reminder and inventory behavior."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**DEFAULT_OPTIONS, **self.config_entry.options}
        schema = vol.Schema({
            vol.Required("reminder_repeat_minutes",
                         default=current["reminder_repeat_minutes"]): vol.All(
                             vol.Coerce(int), vol.Range(min=5, max=1440)),
            vol.Required("missed_after_minutes",
                         default=current["missed_after_minutes"]): vol.All(
                             vol.Coerce(int), vol.Range(min=15, max=1440)),
            vol.Required("missed_dose_action",
                         default=current["missed_dose_action"]): vol.In(["ask", "mark_missed"]),
            vol.Required("auto_deduct_stock",
                         default=current["auto_deduct_stock"]): bool,
            vol.Optional("notify_service", default=current["notify_service"]): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
