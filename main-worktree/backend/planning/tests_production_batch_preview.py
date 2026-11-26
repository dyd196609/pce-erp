from datetime import datetime
from decimal import Decimal
from unittest import TestCase

from planning.production_batch_preview import (
    MemberInput, preview_transition, resolve_transition_mode,
    validate_batch_allocations,
)


class ProductionBatchAllocationPreviewTests(TestCase):
    def test_order_can_split_across_multiple_batches(self):
        result = validate_batch_allocations(
            {"I1": 100},
            [
                {"batchNo": "B1", "salesOrderId": "O1", "items": [{"salesOrderItemId": "I1", "allocatedQuantity": 30}]},
                {"batchNo": "B2", "salesOrderId": "O1", "items": [{"salesOrderItemId": "I1", "allocatedQuantity": 70}]},
            ],
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["items"][0]["remainingQuantity"], "0")

    def test_unexplained_over_allocation_and_cross_order_mix_are_rejected(self):
        result = validate_batch_allocations(
            {"I1": 10},
            [{"batchNo": "B1", "salesOrderId": "O1", "items": [
                {"salesOrderItemId": "I1", "salesOrderId": "O2", "allocatedQuantity": 11},
            ]}],
        )
        self.assertEqual(
            {item["code"] for item in result["errors"]},
            {"CROSS_ORDER_BATCH_NOT_ALLOWED", "UNEXPLAINED_OVER_ALLOCATION"},
        )


class TransitionPreviewTests(TestCase):
    def setUp(self):
        self.start = datetime.fromisoformat("2026-09-08T08:00:00")
        self.members = [
            MemberInput("FAST", Decimal("8"), Decimal("8"), self.start, Decimal("8")),
            MemberInput("SLOW", Decimal("24"), Decimal("8"), self.start, Decimal("8")),
        ]

    def preview(self, default="GENERAL", override=None, members=None, required=None):
        return preview_transition(
            production_batch_no="B1", operation_code="ANY-CODE",
            operation_default=default, routing_step_override=override,
            members=members or self.members, required_member_ids=required or ["FAST", "SLOW"],
        )

    def test_general_flows_each_member_at_own_completion(self):
        result = self.preview()
        self.assertNotEqual(result["members"][0]["nextEarliestStartTime"], result["members"][1]["nextEarliestStartTime"])

    def test_different_capacity_speeds_change_own_completion(self):
        result = self.preview(members=[
            MemberInput("FAST", Decimal("8"), Decimal("16"), self.start, Decimal("8")),
            MemberInput("SLOW", Decimal("8"), Decimal("4"), self.start, Decimal("8")),
        ])
        self.assertLess(result["members"][0]["calculatedCompletionTime"], result["members"][1]["calculatedCompletionTime"])

    def test_kitting_uses_slowest_completion_for_every_member(self):
        result = self.preview(override="KITTING")
        self.assertEqual(result["slowestMember"], "SLOW")
        self.assertTrue(all(row["nextEarliestStartTime"] == result["batchKittingCompletionTime"] for row in result["members"]))
        self.assertNotEqual(result["members"][0]["calculatedCompletionTime"], result["batchKittingCompletionTime"])

    def test_scope_excludes_non_participating_member(self):
        extra = self.members + [MemberInput("NOT_REQUIRED", Decimal("1000"), Decimal("1"), self.start, Decimal("8"), participates_in_step=False)]
        result = self.preview(override="KITTING", members=extra)
        self.assertEqual(result["requiredCount"], 2)
        self.assertEqual(result["slowestMember"], "SLOW")

    def test_missing_member_capacity_and_calendar_block_without_fake_gate_date(self):
        result = self.preview(
            default="KITTING",
            members=[MemberInput("FAST", Decimal("8"), None, self.start, None)],
            required=["FAST", "MISSING"],
        )
        self.assertEqual(result["planningStatus"], "PLANNING_BLOCKED")
        self.assertNotIn("batchKittingCompletionTime", result)
        self.assertIn("FAST:STANDARD_CAPACITY", result["missingRequiredData"])
        self.assertIn("FAST:WORKING_CALENDAR", result["missingRequiredData"])
        self.assertIn("MISSING:REQUIRED_MEMBER", result["missingRequiredData"])

    def test_slower_member_changes_gate(self):
        first = self.preview(default="KITTING")
        changed = self.preview(
            default="KITTING",
            members=[
                MemberInput("FAST", Decimal("40"), Decimal("8"), self.start, Decimal("8")),
                self.members[1],
            ],
        )
        self.assertNotEqual(first["slowestMember"], changed["slowestMember"])

    def test_configuration_switch_changes_result_without_code_or_name_rules(self):
        self.assertEqual(resolve_transition_mode("GENERAL", None).value, "GENERAL")
        self.assertEqual(resolve_transition_mode("GENERAL", "KITTING").value, "KITTING")
        general = self.preview(default="GENERAL")
        kitting = self.preview(default="GENERAL", override="KITTING")
        back = self.preview(default="KITTING", override="GENERAL")
        self.assertIsNone(general["batchKittingCompletionTime"])
        self.assertIsNotNone(kitting["batchKittingCompletionTime"])
        self.assertIsNone(back["batchKittingCompletionTime"])

    def test_mixed_general_then_kitting_propagates_member_times_into_gate(self):
        general = self.preview(default="GENERAL")
        second_members = [
            MemberInput(
                row["memberId"], Decimal("8"), Decimal("8"),
                datetime.fromisoformat(row["nextEarliestStartTime"]), Decimal("8"),
            ) for row in general["members"]
        ]
        kitting = self.preview(default="GENERAL", override="KITTING", members=second_members)
        self.assertEqual(kitting["kittingStatus"], "READY")
        self.assertTrue(all(row["nextEarliestStartTime"] == kitting["batchKittingCompletionTime"] for row in kitting["members"]))

    def test_missing_staffing_blocks_planning(self):
        result = self.preview(members=[
            MemberInput("FAST", Decimal("8"), Decimal("8"), self.start, Decimal("8"), staffing_factor=None),
            self.members[1],
        ])
        self.assertEqual(result["planningStatus"], "PLANNING_BLOCKED")
        self.assertIn("FAST:STAFFING", result["missingRequiredData"])
