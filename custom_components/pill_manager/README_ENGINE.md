# Pill Manager – core v2 milestone

This branch introduces the v2 data model and calculation engine.

- FIFO consumption by received_at, stable input order as tie-breaker.
- No schedule-based stock deduction.
- Intake confirmation is idempotent when occurrence_id is supplied.
- Missed occurrences are separate from intake and do not consume stock.
- Dose targets are in mg; allocations use tablet units, including half-tablets for splittable products.
- Forecast simulates future phases and scheduled times rather than extrapolating today's daily rate.

This is not an installable release yet. Integration wiring, entities, notifications, migration, UI, automated tests and full Home Assistant validation remain necessary. The v2 Store key is separate so legacy data is not silently overwritten.
