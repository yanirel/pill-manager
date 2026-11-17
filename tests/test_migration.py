import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "pill_manager"
PACKAGE = "pill_manager_migration_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package

for name in ("engine", "models", "migration"):
    spec = importlib.util.spec_from_file_location(f"{PACKAGE}.{name}", ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

import_legacy_data = sys.modules[f"{PACKAGE}.migration"].import_legacy_data


class MigrationTests(unittest.TestCase):
    def test_imports_stock_and_history_without_changing_legacy(self):
        legacy = {
            "medications": [{
                "id": "old-med", "name": "Example",
                "strengths": [{"strength": "25 mg", "quantity": 8}],
                "schedules": [{"doses": {"25 mg": 1}, "times": ["08:00"],
                               "weekdays": list(range(7)), "start_date": "2026-01-01"}],
            }],
            "intake": [{"id": "old-intake", "medication_id": "old-med",
                        "taken_at": "2026-01-02T08:00:00+02:00",
                        "doses": [{"strength": "25 mg", "quantity": 1}]}],
        }
        original = repr(legacy)
        v2 = {"medications": [], "intake": []}
        self.assertTrue(import_legacy_data(legacy, v2))
        self.assertEqual(repr(legacy), original)
        self.assertEqual(v2["medications"][0]["products"][0]["stock_batches"][0]["quantity"], 8)
        self.assertEqual(v2["medications"][0]["regimen"]["fixed_phase"]["dose_mg"], 25)
        self.assertEqual(v2["intake"][0]["status"], "historical")
        self.assertEqual(v2["intake"][0]["actual_dose_mg"], 25)
        self.assertTrue(v2["migration"]["legacy_v1_imported"])

    def test_ambiguous_old_schedule_becomes_prn_not_guessed(self):
        legacy = {"medications": [{
            "id": "old", "name": "Example",
            "strengths": [{"strength": "50mg", "quantity": 4}],
            "schedules": [
                {"doses": {"50mg": 1}, "times": ["08:00"]},
                {"doses": {"50mg": 1}, "times": ["20:00"]},
            ],
        }], "intake": []}
        v2 = {"medications": [], "intake": []}
        import_legacy_data(legacy, v2)
        self.assertEqual(v2["medications"][0]["regimen"]["mode"], "prn")
        self.assertTrue(v2["migration"]["warnings"])

    def test_import_is_idempotent(self):
        legacy = {"medications": [{"id": "x", "name": "A",
                   "strengths": [{"strength": "10 mg", "quantity": 1}],
                   "schedules": []}], "intake": []}
        v2 = {"medications": [], "intake": []}
        self.assertTrue(import_legacy_data(legacy, v2))
        self.assertFalse(import_legacy_data(legacy, v2))
        self.assertEqual(len(v2["medications"]), 1)


if __name__ == "__main__":
    unittest.main()
