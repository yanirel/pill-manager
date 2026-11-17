"""Actionable Companion App reminders for scheduled medication doses."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_V2_UPDATED
from .engine import active_phase


def _parse(value):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


async def async_setup_reminders(hass: HomeAssistant, entry, store):
    """Start a lightweight minute-based reminder loop and action listener."""
    options = {
        "reminder_repeat_minutes": 30,
        "missed_after_minutes": 120,
        "missed_dose_action": "ask",
        "auto_deduct_stock": False,
        "notify_service": "",
        **entry.options,
    }
    notify_target = str(options.get("notify_service", "")).strip()

    async def send_notification(occurrence, overdue=False):
        if not notify_target or "." not in notify_target:
            return False
        domain, service = notify_target.split(".", 1)
        if not hass.services.has_service(domain, service):
            return False
        occurrence_id = occurrence["occurrence_id"]
        await hass.services.async_call(domain, service, {
            "title": "מנה שהגיע הזמן לקחת" if not overdue else "מנה שלא אושרה",
            "message": (
                f"{occurrence['medication_name']} · {occurrence['dose_mg']:g} מ״ג"
                if not overdue else
                f"המנה של {occurrence['medication_name']} ({occurrence['dose_mg']:g} מ״ג) עברה את חלון האישור."
            ),
            "data": {
                "tag": f"pill_{occurrence_id}",
                "actions": [
                    {"action": f"PILL_TAKEN|{occurrence_id}", "title": "לקחתי"},
                    {"action": f"PILL_SKIP|{occurrence_id}", "title": "דלג"},
                ],
            },
        }, blocking=True)
        return True

    async def check_reminders(_now=None):
        now = dt_util.now()
        today = now.date()
        changed = False
        for medication in store.data.get("medications", []):
            phase = active_phase(medication.get("regimen", {}), today)
            if not phase or today.weekday() not in phase.get("weekdays", list(range(7))):
                continue
            for time_text in phase.get("times", []):
                try:
                    hour, minute = (int(part) for part in time_text.split(":"))
                    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                except (ValueError, TypeError):
                    continue
                if now < scheduled:
                    continue
                occurrence_id = f"{medication['id']}:{today.isoformat()}:{time_text}"
                if any(x.get("occurrence_id") == occurrence_id and x.get("status") == "taken"
                       for x in store.data.get("intake", [])):
                    continue
                occurrence = next((x for x in store.data.setdefault("occurrences", [])
                                   if x.get("occurrence_id") == occurrence_id), None)
                if occurrence and occurrence.get("status") in ("skipped", "missed"):
                    continue
                elapsed = max(0, int((now - scheduled).total_seconds() // 60))
                overdue = elapsed >= int(options["missed_after_minutes"])
                if overdue and options["missed_dose_action"] == "mark_missed":
                    if occurrence is None:
                        store.data["occurrences"].append({
                            "occurrence_id": occurrence_id,
                            "medication_id": medication["id"],
                            "medication_name": medication["name"],
                            "dose_mg": float(phase["dose_mg"]),
                            "scheduled_at": scheduled.isoformat(),
                            "status": "missed",
                            "updated_at": now.isoformat(),
                        })
                        changed = True
                    continue
                status = "missed_pending" if overdue else "pending"
                if occurrence is None:
                    occurrence = {
                        "occurrence_id": occurrence_id,
                        "medication_id": medication["id"],
                        "medication_name": medication["name"],
                        "dose_mg": float(phase["dose_mg"]),
                        "scheduled_at": scheduled.isoformat(),
                        "status": status,
                        "updated_at": now.isoformat(),
                    }
                    store.data["occurrences"].append(occurrence)
                    changed = True
                elif occurrence.get("status") != status:
                    occurrence["status"] = status
                    occurrence["updated_at"] = now.isoformat()
                    changed = True

                if options["auto_deduct_stock"] and not overdue:
                    try:
                        await hass.services.async_call(DOMAIN, "take_dose", {
                            "medication_id": medication["id"],
                            "intake_id": occurrence_id,
                            "occurrence_id": occurrence_id,
                            "actual_dose_mg": float(phase["dose_mg"]),
                            "scheduled_dose_mg": float(phase["dose_mg"]),
                            "taken_at": scheduled.isoformat(),
                            "source": "scheduled_auto",
                        })
                        continue
                    except Exception:
                        # If stock cannot satisfy the planned dose, fall back to a reminder.
                        pass

                mark = next((x for x in store.data.setdefault("reminder_marks", [])
                             if x.get("occurrence_id") == occurrence_id), None)
                last_sent = _parse(mark.get("last_sent")) if mark else None
                repeat = int(options["reminder_repeat_minutes"])
                if last_sent and now - last_sent < timedelta(minutes=repeat):
                    continue
                try:
                    sent = await send_notification(occurrence, overdue)
                except Exception:  # A notification failure must not stop future reminders.
                    sent = False
                if sent:
                    if mark is None:
                        mark = {"occurrence_id": occurrence_id}
                        store.data["reminder_marks"].append(mark)
                    mark["last_sent"] = now.isoformat()
                    changed = True
        if changed:
            await store.async_save()
            hass.bus.async_fire(EVENT_V2_UPDATED)

    @callback
    def handle_mobile_action(event):
        action = str(event.data.get("action", ""))
        if "|" not in action:
            return
        command, occurrence_id = action.split("|", 1)
        occurrence = next((x for x in store.data.get("occurrences", [])
                           if x.get("occurrence_id") == occurrence_id), None)
        if occurrence is None:
            return
        now = dt_util.now().isoformat()
        if command == "PILL_TAKEN":
            hass.async_create_task(hass.services.async_call(DOMAIN, "take_dose", {
                "medication_id": occurrence["medication_id"],
                "intake_id": occurrence_id,
                "occurrence_id": occurrence_id,
                "actual_dose_mg": float(occurrence["dose_mg"]),
                "scheduled_dose_mg": float(occurrence["dose_mg"]),
                "taken_at": now,
                "source": "mobile_app",
            }))
        elif command == "PILL_SKIP":
            hass.async_create_task(hass.services.async_call(DOMAIN, "skip_dose", {
                "medication_id": occurrence["medication_id"],
                "occurrence_id": occurrence_id,
                "updated_at": now,
            }))

    action_unsub = hass.bus.async_listen("mobile_app_notification_action", handle_mobile_action)
    interval_unsub = async_track_time_interval(hass, check_reminders, timedelta(minutes=1))
    hass.data.setdefault(f"{DOMAIN}_unsubscribers", {}).setdefault(entry.entry_id, []).extend(
        [action_unsub, interval_unsub]
    )
    await check_reminders()
