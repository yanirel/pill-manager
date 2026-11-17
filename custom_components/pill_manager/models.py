"""Canonical data model validation."""
from datetime import date
from .engine import PillManagerError, validate_regimen


def validate_medication(med):
    if not str(med.get("name", "")).strip():
        raise PillManagerError("Medication name is required")

    product_ids = set()
    batch_ids = set()
    if not med.get("products"):
        raise PillManagerError("At least one product strength is required")
    for product in med.get("products", []):
        product_id = product.get("id")
        if not product_id or product_id in product_ids:
            raise PillManagerError("Every product needs a unique id")
        product_ids.add(product_id)
        try:
            strength = float(product.get("strength_mg", 0))
        except (TypeError, ValueError) as err:
            raise PillManagerError("Product strength_mg must be numeric") from err
        if strength <= 0 or abs(strength * 2 - round(strength * 2)) > 1e-7:
            raise PillManagerError("Product strength_mg must be positive and use 0.5 mg increments")

        for batch in product.get("stock_batches", []):
            batch_id = batch.get("id")
            if not batch_id:
                raise PillManagerError("Every stock batch needs an id")
            # Batch IDs are scoped to a product; duplicate IDs within one product are invalid.
            scoped_id = (product_id, batch_id)
            if scoped_id in batch_ids:
                raise PillManagerError("Stock batch IDs must be unique within a product")
            batch_ids.add(scoped_id)
            try:
                quantity = float(batch.get("quantity", 0))
            except (TypeError, ValueError) as err:
                raise PillManagerError("Stock quantity must be numeric") from err
            # Negative balances are retained as warnings, never usable stock.
            if not product.get("splittable", False) and not quantity.is_integer():
                raise PillManagerError("Non-splittable product stock must be whole tablets")
            if batch.get("expires_on"):
                date.fromisoformat(batch["expires_on"])
            if not batch.get("received_at"):
                raise PillManagerError("Every stock batch needs received_at")
            value = str(batch["received_at"])
            try:
                date.fromisoformat(value[:10])
            except ValueError as err:
                raise PillManagerError("received_at must be an ISO date or datetime") from err

    validate_regimen(med.get("regimen", {}))
    return med


def empty_database():
    return {
        "schema_version": 2,
        "medications": [],
        "intake": [],
        "occurrences": [],
        "stock_events": [],
    }
