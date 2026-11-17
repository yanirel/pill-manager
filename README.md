# Pill Manager

A local-first medication inventory and intake tracker for Home Assistant.

## Features
- Dedicated Home Assistant sidebar panel
- Separate stock per medication strength
- Intake is recorded only after explicit confirmation
- Persistent intake history and corrections
- Dose schedules with date ranges, weekdays, and times
- Stock forecast and low-stock warnings
- Local storage in Home Assistant; no cloud account or external service

## Installation
1. Install **Pill Manager** using HACS → Integrations → Custom repositories.
2. Add `https://github.com/yanirel/pill-manager` as an Integration repository if it is not listed in the HACS store.
3. Download and restart Home Assistant.
4. Go to Settings → Devices & services → Add integration → Pill Manager.

The panel appears in the Home Assistant sidebar.

## Data and privacy
Medication names, schedules, stock, and intake history are stored locally in Home Assistant's `/config/.storage/pill_manager` file. Do not put personal medication information in GitHub issues.

## Status
Early development. Test carefully before relying on it for medication decisions. It is a tracking and reminder aid, not medical advice.
