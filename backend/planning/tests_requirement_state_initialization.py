"""Isolated service regressions; no formal order or persistent database fixtures."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from masterdata.models import Material
from procurement.models import InventoryBalance, Warehouse
from system.models import Company, Department, OrganizationOperatingAuditRecord, User
from workflow_runtime.models import BusinessStateTransition

from . import services
from .models import Demand, PlanningRequirement, ProductionPlan, PurchasePlan


class PlanningRequirementStateInitializationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="PCE", name="计划状态隔离测试公司")
        self.department = Department.objects.create(
            company=self.company, code="REQ-STATE", name="计划状态测试部", is_active=True,
        )
        self.user = User.objects.create_user(
            username="requirement_state_test", password="test-only", real_name="计划状态测试员",
            company_id=self.company.pk, is_active=True,
        )
        self.material = Material.objects.create(
            code="REQ-STATE-MAT", name="计划状态测试采购件", unit="件", material_type="auxiliary",
            company_id=self.company.pk, is_active=True, is_purchased=True, is_produced=False,
        )
        warehouse = Warehouse.objects.create(
            code="REQ-STATE-WH", name="计划状态测试仓", company_id=self.company.pk, is_active=True,
        )
        self.balance = InventoryBalance.objects.create(
            warehouse=warehouse, material=self.material, quantity=Decimal("2"),
        )
        self.demand = Demand.objects.create(
            demand_no="DM-REQ-STATE", source_type="manual_demand",
            source_document_type="ManualDemand", source_document_id="state-test",
            source_document_no="DM-REQ-STATE", material=self.material,
            required_qty=Decimal("5"), required_date=date(2026, 10, 20),
            department=self.department, reason="独立合成夹具，不承接正式订单",
            status="confirmed", created_by=self.user,
        )
        self.authorization = {
            "allowed": True, "decisionCode": "ALLOWED",
            "roleCodes": ["PLAN_STATE_TEST"],
            "permissionCodes": ["planning.requirement.calculate"],
            "authoritySource": "ISOLATED_TEST_AUTHORIZATION",
        }

    def calculate(self):
        return services.calculate_requirement(
            user=self.user, demand_id=self.demand.pk, authorization=self.authorization,
        )

    @staticmethod
    def rows(model):
        return list(model.objects.order_by("pk").values())

    def protected_snapshot(self):
        return {
            model._meta.label: self.rows(model)
            for model in (Demand, Material, InventoryBalance, PurchasePlan, ProductionPlan)
        }

    def state_snapshot(self):
        return {
            **self.protected_snapshot(),
            **{
                model._meta.label: self.rows(model)
                for model in (PlanningRequirement, OrganizationOperatingAuditRecord, BusinessStateTransition)
            },
        }

    def assert_empty_state_writes(self):
        self.assertEqual(PlanningRequirement.objects.count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)
        self.assertEqual(BusinessStateTransition.objects.count(), 0)

    def assert_failure_after_real_write_rolls_back(self, helper_name, fail_call=1):
        before = self.state_snapshot()
        original = getattr(services, helper_name)
        calls = []

        def write_then_fail(**kwargs):
            result = original(**kwargs)
            calls.append(result)
            if len(calls) == fail_call:
                self.assertTrue(PlanningRequirement.objects.exists())
                raise RuntimeError("injected after actual state-chain write")
            return result

        with patch.object(services, helper_name, side_effect=write_then_fail):
            with self.assertRaisesRegex(RuntimeError, "injected after actual"):
                self.calculate()
        self.assertEqual(len(calls), fail_call)
        self.assertEqual(self.state_snapshot(), before)
        self.assert_empty_state_writes()

    def test_draft_is_legal_while_legacy_default_and_other_choices_are_preserved(self):
        field = PlanningRequirement._meta.get_field("status")
        self.assertEqual(list(field.choices), [
            ("draft", "草稿"), ("calculated", "已计算"),
            ("confirmed", "已确认"), ("closed", "已关闭"),
        ])
        self.assertEqual(field.default, "calculated")
        self.assertEqual(field.clean("draft", PlanningRequirement()), "draft")

    def test_calculation_persists_two_audits_and_complete_authoritative_state_history(self):
        protected_before = self.protected_snapshot()
        row, calculation_audit = self.calculate()
        row.refresh_from_db()
        self.assertEqual(row.status, "calculated")
        self.assertEqual(row.demand_id, self.demand.pk)
        self.assertEqual(row.material_id, self.material.pk)
        self.assertEqual(row.created_by_id, self.user.pk)
        self.assertEqual(row.required_date, self.demand.required_date)
        self.assertEqual(row.demand_qty, Decimal("5"))
        self.assertEqual(row.available_qty, Decimal("2"))
        self.assertEqual(row.net_required_qty, Decimal("3"))
        self.assertEqual(row.supply_type, "purchase")
        self.assertTrue(row.requirement_no.startswith("REQ"))
        self.assertFalse(row.requirement_no.startswith("TMP"))
        self.assertEqual(row.calculation_facts["formula"], "max(demandQty - availableInventory, 0)")
        self.assertEqual(row.calculation_facts["inventorySource"], "procurement.InventoryBalance")
        self.assertEqual(row.calculation_facts["inventorySemantic"], "AGGREGATE_SNAPSHOT_NOT_ORDER_ALLOCATION")
        self.assertEqual(row.calculation_facts["inventoryAllocationStatus"], "UNALLOCATED_SNAPSHOT")
        self.assertEqual(row.calculation_facts["inventoryWriteCount"], 0)
        self.assertEqual(row.calculation_facts["materialSupplyFacts"], {
            "isPurchased": True, "isProduced": False,
        })
        history = list(BusinessStateTransition.objects.order_by("version", "pk"))
        audits = list(OrganizationOperatingAuditRecord.objects.order_by("pk"))
        self.assertEqual(len(history), 2)
        self.assertEqual(len(audits), 2)
        self.assertEqual(calculation_audit.pk, audits[1].pk)
        self.assertNotEqual(audits[0].pk, audits[1].pk)
        self.assertEqual([(event.source_state, event.target_state, event.version) for event in history], [
            ("", "draft", 1), ("draft", "calculated", 2),
        ])
        for event, audit in zip(history, audits):
            with self.subTest(version=event.version):
                self.assertEqual(event.object_type, "PlanningRequirement")
                self.assertEqual(event.object_id, row.pk)
                self.assertEqual(event.operator_id, self.user.pk)
                self.assertEqual(event.action_code, "planning.requirement.calculate")
                self.assertEqual(event.audit_reference, f"OrganizationOperatingAuditRecord:{audit.pk}")
                self.assertIsNotNone(event.timestamp)
                self.assertTrue(event.reason.strip())
                self.assertIn(self.demand.demand_no, event.reason)
                self.assertIn(row.requirement_no, event.reason)
                self.assertEqual(audit.target_type, event.object_type)
                self.assertEqual(audit.target_id, event.object_id)
                self.assertEqual(audit.target_label, row.requirement_no)
                self.assertEqual(audit.action_code, event.action_code)
                self.assertEqual(audit.actor_id, event.operator_id)
                self.assertEqual(audit.organization_id, self.company.pk)
                self.assertTrue(audit.reason.strip())
                self.assertLessEqual(audit.created_at, event.timestamp)
                self.assertEqual(audit.before_snapshot["state"]["status"], event.source_state)
                self.assertEqual(audit.after_snapshot["state"]["status"], event.target_state)
                self.assertEqual(audit.after_snapshot["state"]["demandId"], self.demand.pk)
                self.assertEqual(audit.after_snapshot["actor"]["account"], self.user.username)
                self.assertEqual(audit.after_snapshot["authorization"], self.authorization)
        self.assertEqual(self.protected_snapshot(), protected_before)

    def test_real_initialization_is_draft_before_calculated_transition(self):
        checkpoints = []
        original_create = services.create_business_object_with_initial_state
        original_transition = services.transition_business_object

        def observe_initialization(**kwargs):
            self.assertIs(kwargs["model"], PlanningRequirement)
            self.assertEqual(kwargs["initial_state"], "draft")
            self.assertNotIn("status", kwargs)
            row = original_create(**kwargs)
            self.assertEqual(PlanningRequirement.objects.get(pk=row.pk).status, "draft")
            self.assertEqual(BusinessStateTransition.objects.count(), 0)
            checkpoints.append("draft_created")
            return row

        def observe_calculation_transition(**kwargs):
            row = kwargs["business_object"]
            self.assertEqual(PlanningRequirement.objects.get(pk=row.pk).status, "draft")
            self.assertIsNone(kwargs["version_field"])
            self.assertEqual(BusinessStateTransition.objects.get().target_state, "draft")
            self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 2)
            checkpoints.append("draft_initialized")
            return original_transition(**kwargs)

        with patch.object(services, "create_business_object_with_initial_state", side_effect=observe_initialization):
            with patch.object(services, "transition_business_object", side_effect=observe_calculation_transition):
                self.calculate()
        self.assertEqual(checkpoints, ["draft_created", "draft_initialized"])

    def test_calculation_does_not_auto_confirm_or_touch_a_draft_demand(self):
        self.demand.status = "draft"
        self.demand.save(update_fields=["status", "updated_at"])
        before = self.protected_snapshot()
        row, _ = self.calculate()
        self.assertEqual(row.status, "calculated")
        self.assertEqual(self.protected_snapshot(), before)
        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, "draft")

    def test_replay_returns_existing_fact_with_zero_writes_and_no_new_history(self):
        row, _ = self.calculate()
        before = self.state_snapshot()
        with patch.object(services, "create_business_object_with_initial_state", side_effect=AssertionError("recreated")):
            with patch.object(services, "record_audit", side_effect=AssertionError("reaudited")):
                repeated, audit = self.calculate()
        self.assertEqual(repeated.pk, row.pk)
        self.assertIsNone(audit)
        self.assertEqual(self.state_snapshot(), before)

    def test_legacy_requirement_replay_does_not_backfill_or_replay_state_events(self):
        legacy = PlanningRequirement.objects.create(
            requirement_no="REQ-STATE-LEGACY", demand=self.demand, material=self.material,
            demand_qty=Decimal("5"), available_qty=Decimal("2"), net_required_qty=Decimal("3"),
            required_date=self.demand.required_date, supply_type="purchase", status="calculated",
            calculation_facts={"legacyFixture": True}, created_by=self.user,
        )
        before = self.state_snapshot()
        repeated, audit = self.calculate()
        self.assertEqual(repeated.pk, legacy.pk)
        self.assertIsNone(audit)
        self.assertEqual(self.state_snapshot(), before)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)
        self.assertEqual(BusinessStateTransition.objects.count(), 0)

    def test_actual_initial_creation_failure_rolls_back(self):
        self.assert_failure_after_real_write_rolls_back("create_business_object_with_initial_state")

    def test_actual_initial_audit_failure_rolls_back(self):
        self.assert_failure_after_real_write_rolls_back("record_audit")

    def test_actual_initial_transition_failure_rolls_back(self):
        self.assert_failure_after_real_write_rolls_back("record_projected_business_transition")

    def test_actual_calculation_audit_failure_rolls_back(self):
        self.assert_failure_after_real_write_rolls_back("record_audit", fail_call=2)

    def test_actual_calculated_transition_failure_rolls_back(self):
        self.assert_failure_after_real_write_rolls_back("transition_business_object")

    def test_missing_demand_fails_before_any_state_or_audit_write(self):
        before = self.state_snapshot()
        with self.assertRaises(services.PlanningBusinessError) as caught:
            services.calculate_requirement(
                user=self.user, demand_id=self.demand.pk + 100, authorization=self.authorization,
            )
        self.assertEqual(caught.exception.code, "DEMAND_NOT_FOUND")
        self.assertEqual(caught.exception.http_status, 404)
        self.assertEqual(self.state_snapshot(), before)
        self.assert_empty_state_writes()

    def test_net_requirement_zero_still_has_initialized_calculation_history_and_no_plan(self):
        self.balance.quantity = Decimal("10")
        self.balance.save(update_fields=["quantity", "updated_at"])
        before = self.protected_snapshot()
        row, _ = self.calculate()
        self.assertEqual(row.net_required_qty, Decimal("0"))
        self.assertEqual(row.status, "calculated")
        self.assertEqual(BusinessStateTransition.objects.count(), 2)
        self.assertEqual(self.protected_snapshot(), before)

    def test_existing_supply_semantics_are_preserved_without_guessing(self):
        for purchased, produced, expected in (
            (False, True, "production"), (False, False, "ambiguous"),
        ):
            with self.subTest(purchased=purchased, produced=produced):
                material = Material.objects.create(
                    code=f"REQ-STATE-{int(purchased)}-{int(produced)}", name="供应语义隔离测试件",
                    unit="件", material_type="finished", company_id=self.company.pk, is_active=True,
                    is_purchased=purchased, is_produced=produced,
                )
                demand = Demand.objects.create(
                    demand_no=f"DM-STATE-{int(purchased)}-{int(produced)}", source_type="manual_demand",
                    source_document_type="ManualDemand", source_document_id="supply-state-test",
                    source_document_no="state-test", material=material, required_qty=Decimal("1"),
                    required_date=self.demand.required_date, department=self.department,
                    reason="现有供应语义回归", status="confirmed", created_by=self.user,
                )
                before = self.protected_snapshot()
                row, _ = services.calculate_requirement(
                    user=self.user, demand_id=demand.pk, authorization=self.authorization,
                )
                self.assertEqual(row.supply_type, expected)
                self.assertEqual(row.net_required_qty, Decimal("1"))
                self.assertEqual(row.status, "calculated")
                self.assertEqual(self.protected_snapshot(), before)
