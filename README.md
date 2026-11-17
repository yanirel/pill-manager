# Pill Manager

A local-first Hebrew medication, schedule, intake and inventory manager for Home Assistant.

## Features

- Add a medication with multiple product strengths / packages (for example 25 mg and 50 mg).
- Define the prescribed dose in mg; the engine calculates a compatible combination of available tablets and half-tablets.
- Fixed schedules or phased regimens with start dates, duration, dose, weekdays and one or more times per day.
- PRN (as-needed) medications without scheduled reminders.
- Reminder notifications, repeat / snooze / skip, and explicit intake confirmation.
- Stock is deducted only after a confirmed intake by default. Automatic scheduled deduction is optional and off by default.
- FIFO stock allocation, expiry-aware batches, undo of a confirmed intake, audited stock corrections and stock-restock records.
- Forecast the date stock will run out, including future dose phases.
- Home Assistant sensors for current dose, remaining stock days and depletion date, plus a due-dose binary sensor and confirmation button.
- Hebrew Home Assistant sidebar panel.
- Separate v2 local storage and non-destructive import of supported legacy records.

## Install

Install as a custom integration through HACS using this repository:

`yanirel/pill-manager`

After installation, restart Home Assistant, add the **Pill Manager** integration under Settings → Devices & services, and open **תרופות** in the sidebar. Configure the notification target in the integration options.

## Important notes

- Pill Manager is a tracking and reminder aid, not medical advice. It does not recommend or change prescribed doses.
- Review imported schedules and the initial stock after migration. Ambiguous legacy schedules are imported as PRN rather than guessed.
- Confirmed intakes reduce stock. Historical imports are read-only where the original stock allocation is unknown.
- Automated CI checks cover the calculation engine, migration, Python import in the Home Assistant 2026.9.1 runtime, JavaScript syntax and JSON metadata. These checks are not a substitute for verifying notification delivery and the complete workflow on the target Home Assistant installation.
- Medication names, regimens, stock and intake history are stored locally in Home Assistant. Do not put personal medication information in GitHub issues.
