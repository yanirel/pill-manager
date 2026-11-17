"""Pure medication schedule and inventory engine."""
from __future__ import annotations
from copy import deepcopy
from datetime import date, timedelta
from typing import Any

class PillManagerError(ValueError):
    """Invalid medication or inventory operation."""

def active_phase(regimen: dict[str, Any], on_date: date) -> dict[str, Any] | None:
    phases = sorted(regimen.get("phases", []), key=lambda p: p["start_date"])
    if regimen.get("mode") == "fixed" and not phases:
        return regimen.get("fixed_phase")
    for phase in phases:
        start = date.fromisoformat(phase["start_date"])
        duration = phase.get("duration_days")
        end = start + timedelta(days=int(duration)-1) if duration else None
        if start <= on_date and (end is None or on_date <= end):
            return phase
    return None

def validate_regimen(regimen: dict[str, Any]) -> None:
    mode = regimen.get("mode", "fixed")
    if mode == "fixed":
        if not regimen.get("fixed_phase") or float(regimen["fixed_phase"].get("dose_mg", 0)) <= 0:
            raise PillManagerError("A fixed regimen needs a positive dose_mg")
        return
    if mode != "phased":
        raise PillManagerError("Unknown regimen mode")
    phases = sorted(regimen.get("phases", []), key=lambda p: p["start_date"])
    if not phases:
        raise PillManagerError("A phased regimen needs at least one phase")
    for i, phase in enumerate(phases):
        if float(phase.get("dose_mg", 0)) <= 0:
            raise PillManagerError("Every phase needs a positive dose_mg")
        if i < len(phases)-1 and not phase.get("duration_days"):
            raise PillManagerError("Only the final phase may be open-ended")
        if phase.get("duration_days") is not None and int(phase["duration_days"]) < 1:
            raise PillManagerError("duration_days must be positive")
    if phases[-1].get("duration_days") is not None:
        raise PillManagerError("The final phase must be open-ended")

def allocate_dose(products: list[dict[str, Any]], target_mg: float,
                  on_date: date | None = None) -> list[dict[str, Any]]:
    """Find an exact dose, preferring fewer tablet halves and FIFO batches."""
    if target_mg <= 0 or abs(target_mg*2-round(target_mg*2)) > 1e-7:
        raise PillManagerError("Dose must be positive and representable to 0.5 mg")
    target = int(round(target_mg*2))
    options = []
    for product in products:
        splittable = bool(product.get("splittable", False))
        step = int(round(float(product["strength_mg"]) if splittable else float(product["strength_mg"])*2))
        batches = sorted(product.get("stock_batches", []), key=lambda b:(b.get("received_at",""),b.get("id","")))
        for batch in batches:
            if on_date and batch.get("expires_on") and date.fromisoformat(batch["expires_on"]) < on_date:
                continue
            count = int(round(float(batch.get("quantity",0))*(2 if splittable else 1)))
            options.extend((step, product, batch) for _ in range(count))
    dp = {0:(0,())}
    for idx,(step,_product,_batch) in enumerate(options):
        for total,(count,chosen) in list(dp.items())[::-1]:
            new_total=total+step
            if new_total<=target and (new_total not in dp or count+1<dp[new_total][0]):
                dp[new_total]=(count+1,chosen+(idx,))
    if target not in dp:
        raise PillManagerError(f"Insufficient compatible stock for {target_mg:g} mg")
    grouped={}
    for idx in dp[target][1]:
        _step,product,batch=options[idx]
        key=(product["id"],batch["id"])
        grouped[key]=grouped.get(key,0)+(0.5 if product.get("splittable") else 1.0)
    return [{"product_id":p,"batch_id":b,"units":u} for (p,b),u in grouped.items()]

def consume_allocation(products, allocation, sign=-1):
    """Atomically consume or restore an allocation."""
    changes=[]
    for item in allocation:
        product=next((p for p in products if p["id"]==item["product_id"]),None)
        batch=next((b for b in product.get("stock_batches",[]) if b["id"]==item["batch_id"]),None) if product else None
        if batch is None:
            raise PillManagerError("Referenced stock batch no longer exists")
        after=float(batch.get("quantity",0))+sign*float(item["units"])
        if sign<0 and after < -1e-8:
            raise PillManagerError("Insufficient stock")
        changes.append((batch,max(0.0,after) if sign<0 else after))
    for batch,quantity in changes:
        batch["quantity"]=quantity

def forecast(products, regimen, start: date, max_days=3650):
    """Simulate future occurrences across every regimen phase."""
    validate_regimen(regimen)
    stock=deepcopy(products)
    for offset in range(max_days):
        day=start+timedelta(days=offset)
        phase=regimen.get("fixed_phase") if regimen.get("mode")=="fixed" else active_phase(regimen,day)
        if not phase or day.weekday() not in phase.get("weekdays",list(range(7))):
            continue
        for _time in phase.get("times",[]):
            try:
                allocation=allocate_dose(stock,float(phase["dose_mg"]),day)
            except PillManagerError:
                return {"depletion_date":day.isoformat(),"days_remaining":offset,
                        "remaining_by_batch":{b["id"]:b.get("quantity",0) for p in stock for b in p.get("stock_batches",[])},
                        "exhausted_or_incompatible":True}
            consume_allocation(stock,allocation)
    return {"depletion_date":None,"days_remaining":None,"horizon_days":max_days}
