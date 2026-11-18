from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from .quantity_semantics import planning_quantity_facts


class PlanningQuantitySemanticsDo3Tests(SimpleTestCase):
    def requirement(self, **facts):
        return SimpleNamespace(
            available_qty=Decimal("2"),
            net_required_qty=Decimal("4"),
            calculation_facts={"inventorySource": "procurement.InventoryBalance", **facts},
        )

    def plan(self, status="confirmed", quantity="4"):
        return SimpleNamespace(status=status, net_required_qty=Decimal(quantity))

    def test_inventory_snapshot_is_not_order_allocation(self):
        facts = planning_quantity_facts(
            demand_qty=Decimal("6"), requirement=self.requirement(), plan=self.plan(),
        )
        self.assertEqual(facts["inventorySnapshotQty"], "2")
        self.assertEqual(facts["effectivePlanQty"], "4")
        self.assertEqual(facts["pendingNetPlanQty"], "0")
        self.assertIsNone(facts["uncoveredDemandQty"])
        self.assertEqual(facts["orderCoverageStatus"], "INVENTORY_ALLOCATION_UNCONFIRMED")
        self.assertEqual(facts["netRequirementPlanCoverageStatus"], "NET_REQUIREMENT_FULLY_PLANNED")

    def test_draft_plan_does_not_count_as_effective_plan(self):
        facts = planning_quantity_facts(
            demand_qty=Decimal("6"), requirement=self.requirement(), plan=self.plan("draft"),
        )
        self.assertEqual(facts["recordedPlanQty"], "4")
        self.assertEqual(facts["effectivePlanQty"], "0")
        self.assertEqual(facts["pendingNetPlanQty"], "4")
        self.assertEqual(facts["netRequirementPlanCoverageStatus"], "NET_REQUIREMENT_PENDING_PLAN")

    def test_legacy_allocation_assertion_is_not_authoritative_order_coverage(self):
        facts = planning_quantity_facts(
            demand_qty=Decimal("6"),
            requirement=self.requirement(
                inventoryAllocationStatus="ALLOCATED", allocatedInventoryQty="2",
            ),
            plan=self.plan(),
        )
        self.assertEqual(facts["inventorySnapshotQty"], "2")
        self.assertEqual(facts["effectivePlanQty"], "4")
        self.assertEqual(facts["inventoryAllocationStatus"], "ALLOCATION_PROOF_UNVERIFIED")
        self.assertEqual(facts["inventoryAllocationProofStatus"], "UNPROVEN")
        self.assertIsNone(facts["effectiveInventoryCoverageQty"])
        self.assertIsNone(facts["uncoveredDemandQty"])
        self.assertEqual(facts["orderCoverageStatus"], "INVENTORY_ALLOCATION_UNCONFIRMED")

    def test_unproved_allocation_contents_cannot_change_quantity_facts(self):
        for value in ("-2", "999999999999999", "not-a-number", {"quantity": "2"}):
            with self.subTest(value=value):
                facts = planning_quantity_facts(demand_qty=Decimal("6"),
                    requirement=self.requirement(inventoryAllocationStatus="ALLOCATED",
                        allocatedInventoryQty=value), plan=self.plan())
                self.assertIsNone(facts["effectiveInventoryCoverageQty"])
                self.assertIsNone(facts["uncoveredDemandQty"])
                self.assertEqual(facts["netRequiredQty"], "4")
                self.assertEqual(facts["orderCoverageStatus"], "INVENTORY_ALLOCATION_UNCONFIRMED")

    def test_plan_over_net_requirement_is_exposed(self):
        facts = planning_quantity_facts(
            demand_qty=Decimal("6"), requirement=self.requirement(), plan=self.plan(quantity="5"),
        )
        self.assertEqual(facts["overPlannedQty"], "1")
        self.assertEqual(facts["netRequirementPlanCoverageStatus"], "OVER_PLANNED")
