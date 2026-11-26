"""Synthetic contract tests only. Never emitted as native Golden evidence."""
import copy
import tempfile
import unittest
from pathlib import Path

import package_support as p


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = p.load_manifest()
        cls.modules = p.reference(cls.manifest)

    def sample(self):
        run = {"run_id":"SYNTHETIC_UNIT_TEST_ONLY", "mode":"USER_SESSION_NATIVE", "execution_status":"PASS", "original_unchanged":True, "source_sha_after":p.EXPECTED_SHA, "run_copy_sha_after":p.EXPECTED_SHA, "plan_sha":"fixture", "excel_pid":123, "excel_version":"TEST_ONLY", "calculation_start":"start", "calculation_end":"end", "result_count":1}
        plan = {"run_id":run["run_id"], "cases":[{"case_id":"fixture", "overrides":[{"sheet":"s","cell":"A1","type":"number","value":0}], "derived_outputs":[{"cell":"s!B1","formula_family":"f","formula":"=A1+1"}]}]}
        golden = {"run_id":run["run_id"], "engine":"Microsoft Excel Calculation Engine", "status":"CAPTURED", "source_sha":p.EXPECTED_SHA, "plan_sha":"fixture", "results":[{"case_id":"fixture", "restored":True, "calculation_start":"start", "calculation_end":"end", "overrides":[{"sheet":"s","cell":"A1","actual":{"type":"number","value":0}}], "outputs":[{"cell":"s!B1","formula_family":"f","has_formula":True,"formula":"=A1+1","excel_raw_value":{"type":"number","value":1}}]}]}
        return run, golden, plan

    def rejected(self, mutate):
        run, golden, plan = self.sample()
        mutate(run, golden, plan)
        with self.assertRaises((ValueError, KeyError)):
            p.validate_native(run, golden, plan, "fixture")

    def test_fixture_schema_only(self):
        self.assertEqual(len(p.validate_native(*self.sample(), "fixture")), 1)

    def test_no_cache_or_python_oracle(self):
        self.rejected(lambda r,g,c:g.update(engine="OpenXML cached values"))
        self.rejected(lambda r,g,c:g.update(engine="Python"))

    def test_no_precheck_oracle(self):
        self.rejected(lambda r,g,c:r.update(mode="PACKAGE_PRECHECK"))

    def test_source_mutation_blocks(self):
        self.rejected(lambda r,g,c:r.update(original_unchanged=False))

    def test_saved_copy_blocks(self):
        self.rejected(lambda r,g,c:r.update(run_copy_sha_after="changed"))

    def test_wrong_case_plan_blocks(self):
        self.rejected(lambda r,g,c:g.update(plan_sha="stale"))

    def test_wrong_run_blocks(self):
        self.rejected(lambda r,g,c:g.update(run_id="another"))

    def test_incomplete_capture_blocks(self):
        self.rejected(lambda r,g,c:g.update(results=[]))

    def test_missing_restore_blocks(self):
        self.rejected(lambda r,g,c:g["results"][0].update(restored=False))

    def test_formula_drift_blocks(self):
        self.rejected(lambda r,g,c:g["results"][0]["outputs"][0].update(formula="=A1+2"))

    def test_boolean_not_number_input(self):
        self.rejected(lambda r,g,c:g["results"][0]["overrides"][0]["actual"].update(value=False))

    def test_input_value_mismatch_blocks(self):
        self.rejected(lambda r,g,c:g["results"][0]["overrides"][0]["actual"].update(value=5))

    def test_string_output_cannot_be_number(self):
        self.rejected(lambda r,g,c:g["results"][0]["outputs"][0]["excel_raw_value"].update(value="1"))

    def test_native_metadata_required(self):
        self.rejected(lambda r,g,c:r.update(excel_pid=None))

    def test_actual_frozen_selection(self):
        family, cases = p.assets(self.manifest)
        selected = p.select_cases(family, cases, self.modules["generated_reference"].FUNCTIONS)
        self.assertEqual(len(selected), 280)
        self.assertTrue(all(c["level"] == 1 for c in selected))
        self.assertEqual(len({o["formula_family"] for c in selected for o in c["derived_outputs"]}), 112)
        self.assertFalse(any("#REF!" in o["formula"] for c in selected for o in c["derived_outputs"]))

    def test_missing_function_not_silently_skipped(self):
        family, cases = p.assets(self.manifest)
        with self.assertRaises(ValueError):
            p.select_cases(family, cases, {})

    def test_type_contract(self):
        self.assertFalse(p.type_matches(False, "integer"))
        self.assertFalse(p.type_matches(float("nan"), "number"))
        self.assertTrue(p.type_matches(None, "nullable_string"))

    def test_file_hash_drift_blocks(self):
        with tempfile.TemporaryDirectory(prefix="pce-runner-contract-") as directory:
            path = Path(directory) / "synthetic.txt"
            path.write_text("contract fixture", encoding="utf-8")
            with self.assertRaises(ValueError):
                p.verify_hashes({str(path):"wrong"})

    def test_comparator_bool_blank_zero(self):
        compare = self.modules["differential"].compare_result
        for a,b in (({"type":"boolean","value":False},{"type":"number","value":0}),({"type":"blank","value":None},{"type":"text","value":""})):
            self.assertEqual(compare(a,b,{})["status"], "FAIL")

    def test_comparator_rounding_retains_delta(self):
        result = self.modules["differential"].compare_result({"type":"number","value":1.23400000001},{"type":"number","value":1.234},{"comparison":"TYPED_SOURCE_DISPLAY_EXACT_WITH_RAW_DELTA","precision":3})
        self.assertEqual((result["status"],result["raw_numeric_delta"]), ("PASS","1E-11"))

    def test_comparator_integer_exact(self):
        self.assertEqual(self.modules["differential"].compare_result({"type":"number","value":1.1},{"type":"number","value":1},{"comparison":"TYPED_INTEGER_EXACT"})["status"], "FAIL")

    def test_no_business_escalation_assignment(self):
        text = (p.ROOT / "package_support.py").read_text("utf-8")
        self.assertNotIn('row["classification"] = "USER_DECISION_REQUIRED"', text)
        self.assertNotIn('row["classification"] = "SOURCE_BUSINESS_ISSUE"', text)

    def test_ps5_encoding_and_batch_launch(self):
        for name in ("native_excel_runner.ps1", "run_excel_golden_validation.ps1", "runner_common.ps1"):
            self.assertTrue((p.ROOT / name).read_bytes().startswith(b"\xef\xbb\xbf"))
        cmd = (p.ROOT / "RUN_EXCEL_GOLDEN_VALIDATION.cmd").read_bytes()
        self.assertIn(b'WindowsPowerShell\\v1.0\\powershell.exe', cmd)
        self.assertIn(b'"%~dp0run_excel_golden_validation.ps1"', cmd)
        self.assertNotIn(b"RunAs", cmd)
        self.assertIn(b"\r\n", cmd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
