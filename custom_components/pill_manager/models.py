"""Canonical data model validation."""
from datetime import date
from .engine import PillManagerError, validate_regimen

def validate_medication(med):
    if not str(med.get("name","")).strip():
        raise PillManagerError("Medication name is required")
    ids=set()
    for product in med.get("products",[]):
        if not product.get("id") or product["id"] in ids:
            raise PillManagerError("Every product needs a unique id")
        ids.add(product["id"])
        if float(product.get("strength_mg",0))<=0:
            raise PillManagerError("Product strength_mg must be positive")
        for batch in product.get("stock_batches",[]):
            if float(batch.get("quantity",0))<0:
                raise PillManagerError("Stock quantity cannot be negative")
            if batch.get("expires_on"):
                date.fromisoformat(batch["expires_on"])
    validate_regimen(med.get("regimen",{}))
    return med

def empty_database():
    return {"schema_version":2,"medications":[],"intake":[],"occurrences":[],"stock_events":[]}
