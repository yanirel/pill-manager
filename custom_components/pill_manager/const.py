"""Constants for Pill Manager."""

DOMAIN = "pill_manager"
STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN
PANEL_URL = "pill-manager"
WS_GET_DATA = f"{DOMAIN}/get_data"
WS_SAVE_MEDICATION = f"{DOMAIN}/save_medication"
WS_DELETE_MEDICATION = f"{DOMAIN}/delete_medication"
WS_CONFIRM_INTAKE = f"{DOMAIN}/confirm_intake"
WS_UPDATE_INTAKE = f"{DOMAIN}/update_intake"
WS_SAVE_SCHEDULE = f"{DOMAIN}/save_schedule"

EVENT_V2_UPDATED = f"{DOMAIN}_v2_updated"
