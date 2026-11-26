import os
import json
import sys
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = SOURCE_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django

django.setup()

from pde import calculation_batch_reuse as service


class PdeCalculationBatchLinearContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = service.load_source()
        cls.door_rows = [row for row in cls.source["realRows"] if row["sheet"] == "房门单"]

    def test_six_projects_are_connected_for_each_applicable_source(self):
        expected = {"横线净长", "竖线净长", "横线开料长", "竖线开料长", "横线条数", "竖线条数"}
        self.assertTrue(self.door_rows)
        for row in self.door_rows:
            results = service.evaluate_linear_row(row)
            self.assertEqual(expected, {item["project"] for item in results})
            self.assertTrue(all(item["resultScope"] == "linear-continuation" for item in results))

    def test_current_sources_reconcile_without_using_comparison_outputs(self):
        for row in self.door_rows:
            for item in service.evaluate_linear_row(row):
                self.assertEqual("calculated", item["state"], item)
                self.assertTrue(item["matched"], item)
                self.assertEqual(Decimal("0"), Decimal(item["difference"]), item)
                self.assertFalse(item["expectedResultsUsedAsInputs"])

    def test_quantity_is_applied_once_and_real_zero_is_preserved(self):
        row = self.door_rows[0]
        original = row["cells"][f"M{row['row']}"]["value"]
        row["cells"][f"M{row['row']}"]["value"] = 3
        try:
            results = {item["project"]: item for item in service.evaluate_linear_row(row)}
        finally:
            row["cells"][f"M{row['row']}"]["value"] = original
        self.assertEqual(Decimal("12"), Decimal(results["竖线条数"]["value"]))
        self.assertEqual(Decimal("3"), Decimal(results["横线条数"]["value"]))
        self.assertEqual(Decimal("2205"), Decimal(results["竖线净长"]["value"]))
        row["cells"][f"M{row['row']}"]["value"] = 0
        try:
            zero_results = {item["project"]: item for item in service.evaluate_linear_row(row)}
        finally:
            row["cells"][f"M{row['row']}"]["value"] = original
        self.assertEqual("calculated", zero_results["竖线条数"]["state"])
        self.assertEqual(Decimal("0"), Decimal(zero_results["竖线条数"]["value"]))
        self.assertEqual(Decimal("0"), Decimal(zero_results["横线条数"]["value"]))

    def test_missing_mode_is_not_defaulted_and_net_lengths_remain(self):
        row = self.door_rows[0]
        key = f"AZ{row['row']}"
        original = row["cells"][key]["value"]
        row["cells"][key]["value"] = None
        try:
            results = {item["project"]: item for item in service.evaluate_linear_row(row)}
        finally:
            row["cells"][key]["value"] = original
        self.assertEqual("calculated", results["竖线净长"]["state"])
        self.assertEqual("calculated", results["横线净长"]["state"])
        self.assertEqual("missing", results["竖线条数"]["state"])
        self.assertEqual("missing", results["横线条数"]["state"])

    def test_cut_length_gap_does_not_remove_net_length(self):
        row = self.door_rows[0]
        key = f"AP{row['row']}"
        original = row["cells"][key]["value"]
        row["cells"][key]["value"] = 2000
        try:
            results = {item["project"]: item for item in service.evaluate_linear_row(row)}
        finally:
            row["cells"][key]["value"] = original
        self.assertEqual("calculated", results["竖线净长"]["state"])
        self.assertEqual("missing", results["竖线开料长"]["state"])
        self.assertIsNone(results["竖线开料长"]["value"])

    def test_source_comparison_change_does_not_change_system_value(self):
        row = self.door_rows[0]
        key = f"AT{row['row']}"
        original = row["cells"][key]["value"]
        baseline = {item["project"]: item for item in service.evaluate_linear_row(row)}["竖线净长"]
        row["cells"][key]["value"] = original + 17
        try:
            changed = {item["project"]: item for item in service.evaluate_linear_row(row)}["竖线净长"]
        finally:
            row["cells"][key]["value"] = original
        self.assertEqual(baseline["value"], changed["value"])
        self.assertFalse(changed["matched"])
        self.assertEqual(Decimal("-17"), Decimal(changed["difference"]))

    def test_full_scope_preserves_original_segment_and_separates_extension(self):
        keys = [f"{row['sheet']}:{row['row']}" for row in self.source["realRows"]]
        result = service.run_batch(keys)
        segments = {item["key"]: item for item in result["segments"]}
        original_count = sum(len(service.evaluate_row(row)) for row in self.source["realRows"])
        extension_count = sum(len(service.evaluate_linear_row(row)) for row in self.source["realRows"])
        self.assertEqual(original_count, segments["original"]["resultCount"])
        self.assertEqual(extension_count, segments["linear-continuation"]["resultCount"])
        self.assertEqual(original_count + extension_count, len(result["rows"]))
        self.assertEqual(340, segments["original"]["resultCount"])
        self.assertEqual(335, segments["original"]["counts"]["对账一致"])
        self.assertEqual(5, segments["original"]["missingCount"])
        self.assertEqual(len(self.door_rows) * 6, segments["linear-continuation"]["resultCount"])
        self.assertEqual(0, segments["linear-continuation"]["missingCount"])

    def test_saved_confirmed_inputs_close_five_gaps_and_recalculate_row_68(self):
        keys = [f"{row['sheet']}:{row['row']}" for row in self.source["realRows"]]
        draft_rows = [
            {"id": "SOURCE-XLSX-三合一生产单-9", "sourceSheet": "三合一生产单", "sourceRow": 9,
             "edgeMode": "白坯", "visibleCondition": "白坯"},
            {"id": "SOURCE-XLSX-三合一生产单-36", "sourceSheet": "三合一生产单", "sourceRow": 36,
             "edgeMode": "四边", "visibleCondition": "双"},
            {"id": "SOURCE-XLSX-三合一生产单-60", "sourceSheet": "三合一生产单", "sourceRow": 60,
             "edgeMode": "白坯", "visibleCondition": "白坯"},
            {"id": "SOURCE-XLSX-三合一生产单-68", "sourceSheet": "三合一生产单", "sourceRow": 68,
             "edgeMode": "一长", "visibleCondition": "单"},
        ]

        result = service.run_batch(keys, draft_rows)
        indexed = {(row["row"], row["column"]): row for row in result["rows"] if row["sheet"] == "三合一生产单"}

        self.assertEqual(388, len(result["rows"]))
        self.assertEqual(0, result["segments"][0]["missingCount"])
        self.assertEqual(6, result["confirmedInputChangeCount"])
        self.assertEqual(6, result["confirmedOutputCount"])
        self.assertEqual(382, result["counts"]["对账一致"])
        self.assertEqual(6, result["counts"]["用户确认条件已计算"])
        expected = {
            (9, "Q"): "0.000000", (9, "R"): "0.000000", (9, "S"): "0.120000",
            (36, "Q"): "2.964000", (36, "R"): "4.930000", (36, "S"): "1.482000",
            (60, "Q"): "0.000000", (60, "R"): "0.000000", (60, "S"): "0.321875",
            (68, "Q"): "0.122000", (68, "R"): "2.440000", (68, "S"): "0.122000",
        }
        for key, value in expected.items():
            self.assertEqual(value, indexed[key]["value"], key)
        for key in ((9, "R"), (36, "Q"), (36, "R"), (60, "R"), (68, "Q"), (68, "R")):
            self.assertEqual("用户确认条件已计算", indexed[key]["statusLabel"], key)

    def _accepted_comparison_fixture(self):
        profile = json.loads(service.ACCEPTED_DIFFERENCE_PROFILE_PATH.read_text(encoding="utf-8"))
        rows = []
        for accepted in profile["confirmedDifferences"]:
            rows.append({
                "id": accepted["id"], "sourceKey": accepted["sourceKey"],
                "project": accepted["project"], "state": "calculated",
                "value": accepted["currentValue"], "expected": accepted["independentValue"],
                "difference": accepted["difference"], "unit": accepted["unit"],
                "sourceCell": accepted["sourceCell"], "expression": accepted["expression"],
                "ruleVersion": accepted["ruleVersion"], "matched": False,
                "statusLabel": "发现差异",
            })
        rows.extend({
            "id": f"consistent:{index}", "state": "calculated", "value": "1.000000",
            "expected": "1", "difference": "0.000000", "matched": True,
            "statusLabel": "对账一致",
        } for index in range(309))
        rows.extend({
            "id": f"no-comparison:{index}", "state": "calculated", "value": "1.000000",
            "expected": None, "difference": None, "matched": False,
            "statusLabel": "已计算，缺独立对照",
        } for index in range(68))
        design_inputs = [
            {"sourceKey": "房门单:11", "designItemNo": "SO202609180003-DES-01-SRC-0003"},
            {"sourceKey": "三合一生产单:10", "designItemNo": "SO202609180003-DES-03-SRC-0014"},
            {"sourceKey": "三合一生产单:68", "designItemNo": "SO202609180003-DES-03-SRC-0070"},
        ]
        changes = [
            {"designItemNo": "SO202609180003-DES-01-SRC-0003", "sourceKey": "房门单:11",
             "field": "designWidth", "before": 938, "after": "940.000000"},
            {"designItemNo": "SO202609180003-DES-03-SRC-0014", "sourceKey": "三合一生产单:10",
             "field": "designLength", "before": 51, "after": "52.000000"},
            {"designItemNo": "SO202609180003-DES-03-SRC-0070", "sourceKey": "三合一生产单:68",
             "field": "visibleCondition", "before": "白坯", "after": "单"},
        ]
        return profile, rows, design_inputs, changes

    def test_historical_acceptance_requires_all_eleven_exact_row_facts(self):
        profile, rows, design_inputs, changes = self._accepted_comparison_fixture()
        summary, regression = service._classify_current_comparison(
            rows, design_inputs, changes, profile,
        )
        self.assertEqual(388, summary["closureTotal"])
        self.assertEqual(309, summary["consistent"])
        self.assertEqual(68, summary["noIndependentComparison"])
        self.assertEqual(11, summary["confirmedDesignChangeDifferences"])
        self.assertEqual(0, summary["unexplainedDifferences"])
        self.assertEqual(0, summary["missing"])
        self.assertTrue(regression["match"])
        self.assertEqual("HISTORICAL_ACCEPTED_RESULT_MATCH", regression["statusCode"])
        self.assertEqual(11, len(regression["matchedDifferenceIds"]))
        self.assertTrue(all(
            row["statusLabel"] == "已确认设计变更差异"
            for row in rows[:11]
        ))

    def test_historical_acceptance_does_not_hide_a_new_or_changed_difference(self):
        profile, rows, design_inputs, changes = self._accepted_comparison_fixture()
        changed = deepcopy(rows)
        changed[0]["value"] = "921.000000"
        changed[0]["difference"] = "3.000000"
        summary, regression = service._classify_current_comparison(
            changed, design_inputs, changes, profile,
        )
        self.assertEqual(10, summary["confirmedDesignChangeDifferences"])
        self.assertEqual(1, summary["unexplainedDifferences"])
        self.assertFalse(regression["match"])
        self.assertEqual("HISTORICAL_ACCEPTED_RESULT_MISMATCH", regression["statusCode"])
        self.assertEqual("NEW_UNEXPLAINED_DIFFERENCE", changed[0]["comparisonClassification"])
        self.assertEqual(["currentValue", "difference"], regression["mismatchedAcceptedRows"][0]["failedChecks"])


if __name__ == "__main__":
    unittest.main()
