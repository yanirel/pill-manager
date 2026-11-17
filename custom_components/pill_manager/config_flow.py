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
    "notify_entity": "",
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

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**DEFAULT_OPTIONS, **self.config_entry.options}

        # Home Assistant exposes notify targets as services in the notify domain.
        # Use the live service registry so users can select a Companion App target
        # without typing a service name or creating a separate automation.
        notify_services = self.hass.services.async_services().get("notify", {})
        service_options = [""] + [
            f"notify.{service_name}" for service_name in sorted(notify_services)
            if service_name.startswith("mobile_app_")
        ]
        selected_service = current.get("notify_service", "")
        if selected_service and selected_service not in service_options:
            service_options.append(selected_service)

        entity_options = [""] + sorted(self.hass.states.async_entity_ids("notify"))
        selected_entity = current.get("notify_entity", "")
        if selected_entity and selected_entity not in entity_options:
            entity_options.append(selected_entity)

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
            vol.Required("notify_entity",
                         default=selected_entity): vol.In(entity_options),
            vol.Required("notify_service",
                         default=selected_service): vol.In(service_options),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
