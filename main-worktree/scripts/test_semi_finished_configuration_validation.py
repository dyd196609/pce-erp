"""Current user adjudication is separate from source-only historical projection tests."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from engineering_material_configuration_audit import snapshot, save
from pde.semi_finished_configuration_preview import build_projection, load_source
from pde.semi_finished_configuration_validation import apply_validation, load_evidence


class ValidationProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = build_projection(load_source(), snapshot()["formal"], 1)
        cls.after = apply_validation(cls.before)

    def config(self, code):
        return next(c for c in self.after["configurations"] if c["sourceCode"] == code)

    def test_only_two_user_validated(self):
        self.assertEqual([c["sourceCode"] for c in self.after["configurations"] if c["userValidated"]], ["QSFB4601001", "BTKF2601001"])
        self.assertEqual(sum(not c["userValidated"] and c["identity"]["status"] == "MATCHED" for c in self.after["configurations"]), 56)

    def test_source_only_history_not_mutated(self):
        self.assertTrue(all(not c["userValidated"] for c in self.before["configurations"]))

    def test_unknown_is_validated_not_false(self):
        fields = [a for a in self.config("BTKF2601001")["attributes"] if a["key"] in {"splice", "skinFeel"}]
        self.assertTrue(all(a["sourceValidated"] and a["sourceValue"] is None and a["canonicalValue"] is None and a["knowledgeLabel"] == "未知（保持来源）" for a in fields))

    def test_source_canonical_formal_three_values(self):
        p = next(a for a in self.config("BTKF2601001")["attributes"] if a["key"] == "paintProcess")
        self.assertEqual((p["sourceValue"], p["canonicalValue"], p["formalTargets"][0]["name"]), ("半透工艺", "半透开放工艺", "半透开放"))

    def test_business_validation_not_procurement_resolution(self):
        self.assertTrue(all(a["sourceValidated"] and a["formalStatus"] == "UNRESOLVED" for c in [self.config("BTKF2601001"), self.config("QSFB4601001")] for a in c["attributes"] if a["key"] in {"color", "veneer"}))

    def test_isolated_not_production_and_not_quantity_ready(self):
        self.assertEqual(self.after["summary"]["productionConfigurationCount"], 0)
        self.assertFalse(self.after["summary"]["productionMigrationApplied"])
        self.assertTrue(all(r["quantity"] is None and r["status"] == "BLOCKED" for c in [self.config("BTKF2601001"), self.config("QSFB4601001")] for r in c["isolatedReplay"]["roles"]))

    def test_confirmed_unknowns_not_reasked(self):
        self.assertTrue(all(not g["decisionRequiredNow"] for g in self.after["gaps"]))
        self.assertEqual(self.after["summary"]["userDecisionGroupCount"], 0)

    def test_third_candidate_rejected(self):
        evidence = load_evidence()
        evidence["cases"][1]["configurationCode"] = "QSFB2601001"
        with self.assertRaisesRegex(ValueError, "SCOPE"):
            apply_validation(self.before, evidence)

    def test_formal_identity_drift_fails_closed(self):
        source = copy.deepcopy(self.before)
        next(c for c in source["configurations"] if c["sourceCode"] == "BTKF2601001")["identity"]["formal"]["id"] = 999
        with self.assertRaisesRegex(ValueError, "LIVE_IDENTITY_DRIFT"):
            apply_validation(source)

    def test_evidence_file_tamper_fails_closed(self):
        with patch("pathlib.Path.read_bytes", return_value=b"{}"):
            with self.assertRaisesRegex(ValueError, "INTEGRITY"):
                load_evidence()

    def test_no_conflation_of_attributes_consumption(self):
        for c in [self.config("BTKF2601001"), self.config("QSFB4601001")]:
            self.assertEqual({r["roleCode"] for r in c["isolatedReplay"]["roles"]}, {"SUBSTRATE", "VENEER", "EDGE", "SURFACE_PAINT", "OTHER_FIXED"})
            self.assertTrue(all(r["formalMaterialId"] is None for r in c["isolatedReplay"]["roles"]))


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(ValidationProjectionTests))
    report = {"tests": result.testsRun, "status": "PASS" if result.wasSuccessful() else "FAIL", "productionBusinessWrite": 0}
    save(ROOT / "docs/evidence/semi_finished_model_closure_20260909/VALIDATION_PROJECTION_TESTS.json", report)
    raise SystemExit(0 if result.wasSuccessful() else 1)
