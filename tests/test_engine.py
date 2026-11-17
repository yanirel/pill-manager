import importlib.util
import unittest
from datetime import date
from pathlib import Path

ENGINE_PATH = Path(__file__).parents[1] / "custom_components" / "pill_manager" / "engine.py"
SPEC = importlib.util.spec_from_file_location("pill_manager_engine", ENGINE_PATH)
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)
PillManagerError = ENGINE.PillManagerError
allocate_dose = ENGINE.allocate_dose
consume_allocation = ENGINE.consume_allocation
forecast = ENGINE.forecast
validate_regimen = ENGINE.validate_regimen


def product(pid, strength, qty, received, split=False, batch="b"):
    return {"id": pid, "strength_mg": strength, "splittable": split,
            "stock_batches": [{"id": batch, "quantity": qty, "received_at": received}]}


class EngineTests(unittest.TestCase):
    def test_combines_strengths_for_target_mg(self):
        products = [product("p25", 25, 4, "2026-01-01", True),
                    product("p50", 50, 4, "2026-01-02", True)]
        allocation = allocate_dose(products, 75, date(2026, 2, 1))
        actual = sum(next(p["strength_mg"] for p in products if p["id"] == x["product_id"]) * x["units"] for x in allocation)
        self.assertEqual(actual, 75)

    def test_half_tablet_supported(self):
        products = [product("p25", 25, 1, "2026-01-01", True)]
        allocation = allocate_dose(products, 12.5, date(2026, 2, 1))
        self.assertEqual(allocation[0]["units"], 0.5)

    def test_fifo_across_strengths(self):
        products = [product("new", 50, 1, "2026-02-01", True),
                    product("old", 25, 2, "2026-01-01", True)]
        allocation = allocate_dose(products, 25, date(2026, 3, 1))
        self.assertEqual(allocation, [{"product_id": "old", "batch_id": "b", "units": 1.0}])

    def test_consumption_is_atomic(self):
        products = [product("p25", 25, 0.5, "2026-01-01", True)]
        with self.assertRaises(PillManagerError):
            consume_allocation(products, [{"product_id": "p25", "batch_id": "b", "units": 1.0}])
        self.assertEqual(products[0]["stock_batches"][0]["quantity"], 0.5)

    def test_forecast_walks_future_phases(self):
        products = [product("p25", 25, 2, "2026-01-01", True)]
        regimen = {"mode": "phased", "phases": [
            {"start_date": "2026-11-17", "duration_days": 1, "dose_mg": 25, "times": ["08:00"]},
            {"start_date": "2026-11-18", "duration_days": None, "dose_mg": 50, "times": ["08:00"]}]}
        result = forecast(products, regimen, date(2026, 11, 17), max_days=10)
        self.assertEqual(result["depletion_date"], "2026-11-18")

    def test_prn_has_no_forecast_or_scheduled_phase(self):
        regimen = {"mode": "prn"}
        validate_regimen(regimen)
        self.assertIsNone(ENGINE.active_phase(regimen, date(2026, 11, 17)))
        self.assertEqual(forecast([], regimen, date(2026, 11, 17))["reason"], "prn")

    def test_phases_must_be_contiguous(self):
        regimen = {"mode": "phased", "phases": [
            {"start_date": "2026-01-01", "duration_days": 2, "dose_mg": 25, "times": ["08:00"]},
            {"start_date": "2026-01-04", "duration_days": None, "dose_mg": 50, "times": ["08:00"]}]}
        with self.assertRaises(PillManagerError):
            validate_regimen(regimen)

    def test_batch_ids_are_scoped_to_product(self):
        products = [product("a", 25, 1, "2026-01-01", True, "same"),
                    product("b", 25, 1, "2026-01-02", True, "same")]
        result = forecast(products, {"mode": "fixed", "fixed_phase": {
            "dose_mg": 25, "times": ["08:00"]}}, date(2026, 1, 1), max_days=4)
        self.assertIn("a:same", result["batch_depletion_dates"])
        self.assertIn("b:same", result["batch_depletion_dates"])

    def test_backdated_intake_ignores_batches_received_later(self):
        products = [product("future", 25, 2, "2026-11-18", True)]
        with self.assertRaises(PillManagerError):
            allocate_dose(products, 25, date(2026, 11, 17))

    def test_negative_stock_is_not_allocatable(self):
        products = [product("negative", 25, -1, "2026-01-01", True)]
        with self.assertRaises(PillManagerError):
            allocate_dose(products, 25, date(2026, 11, 17))

    def test_invalid_fractional_stock_is_rejected(self):
        products = [product("fractional", 25, 0.25, "2026-01-01", True)]
        with self.assertRaises(PillManagerError):
            allocate_dose(products, 12.5, date(2026, 11, 17))

    def test_scheduled_phase_requires_time(self):
        regimen = {"mode": "fixed", "fixed_phase": {"dose_mg": 25, "times": []}}
        with self.assertRaises(PillManagerError):
            validate_regimen(regimen)

    def test_forecast_does_not_count_already_taken_dose_today(self):
        products = [product("p25", 25, 1, "2026-01-01", True)]
        regimen = {"mode": "fixed", "fixed_phase": {
            "dose_mg": 25, "times": ["08:00", "20:00"]}}
        result = forecast(
            products, regimen, date(2026, 11, 17), max_days=3,
            medication_id="med",
            intake_records=[{"occurrence_id": "med:2026-11-17:08:00", "status": "taken"}],
        )
        self.assertEqual(result["depletion_date"], "2026-11-18")


if __name__ == "__main__":
    unittest.main()
