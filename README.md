# Pill Manager

A local-first medication inventory and intake tracker for Home Assistant.

## Capabilities under development
- Separate medication, product strength, stock batch, and dose regimen records.
- Dose tracking in milligrams, with support for combining strengths and half tablets.
- Fixed, phased/tapered, and as-needed (PRN) regimens.
- FIFO stock allocation, expiry-aware inventory, and future regimen forecasting.
- Explicit intake confirmation; automatic stock deduction is off by default.
- Actionable Home Assistant Companion App notifications through a selectable `notify.*` service.
- Hebrew standalone Home Assistant sidebar panel.
- Local persistence in Home Assistant.

## Development status

The active development work is on the `feature/core-v2` branch and in [draft pull request #1](https://github.com/yanirel/pill-manager/pull/1).

**This is not a released or installable version.** Pure engine and migration tests are running in CI, and a Home Assistant runtime import check is being added. Full lifecycle tests on a real Home Assistant instance and end-to-end Companion App verification are still required. Do not install this development branch on a production Home Assistant instance yet.

## Migration safety

On first v2 startup, if legacy data exists and the v2 store is empty, the integration copies supported medications and historical intake records into the new store. It never modifies or deletes the legacy store. Imported historical intakes are read-only because their original stock-batch allocation is unknown. Ambiguous, expired, future-dated, or unsupported old schedules are not guessed: the medication is imported as PRN and a warning is shown in the panel so the user can review its regimen. A full legacy backup is retained in the v2 store.

## Development tests
GitHub Actions runs:
- Pure dose and inventory engine tests.
- Non-destructive migration tests.
- Home Assistant integration module import checks.
- Python compilation, frontend JavaScript syntax validation, and JSON validation.

## Data and privacy
Medication names, regimens, stock, and intake history are stored locally in Home Assistant's `.storage` system. The v2 data store uses the separate key `pill_manager_v2`. Do not put personal medication information in GitHub issues.

## Safety
Pill Manager is a tracking and reminder aid, not medical advice. It does not recommend or change prescribed doses.
