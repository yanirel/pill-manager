# Pill Manager – v2 development milestone

The feature/core-v2 branch contains the new medication model, stock engine, dedicated Hebrew panel, Home Assistant status entities, and Companion App reminder loop.

## Implemented in this branch
- Distinct medication, product strength, stock batch, regimen, intake, and occurrence records.
- Fixed, phased/tapered, and PRN regimen modes. The integration tracks prescribed values only; it does not recommend or change doses.
- Dose targets in mg, combined strengths, half tablets, FIFO allocation, expiry checks, and future-phase forecasting.
- Explicit intake confirmation, idempotency, undo, skip, restock, and audited stock correction.
- Companion App actions: taken, snooze, and skip; repeat interval and missed-dose handling options.
- Default automatic stock deduction is off. Negative stock balances remain visible as warnings and are not considered usable stock.
- Sensors for remaining stock days, depletion date, current dose; a due-dose binary sensor; and a taken-confirmation button.
- Separate v2 local storage key so legacy data is not silently overwritten.

## Validation status
The GitHub Actions workflow runs the calculation-engine tests, compiles the Python integration files, checks JavaScript syntax, and validates JSON metadata. These checks do not replace an end-to-end test inside a real Home Assistant instance. Notifications, options reload, entity lifecycle, and the panel still need runtime validation before a release.

This branch is not a released installation. Do not merge or install it as a production integration until the remaining Home Assistant runtime checks and data migration plan are complete.
