"""Config flow for Pill Manager."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


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
