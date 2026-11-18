"""BOM source-current gate distinguishes main calculations from saved consumers.

The existing synthetic order fixture is reused in a RAM test database.  These
tests read the real calculation QuerySet and projection; they do not review,
publish, or modify any deployed source or business proof.
"""
from types import SimpleNamespace as NS
from unittest.mock import patch

from django.test import TestCase

from . import bom_version_release_preflight as bom
from .models import EngineeringCalculationRecord
from .tests_order_calculation_bom_closure import OrderCalculationBomClosureTests


class BomMainCalculationCurrentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        OrderCalculationBomClosureTests.setUpTestData.__func__(cls)
        cls.main = cls._calculation(scope="order_engineering", revision=2)

    @classmethod
    def _calculation(cls, *, scope, revision=1, status="completed", supersedes=None):
        return EngineeringCalculationRecord.objects.create(
            company=cls.company, source_record=cls.source,
            sales_order_item=cls.item, engineering_instance=cls.instance,
            calculation_no=f"BOM-SCOPE-{EngineeringCalculationRecord.objects.count()}",
            rule_set_version="BOM-MAIN-SCOPE-SYNTHETIC", scope=scope,
            revision=revision, status=status, supersedes=supersedes,
            origin_calculation=cls.main if scope == "fact_extension" else None,
            trace={"baselineReference": {"id": 1, "snapshotHash": "fixture-baseline"}},
        )

    def _project(self, calculation=None, *, bom_version="FIXTURE-BOM", status="draft"):
        calculation = calculation or self.main
        baseline = NS(pk=1, status="confirmed", company_id=self.company.pk,
            sales_order_id=self.order.pk, snapshot_hash="fixture-baseline",
            baseline_no="FIXTURE-BASELINE", get_status_display=lambda: "已确认")
        version = NS(pk=999, bom_id=999, bom=NS(company_id=self.company.pk),
            bom_version=bom_version, revision=1, status=status,
            approval_state="not_submitted", get_status_display=lambda: "草稿",
            source_calculation=calculation, order_engineering_instance=self.instance,
            items=NS(all=lambda: []))
        # Only unrelated approval/lineage projections are isolated.  Calculation
        # storage and scope filtering remain the actual Django ORM read.
        readiness = {
            "workflowRuntime": {"statusCode": "READY", "blocker": {}},
            "segregationOfDuties": {"statusCode": "READY", "blockerCode": "",
                "reviewActors": [], "releaseActors": [], "separatedActorPairCount": 1},
            "formalExecutionReady": True,
        }
        with patch.object(bom.OrderEngineeringBaseline, "objects") as baselines, \
                patch.object(bom, "_partition_bom_version_conflicts", return_value=([], [], [])), \
                patch.object(bom, "_eligible_release_actors", return_value=[]), \
                patch.object(bom, "control_chain_readiness", return_value=readiness), \
                patch.object(bom, "workflow_projection", return_value={
                    "workflow": None, "decisions": [], "projectionConsistent": False,
                    "projectionState": "not_submitted"}), \
                patch.object(bom, "release_readback", return_value={"released": False}):
            baselines.filter.return_value.first.return_value = baseline
            baselines.filter.return_value.order_by.return_value = [baseline]
            return bom.project_bom_version_release_preflight(version, material_details=[])

    def _current_gate(self, calculation=None):
        projection = self._project(calculation)
        gate = next(row for row in projection["gates"] if row["code"] == "CALCULATION_CURRENT")
        return gate, projection["calculation"]

    def test_later_operation_requirement_does_not_replace_main(self):
        self._calculation(scope="operation_requirement", revision=20)
        gate, fact = self._current_gate()
        self.assertEqual(gate["statusCode"], "PASS")
        self.assertEqual(fact["laterCandidateCount"], 0)

    def test_later_fact_extension_does_not_replace_main(self):
        self._calculation(scope="fact_extension", revision=20)
        gate, fact = self._current_gate()
        self.assertEqual(gate["statusCode"], "PASS")
        self.assertEqual(fact["laterCandidateCount"], 0)

    def test_later_validation_does_not_replace_main(self):
        self._calculation(scope="validation", revision=20)
        gate, fact = self._current_gate()
        self.assertEqual(gate["statusCode"], "PASS")
        self.assertEqual(fact["laterCandidateCount"], 0)

    def test_newer_main_still_blocks_for_every_existing_active_status(self):
        for status in ("completed", "prepared", "running"):
            with self.subTest(status=status):
                candidate = self._calculation(scope="order_engineering", revision=3,
                    status=status, supersedes=self.main)
                gate, fact = self._current_gate()
                self.assertEqual(gate["statusCode"], "FAIL")
                self.assertGreaterEqual(fact["laterCandidateCount"], 1)
                self.assertEqual(candidate.scope, "order_engineering")

    def test_later_created_main_with_same_revision_still_blocks(self):
        self._calculation(scope="order_engineering", revision=self.main.revision)
        gate, fact = self._current_gate()
        self.assertEqual(gate["statusCode"], "FAIL")
        self.assertEqual(fact["laterCandidateCount"], 1)

    def test_non_main_cannot_be_selected_as_current_bom_source(self):
        for scope in ("operation_requirement", "fact_extension", "validation"):
            with self.subTest(scope=scope):
                candidate = self._calculation(scope=scope, revision=20)
                gate, fact = self._current_gate(candidate)
                self.assertEqual(gate["statusCode"], "FAIL")
                self.assertFalse(fact["isCurrent"])

    def test_failed_or_incomplete_selected_main_remains_blocked(self):
        for status in ("draft", "prepared", "running", "failed", "superseded", "obsolete"):
            with self.subTest(status=status):
                self.main.status = status
                gate, fact = self._current_gate()
                self.assertEqual(gate["statusCode"], "FAIL")
                self.assertFalse(fact["isCurrent"])

    def test_new_bom_labels_and_current_state_never_refer_to_old_calc3(self):
        for status in ("draft", "reviewed"):
            with self.subTest(status=status):
                projection = self._project(bom_version="CALC-1327", status=status)
                self.assertNotIn("CALC-3", str(projection))
                self.assertIn(f"CALC-1327当前为{status} / not_submitted", projection["firstBlockerLabel"])
                for code in ("IDENTITY_UNIQUE", "BUSINESS_STATE_TRANSITION", "IDEMPOTENT_RELEASE"):
                    gate = next(row for row in projection["gates"] if row["code"] == code)
                    self.assertIn("CALC-1327", gate["label"] + gate["evidence"])
