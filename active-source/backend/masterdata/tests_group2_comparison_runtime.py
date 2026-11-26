from django.test import TestCase

from masterdata.group2_comparison_runtime import _snapshot, build_group2_comparison
from masterdata.models import Material


class Group2ComparisonRuntimeTests(TestCase):
    def test_source_snapshot_excludes_formula_zero_rows_and_keeps_placeholders_visible(self):
        summary = _snapshot()["summary"]
        self.assertEqual(summary["materialSourceRecordCount"], 193)
        self.assertEqual(summary["materialCandidateCount"], 190)
        self.assertEqual(summary["invalidMaterialSourceCount"], 3)
        self.assertEqual(summary["productOrderLineCount"], 37)
        self.assertEqual(summary["distinctProductCandidateCount"], 3)
        self.assertEqual(summary["distinctEngineeredMaterialCodeCount"], 8)
        evidence = _snapshot()["engineeringIdentityEvidence"]
        self.assertEqual(evidence["linkageTo08"], "NO_STABLE_KEY")
        self.assertEqual(len(evidence["rows"]), 71)
        self.assertTrue(all(row["productName"] not in {"", "0"} for row in evidence["rows"]))

    def test_material_comparison_is_read_only_and_classifies_history(self):
        source = next(row for row in _snapshot()["materialRows"] if row["sourceValidity"] == "VALID")
        Material.objects.create(
            company_id=1,
            code=source["sourceCode"],
            name=source["sourceName"],
            specification=source["specification"],
            material_type="semi",
            is_produced=True,
        )
        Material.objects.create(
            company_id=1,
            code="MT004",
            name="无线鼠标",
            specification="开发历史样例",
            material_type="fixed_asset",
            is_purchased=True,
        )
        before = Material.objects.count()
        facts = build_group2_comparison("materials", 1)
        self.assertEqual(facts["productionBusinessWriteCount"], 0)
        self.assertEqual(facts["exactMatchCount"], 1)
        self.assertEqual(facts["matchCount"], 1)
        self.assertEqual(facts["testHistoricalCount"], 1)
        self.assertEqual(Material.objects.count(), before)
        mouse = next(row for row in facts["formalRows"] if row["formalCode"] == "MT004")
        self.assertEqual(mouse["classification"], "TEST_HISTORICAL")
        self.assertEqual(len(facts["missingSourceRows"]), 192)
        self.assertTrue(facts["historicalSummary"])

    def test_empty_product_tables_keep_category_and_product_identity_separate(self):
        facts = build_group2_comparison("products", 1)
        self.assertEqual(facts["sourceRecordCount"], 37)
        self.assertEqual(facts["distinctSourceCandidateCount"], 3)
        self.assertEqual(facts["formalRecordCount"], 0)
        self.assertEqual(facts["proposedMappingCount"], 0)
        self.assertEqual(facts["missingSourceCount"], 37)
        self.assertTrue(facts["manualValidationReady"])
        self.assertEqual(
            [(row["sourceCategory"], row["sourceRowCount"]) for row in facts["categoryPreviewRows"]],
            [("房门", 7), ("柜体", 22), ("饰面", 8)],
        )
        self.assertEqual(facts["productDefinitionPreviewRows"], [])
        self.assertEqual(len(facts["orderEngineeredPreviewRows"]), 37)
        self.assertEqual(len(facts["unableToDetermineRows"]), 37)
        self.assertEqual(facts["engineeringIdentityEvidence"]["recordCount"], 71)
        self.assertEqual(facts["productionBusinessWriteCount"], 0)

    def test_version_configuration_status_stays_missing(self):
        facts = build_group2_comparison("product-versions-configurations", 1)
        self.assertEqual(facts["productVersion"]["formalRecordCount"], 0)
        self.assertEqual(facts["productConfiguration"]["formalRecordCount"], 0)
        self.assertEqual(facts["productionBusinessWriteCount"], 0)
        self.assertEqual(len(facts["versionReadinessRows"]), 3)
        self.assertTrue(all(not row["sourceVersionFactPresent"] for row in facts["versionReadinessRows"]))
        self.assertTrue(all(row["currentSelection"] == "PENDING USER DECISION" for row in facts["configurationReadinessRows"]))
        self.assertTrue(all(row["options"] == [] for row in facts["configurationReadinessRows"]))
