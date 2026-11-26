"""SIMULATED_FOR_TEST: real multiple-object plan-step allocation contracts.

The parent runner owns the disposable database. Formal source generation, native
proofs, immutable saves and audits are exercised; no acceptance database, login,
date preview or APS entry is used. No proof or authorization result is mocked.
"""
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase

from system.models import (Company, OrganizationOperatingAuditRecord, Permission,
    Role, RolePermission, User, UserRoleScopeAssignment)
from . import operation_requirement_service as operation
from . import tests_calc4_routing_correction as correction
from . import tests_plan_legal_extension_admission as legal
from .engineering_fact_extension_service import CONTRACT as EXTENSION_CONTRACT
from .models import (EngineeringOperationRequirement, EngineeringRuleDefinition,
    ProductionPlanOperationRequirementAllocation, RoutingStep, RoutingVersion,
    WorkCenter, WorkCenterOperationCapability)
from .operation_requirement_correction_service import OperationRequirementCorrectionService


class PlanMultiContributionTests(TestCase):
    def setUp(self):
        original_advance = correction.Calc4RoutingCorrectionTests.advance
        occurrence_count = 13 if self._testMethodName == "test_full_39_group_atomic_save_readback_and_replay" else 2

        def advance_with_second_draft_step(fixture, obj, target, *, status_field="status"):
            # The extra occurrence is built while the version is still draft,
            # before its formal review/release and before any rule or EOR binds it.
            if isinstance(obj, RoutingVersion) and target == "reviewed":
                for sequence in range(2, occurrence_count + 1):
                    RoutingStep.objects.create(routing_version=obj, sequence=sequence,
                        operation=fixture.op_area, standard_hours=Decimal("777"),
                        operation_parameters={"applicability": {
                            "contractVersion": "PCE-ROUTING-STEP-APPLICABILITY-V1.0", "mode": "MANDATORY"}})
            return original_advance(fixture, obj, target, status_field=status_field)

        # Load fixture construction through its module. Do not inherit or import
        # the TestCase class as a discovered test, which would rerun old suites.
        fixture = legal.PlanLegalExtensionAdmissionTests(methodName="runTest")
        with patch.object(correction.Calc4RoutingCorrectionTests, "advance", advance_with_second_draft_step):
            fixture.setUp()
        self.base, self.f = fixture, fixture.f
        self.plan, self.requirements = fixture.plan, fixture.requirements
        self.second_step = RoutingStep.objects.get(routing_version=self.f.version, sequence=2)
        self.assertEqual(len(self.requirements), 3)
        self.assertEqual(len({fact.trace["group"]["designItemId"] for fact in fixture.facts}), 3)
        self.assertEqual(sum((req.workload_quantity for req in self.requirements), Decimal(0)), Decimal(4))

    def contributions(self, requirements=None, *, step=None, prefix="sim-multi"):
        return [{"operationRequirementId": req.pk, "routingStepId": (step or self.f.step).pk,
                 "idempotencyKey": f"{prefix}-{req.pk}"} for req in (requirements or self.requirements)]

    def preview(self, contributions=None, *, user=None):
        return operation.OperationRequirementService.allocation_group_readiness(
            user=user or self.f.user, production_plan_id=self.plan.pk,
            contributions=contributions if contributions is not None else self.contributions())

    def save(self, contributions=None, *, user=None):
        return operation.OperationRequirementService.allocate_group(user=user or self.f.user,
            production_plan_id=self.plan.pk,
            contributions=contributions if contributions is not None else self.contributions(),
            reason="SIMULATED_FOR_TEST")

    def reject_group(self, contributions=None, *, user=None, expected=None):
        rows = contributions if contributions is not None else self.contributions()
        before = self.f.full_database_snapshot()
        try:
            preview = self.preview(rows, user=user)
        except operation.OperationRequirementError as exc:
            code = exc.code
        else:
            self.assertFalse(preview["ready"], preview)
            self.assertFalse(preview["canSave"], preview)
            self.assertEqual(preview["businessWriteCount"], 0)
            code = preview["blockers"][0]["code"]
        with self.assertRaises(operation.OperationRequirementError) as caught:
            self.save(rows, user=user)
        self.assertEqual(caught.exception.code, code)
        if expected:
            self.assertEqual(code, expected)
        self.assertEqual(self.f.full_database_snapshot(), before)
        return code

    def new_requirement(self, *, fact_index=0, step=None, mode=None, center=None, capacity=None):
        f = self.f
        fact = self.base.facts[fact_index]
        step, mode = step or f.step, mode or f.mode
        capacity = capacity or f.capacity
        rule = f.make_mapping(fact, f.op_area, f.area, mode=mode, capacity=capacity,
            manufacturing_overrides={"workCenterId": (center or f.center).pk},
            dynamic_source_basis=True, release=False)
        spec = deepcopy(rule.specification)
        spec["manufacturing"]["sourceSelector"]["traceEquals"] = {"contractVersion": EXTENSION_CONTRACT}
        spec["manufacturing"]["routingContext"] = {"contractVersion": correction.ROUTE_CONTRACT,
            "routingId": f.route.pk, "routingVersionId": f.version.pk, "routingStepId": step.pk}
        spec["sourceEvidence"]["formalRouting"] = f.route_evidence(f.version, step)
        rule.specification = spec
        rule.save(update_fields=("specification",))
        f.advance(rule, "reviewed")
        f.advance(rule, "released")
        generated = operation.OperationRequirementService.generate(user=f.user,
            source_calculation_id=self.base.extension.pk, source_fact_id=fact.pk,
            rule_id=rule.pk, idempotency_key=f"sim-extra-eor-{rule.pk}-{fact.pk}",
            reason="SIMULATED_FOR_TEST")
        return EngineeringOperationRequirement.objects.get(pk=generated["operationRequirementId"])

    def step_demand(self):
        return operation.process_demand_for_plan(self.plan, self.f.output, self.f.item,
            {"stepId": self.f.step.pk, "operationId": self.f.op_area.pk}, company_id=self.f.company.pk)

    def test_group_preview_checks_three_saved_object_contributions_without_writes(self):
        before = self.f.full_database_snapshot()
        preview = self.preview()
        self.assertTrue(preview["ready"], preview)
        self.assertTrue(preview["canSave"], preview)
        self.assertTrue(preview["batchSaveAllowed"], preview)
        self.assertEqual(preview["assessmentScope"], "CONTRIBUTION_GROUP")
        self.assertFalse(preview["executionPerformed"])
        self.assertEqual(preview["businessWriteCount"], 0)
        self.assertEqual(preview["auditWriteCount"], 0)
        self.assertEqual({row["operationRequirementId"] for row in preview["contributions"]},
            {req.pk for req in self.requirements})
        self.assertTrue(all(row["ready"] for row in preview["contributions"]))
        self.assertEqual(len(preview["steps"]), 1)
        step = preview["steps"][0]
        self.assertEqual(step["contributionCount"], 3)
        self.assertEqual(Decimal(step["allocatedQuantity"]), Decimal(4))
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_second_and_third_contribution_can_save_without_changing_existing_snapshot(self):
        first = self.base.allocate()
        original = deepcopy(ProductionPlanOperationRequirementAllocation.objects.get(
            pk=first["allocationId"]).source_snapshot)
        for req in self.requirements[1:]:
            preview = self.base.preview(req=req)
            self.assertTrue(preview["ready"], preview)
            created = self.base.allocate(req=req, key=f"sim-next-{req.pk}")
            self.assertEqual(created["businessWriteCount"], 1)
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 3)
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.get(
            pk=first["allocationId"]).source_snapshot, original)
        self.assertEqual(self.step_demand()["quantity"], Decimal(4))

    def test_group_save_is_atomic_and_same_group_replay_has_zero_new_audit_or_business_rows(self):
        protected = self.f.protected_snapshot()
        result = self.save()
        self.assertTrue(result["atomic"], result)
        self.assertFalse(result["idempotent"])
        self.assertEqual(result["businessWriteCount"], 3)
        self.assertEqual(result["auditWriteCount"], 3)
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 3)
        before = self.f.full_database_snapshot()
        again = self.save()
        self.assertTrue(again["idempotent"], again)
        self.assertEqual(again["businessWriteCount"], 0)
        self.assertEqual(again["auditWriteCount"], 0)
        self.assertEqual(self.f.full_database_snapshot(), before)
        self.assertEqual(self.f.protected_snapshot(), protected)

    def test_real_first_save_then_second_persistence_failure_rolls_back_all_rows_and_audits(self):
        self.assertTrue(self.preview()["ready"])
        before = self.f.full_database_snapshot()
        audit_count = OrganizationOperatingAuditRecord.objects.count()
        original_save = ProductionPlanOperationRequirementAllocation.save
        persisted = []

        def fail_on_second(row, *args, **kwargs):
            if persisted:
                self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 1)
                self.assertGreater(OrganizationOperatingAuditRecord.objects.count(), audit_count)
                raise RuntimeError("SIMULATED_FOR_TEST second real persistence failure")
            result = original_save(row, *args, **kwargs)
            persisted.append(row.pk)
            return result

        with patch.object(ProductionPlanOperationRequirementAllocation, "save", fail_on_second):
            with self.assertRaisesRegex(RuntimeError, "second real persistence failure"):
                self.save()
        self.assertEqual(len(persisted), 1, "The test must fail after the first real save, not at preflight")
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 0)
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_same_contribution_replay_under_original_key_has_zero_new_rows(self):
        row = self.contributions()[0]
        self.save([row])
        before = self.f.full_database_snapshot()
        replay = self.save([row])
        self.assertTrue(replay["idempotent"])
        self.assertEqual(replay["businessWriteCount"], 0)
        self.assertEqual(replay["auditWriteCount"], 0)
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_same_contribution_twice_in_one_candidate_group_is_rejected(self):
        row = self.contributions()[0]
        self.reject_group([row, {**row, "idempotencyKey": "sim-duplicate-other-key"}],
            expected="ALLOCATION_CONTRIBUTION_DUPLICATE")

    def test_same_idempotency_key_for_different_object_is_a_conflict(self):
        rows = self.contributions()
        rows[1]["idempotencyKey"] = rows[0]["idempotencyKey"]
        self.reject_group(rows, expected="IDEMPOTENCY_PAYLOAD_CONFLICT")

    def test_existing_key_cannot_be_rebound_to_another_object(self):
        rows = self.contributions()
        self.save(rows[:1])
        rows[1]["idempotencyKey"] = rows[0]["idempotencyKey"]
        self.reject_group(rows[1:2], expected="IDEMPOTENCY_PAYLOAD_CONFLICT")

    def test_different_eor_for_same_saved_object_is_not_a_second_contribution(self):
        duplicate = self.new_requirement(fact_index=0)
        self.assertTrue(self.base.preview(req=duplicate)["ready"])
        rows = self.contributions(self.requirements[:1] + [duplicate])
        self.reject_group(rows, expected="ALLOCATION_CONTRIBUTION_OVERLAP")

    def test_different_valid_resource_contributions_cannot_merge_same_step(self):
        f = self.f
        center = WorkCenter.objects.create(company=f.company, workshop=f.workshop,
            department=f.department, code="SIM-MULTI-OTHER-WC", name="Abstract second resource")
        WorkCenterOperationCapability.objects.create(work_center=center, operation=f.op_area,
            assignment_role="primary", is_active=True)
        capacity = f.make_capacity(f.op_area, f.area, "SIM-MULTI-OTHER-CAP", work_center=center)
        other = self.new_requirement(fact_index=1, center=center, capacity=capacity)
        self.assertTrue(self.base.preview(req=other)["ready"])
        self.reject_group(self.contributions(self.requirements[:1] + [other]),
            expected="ALLOCATION_CONTRIBUTION_INCOMPATIBLE")

    def test_different_valid_manufacturing_modes_cannot_merge_same_step(self):
        mode = self.f.make_mode(self.f.area, "SIM-MULTI-OTHER-MODE")
        other = self.new_requirement(fact_index=1, mode=mode)
        self.assertTrue(self.base.preview(req=other)["ready"])
        self.reject_group(self.contributions(self.requirements[:1] + [other]),
            expected="ALLOCATION_CONTRIBUTION_INCOMPATIBLE")

    def test_different_formal_purpose_fields_cannot_merge_same_step(self):
        f = self.f
        # Both candidates have real native proofs. The direct source canonical
        # field is opaque_area; the extension field is PaintingProcessAreaQuantity.
        # Different official purposes cannot merge merely because units match.
        generated = operation.OperationRequirementService.generate(user=f.user,
            source_calculation_id=f.source_calc.pk, source_fact_id=f.facts[1].pk,
            rule_id=f.correct_rule.pk, idempotency_key="sim-multi-other-purpose",
            reason="SIMULATED_FOR_TEST")
        other = EngineeringOperationRequirement.objects.get(pk=generated["operationRequirementId"])
        self.assertTrue(self.base.preview(req=other)["ready"])
        self.reject_group(self.contributions(self.requirements[:1] + [other]),
            expected="ALLOCATION_CONTRIBUTION_INCOMPATIBLE")

    def test_unit_drift_is_rejected_without_implicit_conversion(self):
        self.base.raw(self.requirements[1], "uom", self.f.pcs.pk)
        preview = self.preview()
        self.assertFalse(preview["dataReady"], preview)
        for key in ("contributionCompatibility", "quantityBudget"):
            self.assertIsNot(preview["groupChecks"].get(key, {}).get("passed"), True, preview)
        self.reject_group()

    def test_same_eor_cannot_be_duplicated_to_a_second_operation_occurrence(self):
        row = self.contributions()[0]
        self.reject_group([row, {**row, "routingStepId": self.second_step.pk,
            "idempotencyKey": "sim-second-step-copy"}], expected="PROCESS_STEP_MAPPING_AMBIGUOUS")

    def test_six_distinct_step_contributions_count_plan_budget_once(self):
        second = [self.new_requirement(fact_index=index, step=self.second_step) for index in range(3)]
        rows = self.contributions() + self.contributions(second, step=self.second_step, prefix="sim-second-step")
        preview = self.preview(rows)
        self.assertTrue(preview["ready"], preview)
        self.assertEqual(len(preview["steps"]), 2)
        self.assertEqual([Decimal(step["allocatedQuantity"]) for step in preview["steps"]], [Decimal(4), Decimal(4)])
        result = self.save(rows)
        self.assertEqual(result["businessWriteCount"], 6)
        self.assertEqual(operation._scope_budget(self.requirements[0], self.f.company.pk), {self.plan.pk: Decimal(37)})
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.planned_qty, Decimal(37))
        before = self.f.full_database_snapshot()
        with self.assertRaises(operation.OperationRequirementError) as caught:
            operation._scope_budget(self.requirements[0], self.f.company.pk,
                proposed_plan=SimpleNamespace(pk=self.plan.pk + 10000), proposed_quantity=Decimal(37))
        self.assertEqual(caught.exception.code, "ALLOCATION_SCOPE_EXCEEDED")
        self.assertEqual(self.f.full_database_snapshot(), before)

    def test_partial_plan_still_requires_formal_rule_and_is_not_proportioned(self):
        self.base.raw(self.plan, "planned_qty", Decimal(36))
        self.base.raw(self.plan.planning_requirement, "net_required_qty", Decimal(36))
        self.reject_group(expected="SOURCE_SCOPE_PARTIAL_ALLOCATION_BLOCKED")

    def test_history_remains_rejected_in_a_group_with_other_effective_objects(self):
        spec = deepcopy(self.base.rule.specification)
        spec["rulePackage"]["version"] = "V3"
        replacement = self.f.initial(EngineeringRuleDefinition, "draft", company=self.f.company,
            rule_code=self.base.rule.rule_code, rule_name="SIMULATED_FOR_TEST group replacement",
            version="V3", rule_kind="formula", specification=spec)
        self.f.advance(replacement, "reviewed")
        self.f.advance(replacement, "released")
        OperationRequirementCorrectionService.correct(user=self.f.user, replacements=[{
            "operationRequirementId": self.requirements[0].pk, "ruleId": replacement.pk}],
            idempotency_key="sim-multi-history", reason="SIMULATED_FOR_TEST")
        preview = self.preview()
        self.assertFalse(preview["dataReady"], preview)
        for key in ("contributionCompatibility", "quantityBudget"):
            self.assertIsNot(preview["groupChecks"].get(key, {}).get("passed"), True, preview)
        self.reject_group(expected="OPERATION_REQUIREMENT_SUPERSEDED")

    def test_cross_company_wrong_baseline_object_hash_and_step_remain_rejected(self):
        company = Company.objects.create(code="SIM-MULTI-FOREIGN", name="SIMULATED_FOR_TEST foreign company")
        for target, field, change in (
                (self.base.extension, "company", company.pk),
                (self.base.extension, "input_hash", "0" * 64),
                (self.requirements[1], "source_hash", "0" * 64)):
            with self.subTest(field=field, pk=target.pk), transaction.atomic():
                self.base.raw(target, field, change)
                self.reject_group()
                transaction.set_rollback(True)
        for edit in (lambda trace: trace.update(baselineId=self.f.baseline.pk + 1000),
                     lambda trace: trace.update(designItemId=self.f.baseline_items[2].design_item_id)):
            with transaction.atomic():
                trace = deepcopy(self.base.facts[1].trace)
                edit(trace)
                self.base.raw(self.base.facts[1], "trace", trace)
                self.reject_group()
                transaction.set_rollback(True)
        rows = self.contributions()
        rows[1]["routingStepId"] = self.f.wrong_step.pk
        self.reject_group(rows)

    def test_readback_sums_all_contributions_and_retains_original_trace_and_single_shape(self):
        first = self.base.allocate()
        single = self.step_demand()
        self.assertEqual(single["allocationId"], first["allocationId"])
        self.assertEqual(single["operationRequirementId"], self.requirements[0].pk)
        self.assertEqual(single["quantity"], self.requirements[0].workload_quantity)
        self.save(self.contributions(self.requirements[1:]))
        demand = self.step_demand()
        self.assertNotIn("allocationId", demand)
        self.assertEqual(demand["quantity"], Decimal(4))
        self.assertEqual(set(demand["operationRequirementIds"]), {req.pk for req in self.requirements})
        self.assertEqual(len(demand["allocationIds"]), 3)
        self.assertEqual({row["sourceFactId"] for row in demand["contributions"]},
            {req.source_fact_id for req in self.requirements})
        self.assertEqual({row["sourceCalculationId"] for row in demand["contributions"]}, {self.base.extension.pk})
        readback = operation.OperationRequirementService.read(user=self.f.user, production_plan_id=self.plan.pk)
        self.assertTrue(readback["passed"], readback)
        self.assertEqual(len(readback["allocations"]), 3)
        from .daily_capacity_views import process_demand_for_plan as consume_existing_step
        self.assertEqual(consume_existing_step(self.plan, self.f.output, self.f.item,
            {"stepId": self.f.step.pk, "operationId": self.f.op_area.pk}, company_id=self.f.company.pk), demand)

    def test_existing_purpose_projection_sums_all_saved_objects_without_new_metrics(self):
        self.save()
        from .engineering_workload_review import build_purpose_review
        result = build_purpose_review(user=self.f.user, calculations=[self.f.source_calc])
        loads = result["operationLoads"]
        self.assertEqual(len(loads), 1, result)
        self.assertEqual(Decimal(loads[0]["effectiveQuantity"]), Decimal(4))
        self.assertEqual(Decimal(loads[0]["allocatedQuantity"]), Decimal(4))
        self.assertEqual(set(loads[0]["requirementIds"]), {req.pk for req in self.requirements})

    def test_group_view_permission_does_not_grant_execution_or_formal_actor_chain(self):
        reader = User.objects.create_user(username="sim_multi_reader", company_id=self.f.company.pk)
        role = Role.objects.create(code="SIM-MULTI-READER", name="SIMULATED_FOR_TEST reader")
        for code in (operation.PLAN_VIEW, operation.VIEW):
            RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
        UserRoleScopeAssignment.objects.create(user=reader, role=role, organization=self.f.company,
            scope_code="ORGANIZATION", active=True, business_hash="SIMULATED_FOR_TEST")
        self.reject_group(user=reader, expected="PERMISSION_DENIED")
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=operation.EXECUTE))
        self.reject_group(user=reader, expected="FORMAL_EXECUTION_CHAIN_REQUIRED")
        denied = User.objects.create_user(username="sim_multi_no_view", company_id=self.f.company.pk)
        self.reject_group(user=denied, expected="PERMISSION_DENIED")

    def test_full_39_group_atomic_save_readback_and_replay(self):
        rows = self.contributions()
        steps = list(RoutingStep.objects.filter(routing_version=self.f.version).order_by("sequence"))
        self.assertEqual(len(steps), 13)
        for step in steps[1:]:
            requirements = [self.new_requirement(fact_index=index, step=step) for index in range(3)]
            rows.extend(self.contributions(requirements, step=step, prefix=f"sim-full-step-{step.sequence}"))
        self.assertEqual(len(rows), 39)
        before = self.f.full_database_snapshot()
        preview = self.preview(rows)
        self.assertTrue(preview["ready"], preview)
        self.assertEqual(len(preview["contributions"]), 39)
        self.assertEqual(len(preview["steps"]), 13)
        self.assertTrue(all(step["contributionCount"] == 3
            and Decimal(step["allocatedQuantity"]) == Decimal(4) for step in preview["steps"]))
        self.assertEqual(self.f.full_database_snapshot(), before)
        saved = self.save(rows)
        self.assertTrue(saved["atomic"], saved)
        self.assertEqual(saved["businessWriteCount"], 39)
        self.assertEqual(saved["auditWriteCount"], 39)
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 39)
        readback = operation.OperationRequirementService.read(user=self.f.user, production_plan_id=self.plan.pk)
        self.assertTrue(readback["passed"], readback)
        self.assertEqual(len(readback["allocations"]), 39)
        self.assertEqual({row["operationRequirementId"] for row in readback["allocations"]},
            {row["operationRequirementId"] for row in rows})
        for step in steps:
            demand = operation.process_demand_for_plan(self.plan, self.f.output, self.f.item,
                {"stepId": step.pk, "operationId": self.f.op_area.pk}, company_id=self.f.company.pk)
            self.assertEqual(demand["quantity"], Decimal(4))
            self.assertEqual(len(demand["allocationIds"]), 3)
        self.assertEqual(operation._scope_budget(self.requirements[0], self.f.company.pk), {self.plan.pk: Decimal(37)})
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.planned_qty, Decimal(37))
        before_replay = self.f.full_database_snapshot()
        replay = self.save(rows)
        self.assertTrue(replay["idempotent"], replay)
        self.assertEqual(replay["businessWriteCount"], 0)
        self.assertEqual(replay["auditWriteCount"], 0)
        self.assertEqual(self.f.full_database_snapshot(), before_replay)

    def test_saved_proofs_do_not_survive_plan_hash_or_fact_drift_across_public_calls(self):
        self.save()
        self.assertTrue(operation.OperationRequirementService.read(user=self.f.user,
            production_plan_id=self.plan.pk)["passed"])
        self.assertTrue(self.preview()["ready"])
        for target, field, value in (
                (self.plan, "status", "released"),
                (self.requirements[1], "source_hash", "0" * 64),
                (self.base.facts[1], "value", {"decimal": "999"})):
            with self.subTest(field=field, pk=target.pk), transaction.atomic():
                self.base.raw(target, field, value)
                before = self.f.full_database_snapshot()
                readback = operation.OperationRequirementService.read(user=self.f.user,
                    production_plan_id=self.plan.pk)
                self.assertFalse(readback["passed"], readback)
                self.assertTrue(readback["blockers"], readback)
                preview = self.preview()
                self.assertFalse(preview["ready"], preview)
                self.assertFalse(preview["canSave"], preview)
                self.assertTrue(preview["blockers"], preview)
                self.assertEqual(preview["businessWriteCount"], 0)
                self.assertEqual(self.f.full_database_snapshot(), before)
                transaction.set_rollback(True)
            self.assertTrue(operation.OperationRequirementService.read(user=self.f.user,
                production_plan_id=self.plan.pk)["passed"])
            self.assertTrue(self.preview()["ready"])

    def test_reused_native_read_cache_does_not_hide_current_fact_value_drift(self):
        cache = {}
        arguments = {"user": self.f.user, "production_plan_id": self.plan.pk,
            "contributions": self.contributions(), "read_cache": cache}
        first = operation.OperationRequirementService.allocation_group_readiness(**arguments)
        self.assertTrue(first["ready"], first)
        self.base.raw(self.base.facts[1], "value", {"decimal": "999"})
        before = self.f.full_database_snapshot()
        second = operation.OperationRequirementService.allocation_group_readiness(**arguments)
        self.assertFalse(second["ready"], second)
        self.assertFalse(second["dataReady"], second)
        self.assertTrue(second["blockers"], second)
        self.assertEqual(second["businessWriteCount"], 0)
        self.assertEqual(self.f.full_database_snapshot(), before)
