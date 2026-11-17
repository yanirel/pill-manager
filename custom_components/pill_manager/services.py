"""Public Home Assistant services for medication inventory and intake."""
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .engine import allocate_dose, consume_allocation, PillManagerError

async def async_setup_services(hass: HomeAssistant):
    def get_store():
        entries=hass.data.get(DOMAIN,{})
        if not entries:
            raise HomeAssistantError("Pill Manager is not configured")
        return next(iter(entries.values()))
    async def take_dose(call: ServiceCall):
        store=get_store()
        occ=call.data.get("occurrence_id")
        if occ and any(x.get("occurrence_id")==occ and x.get("status")=="taken" for x in store.data["intake"]):
            return
        med=next((m for m in store.data["medications"] if m["id"]==call.data["medication_id"]),None)
        if med is None: raise HomeAssistantError("Medication not found")
        try:
            dose=float(call.data["actual_dose_mg"])
            allocation=allocate_dose(med["products"],dose)
            consume_allocation(med["products"],allocation)
            store.data["intake"].append({"id":call.data["intake_id"],"medication_id":med["id"],
                "occurrence_id":occ,"actual_dose_mg":dose,"scheduled_dose_mg":call.data.get("scheduled_dose_mg"),
                "taken_at":call.data["taken_at"],"allocation":allocation,"status":"taken",
                "source":call.data.get("source","manual")})
            await store.async_save()
        except (KeyError,ValueError,PillManagerError) as err:
            raise HomeAssistantError(str(err)) from err
    async def skip_dose(call: ServiceCall):
        store=get_store(); occ=call.data["occurrence_id"]
        if any(x.get("occurrence_id")==occ for x in store.data["occurrences"]): return
        store.data["occurrences"].append({"occurrence_id":occ,"medication_id":call.data["medication_id"],
            "status":"skipped","updated_at":call.data["updated_at"]})
        await store.async_save()
    async def undo_dose(call: ServiceCall):
        store=get_store()
        record=next((x for x in store.data["intake"] if x["id"]==call.data["intake_id"]),None)
        if record is None: raise HomeAssistantError("Intake record not found")
        if record.get("status")=="undone": return
        med=next((m for m in store.data["medications"] if m["id"]==record["medication_id"]),None)
        if med is None: raise HomeAssistantError("Medication not found")
        consume_allocation(med["products"],record["allocation"],sign=1)
        record["status"]="undone"
        await store.async_save()
    async def add_stock(call: ServiceCall):
        store=get_store()
        med=next((m for m in store.data["medications"] if m["id"]==call.data["medication_id"]),None)
        if med is None: raise HomeAssistantError("Medication not found")
        product=next((p for p in med["products"] if p["id"]==call.data["product_id"]),None)
        if product is None: raise HomeAssistantError("Product not found")
        product.setdefault("stock_batches",[]).append({"id":call.data["batch_id"],"quantity":call.data["quantity"],
            "expires_on":call.data.get("expires_on"),"received_at":call.data["received_at"]})
        await store.async_save()
    schemas={
      "take_dose":vol.Schema({vol.Required("medication_id"):str,vol.Required("intake_id"):str,
        vol.Optional("occurrence_id"):str,vol.Required("actual_dose_mg"):vol.Coerce(float),
        vol.Optional("scheduled_dose_mg"):vol.Coerce(float),vol.Required("taken_at"):str,
        vol.Optional("source",default="manual"):str}),
      "skip_dose":vol.Schema({vol.Required("medication_id"):str,vol.Required("occurrence_id"):str,vol.Required("updated_at"):str}),
      "undo_dose":vol.Schema({vol.Required("intake_id"):str}),
      "add_stock":vol.Schema({vol.Required("medication_id"):str,vol.Required("product_id"):str,
        vol.Required("batch_id"):str,vol.Required("quantity"):vol.Coerce(float),
        vol.Optional("expires_on"):str,vol.Required("received_at"):str})}
    for name,handler in (("take_dose",take_dose),("skip_dose",skip_dose),("undo_dose",undo_dose),("add_stock",add_stock)):
        hass.services.async_register(DOMAIN,name,handler,schema=schemas[name])
