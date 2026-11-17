"""Pill Manager integration."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .storage import PillStore
from .websocket import async_setup_websocket

PLATFORMS: list[str] = []


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration domain."""
    async_setup_websocket(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a configured instance."""
    store = PillStore(hass)
    await store.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = store

    frontend_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths([
        StaticPathConfig("/pill_manager_static", str(frontend_dir), False)
    ])
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="pill-manager-panel",
        frontend_url_path="pill-manager",
        module_url="/pill_manager_static/pill-manager.js",
        sidebar_title="תרופות",
        sidebar_icon="mdi:pill",
        require_admin=False,
        config={},
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an instance."""
    from homeassistant.components import frontend

    frontend.async_remove_panel(hass, "pill-manager")
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
