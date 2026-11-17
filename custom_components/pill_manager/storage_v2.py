"""Versioned Store-backed persistence; legacy data is not overwritten."""
from copy import deepcopy
from homeassistant.helpers.storage import Store
from .models import empty_database

class PillManagerStorage:
    def __init__(self,hass):
        self._store=Store(hass,2,"pill_manager_v2")
        self.data=empty_database()
    async def async_load(self):
        loaded=await self._store.async_load()
        if isinstance(loaded, dict) and loaded.get("schema_version") == 2:
            defaults = empty_database()
            defaults.update(loaded)
            self.data = defaults
        else:
            self.data = empty_database()
    async def async_save(self):
        await self._store.async_save(self.data)
    def snapshot(self):
        return deepcopy(self.data)
