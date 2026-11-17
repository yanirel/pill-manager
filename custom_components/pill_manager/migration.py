"""Non-destructive one-time import from the first-generation storage."""
from __future__ import annotations

import re
from copy import deepcopy
from datetime import date
from uuid import uuid4

from .models import validate_medication
from .engine import PillManagerError


def _strength_mg(value):
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", str(value))
    if not match:
        return None
    try:
        number = float(match.group())
    except ValueError:
        return None
    return number if number > 0 and abs(number * 2 - round(number * 2)) < 1e-7 else None


def _legacy_regimen(schedules, strength_map):
    """Convert only a single indefinite schedule; ambiguous plans become PRN."""
    if len(schedules or []) != 1:
        return {"mode": "prn"}, "לוח המינון הישן לא ניתן להמרה חד-משמעית; הוגדר 'לפי הצורך' עד לבדיקה."
    schedule = schedules[0]
    if schedule.get("start_date"):
        try:
            if date.fromisoformat(schedule["start_date"]) > date.today():
                return {"mode": "prn"}, "לוח המינון הישן מתחיל בעתיד; הוגדר 'לפי הצורך' עד לבדיקה."
        except (TypeError, ValueError):
            return {"mode": "prn"}, "תאריך תחילת לוח המינון הישן אינו תקין; הוגדר 'לפי הצורך' עד לבדיקה."
    if schedule.get("end_date"):
        return {"mode": "prn"}, "לוח המינון הישן מוגבל בזמן; הוגדר 'לפי הצורך' כדי לא להמציא מינון לאחר סיומו."
    doses = schedule.get("doses") or {}
    dose_mg = 0.0
    for old_strength, amount in doses.items():
        strength = strength_map.get(str(old_strength))
        if strength is None:
            return {"mode": "prn"}, "לא ניתן לזהות חוזק באחד מלוחות המינון; נדרש להגדיר משטר מחדש."
        try:
            quantity = float(amount)
        except (TypeError, ValueError):
            return {"mode": "prn"}, "כמות בלוח המינון הישן אינה תקינה; נדרש להגדיר משטר מחדש."
        if quantity < 0 or abs(quantity - round(quantity)) > 1e-7:
            return {"mode": "prn"}, "כמות טבליות בלוח הישן אינה שלמה; נדרש להגדיר משטר מחדש."
        dose_mg += strength * quantity
    if dose_mg <= 0:
        return {"mode": "prn"}, "לא נמצא מינון חד-משמעי בלוח הישן; נדרש להגדיר משטר מחדש."
    times = schedule.get("times") or ([schedule["time"]] if schedule.get("time") else [])
    if not times:
        return {"mode": "prn"}, "לא נמצאו שעות נטילה בלוח הישן; נדרש להגדיר משטר מחדש."
    weekdays = schedule.get("weekdays", list(range(7)))
    return {
        "mode": "fixed",
        "fixed_phase": {
            "dose_mg": dose_mg,
            "times": list(times),
            "weekdays": list(weekdays),
        },
    }, None


def import_legacy_data(legacy_data, v2_data):
    """Copy supported legacy data into v2 without changing the legacy store."""
    if v2_data.get("migration", {}).get("legacy_v1_imported"):
        return False
    if v2_data.get("medications") or v2_data.get("intake"):
        return False

    today = date.today().isoformat()
    imported_ids = {}
    warnings = []
    for old in legacy_data.get("medications", []):
        strengths = old.get("strengths", [])
        products = []
        strength_map = {}
        for index, item in enumerate(strengths):
            strength_text = str(item.get("strength", ""))
            strength = _strength_mg(strength_text)
            if strength is None:
                warnings.append(f"{old.get('name', 'תרופה')}: לא זוהה החוזק {strength_text!r}; התרופה נשמרה בגיבוי הישן בלבד.")
                continue
            try:
                quantity = float(item.get("quantity", 0))
            except (TypeError, ValueError):
                quantity = 0
            if abs(quantity - round(quantity)) > 1e-7:
                warnings.append(f"{old.get('name', 'תרופה')}: מלאי לא שלם בחוזק {strength_text!r}; הכמות יובאה כאפס כדי לא להציג מלאי שגוי. יש לתקן ידנית.")
                quantity = 0
            elif quantity < 0:
                warnings.append(f"{old.get('name', 'תרופה')}: נמצאה יתרת מלאי שלילית בחוזק {strength_text!r}; היא נשמרה לבדיקה.")
            product_id = uuid4().hex
            strength_map[strength_text] = strength
            products.append({
                "id": product_id,
                "name": strength_text,
                "strength_mg": strength,
                "splittable": False,
                "stock_batches": [{
                    "id": uuid4().hex,
                    "quantity": quantity,
                    "received_at": "1970-01-01",
                }],
            })
        if not products:
            continue
        regimen, warning = _legacy_regimen(old.get("schedules", []), strength_map)
        if warning:
            warnings.append(f"{old.get('name', 'תרופה')}: {warning}")
        medication = {
            "id": old.get("id") or uuid4().hex,
            "name": str(old.get("name", "תרופה")).strip() or "תרופה",
            "products": products,
            "regimen": regimen,
            "migration_source": "legacy_v1",
        }
        try:
            validate_medication(medication)
        except (PillManagerError, TypeError, ValueError) as err:
            warnings.append(f"{medication['name']}: לא יובאה אוטומטית ({err}).")
            continue
        v2_data["medications"].append(medication)
        imported_ids[old.get("id")] = medication["id"]

    # Preserve all old intake records as historical-only entries. They have no
    # batch allocation, so the new Undo action must never restore their stock.
    for old_record in legacy_data.get("intake", []):
        med_id = imported_ids.get(old_record.get("medication_id"))
        if not med_id:
            continue
        dose_mg = 0.0
        legacy_doses = deepcopy(old_record.get("doses", []))
        for item in legacy_doses:
            strength = _strength_mg(item.get("strength", ""))
            try:
                dose_mg += (strength or 0) * float(item.get("quantity", 0))
            except (TypeError, ValueError):
                pass
        v2_data["intake"].append({
            "id": f"legacy:{old_record.get('id') or uuid4().hex}",
            "medication_id": med_id,
            "actual_dose_mg": dose_mg or None,
            "taken_at": old_record.get("taken_at"),
            "status": "historical",
            "source": "legacy_import",
            "legacy_doses": legacy_doses,
            "note": old_record.get("note", ""),
        })

    v2_data["legacy_backup"] = {
        "medications": deepcopy(legacy_data.get("medications", [])),
        "intake": deepcopy(legacy_data.get("intake", [])),
    }
    v2_data["migration"] = {
        "legacy_v1_imported": True,
        "imported_at": today,
        "imported_medications": len(imported_ids),
        "imported_history_records": sum(1 for x in v2_data["intake"] if x.get("source") == "legacy_import"),
        "warnings": warnings,
    }
    return True
