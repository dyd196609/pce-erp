"""SIMULATED_FOR_TEST: exact-step native saved-load/capacity assessment.

The parent runner must select a disposable, guarded database before Django is
imported. Existing builders create real released sources, requirements and
allocations. No proof, authorization or successful assessment is mocked.
"""
from contextlib import ExitStack
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.db import connection, transaction
from django.test import TestCase

from system.models import (
    Company, Permission, Process, RolePermission, User, UserRoleScopeAssignment,
)
from . import daily_capacity_service as capacity
from . import daily_capacity_views as date_views
from . import operation_requirement_service as operation
from . import operation_workload_source_service as sources
from . import routing_object_applicability_service as object_service
from . import tests_calc4_routing_correction as source_fixtures
from . import tests_no_date_allocated_capacity as saved_fixtures
from . import tests_routing_object_applicability_service as object_fixtures
from .engineering_fact_extension_service import EngineeringFactExtensionService
from .manufacturing_configuration_service import ManufacturingConfigurationService
from .models import ProductionPlanOperationRequirementAllocation, RoutingStep, RoutingVersion
from .routing_step_applicability_service import RoutingStepApplicabilityResolver


_TARGET = object()
_DML = {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP", "ATTACH", "DETACH"}


class SingleStepNoDateCapacityTests(TestCase):
    def setUp(self):
        original_advance = source_fixtures.Calc4RoutingCorrectionTests.advance
        explicit_zero = self._testMethodName == "test_explicit_zero_step_times_win_over_standard_capacity_times"

        def add_unready_step_before_release(fixture, obj, target, *, status_field="status"):
            if isinstance(obj, RoutingVersion) and target == "reviewed":
                if not hasattr(fixture, "single_scope_other_operation"):
                    fixture.single_scope_other_operation = Process.objects.create(
                        company=fixture.company, code="SIM-SINGLE-OTHER-OP",
                        name="Abstract unrelated unready operation", workshop=fixture.workshop,
                        work_center=fixture.center, calculation_basis="area", calculation_uom=fixture.area)
                other = RoutingStep.objects.create(routing_version=obj, sequence=2,
                    operation=fixture.single_scope_other_operation, predecessor_sequences=[1],
                    operation_parameters={"applicability": {
                        "contractVersion": "PCE-ROUTING-STEP-APPLICABILITY-V1.0", "mode": "MANDATORY"}})
                if obj.routing_version == "SIM-V1":
                    fixture.single_scope_other_step = other
                if explicit_zero:
                    # Time facts are declared while the version is draft,
                    # before any immutable source/requirement/allocation exists.
                    primary = RoutingStep.objects.get(routing_version=obj, sequence=1)
                    primary.preparation_days = Decimal("0")
                    primary.transfer_days = Decimal("0")
                    primary.save(update_fields=("preparation_days", "transfer_days"))
            return original_advance(fixture, obj, target, status_field=status_field)

        self.saved = saved_fixtures.NoDateAllocatedCapacityPersistenceTests(methodName="runTest")
        with patch.object(source_fixtures.Calc4RoutingCorrectionTests, "advance", add_unready_step_before_release):
            self.saved.setUp()
        self.f, self.plan = self.saved.f, self.saved.plan
        self.step, self.other_step = self.f.step, self.f.single_scope_other_step
        self.step.refresh_from_db()
        self.requirements = self.saved.requirements
        for code in (operation.VIEW, operation.PLAN_VIEW, sources.RULE_VIEW):
            permission, _ = Permission.objects.get_or_create(code=code,
                defaults={"name": code, "module": "PRODUCTION"})
            RolePermission.objects.get_or_create(role=self.f.role, permission=permission)
        self.assertEqual(len(self.requirements), 3)
        self.assertEqual(self.other_step.predecessor_sequences, [self.step.sequence])

    def snapshot(self):
        result = self.f.full_database_snapshot()
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
            if cursor.fetchone():
                cursor.execute("SELECT name, seq FROM sqlite_sequence ORDER BY name")
                result["__sqlite_sequence__"] = tuple(cursor.fetchall())
        return result

    def save_contributions(self, requirements=None):
        return self.saved.save_contributions(requirements)

    def _readonly(self, action, *, allow_error=False):
        before, writes = self.snapshot(), []

        def watch(execute, sql, params, many, context):
            verb = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
            if verb in _DML:
                writes.append(verb)
                raise AssertionError("A read-only capacity assessment attempted " + verb)
            return execute(sql, params, many, context)

        forbidden = AssertionError("Single-step capacity assessment must not generate, save, preview dates or book resources")
        try:
            with ExitStack() as stack:
                for owner, name in (
                    (operation.OperationRequirementService, "generate"),
                    (operation.OperationRequirementService, "generate_readiness"),
                    (operation.OperationRequirementService, "allocate"),
                    (operation.OperationRequirementService, "allocate_group"),
                    (EngineeringFactExtensionService, "derive"),
                    (ManufacturingConfigurationService, "configure"),
                    (ManufacturingConfigurationService, "generate_for_calculation"),
                    (date_views, "production_plan_date_preview"),
                    (date_views, "working_date_window"),
                    (capacity, "working_date_window"),
                ):
                    stack.enter_context(patch.object(owner, name, side_effect=forbidden))
                stack.enter_context(connection.execute_wrapper(watch))
                try:
                    return action()
                except Exception as error:
                    if not allow_error or not getattr(error, "code", None):
                        raise
                    return error
        finally:
            self.assertEqual(writes, [])
            self.assertEqual(self.snapshot(), before,
                "Read-only assessment must preserve all rows, audits, CodeRule and SQLite sequences")

    def read(self, *, routing_step_id=_TARGET, user=None, plan_id=None, whole=False, allow_error=False):
        kwargs = {"user": user or self.f.user,
            "production_plan_id": self.plan.pk if plan_id is None else plan_id}
        if not whole:
            kwargs["routing_step_id"] = self.step.pk if routing_step_id is _TARGET else routing_step_id
        return self._readonly(lambda: capacity.AllocatedLoadCapacityReadinessService.assess(**kwargs),
            allow_error=allow_error)

    def lower_read(self, step_id):
        output = self.f.output
        return self._readonly(lambda: capacity.DailyCapacityReadinessService.assess(
            output.routing_version, routing_step_id=step_id, bom_version=output.bom_version,
            engineering_calculation=output.engineering_calculation,
            engineering_document_version=output.engineering_document_version,
            order_engineering_instance=output.order_engineering_instance,
            order_engineering_baseline=output.order_engineering_baseline,
            production_plan=self.plan, manufacturing_output=output))

    def assert_scoped(self, result, *, step_id=None):
        step_id = self.step.pk if step_id is None else step_id
        self.assertEqual(result["evaluationScope"], {
            "type": "SINGLE_STEP", "routingStepId": step_id, "wholeRouteEvaluated": False})
        self.assertFalse(result["noDateReady"])
        self.assertFalse(result["allRequiredStepsCovered"])
        self.assertFalse(result["planningReady"])
        self.assertFalse(result["planExecutionWindowEvaluated"])
        self.assertEqual(result["businessWriteCount"], 0)
        self.assertEqual(result["dateOccupationCount"], 0)
        self.assertEqual(result["productionScheduleCreatedCount"], 0)
        self.assertNotIn("dates", result)
        self.assertNotIn("startDateInput", result)
        self.assertEqual([row["stepId"] for row in result["steps"]], [step_id])
        self.assertEqual(result["readiness"]["evaluationScope"], result["evaluationScope"])
        self.assertEqual([row["stepId"] for row in result["readiness"]["steps"]], [step_id])
        return result["steps"][0]

    def assert_blocked(self, result):
        if isinstance(result, Exception):
            self.assertTrue(getattr(result, "code", None))
            return
        self.assertFalse(result.get("scopeNoDateReady", False), result)
        self.assertFalse(result.get("noDateReady", False), result)
        self.assertFalse(result.get("planningReady", False), result)
        self.assertTrue(result.get("blockers") or not result.get("evaluatedRequiredStepsCovered", True), result)

    def assert_time_source(self, selection, source, source_id, selected):
        self.assertEqual(selection["source"], source)
        self.assertEqual(selection["sourceId"], source_id)
        self.assertEqual(selection["timeUnit"], "DAY")
        self.assertEqual(Decimal(selection["selectedDays"]), Decimal(selected))
        standards = {row["standardCapacityId"]: row["days"] for row in selection["standardCapacityDays"]}
        self.assertEqual(Decimal(standards[self.f.capacity.pk]), Decimal(".1"))

    def test_real_saved_target_reads_every_contribution_and_attributes_sc_time_once(self):
        saved = self.save_contributions()
        result = self.read()
        row = self.assert_scoped(result)
        self.assertTrue(result["scopeNoDateReady"], result)
        self.assertTrue(result["evaluatedRequiredStepsCovered"], result)
        self.assertTrue(row["noDateMatchPassed"], row)
        self.assertEqual(result["matchedAllocationCount"], 3)
        demand = row["processDemand"]
        self.assertEqual(Decimal(demand["quantity"]), Decimal("4"))
        self.assertEqual(set(demand["operationRequirementIds"]), {req.pk for req in self.requirements})
        self.assertEqual(set(demand["allocationIds"]), {row["allocationId"] for row in saved["allocations"]})
        self.assertEqual(len(demand["savedContributions"]), 3)
        self.assertTrue(row["objectCoverage"]["complete"])
        match, = row["capacityMatches"]
        self.assertEqual(match["standardCapacityId"], self.f.capacity.pk)
        self.assertEqual((Decimal(match["productionDays"]), Decimal(match["durationDays"])),
            (Decimal(".008"), Decimal(".208")))
        selected = result["readiness"]["steps"][0]["timeSelection"]
        self.assertEqual(match["timeSelection"], selected)
        for name in ("preparation", "transfer"):
            self.assertIsNone(selected[name]["stepDays"])
            self.assert_time_source(selected[name], "StandardCapacity", self.f.capacity.pk, ".1")

    def test_unready_other_real_step_is_not_resolved_or_timed_by_single_step_call(self):
        self.save_contributions()
        real_resolve = RoutingStepApplicabilityResolver.resolve
        real_duration = capacity._allocated_capacity_duration
        resolved, timed = [], []

        def resolve(step, **kwargs):
            self.assertEqual(step.pk, self.step.pk,
                "Only the target may enter applicability assessment; version metadata is not an assessment")
            resolved.append(step.pk)
            return real_resolve(step, **kwargs)

        def duration(step, *args, **kwargs):
            self.assertEqual(step["stepId"], self.step.pk)
            timed.append(step["stepId"])
            return real_duration(step, *args, **kwargs)

        with patch.object(RoutingStepApplicabilityResolver, "resolve", side_effect=resolve), \
                patch.object(capacity, "_allocated_capacity_duration", side_effect=duration), \
                patch.object(operation.OperationRequirementService, "read",
                    side_effect=AssertionError("Single-step path must not load the whole plan then filter")):
            result = self.read()
        self.assertTrue(result["scopeNoDateReady"], result)
        self.assertTrue(resolved)
        self.assertEqual(timed, [self.step.pk])

    def test_omitted_scope_and_explicit_none_keep_default_whole_route_behavior(self):
        self.save_contributions()
        implicit = self.read(whole=True)
        explicit = self.read(routing_step_id=None)
        self.assertEqual(implicit, explicit)
        self.assertEqual({row["stepId"] for row in implicit["steps"]}, {self.step.pk, self.other_step.pk})
        target = next(row for row in implicit["steps"] if row["stepId"] == self.step.pk)
        self.assertTrue(target["noDateMatchPassed"], target)
        self.assertFalse(implicit["noDateReady"], implicit)
        other = next(row for row in implicit["steps"] if row["stepId"] == self.other_step.pk)
        self.assertFalse(other["noDateMatchPassed"], other)

    def test_invalid_ids_foreign_company_version_and_permissions_fail_before_capacity_assessment(self):
        self.save_contributions()
        other_company = Company.objects.create(code="SIM-SINGLE-FOREIGN", name="SIM-SINGLE-FOREIGN-COMPANY")
        foreign = User.objects.create_user(username="sim_single_foreign", company_id=other_company.pk)
        UserRoleScopeAssignment.objects.create(user=foreign, role=self.f.role, organization=other_company,
            scope_code="ORGANIZATION", active=True, business_hash="SIMULATED_FOR_TEST")
        denied = User.objects.create_user(username="sim_single_denied", company_id=self.f.company.pk)
        cases = ([{"routing_step_id": value} for value in (True, False, 0, -1, "1", 1.5)]
            + [{"plan_id": True}, {"plan_id": self.plan.pk + 10000}, {"routing_step_id": self.f.wrong_step.pk},
               {"user": foreign}, {"user": denied}])
        with patch.object(capacity.DailyCapacityReadinessService, "assess",
                side_effect=AssertionError("Invalid exact scope must fail before capacity evaluation")):
            for kwargs in cases:
                with self.subTest(scope=kwargs):
                    self.assert_blocked(self.read(**kwargs, allow_error=True))

    def test_absent_or_partial_saved_target_never_uses_unsaved_candidate_or_zero_load(self):
        for count in (0, 1, 2):
            with self.subTest(savedCount=count), transaction.atomic():
                if count:
                    self.save_contributions(self.requirements[:count])
                result = self.read(allow_error=True)
                self.assert_blocked(result)
                if not isinstance(result, Exception):
                    self.assertFalse(result.get("evaluatedRequiredStepsCovered", False))
                    self.assertLessEqual(result.get("matchedAllocationCount", 0), count)
                    for row in result.get("steps", []):
                        if count == 0:
                            self.assertIsNone(row.get("processDemand"))
                            self.assertEqual(row["capacityMatches"], [])
                transaction.set_rollback(True)

    def test_corrupt_second_saved_target_cannot_be_hidden_by_first_valid_contribution(self):
        self.save_contributions()
        rows = list(ProductionPlanOperationRequirementAllocation.objects.filter(
            production_plan=self.plan, routing_step=self.step).order_by("pk"))
        self.assertEqual(len(rows), 3)
        self.saved.fixture.raw(rows[1], "source_snapshot", deepcopy(rows[0].source_snapshot))
        self.saved.fixture.raw(rows[1], "input_hash", rows[0].input_hash)
        self.assert_blocked(self.read(allow_error=True))

    def test_current_source_capacity_and_units_are_reproved_without_reusing_success(self):
        self.save_contributions()
        self.assertTrue(self.read()["scopeNoDateReady"])
        changes = ((self.f.capacity, "quantity", Decimal("999")),
            (self.f.capacity, "uom", self.f.pcs.pk),
            (self.requirements[1].source_fact, "value", {"decimal": "999"}))
        for obj, field, value in changes:
            with self.subTest(field=field, objectId=obj.pk), transaction.atomic():
                self.saved.fixture.raw(obj, field, value)
                self.assert_blocked(self.read(allow_error=True))
                transaction.set_rollback(True)
        with transaction.atomic():
            # A legacy not_determinable row has NULL quantity by the existing
            # CHECK constraint. Change both together in this isolated corrupt-
            # source fixture; no invalid transitional combination is persisted.
            with connection.cursor() as cursor:
                cursor.execute('UPDATE pde_standard_capacity SET quantity=NULL, measurement_status=%s WHERE id=%s',
                    ['not_determinable', self.f.capacity.pk])
            self.assert_blocked(self.read(allow_error=True))
            transaction.set_rollback(True)

    def test_explicit_zero_step_times_win_over_standard_capacity_times(self):
        self.save_contributions()
        result = self.read()
        row = self.assert_scoped(result)
        self.assertTrue(result["scopeNoDateReady"], result)
        match, = row["capacityMatches"]
        self.assertEqual(Decimal(match["durationDays"]), Decimal(".008"))
        for name in ("preparation", "transfer"):
            selection = match["timeSelection"][name]
            self.assertEqual(Decimal(selection["stepDays"]), Decimal("0"))
            self.assert_time_source(selection, "RoutingStep", self.step.pk, "0")

    def test_missing_times_are_not_filled_with_zero_or_a_same_named_record(self):
        self.save_contributions()
        self.saved.fixture.raw(self.f.capacity, "preparation_days", None)
        self.saved.fixture.raw(self.f.capacity, "transfer_days", None)
        result = self.read(allow_error=True)
        self.assert_blocked(result)
        if not isinstance(result, Exception) and result.get("readiness"):
            row, = result["readiness"]["steps"]
            for name in ("preparation", "transfer"):
                selection = row["timeSelection"][name]
                self.assertIsNone(selection["selectedDays"])
                self.assertIsNone(selection["source"])
                self.assertIsNone(selection["sourceId"])

    def test_ambiguous_same_resource_capacity_never_selects_first_or_fills_null_times(self):
        self.save_contributions()
        self.f.make_capacity(self.f.op_area, self.f.area, "SIM-SINGLE-DUPLICATE-SC",
            quantity=Decimal("700"), preparation_days=Decimal(".1"), transfer_days=Decimal(".1"))
        result = self.read()
        self.assert_blocked(result)
        row = self.assert_scoped(result)
        self.assertEqual(row["capacityMatches"], [])
        lower, = result["readiness"]["steps"]
        self.assertIn("DAILY_CAPACITY_AMBIGUOUS", lower["blockerCodes"])
        for name in ("preparation", "transfer"):
            self.assertIsNone(lower["timeSelection"][name]["selectedDays"])
            self.assertIsNone(lower["timeSelection"][name]["source"])

    def test_scoped_lower_reader_keeps_real_predecessor_metadata_without_evaluating_it(self):
        real_resolve = RoutingStepApplicabilityResolver.resolve

        def resolve(step, **kwargs):
            self.assertEqual(step.pk, self.other_step.pk)
            return real_resolve(step, **kwargs)

        with patch.object(RoutingStepApplicabilityResolver, "resolve", side_effect=resolve):
            result = self.lower_read(self.other_step.pk)
        self.assertEqual(result["evaluationScope"], {
            "type": "SINGLE_STEP", "routingStepId": self.other_step.pk, "wholeRouteEvaluated": False})
        row, = result["steps"]
        self.assertEqual(row["stepId"], self.other_step.pk)
        self.assertEqual(row["predecessorSequences"], [self.step.sequence])
        self.assertNotIn("DEPENDENCY_REFERENCE_MISSING", row["blockerCodes"])
        self.assertIn("DAILY_CAPACITY_MISSING", row["blockerCodes"])

    def test_real_object_partition_preserves_required_subset_and_unknown_is_not_success(self):
        for mode in ("mixed", "partial"):
            with self.subTest(objectScope=mode), transaction.atomic():
                fixture = object_fixtures.make_object_applicability_fixture(f=self.f, plan=self.plan)
                first = self.f.baseline_items[0]
                matching = [req for req in self.requirements
                    if req.source_fact.trace.get("baselineItemId") == first.pk
                    and req.source_fact.trace.get("designItemId") == first.design_item_id]
                self.assertEqual(len(matching), 1)
                self.save_contributions(matching)
                contributions = []
                for index, template in enumerate(fixture.contributions):
                    if mode == "partial" and index:
                        continue
                    row = deepcopy(template)
                    row["decision"] = "REQUIRED" if mode == "mixed" and index == 0 else "NOT_APPLICABLE"
                    contributions.append(row)
                object_service.confirm_group(self.f.user, self.plan.pk, self.step.pk,
                    contributions, "SIMULATED_FOR_TEST single-step object scope")
                result = self.read(allow_error=True)
                if mode == "partial":
                    self.assert_blocked(result)
                else:
                    row = self.assert_scoped(result)
                    self.assertTrue(result["scopeNoDateReady"], result)
                    self.assertTrue(result["evaluatedRequiredStepsCovered"])
                    self.assertEqual(result["matchedAllocationCount"], 1)
                    self.assertEqual(row["objectCoverage"]["expectedDesignItemIds"], [first.design_item_id])
                    self.assertEqual(Decimal(row["processDemand"]["quantity"]), matching[0].workload_quantity)
                    self.assertEqual(len(row["processDemand"]["savedContributions"]), 1)
                transaction.set_rollback(True)
