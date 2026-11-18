"""Synthetic, isolated ProductionPlan lifecycle regressions; no formal order data."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate

from masterdata.models import Material
from procurement.models import InventoryBalance, Warehouse
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Role,
    RolePermission, User, UserRoleScopeAssignment,
)
from workflow_runtime.models import BusinessStateTransition

from . import services
from .models import (
    Demand, MasterProductionScheduleRun, MasterProductionScheduleLine,
    MaterialRequirementsPlanningRun, MaterialRequirementProposal, MPSDemandAllocation,
    PlanningRequirement, ProductionPlan, PurchasePlan,
)
from .views import SupplyPlanConfirmView


class ProductionPlanStateInitializationTests(TestCase):
    action_code = "planning.production_plan.confirm"

    def setUp(self):
        self.company = Company.objects.create(code="MP-STATE", name="生产计划状态隔离测试公司")
        self.department = Department.objects.create(
            company=self.company, code="MP-STATE", name="生产计划状态测试部", is_active=True,
        )
        self.user = User.objects.create_user(
            username="production_plan_state_test", password="test-only",
            real_name="生产计划状态测试员", company_id=self.company.pk, is_active=True,
        )
        self.material = Material.objects.create(
            code="MP-STATE-MAT", name="生产计划状态测试自制件", unit="件", material_type="finished",
            company_id=self.company.pk, is_active=True, is_purchased=False, is_produced=True,
        )
        warehouse = Warehouse.objects.create(
            code="MP-STATE-WH", name="生产计划状态测试仓", company_id=self.company.pk, is_active=True,
        )
        self.balance = InventoryBalance.objects.create(
            warehouse=warehouse, material=self.material, quantity=Decimal("2"),
        )
        self.authorization = {
            "allowed": True, "decisionCode": "ALLOWED", "roleCodes": ["MP_STATE_TEST"],
            "permissionCodes": [self.action_code], "authoritySource": "ISOLATED_TEST_AUTHORIZATION",
        }
        # The shared initializer constructs a draft synthetic Demand. Production confirmation
        # must not advance this upstream object or the calculated Requirement it produces.
        self.demand = services.create_business_object_with_initial_state(
            model=Demand, initial_state="draft", demand_no="DM-MP-STATE",
            source_type="manual_demand", source_document_type="ManualDemand",
            source_document_id="mp-state-test", source_document_no="DM-MP-STATE",
            material=self.material, required_qty=Decimal("5"), required_date=date(2026, 10, 20),
            department=self.department, reason="独立合成夹具，不承接正式订单", created_by=self.user,
        )
        self.requirement, _ = services.calculate_requirement(
            user=self.user, demand_id=self.demand.pk,
            authorization={**self.authorization, "permissionCodes": ["planning.requirement.calculate"]},
        )

    def confirm(self):
        return services.confirm_supply_plan(
            user=self.user, requirement_id=self.requirement.pk, authorization=self.authorization,
        )

    @staticmethod
    def rows(model):
        return list(model.objects.order_by("pk").values())

    def protected_snapshot(self):
        return {
            model._meta.label: self.rows(model)
            for model in (
                Demand, PlanningRequirement, Material, InventoryBalance, Warehouse, PurchasePlan,
                MasterProductionScheduleRun, MasterProductionScheduleLine, MPSDemandAllocation,
                MaterialRequirementsPlanningRun, MaterialRequirementProposal,
            )
        }

    def state_snapshot(self):
        return {
            **self.protected_snapshot(),
            **{
                model._meta.label: self.rows(model)
                for model in (ProductionPlan, OrganizationOperatingAuditRecord, BusinessStateTransition)
            },
        }

    def production_history(self):
        return list(BusinessStateTransition.objects.filter(
            object_type="ProductionPlan",
        ).order_by("version", "pk"))

    def production_audits(self):
        return list(OrganizationOperatingAuditRecord.objects.filter(
            target_type="ProductionPlan", action_code=self.action_code,
        ).order_by("pk"))

    def assert_no_production_writes(self):
        self.assertEqual(ProductionPlan.objects.count(), 0)
        self.assertEqual(self.production_history(), [])
        self.assertEqual(self.production_audits(), [])

    def assert_no_dml(self, captured):
        writes = [query["sql"] for query in captured.captured_queries if query["sql"].lstrip().upper().startswith(
            ("INSERT", "UPDATE", "DELETE", "REPLACE"),
        )]
        self.assertEqual(writes, [])

    def assert_actual_write_rollback(self, helper_name, fail_call=1):
        before = self.state_snapshot()
        original = getattr(services, helper_name)
        calls = []

        def write_then_fail(**kwargs):
            result = original(**kwargs)
            calls.append(result)
            if len(calls) == fail_call:
                self.assertTrue(ProductionPlan.objects.exists())
                if helper_name == "record_audit":
                    self.assertTrue(OrganizationOperatingAuditRecord.objects.filter(pk=result.pk).exists())
                if helper_name in {"record_projected_business_transition", "transition_business_object"}:
                    self.assertTrue(BusinessStateTransition.objects.filter(pk=result.pk).exists())
                raise RuntimeError("injected after actual production state-chain write")
            return result

        with patch.object(services, helper_name, side_effect=write_then_fail):
            with self.assertRaisesRegex(RuntimeError, "injected after actual"):
                self.confirm()
        self.assertEqual(len(calls), fail_call)
        self.assertEqual(self.state_snapshot(), before)
        self.assert_no_production_writes()

    def test_draft_is_legal_and_legacy_model_default_is_preserved(self):
        field = ProductionPlan._meta.get_field("status")
        self.assertEqual(list(field.choices), [
            ("draft", "草稿"), ("confirmed", "已确认"), ("released", "已下达"), ("closed", "已关闭"),
        ])
        self.assertEqual(field.default, "confirmed")
        self.assertEqual(field.clean("draft", ProductionPlan()), "draft")

    def test_confirmation_persists_two_real_audits_and_contiguous_state_history(self):
        plan, confirmation_audit = self.confirm()
        plan.refresh_from_db()
        self.assertEqual(plan.status, "confirmed")
        history = self.production_history()
        audits = self.production_audits()
        self.assertEqual(len(history), 2)
        self.assertEqual(len(audits), 2)
        self.assertNotEqual(audits[0].pk, audits[1].pk)
        self.assertEqual(confirmation_audit.pk, audits[1].pk)
        self.assertEqual([(row.source_state, row.target_state, row.version) for row in history], [
            ("", "draft", 1), ("draft", "confirmed", 2),
        ])
        for event, audit in zip(history, audits):
            with self.subTest(version=event.version):
                self.assertEqual(event.object_type, "ProductionPlan")
                self.assertEqual(event.object_id, plan.pk)
                self.assertEqual(event.action_code, self.action_code)
                self.assertEqual(event.operator_id, self.user.pk)
                self.assertEqual(event.audit_reference, f"OrganizationOperatingAuditRecord:{audit.pk}")
                self.assertIsNotNone(event.timestamp)
                self.assertTrue(event.reason.strip())
                self.assertIn(self.requirement.requirement_no, event.reason)
                self.assertIn(plan.plan_no, event.reason)
                self.assertEqual(audit.target_type, event.object_type)
                self.assertEqual(audit.target_id, event.object_id)
                self.assertEqual(audit.target_label, plan.plan_no)
                self.assertEqual(audit.action_code, event.action_code)
                self.assertEqual(audit.actor_id, event.operator_id)
                self.assertEqual(audit.organization_id, self.company.pk)
                self.assertTrue(audit.reason.strip())
                self.assertLessEqual(audit.created_at, event.timestamp)
                self.assertEqual(audit.before_snapshot["state"]["status"], event.source_state)
                self.assertEqual(audit.after_snapshot["state"]["status"], event.target_state)
                self.assertEqual(audit.after_snapshot["state"]["sourceRequirementId"], self.requirement.pk)
                self.assertEqual(audit.after_snapshot["state"]["demandId"], self.demand.pk)
                self.assertEqual(audit.after_snapshot["actor"]["account"], self.user.username)
                self.assertEqual(audit.after_snapshot["authorization"], self.authorization)

    def test_real_persisted_draft_precedes_confirmed_transition(self):
        checkpoints = []
        original_create = services.create_business_object_with_initial_state
        original_transition = services.transition_business_object

        def observe_initialization(**kwargs):
            self.assertIs(kwargs["model"], ProductionPlan)
            self.assertEqual(kwargs["initial_state"], "draft")
            self.assertNotIn("status", kwargs)
            plan = original_create(**kwargs)
            self.assertEqual(ProductionPlan.objects.get(pk=plan.pk).status, "draft")
            self.assertEqual(self.production_history(), [])
            checkpoints.append("draft_created")
            return plan

        def observe_confirmation(**kwargs):
            plan = kwargs["business_object"]
            self.assertEqual(ProductionPlan.objects.get(pk=plan.pk).status, "draft")
            self.assertEqual(kwargs["source_state"], "draft")
            self.assertEqual(kwargs["target_state"], "confirmed")
            self.assertIsNone(kwargs["version_field"])
            self.assertEqual(len(self.production_history()), 1)
            self.assertEqual(self.production_history()[0].target_state, "draft")
            self.assertEqual(len(self.production_audits()), 2)
            checkpoints.append("draft_initialized")
            return original_transition(**kwargs)

        with patch.object(services, "create_business_object_with_initial_state", side_effect=observe_initialization):
            with patch.object(services, "transition_business_object", side_effect=observe_confirmation):
                self.confirm()
        self.assertEqual(checkpoints, ["draft_created", "draft_initialized"])

    def test_existing_number_quantity_and_source_contract_are_preserved(self):
        plan, _ = self.confirm()
        self.assertEqual(plan.plan_no, f"MP{date.today():%Y%m%d}{plan.pk:04d}")
        self.assertEqual(plan.planning_requirement_id, self.requirement.pk)
        self.assertEqual(plan.material_id, self.material.pk)
        self.assertEqual(plan.planned_qty, Decimal("3"))
        self.assertEqual(plan.required_date, self.requirement.required_date)
        self.assertEqual(plan.source_type, "PlanningRequirement")
        self.assertEqual(plan.source_id, str(self.requirement.pk))
        self.assertEqual(plan.planning_engine, "DIRECT_V1")
        self.assertEqual(plan.run_batch, f"DIRECT-{self.requirement.pk}")
        self.assertEqual(plan.source_version, "DIRECT-V1")
        self.assertEqual(plan.mps_source_id, "")
        self.assertEqual(plan.mrp_source_id, "")
        self.assertEqual(plan.confirmed_by_id, self.user.pk)
        self.assertEqual(ProductionPlan.objects.filter(planning_requirement=self.requirement).count(), 1)

    def test_demand_requirement_material_inventory_and_downstream_remain_unchanged(self):
        before = self.protected_snapshot()
        self.confirm()
        self.assertEqual(self.protected_snapshot(), before)
        self.requirement.refresh_from_db()
        self.demand.refresh_from_db()
        self.assertEqual(self.requirement.status, "calculated")
        self.assertEqual(self.demand.status, "draft")

    def test_replay_returns_existing_fact_without_sql_writes_or_history_changes(self):
        plan, _ = self.confirm()
        before = self.state_snapshot()
        with patch.object(services, "create_business_object_with_initial_state", side_effect=AssertionError("recreated")):
            with patch.object(services, "record_audit", side_effect=AssertionError("reaudited")):
                with CaptureQueriesContext(connection) as captured:
                    repeated, audit = self.confirm()
        self.assertEqual(repeated.pk, plan.pk)
        self.assertIsNone(audit)
        self.assert_no_dml(captured)
        self.assertEqual(self.state_snapshot(), before)

    def test_legacy_plan_replay_has_no_backfill_or_business_replay(self):
        # Explicit historical fixture only; never invoked against a persisted business database.
        legacy = ProductionPlan.objects.create(
            plan_no="MP-STATE-LEGACY", planning_requirement=self.requirement, material=self.material,
            planned_qty=Decimal("3"), required_date=self.requirement.required_date,
            source_id=str(self.requirement.pk), status="confirmed", confirmed_by=self.user,
        )
        before = self.state_snapshot()
        with CaptureQueriesContext(connection) as captured:
            repeated, audit = self.confirm()
        self.assertEqual(repeated.pk, legacy.pk)
        self.assertIsNone(audit)
        self.assert_no_dml(captured)
        self.assertEqual(self.state_snapshot(), before)
        self.assertEqual(self.production_history(), [])
        self.assertEqual(self.production_audits(), [])

    def test_actual_initial_creation_failure_rolls_back(self):
        self.assert_actual_write_rollback("create_business_object_with_initial_state")

    def test_actual_initial_audit_failure_rolls_back(self):
        self.assert_actual_write_rollback("record_audit")

    def test_actual_initial_bst_failure_rolls_back(self):
        self.assert_actual_write_rollback("record_projected_business_transition")

    def test_actual_confirmation_audit_failure_rolls_back(self):
        self.assert_actual_write_rollback("record_audit", fail_call=2)

    def test_actual_confirmation_bst_failure_rolls_back_status_and_history(self):
        self.assert_actual_write_rollback("transition_business_object")

    def test_missing_requirement_is_blocked_before_write(self):
        before = self.state_snapshot()
        with self.assertRaises(services.PlanningBusinessError) as caught:
            services.confirm_supply_plan(
                user=self.user, requirement_id=self.requirement.pk + 100, authorization=self.authorization,
            )
        self.assertEqual(caught.exception.code, "REQUIREMENT_NOT_FOUND")
        self.assertEqual(caught.exception.http_status, 404)
        self.assertEqual(self.state_snapshot(), before)
        self.assert_no_production_writes()

    def test_zero_net_requirement_is_blocked_before_write(self):
        # Isolated fixture mutation, not part of the service's allowed writes.
        PlanningRequirement.objects.filter(pk=self.requirement.pk).update(net_required_qty=Decimal("0"))
        before = self.state_snapshot()
        with self.assertRaises(services.PlanningBusinessError) as caught:
            self.confirm()
        self.assertEqual(caught.exception.code, "NET_REQUIREMENT_ZERO")
        self.assertEqual(self.state_snapshot(), before)
        self.assert_no_production_writes()

    def test_ambiguous_supply_is_blocked_without_guessing_or_write(self):
        PlanningRequirement.objects.filter(pk=self.requirement.pk).update(supply_type="ambiguous")
        before = self.state_snapshot()
        with self.assertRaises(services.PlanningBusinessError) as caught:
            self.confirm()
        self.assertEqual(caught.exception.code, "SUPPLY_TYPE_AMBIGUOUS")
        self.assertEqual(self.state_snapshot(), before)
        self.assert_no_production_writes()

    def api_confirm(self):
        request = APIRequestFactory().post(
            f"/api/planning/requirements/{self.requirement.pk}/confirm-plan/", {}, format="json",
        )
        force_authenticate(request, user=self.user)
        return SupplyPlanConfirmView.as_view()(request, requirement_id=self.requirement.pk)

    def test_existing_api_denies_actor_without_production_permission_and_is_zero_write(self):
        before = self.state_snapshot()
        with CaptureQueriesContext(connection) as captured:
            response = self.api_confirm()
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data["data"]["authorization"]["allowed"])
        self.assert_no_dml(captured)
        self.assertEqual(self.state_snapshot(), before)
        self.assert_no_production_writes()

    def test_existing_api_preserves_authorization_confirmed_response_and_idempotence(self):
        role = Role.objects.create(code="MP_STATE_API_TEST", name="生产计划状态API测试角色")
        permission, _ = Permission.objects.get_or_create(
            code=self.action_code, defaults={"name": "生产计划确认测试权限", "module": "PLAN"},
        )
        RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=self.user, role=role, organization=self.company, scope_code="ORGANIZATION",
            active=True, version=1, business_hash="mp-state-api-test",
        )
        protected_before = self.protected_snapshot()
        response = self.api_confirm()
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertTrue(data["authorization"]["allowed"])
        self.assertFalse(data["idempotent"])
        self.assertEqual(data["plan"]["type"], "ProductionPlan")
        self.assertEqual(data["plan"]["status"], "confirmed")
        self.assertEqual(data["plan"]["statusLabel"], "已确认")
        self.assertEqual(data["auditId"], self.production_audits()[1].pk)
        self.assertEqual(self.protected_snapshot(), protected_before)
        before_replay = self.state_snapshot()
        with CaptureQueriesContext(connection) as captured:
            repeated = self.api_confirm()
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.data["data"]["plan"], data["plan"])
        self.assertTrue(repeated.data["data"]["idempotent"])
        self.assertIsNone(repeated.data["data"]["auditId"])
        self.assert_no_dml(captured)
        self.assertEqual(self.state_snapshot(), before_replay)
