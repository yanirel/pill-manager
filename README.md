# Pill Manager

A local-first medication inventory and intake tracker for Home Assistant.

## Planned capabilities
- Separate medication, product strength, stock batch, and dose regimen records.
- Dose tracking in milligrams, with support for combining strengths and half tablets.
- Fixed, phased/tapered, and as-needed (PRN) regimens.
- FIFO stock allocation, expiry-aware inventory, and future regimen forecasting.
- Explicit intake confirmation; scheduled reminders do not automatically consume stock by default.
- Hebrew, standalone Home Assistant sidebar panel.
- Local persistence in Home Assistant.

## Development status

The active development work is on the feature/core-v2 branch and in [draft pull request #1](https://github.com/yanirel/pill-manager/pull/1).

**This is not a released or installable version.** The v2 panel and core API are being built and tested. Notifications, Home Assistant entities, migration, and full end-to-end validation are still in progress. Do not install this development branch on a production Home Assistant instance yet.

## Development tests
The GitHub Actions workflow runs the pure calculation-engine tests, compiles the integration Python files, checks the panel JavaScript syntax, and validates integration JSON files.

## Data and privacy
The v2 data store uses Home Assistant's local .storage system under the separate key pill_manager_v2. The existing legacy store is intentionally kept separate during development. Do not put personal medication information in GitHub issues.

## Safety
Pill Manager is a tracking and reminder aid, not medical advice. It does not recommend or change prescribed doses.
