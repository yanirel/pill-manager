"""Pure medication schedule and inventory engine."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any


class PillManagerError(ValueError):
    """Invalid medication or inventory operation."""


def active_phase(regimen: dict[str, Any], on_date: date) -> dict[str, Any] | None:
    """Return the active scheduled phase; PRN regimens have no scheduled phase."""
    mode = regimen.get("mode", "fixed")
    if mode == "prn":
        return None
    if mode == "fixed":
        return regimen.get("fixed_phase")
    phases = sorted(regimen.get("phases", []), key=lambda p: str(p.get("start_date", "")))
    for phase in phases:
        start = date.fromisoformat(phase["start_date"])
        duration = phase.get("duration_days")
        end = start + timedelta(days=int(duration) - 1) if duration else None
        if start <= on_date and (end is None or on_date <= end):
            return phase
    return None


def validate_regimen(regimen: dict[str, Any]) -> None:
    """Validate fixed, phased, and as-needed regimens."""
    mode = regimen.get("mode", "fixed")
    if mode == "prn":
        return
    if mode == "fixed":
        phase = regimen.get("fixed_phase")
        if not phase:
            raise PillManagerError("A fixed regimen needs a positive dose_mg")
        try:
            dose = float(phase.get("dose_mg", 0))
        except (TypeError, ValueError) as err:
            raise PillManagerError("A fixed regimen needs a numeric dose_mg") from err
        if dose <= 0:
            raise PillManagerError("A fixed regimen needs a positive dose_mg")
        _validate_phase_schedule(phase)
        return
    if mode != "phased":
        raise PillManagerError("Unknown regimen mode")

    phases = sorted(regimen.get("phases", []), key=lambda p: p["start_date"])
    if not phases:
        raise PillManagerError("A phased regimen needs at least one phase")
    previous_end = None
    for index, phase in enumerate(phases):
        try:
            start = date.fromisoformat(phase["start_date"])
        except (KeyError, TypeError, ValueError) as err:
            raise PillManagerError("Every phase needs a valid start_date") from err
        try:
            dose = float(phase.get("dose_mg", 0))
        except (TypeError, ValueError) as err:
            raise PillManagerError("Every phase needs a numeric dose_mg") from err
        if dose <= 0:
            raise PillManagerError("Every phase needs a positive dose_mg")
        duration = phase.get("duration_days")
        if index < len(phases) - 1 and duration is None:
            raise PillManagerError("Only the final phase may be open-ended")
        if duration is not None:
            try:
                duration = int(duration)
            except (TypeError, ValueError) as err:
                raise PillManagerError("duration_days must be a positive integer") from err
            if duration < 1:
                raise PillManagerError("duration_days must be positive")
        if previous_end is not None and start != previous_end + timedelta(days=1):
            raise PillManagerError("Phases must be consecutive with no gaps or overlaps")
        previous_end = start + timedelta(days=duration - 1) if duration is not None else None
        _validate_phase_schedule(phase)
    if phases[-1].get("duration_days") is not None:
        raise PillManagerError("The final phase must be open-ended")


def _validate_phase_schedule(phase: dict[str, Any]) -> None:
    try:
        dose = float(phase.get("dose_mg", 0))
    except (TypeError, ValueError) as err:
        raise PillManagerError("Dose must be numeric") from err
    if dose <= 0 or abs(dose * 2 - round(dose * 2)) > 1e-7:
        raise PillManagerError("Dose must be positive and representable to 0.5 mg")
    times = phase.get("times", [])
    if not isinstance(times, list) or not times:
        raise PillManagerError("Every scheduled phase needs at least one time")
    for value in times:
        try:
            datetime.strptime(value, "%H:%M")
        except (TypeError, ValueError) as err:
            raise PillManagerError("Times must use HH:MM format") from err
    weekdays = phase.get("weekdays", list(range(7)))
    if not weekdays or any(not isinstance(day, int) or day < 0 or day > 6 for day in weekdays):
        raise PillManagerError("weekdays must contain values from 0 to 6")


def _inventory_units(products, on_date):
    options = []
    for product_index, product in enumerate(products):
        splittable = bool(product.get("splittable", False))
        strength = float(product["strength_mg"])
        step = int(round(strength if splittable else strength * 2))
        if step <= 0:
            continue
        for batch_index, batch in enumerate(product.get("stock_batches", [])):
            quantity = float(batch.get("quantity", 0))
            if splittable and abs(quantity * 2 - round(quantity * 2)) > 1e-7:
                raise PillManagerError("Splittable stock quantities must use 0.5 tablet increments")
            if not splittable and abs(quantity - round(quantity)) > 1e-7:
                raise PillManagerError("Non-splittable stock quantities must be whole tablets")
            if on_date and batch.get("expires_on") and date.fromisoformat(batch["expires_on"]) < on_date:
                continue
            if on_date and batch.get("received_at"):
                received_date = date.fromisoformat(str(batch["received_at"])[:10])
                if received_date > on_date:
                    continue
            count = max(0, int(round(float(batch.get("quantity", 0)) * (2 if splittable else 1))))
            received = batch.get("received_at", "")
            for unit_index in range(count):
                options.append((received, product_index, batch_index, unit_index, step,
                                product, batch, 0.5 if splittable else 1.0))
    return sorted(options, key=lambda x: (x[0], x[1], x[2], x[3]))


def allocate_dose(products: list[dict[str, Any]], target_mg: float,
                  on_date: date | None = None) -> list[dict[str, Any]]:
    """Find an exact dose, preferring oldest received stock before portion count."""
    if target_mg <= 0 or abs(target_mg * 2 - round(target_mg * 2)) > 1e-7:
        raise PillManagerError("Dose must be positive and representable to 0.5 mg")
    target = int(round(target_mg * 2))
    options = _inventory_units(products, on_date)
    # 0/1 subset-sum: each physical half/full tablet portion can be used once.
    dp = {0: (0, ())}
    for idx, option in enumerate(options):
        step = option[4]
        for total, (count, chosen) in sorted(list(dp.items()), reverse=True):
            new_total = total + step
            candidate = chosen + (idx,)
            if new_total <= target and (new_total not in dp or candidate < dp[new_total][1]):
                # FIFO takes precedence over minimizing tablet portions: never
                # consume newer stock merely because it uses fewer pieces.
                dp[new_total] = (count + 1, candidate)
    if target not in dp:
        raise PillManagerError(f"Insufficient compatible stock for {target_mg:g} mg")
    grouped = {}
    for idx in dp[target][1]:
        option = options[idx]
        product, batch, unit_size = option[5], option[6], option[7]
        key = (product["id"], batch["id"])
        grouped[key] = grouped.get(key, 0.0) + unit_size
    return [{"product_id": pid, "batch_id": bid, "units": units}
            for (pid, bid), units in grouped.items()]


def consume_allocation(products, allocation, sign=-1):
    """Apply an allocation atomically; sign=-1 consumes and sign=+1 restores."""
    if sign not in (-1, 1):
        raise PillManagerError("sign must be -1 or 1")
    changes = []
    for item in allocation:
        product = next((p for p in products if p["id"] == item["product_id"]), None)
        batch = next((b for b in product.get("stock_batches", [])
                      if b["id"] == item["batch_id"]), None) if product else None
        if batch is None:
            raise PillManagerError("Referenced stock batch no longer exists")
        after = float(batch.get("quantity", 0)) + sign * float(item["units"])
        if sign < 0 and after < -1e-8:
            raise PillManagerError("Insufficient stock")
        changes.append((batch, max(0.0, after) if sign < 0 else after))
    for batch, quantity in changes:
        batch["quantity"] = quantity


def forecast(products, regimen, start: date, max_days=3650, medication_id=None,
             intake_records=None, occurrences=None):
    """Simulate future doses, excluding today's already handled occurrences."""

    validate_regimen(regimen)
    if regimen.get("mode", "fixed") == "prn":
        return {"depletion_date": None, "days_remaining": None,
                "batch_depletion_dates": {}, "reason": "prn"}
    stock = deepcopy(products)
    handled_today = {
        item.get("occurrence_id") for item in (intake_records or [])
        if item.get("status") == "taken" and item.get("occurrence_id")
    }
    handled_today.update(
        item.get("occurrence_id") for item in (occurrences or [])
        if item.get("status") in ("skipped", "missed") and item.get("occurrence_id")
    )
    batch_dates = {(p["id"], b["id"]): None
                   for p in stock for b in p.get("stock_batches", [])}
    for offset in range(max_days):
        day = start + timedelta(days=offset)
        phase = active_phase(regimen, day)
        if not phase or day.weekday() not in phase.get("weekdays", list(range(7))):
            continue
        for _time in phase.get("times", []):
            if offset == 0 and medication_id:
                occurrence_id = f"{medication_id}:{day.isoformat()}:{_time}"
                if occurrence_id in handled_today:
                    continue
            try:
                allocation = allocate_dose(stock, float(phase["dose_mg"]), day)
            except PillManagerError:
                return {"depletion_date": day.isoformat(), "days_remaining": offset,
                        "batch_depletion_dates": {
                            f"{pid}:{bid}": value.isoformat() if value else None
                            for (pid, bid), value in batch_dates.items()},
                        "remaining_by_batch": {
                            f"{p['id']}:{b['id']}": b.get("quantity", 0)
                            for p in stock for b in p.get("stock_batches", [])},
                        "exhausted_or_incompatible": True}
            consume_allocation(stock, allocation)
            for item in allocation:
                key = (item["product_id"], item["batch_id"])
                batch = next(b for p in stock for b in p.get("stock_batches", [])
                             if p["id"] == item["product_id"] and b["id"] == item["batch_id"])
                if float(batch.get("quantity", 0)) <= 1e-8 and batch_dates[key] is None:
                    batch_dates[key] = day
    return {"depletion_date": None, "days_remaining": None,
            "batch_depletion_dates": {
                f"{pid}:{bid}": value.isoformat() if value else None
                for (pid, bid), value in batch_dates.items()},
            "horizon_days": max_days}
