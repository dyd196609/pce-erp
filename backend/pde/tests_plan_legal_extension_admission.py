"""SIMULATED_FOR_TEST only: legal extension admission and immutable plan bridges.

All fixture/configuration/generation/allocation writes belong to the disposable
test database. No acceptance database, date preview or APS entry is used.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
from unittest.mock import patch

from django.db import connection, transaction
from django.test import TestCase

from planning.models import Demand, PlanningRequirement, ProductionPlan
from sales.models import SalesOrderItem
from system.models import Company, Permission, Role, RolePermission, User, UserRoleScopeAssignment
from . import operation_requirement_service as operation
from . import tests_calc4_routing_correction as correction
from . import tests_classified_fact_eor as classified
from . import tests_engineering_fact_extension as extension
from .engineering_fact_extension_service import CONTRACT, EngineeringFactExtensionService
from .manufacturing_configuration_service import CREATE, RELEASE
from .operation_requirement_correction_service import OperationRequirementCorrectionService
from .models import (EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringOperationRequirement,
    EngineeringRuleDefinition, OrderEngineeringInstance, ProductManufacturingOutput,
    ProductionPlanOperationRequirementAllocation)


class PlanLegalExtensionAdmissionTests(TestCase):
    def setUp(self):
        class Fixture(correction.Calc4RoutingCorrectionTests):
            def advance(self, obj, target, *, status_field="status"):
                if isinstance(obj, EngineeringCalculationRecord) and obj.scope == "order_engineering" and target == "completed":
                    classified.ClassifiedFactEorTests.finish_source_hashes(self, obj, list(obj.derived_facts.order_by("sequence")))
                return super().advance(obj, target, status_field=status_field)
        f = Fixture()
        f.setUp()
        self.f = f
        # The actual graph/results envelope was saved while the source was still
        # running, before its formal terminal state; no frozen source is edited.
        for code in (operation.PLAN_VIEW, CREATE, RELEASE):
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": code, "module": "PRODUCTION"})
            RolePermission.objects.get_or_create(role=f.role, permission=permission)
        identities = ("baselineId", "baselineItemId", "designItemId", "sourceAttributeId")
        config = {"strategy": "GROUP_SUM", "groupKeys": list(identities), "metadataBindings": [
            {"name": key, "sourceType": "FORMAL_SOURCE_IDENTITY", "valueField": key} for key in identities],
            "bindings": [extension.EngineeringFactExtensionTests.binding(f, "area_quantity", "opaque_area", f.producer, f.area, f.area)]}
        spec = extension.EngineeringFactExtensionTests.spec(f, [{"canonicalName": "area_quantity", "valueType": "decimal",
            "unit": f.area.code, "unitDimension": "area", "sourceType": "AGGREGATED", "required": True,
            "unitRequired": True}], "PaintingProcessAreaQuantity", "area_quantity", config)
        rules = EngineeringFactExtensionService.configure(user=f.user, reason="SIMULATED_FOR_TEST", package={
            "contractVersion": CONTRACT, "companyId": f.company.pk, "rules": [{"ruleCode": "SIM-LEGAL-EXTENSION",
                "ruleName": "Abstract formal grouped area", "version": "V2", "specification": spec}]})["ruleIds"]
        result = EngineeringFactExtensionService.derive(user=f.user, source_calculation_id=f.source_calc.pk,
            rule_ids=rules, idempotency_key="sim-legal-extension", reason="SIMULATED_FOR_TEST")
        self.extension = EngineeringCalculationRecord.objects.get(pk=result["calculationId"])
        self.facts = list(self.extension.derived_facts.order_by("sequence"))
        rule = f.make_mapping(self.facts[0], f.op_area, f.area, mode=f.mode, capacity=f.capacity,
            dynamic_source_basis=True, release=False)
        spec = deepcopy(rule.specification)
        spec["manufacturing"]["sourceSelector"]["traceEquals"] = {"contractVersion": CONTRACT}
        spec["manufacturing"]["routingContext"] = {"contractVersion": correction.ROUTE_CONTRACT,
            "routingId": f.route.pk, "routingVersionId": f.version.pk, "routingStepId": f.step.pk}
        spec["sourceEvidence"]["formalRouting"] = f.route_evidence(f.version, f.step)
        rule.specification = spec
        rule.save(update_fields=("specification",))
        f.advance(rule, "reviewed")
        f.advance(rule, "released")
        self.rule = rule
        self.requirements = []
        for fact in self.facts:
            generated = operation.OperationRequirementService.generate(user=f.user, source_calculation_id=self.extension.pk,
                source_fact_id=fact.pk, rule_id=rule.pk, idempotency_key=f"sim-legal-eor-{fact.pk}", reason="SIMULATED_FOR_TEST")
            self.requirements.append(EngineeringOperationRequirement.objects.get(pk=generated["operationRequirementId"]))
        self.plan = self.make_plan()

    def make_plan(self):
        f = self.f
        demand = f.initial(Demand, "draft", demand_no="SIM-LEGAL-DEMAND", source_type="sales_order",
            source_document_type="SalesOrder", source_document_id=str(f.order.pk), source_document_no=f.order.order_no,
            sales_order_item=f.item, manufacturing_output=f.output, material=f.item.material, required_qty=37,
            required_date=date.today(), department=f.department, reason="SIMULATED_FOR_TEST",
            acceptance_marker="SIMULATED_FOR_TEST", created_by=f.user)
        f.advance(demand, "confirmed")
        requirement = f.initial(PlanningRequirement, "draft", requirement_no="SIM-LEGAL-REQUIREMENT", demand=demand,
            material=f.item.material, demand_qty=37, available_qty=0, net_required_qty=37, required_date=date.today(),
            supply_type="production", calculation_facts={"sourceKind": "SIMULATED_FOR_TEST"}, created_by=f.user)
        f.advance(requirement, "calculated")
        f.advance(requirement, "confirmed")
        plan = f.initial(ProductionPlan, "draft", plan_no="SIM-LEGAL-PLAN", planning_requirement=requirement,
            material=f.item.material, planned_qty=37, required_date=date.today(), source_id=str(requirement.pk), confirmed_by=f.user)
        f.advance(plan, "confirmed")
        return plan

    def preview(self, *, req=None, user=None, step=None):
        return operation.OperationRequirementService.allocation_readiness(user=user or self.f.user,
            production_plan_id=self.plan.pk, operation_requirement_id=(req or self.requirements[0]).pk,
            routing_step_id=(step or self.f.step).pk)

    def allocate(self, *, req=None, user=None, step=None, key="sim-legal-allocation"):
        return operation.OperationRequirementService.allocate(user=user or self.f.user, production_plan_id=self.plan.pk,
            operation_requirement_id=(req or self.requirements[0]).pk, routing_step_id=(step or self.f.step).pk,
            idempotency_key=key, reason="SIMULATED_FOR_TEST")

    def reject_both(self, *, req=None, user=None, step=None, expected=None):
        before = self.f.full_database_snapshot()
        try:
            preview = self.preview(req=req, user=user, step=step)
        except operation.OperationRequirementError as error:
            code = error.code
        else:
            self.assertFalse(preview["ready"], preview)
            self.assertEqual(preview["businessWriteCount"], 0)
            code = preview["blockers"][0]["code"]
        with self.assertRaises(operation.OperationRequirementError) as caught:
            self.allocate(req=req, user=user, step=step, key=f"sim-rejected-{(req or self.requirements[0]).pk}")
        self.assertEqual(caught.exception.code, code)
        if expected:
            self.assertEqual(code, expected)
        self.assertEqual(self.f.full_database_snapshot(), before)
        return code

    def raw(self, obj, field, value):
        column = obj._meta.get_field(field).column
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        with connection.cursor() as cursor:
            cursor.execute(f'UPDATE "{obj._meta.db_table}" SET "{column}" = %s WHERE id = %s', [value, obj.pk])

    def test_legal_extension_preview_is_readonly_and_uses_fixed_main_calculation(self):
        before = self.f.full_database_snapshot()
        for req in self.requirements:
            preview = self.preview(req=req)
            self.assertTrue(preview["ready"], preview)
            self.assertEqual(preview["assessmentScope"], "SINGLE_REQUIREMENT")
            self.assertIsNone(preview["batchSaveAllowed"])
            self.assertFalse(preview["executionPerformed"])
            for key in ("requirementValidity", "planState", "sourceConsistency", "objectCoverage",
                        "quantityMappingBudget", "stepResourceApplicability", "saveConditions"):
                self.assertEqual(preview["checks"][key]["status"], "passed", preview)
            self.assertTrue(preview["canSave"], preview)
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_real_isolated_allocate_read_and_idempotent_snapshot_preserve_plan_and_sources(self):
        protected = {model.__name__: list(model.objects.order_by("pk").values()) for model in (
            EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringOperationRequirement,
            ProductionPlan, ProductManufacturingOutput, EngineeringRuleDefinition)}
        created = self.allocate()
        row = ProductionPlanOperationRequirementAllocation.objects.get(pk=created["allocationId"])
        self.assertEqual(row.operation_requirement.source_calculation_id, self.extension.pk)
        self.assertEqual(row.source_quantity, Decimal(37))
        self.assertEqual(row.allocated_quantity, self.requirements[0].workload_quantity)
        self.assertEqual(row.uom_id, self.f.area.pk)
        snapshot = deepcopy(row.source_snapshot)
        self.assertEqual(snapshot["planEngineeringSource"]["sourceType"], "LEGAL_EXTENSION")
        self.assertEqual(snapshot["planEngineeringSource"]["sourceEngineeringCalculationId"], self.f.source_calc.pk)
        self.assertEqual(snapshot["planEngineeringSource"]["sourceFactCalculationId"], self.extension.pk)
        self.assertEqual(snapshot["planEngineeringSource"]["sourceFactId"], self.requirements[0].source_fact_id)
        readback = operation.OperationRequirementService.read(user=self.f.user, production_plan_id=self.plan.pk)
        self.assertTrue(readback["passed"], readback)
        replay = self.allocate()
        self.assertTrue(replay["idempotent"])
        self.assertEqual(replay["businessWriteCount"], 0)
        row.refresh_from_db()
        self.assertEqual(row.source_snapshot, snapshot)
        for model in (EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringOperationRequirement,
                      ProductionPlan, ProductManufacturingOutput, EngineeringRuleDefinition):
            self.assertEqual(list(model.objects.order_by("pk").values()), protected[model.__name__])

    def test_baseline_hash_uses_original_source_order_not_model_default_order(self):
        from .models import OrderEngineeringBaselineItem
        before = self.f.full_database_snapshot()
        # The frozen source used source-attribute order. ORM default ordering
        # must not change that already persisted, order-sensitive identity.
        with patch.object(OrderEngineeringBaselineItem._meta, 'ordering', ['-design_item_id', '-pk']):
            preview = self.preview()
        self.assertTrue(preview['ready'], preview)
        self.assertTrue(preview['checks']['objectCoverage']['passed'], preview)
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_second_object_same_plan_step_preserves_distinct_formal_contributions(self):
        self.allocate()
        preview = self.preview(req=self.requirements[1])
        self.assertTrue(preview["ready"], preview)
        second = self.allocate(req=self.requirements[1], key="sim-legal-second-object")
        self.assertFalse(second["idempotent"])
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 2)
        readback = operation.OperationRequirementService.read(user=self.f.user, production_plan_id=self.plan.pk)
        self.assertTrue(readback["passed"], readback)
        self.assertEqual({row["operationRequirementId"] for row in readback["allocations"]},
            {req.pk for req in self.requirements[:2]})

    def test_origin_id_alone_cannot_validate_an_illegal_extension(self):
        trace = deepcopy(self.extension.trace)
        trace["purpose"] = "SIM-INVALID"
        self.raw(self.extension, "trace", trace)
        self.reject_both()

    def test_extension_company_order_line_instance_and_hash_drift_are_rejected(self):
        f = self.f
        other_company = Company.objects.create(code="SIM-OTHER-COMPANY", name="SIMULATED_FOR_TEST other company")
        other_item = SalesOrderItem.objects.create(sales_order=f.order, line_no=2, material=f.item.material,
            quantity=37, uom=f.pcs, required_date=date.today(), engineering_mode="ORDER_ENGINEERED")
        other_instance = f.initial(OrderEngineeringInstance, "draft", company=f.company, instance_no="SIM-OTHER-INSTANCE",
            sales_order_item=other_item, product_category=f.category, selected_process_type=f.kind, source_record=f.source)
        for field, value in (("company", other_company.pk), ("sales_order_item", other_item.pk),
                             ("engineering_instance", other_instance.pk), ("input_hash", "0" * 64),
                             ("result_hash", "0" * 64), ("origin_calculation",
                              EngineeringOperationRequirement.objects.get(pk=f.old_ids[0]).calculation_id)):
            with self.subTest(field=field), transaction.atomic():
                self.raw(self.extension, field, value)
                self.reject_both()
                transaction.set_rollback(True)

    def test_object_baseline_and_input_contribution_drift_are_rejected(self):
        for target, field, update in ((self.facts[0], "trace", lambda t: t.update(baselineId=self.f.baseline.pk + 900)),
                (self.facts[0], "trace", lambda t: t.update(designItemId=self.f.baseline_items[1].design_item_id)),
                (self.facts[0], "trace", lambda t: t["group"].update(baselineItemId=self.f.baseline_items[1].pk)),
                (self.extension, "trace", lambda t: t.update(plan={}))):
            with self.subTest(field=field, target=target.pk), transaction.atomic():
                value = deepcopy(getattr(target, field)); update(value)
                self.raw(target, field, value)
                self.reject_both()
                transaction.set_rollback(True)

    def test_plan_state_and_unconfirmed_partial_quantity_keep_the_same_rejection(self):
        for field, value in (("status", "released"), ("status", "draft"), ("planned_qty", Decimal(36))):
            with self.subTest(field=field, value=value), transaction.atomic():
                self.raw(self.plan, field, value)
                self.reject_both()
                transaction.set_rollback(True)
        with transaction.atomic():
            self.raw(self.plan, "planned_qty", Decimal(36))
            self.raw(self.plan.planning_requirement, "net_required_qty", Decimal(36))
            self.reject_both(expected="SOURCE_SCOPE_PARTIAL_ALLOCATION_BLOCKED")
            transaction.set_rollback(True)

    def test_source_unit_and_wrong_fixed_version_step_stay_blocked(self):
        self.reject_both(step=self.f.wrong_step)
        with transaction.atomic():
            self.raw(self.f.item, "uom", self.f.area.pk)
            self.reject_both()
            transaction.set_rollback(True)

    def test_read_permission_and_execution_permission_are_not_interchangeable(self):
        reader = User.objects.create_user(username="sim_legal_reader", company_id=self.f.company.pk)
        role = Role.objects.create(code="SIM-LEGAL-READER", name="SIMULATED_FOR_TEST")
        for code in (operation.PLAN_VIEW, operation.VIEW):
            RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
        UserRoleScopeAssignment.objects.create(user=reader, role=role, organization=self.f.company,
            scope_code="ORGANIZATION", active=True, business_hash="SIMULATED_FOR_TEST")
        result = self.preview(user=reader)
        self.assertTrue(result["dataReady"], result)
        self.assertFalse(result["ready"], result)
        self.assertFalse(result["canSave"])
        self.assertEqual(result["checks"]["writeAuthorization"]["status"], "blocked")
        with self.assertRaises(operation.OperationRequirementError):
            self.allocate(user=reader)
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=operation.EXECUTE))
        no_actor = self.preview(user=reader)
        self.assertTrue(no_actor["dataReady"], no_actor)
        self.assertFalse(no_actor["ready"], no_actor)
        self.assertFalse(no_actor["canSave"], no_actor)
        self.assertIn('计划分配执行账号', no_actor['checks']['writeAuthorization']['statusLabel'])
        with self.assertRaises(operation.OperationRequirementError):
            self.allocate(user=reader)
        denied = User.objects.create_user(username="sim_legal_denied", company_id=self.f.company.pk)
        self.reject_both(user=denied, expected="PERMISSION_DENIED")

    def test_historical_replacement_is_rejected_before_obsolete_native_input(self):
        f = self.f
        spec = deepcopy(self.rule.specification)
        spec["rulePackage"]["version"] = "V3"
        replacement = f.initial(EngineeringRuleDefinition, "draft", company=f.company,
            rule_code=self.rule.rule_code, rule_name="SIMULATED_FOR_TEST replacement", version="V3",
            rule_kind="formula", specification=spec)
        f.advance(replacement, "reviewed")
        f.advance(replacement, "released")
        OperationRequirementCorrectionService.correct(user=f.user, replacements=[{
            "operationRequirementId": self.requirements[0].pk, "ruleId": replacement.pk}],
            idempotency_key="sim-legal-history", reason="SIMULATED_FOR_TEST")
        self.reject_both(expected="OPERATION_REQUIREMENT_SUPERSEDED")

    def test_budget_counts_the_same_plan_once_and_blocks_another_full_scope_proposal(self):
        from types import SimpleNamespace
        self.allocate()
        current = EngineeringOperationRequirement.objects.get(pk=self.requirements[0].pk)
        existing = operation._scope_budget(current, self.f.company.pk)
        self.assertEqual(existing, {self.plan.pk: Decimal(37)})
        replay = operation._scope_budget(current, self.f.company.pk,
            proposed_plan=self.plan, proposed_quantity=Decimal(37))
        self.assertEqual(replay, existing)
        before = self.f.full_database_snapshot()
        # Demand/Requirement/Plan are one-to-one today. This exercises the shared
        # proposed second-plan budget without forging a second persisted chain.
        with self.assertRaises(operation.OperationRequirementError) as caught:
            operation._scope_budget(current, self.f.company.pk,
                proposed_plan=SimpleNamespace(pk=self.plan.pk + 10000), proposed_quantity=Decimal(37))
        self.assertEqual(caught.exception.code, "ALLOCATION_SCOPE_EXCEEDED")
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_plan_drift_after_real_save_rejects_readback_and_replay(self):
        self.allocate()
        self.raw(self.plan, "status", "released")
        readback = operation.OperationRequirementService.read(user=self.f.user, production_plan_id=self.plan.pk)
        self.assertFalse(readback["passed"])
        self.assertTrue(readback["blockers"])
        self.reject_both()

    def test_projection_no_longer_reports_old_id_equality_blocker_for_proven_extension(self):
        from .engineering_workload_review import build_purpose_review
        result = build_purpose_review(user=self.f.user, calculations=[self.f.source_calc])
        loads = result["operationLoads"]
        self.assertTrue(loads, result)
        self.assertEqual(sum(Decimal(row["effectiveQuantity"]) for row in loads), Decimal(4))
        self.assertNotIn("ALLOCATION_SOURCE_MISMATCH", [reason["code"] for row in loads for reason in row["missingReasons"]])
