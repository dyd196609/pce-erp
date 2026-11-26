from django.test import TestCase

from masterdata.group3_comparison_runtime import _source, build_group3_comparison
from pde.models import BOMItem, BOMVersion, ProductBOM, Routing, RoutingStep, RoutingVersion
from system.models import Process


class Group3ComparisonRuntimeTests(TestCase):
    def test_source_snapshot_has_full_business_counts_and_stable_linkage_guard(self):
        source = _source()
        self.assertTrue(source["readOnly"])
        self.assertEqual(len(source["operationRows"]), 32)
        self.assertEqual(len(source["routingRows"]), 42)
        self.assertEqual(len(source["routingStepRows"]), 1137)
        self.assertEqual(len(source["engineeringBreakdown"]["rows"]), 71)
        self.assertEqual(source["engineeringBreakdown"]["linkageTo08"], "NO_STABLE_KEY")
        self.assertEqual(
            sorted({row["operationName"] for row in source["routingStepRows"]} - {row["sourceName"] for row in source["operationRows"]}),
            ["拉丝"],
        )

    def test_all_group3_previews_are_read_only(self):
        before = {
            "operation": Process.objects.count(),
            "bom": ProductBOM.objects.count(),
            "bomVersion": BOMVersion.objects.count(),
            "bomItem": BOMItem.objects.count(),
            "routing": Routing.objects.count(),
            "routingVersion": RoutingVersion.objects.count(),
            "routingStep": RoutingStep.objects.count(),
        }
        facts = {entity: build_group3_comparison(entity, 1) for entity in ("operations", "boms", "routings", "routing-steps")}
        after = {
            "operation": Process.objects.count(),
            "bom": ProductBOM.objects.count(),
            "bomVersion": BOMVersion.objects.count(),
            "bomItem": BOMItem.objects.count(),
            "routing": Routing.objects.count(),
            "routingVersion": RoutingVersion.objects.count(),
            "routingStep": RoutingStep.objects.count(),
        }
        self.assertEqual(before, after)
        self.assertTrue(all(item["productionManufacturingMasterDataWriteCount"] == 0 for item in facts.values()))
        self.assertEqual(facts["routings"]["proposedCount"], 42)
        self.assertEqual(facts["routing-steps"]["unresolvedOperationMappingCount"], 3)
        self.assertEqual(facts["boms"]["engineeringLinkage"], "NOT_REQUIRED_TO_08")
        self.assertTrue(facts["boms"]["userValidated"])
        self.assertEqual(facts["boms"]["hierarchyCardCount"], 31)
        self.assertEqual(facts["boms"]["ready"], "STRUCTURE_USER_VALIDATED_CALCULATION_REQUIRED")
        self.assertEqual(facts["boms"]["linkageAudit"]["status"], "SUPERSEDED_NOT_REQUIRED")

    def test_area_is_a_basis_not_an_auto_filled_uom(self):
        area_rows = [row for row in _source()["operationRows"] if row["sourceCalculationExpression"] == "面积"]
        self.assertTrue(area_rows)
        self.assertTrue(all(row["proposedCalculationBasis"] == "AREA" for row in area_rows))
        self.assertTrue(all(row["proposedCalculationUom"] == "" for row in area_rows))
