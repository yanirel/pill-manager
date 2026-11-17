"""Pill Manager integration."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .storage import PillStore
from .storage_v2 import PillManagerStorage
from .services import async_setup_services
from .websocket import async_setup_websocket
from .websocket_v2 import async_setup_v2_websocket

PLATFORMS: list[str] = []


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration domain."""
    async_setup_websocket(hass)
    async_setup_v2_websocket(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a configured instance while preserving the legacy data store."""
    legacy_store = PillStore(hass)
    await legacy_store.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = legacy_store

    # Keep the new schema in its own storage key; never reinterpret or overwrite
    # the existing pill_manager storage used by the first-generation panel.
    v2_store = PillManagerStorage(hass)
    await v2_store.async_load()
    hass.data.setdefault(f"{DOMAIN}_v2", {})[entry.entry_id] = v2_store
    await async_setup_services(hass)

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
    v2_entries = hass.data.get(f"{DOMAIN}_v2", {})
    v2_entries.pop(entry.entry_id, None)
    if not v2_entries:
        for service in ("take_dose", "skip_dose", "undo_dose", "add_stock", "adjust_stock"):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
    return True
