"""RAM-only distinction between independent source consumption and step handoff.

Reuses the existing upstream fixture's two explicit document proof stubs. Native
manufacturing generation/release, saved internal facts, source identities and
consumer validation run without stubbing their validators or route mapping.
This is not evidence of a real human document/manufacturing publication.
"""
from unittest.mock import patch

from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings

from masterdata.models import MasterDataWriteRequest
from planning.models import Demand, PlanningRequirement, ProductionPlan
from sales.manufacturing_input import resolve_order_engineered_input
from system.models import OrganizationOperatingAuditRecord, Permission, RolePermission
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state

from . import tests_engineering_version_handoff_upstream as upstream
from .manufacturing_output_generation_service import (
    ManufacturingOutputError, generation_readback, validate_selected_output,
)
from .models import EngineeringDocumentVersion, PlanStepVersionBinding, ProductManufacturingOutput, RoutingStep, RoutingVersion
from .plan_step_context_service import PlanStepContextError, route_mapping
from .plan_step_version_handoff_service import PlanStepVersionHandoffService
from .tests_manufacturing_output_generation import SCOPE


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE)
class IndependentManufacturingSourceTests(TestCase):
    _generate = upstream.EngineeringVersionHandoffUpstreamTests._generate
    _release = upstream.EngineeringVersionHandoffUpstreamTests._release
    _successor_sources = upstream.EngineeringVersionHandoffUpstreamTests._successor_sources
    _counts = upstream.EngineeringVersionHandoffUpstreamTests._counts

    def setUp(self):
        upstream.EngineeringVersionHandoffUpstreamTests.setUp(self)
        self.old, _ = self._generate()
        self._release(self.old, "independent-root-release")
        self.old_before = ProductManufacturingOutput.objects.filter(pk=self.old.pk).values().get()
        self.old_audits = list(OrganizationOperatingAuditRecord.objects.filter(
            target_type="ProductManufacturingOutput", target_id=self.old.pk).values().order_by("pk"))
        baseline, calculation, bom, _, _ = self._successor_sources()
        # A valid, independently authored route adds a required step. It is not
        # declared to be a complete topology-preserving old-plan step migration.
        route = RoutingVersion.objects.create(routing=self.category_routing,
            routing_version="INDEPENDENT-SOURCE-V3", revision=3, status="draft")
        self.old_step = self.old.routing_version.steps.get()
        self.first = RoutingStep.objects.create(routing_version=route, sequence=1,
            operation=self.old_step.operation, predecessor_step=self.old_step,
            operation_parameters={"applicability": {"mode": "MANDATORY"}})
        RoutingStep.objects.create(routing_version=route, sequence=2,
            operation=self.old_step.operation, predecessor_sequences=[1],
            operation_parameters={"applicability": {"mode": "MANDATORY"}})
        RoutingVersion.objects.filter(pk=route.pk).update(status="released")
        route.refresh_from_db()
        route.full_clean()
        document = EngineeringDocumentVersion.objects.create(document=self.order_document,
            document_name="独立新制造来源资料", document_version="INDEPENDENT-SOURCE-V3",
            release_subject_type="ORDER_ENGINEERED_PRODUCT", order_engineering_instance=self.instance,
            order_engineering_baseline=baseline, engineering_calculation=calculation,
            related_bom=bom, related_routing=route, status="released")
        document.full_clean()
        self.new, _ = self._generate(document, self.old, "independent-new-output")
        self._release(self.new, "independent-new-release")

    def _old_plan(self):
        demand = create_business_object_with_initial_state(model=Demand, initial_state="draft",
            demand_no="INDEPENDENT-OLD-DEMAND", source_type="sales_order", source_document_type="SalesOrderItem",
            source_document_id=str(self.order_item.pk), source_document_no=self.order.order_no,
            sales_order_item=self.order_item, manufacturing_output=self.old, material=self.finished,
            required_qty=self.order_item.quantity, required_date=self.order_item.required_date,
            department=self.department, reason="RAM retained old source", created_by=self.executor)
        requirement = PlanningRequirement.objects.create(requirement_no="INDEPENDENT-OLD-REQUIREMENT",
            demand=demand, material=self.finished, demand_qty=demand.required_qty, available_qty=0,
            net_required_qty=demand.required_qty, required_date=demand.required_date,
            supply_type="production", status="confirmed", created_by=self.executor)
        return ProductionPlan.objects.create(plan_no="INDEPENDENT-OLD-PLAN",
            planning_requirement=requirement, material=self.finished, planned_qty=requirement.net_required_qty,
            required_date=requirement.required_date, source_id=str(requirement.pk),
            confirmed_by=self.executor, status="confirmed")

    def _assert_old_unchanged(self):
        self.assertEqual(self.old_before, ProductManufacturingOutput.objects.filter(pk=self.old.pk).values().get())
        self.assertEqual(self.old_audits, list(OrganizationOperatingAuditRecord.objects.filter(
            pk__in=[row["id"] for row in self.old_audits]).values().order_by("pk")))

    def test_01_independent_different_topology_consumes_exact_source_and_preserves_old_plan(self):
        plan = self._old_plan()
        frozen = {model.__name__: list(model.objects.filter(pk=pk).values()) for model, pk in (
            (ProductionPlan, plan.pk), (PlanningRequirement, plan.planning_requirement_id),
            (Demand, plan.planning_requirement.demand_id))}
        counts, changes = self._counts(), connection.connection.total_changes
        new = resolve_order_engineered_input(self.order_item, output_id=self.new.pk)
        old = resolve_order_engineered_input(self.order_item, output_id=self.old.pk)
        self.assertEqual(new["output"].pk, self.new.pk)
        self.assertEqual(new["facts"]["engineeringCalculationId"], self.new.engineering_calculation_id)
        self.assertEqual(new["facts"]["orderEngineeringBaselineId"], self.new.order_engineering_baseline_id)
        self.assertEqual(new["facts"]["routingVersionId"], self.new.routing_version_id)
        self.assertEqual(old["output"].pk, self.old.pk)
        self.assertTrue(validate_selected_output(self.new, user=self.executor)["releaseReadback"]["completed"])
        self.assertEqual(counts, self._counts())
        self.assertEqual(changes, connection.connection.total_changes)
        for model, pk in ((ProductionPlan, plan.pk), (PlanningRequirement, plan.planning_requirement_id),
                (Demand, plan.planning_requirement.demand_id)):
            self.assertEqual(frozen[model.__name__], list(model.objects.filter(pk=pk).values()))
        self._assert_old_unchanged()

    def test_02_real_old_plan_step_handoff_still_rejects_changed_complete_topology(self):
        for code in ("production.engineering.calculation.view", "planning.view"):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code, "module": "PDE"})
            RolePermission.objects.get_or_create(role=self.executing_role, permission=permission)
        plan = self._old_plan()
        before, changes = self._counts(), connection.connection.total_changes
        with self.assertRaises(PlanStepContextError) as caught:
            route_mapping(self.old.routing_version, self.new.routing_version)
        self.assertEqual(caught.exception.code, "STEP_VERSION_TOPOLOGY_CHANGED")
        with patch("pde.plan_step_version_handoff_service._impact",
                side_effect=AssertionError("Changed topology must stop before impact")):
            with self.assertRaises(PlanStepContextError) as caught:
                PlanStepVersionHandoffService.preview(user=self.executor, production_plan_id=plan.pk,
                    root_step_id=self.old_step.pk, manufacturing_output_id=self.new.pk,
                    target_step_id=self.first.pk, impact_basis={})
        self.assertEqual(caught.exception.code, "STEP_VERSION_TOPOLOGY_CHANGED")
        self.assertEqual(PlanStepVersionBinding.objects.count(), 0)
        self.assertEqual(before, self._counts())
        self.assertEqual(changes, connection.connection.total_changes)
        self._assert_old_unchanged()

    def test_03_cross_source_and_revision_changes_remain_rejected(self):
        mutations = {"engineering_calculation_id": self.old.engineering_calculation_id,
            "order_engineering_baseline_id": self.old.order_engineering_baseline_id,
            "bom_version_id": self.old.bom_version_id, "routing_version_id": self.old.routing_version_id,
            "engineering_document_version_id": self.old.engineering_document_version_id,
            "revision": 3}
        for field, value in mutations.items():
            with self.subTest(field=field), transaction.atomic():
                ProductManufacturingOutput.objects.filter(pk=self.new.pk).update(**{field: value})
                with self.assertRaises(ManufacturingOutputError):
                    validate_selected_output(ProductManufacturingOutput.objects.get(pk=self.new.pk))
                transaction.set_rollback(True)
        with transaction.atomic():
            # Removing the predecessor would create a second root; the original
            # database uniqueness contract rejects it before consumer validation.
            with self.assertRaises(IntegrityError):
                ProductManufacturingOutput.objects.filter(pk=self.new.pk).update(predecessor_id=None)
            transaction.set_rollback(True)
        self._assert_old_unchanged()

    def test_04_current_company_and_published_predecessor_remain_mandatory(self):
        from types import SimpleNamespace
        with self.assertRaises(ManufacturingOutputError) as caught:
            validate_selected_output(self.new, user=SimpleNamespace(company_id=self.company.pk + 1))
        self.assertEqual(caught.exception.code, "ORDER_ENGINEERING_RELEASE_SCOPE_CONFLICT")
        with transaction.atomic():
            ProductManufacturingOutput.objects.filter(pk=self.old.pk).update(release_status="inactive")
            with self.assertRaises(ManufacturingOutputError):
                validate_selected_output(ProductManufacturingOutput.objects.get(pk=self.new.pk))
            transaction.set_rollback(True)
        self._assert_old_unchanged()

    def test_05_native_frozen_audit_ledger_and_release_history_still_fail_closed(self):
        generation = generation_readback(self.new)
        generated = OrganizationOperatingAuditRecord.objects.get(pk=generation["auditId"])
        released = OrganizationOperatingAuditRecord.objects.get(action_code="pde.manufacturing_output.release",
            target_type="ProductManufacturingOutput", target_id=self.new.pk)
        ledger = MasterDataWriteRequest.objects.get(pk=generation["writeRequestId"])
        transition = BusinessStateTransition.objects.get(object_type="ProductManufacturingOutput",
            object_id=self.new.pk, target_state="released_to_manufacturing")
        changes = {
            "generationFrozenFingerprint": lambda: OrganizationOperatingAuditRecord.objects.filter(pk=generated.pk).update(
                after_snapshot={**generated.after_snapshot, "sourceFingerprint": "0" * 64}),
            "releaseFrozenSource": lambda: OrganizationOperatingAuditRecord.objects.filter(pk=released.pk).update(
                after_snapshot={**released.after_snapshot, "sourceSnapshot": {"bom_version_id": self.old.bom_version_id}}),
            "generationLedgerResult": lambda: MasterDataWriteRequest.objects.filter(pk=ledger.pk).update(
                result={**ledger.result, "auditId": -1}),
            "releaseHistoryAction": lambda: BusinessStateTransition.objects.filter(pk=transition.pk).update(
                action_code="unrelated.action"),
        }
        for field, mutate in changes.items():
            with self.subTest(field=field), transaction.atomic():
                mutate()
                with self.assertRaises(ManufacturingOutputError):
                    validate_selected_output(ProductManufacturingOutput.objects.get(pk=self.new.pk))
                transaction.set_rollback(True)
        self._assert_old_unchanged()
