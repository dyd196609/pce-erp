"""SIMULATED_FOR_TEST: request-local plan-allocation budget validation.

Real rules, frozen object facts, EORs, plans and allocation audits are created
only by the isolated Django test runner. Readers retain the native proofs.
SQL counts exclude fixture construction and protection snapshots; no timing or
customer-specific identifier is used as a performance assertion.
"""

from contextlib import ExitStack
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
import re
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from planning.models import Demand, PlanningRequirement, ProductionPlan
from sales.models import SalesOrderItem
from system.models import (
    Company, OrganizationOperatingAuditRecord, Permission, RolePermission,
    User, UserRoleScopeAssignment,
)
from workflow_runtime.models import BusinessStateTransition
from . import operation_requirement_service as operation
from . import tests_calc4_routing_correction as correction
from . import tests_classified_fact_eor as classified
from . import tests_plan_legal_extension_admission as legal
from .engineering_calculation_service import EngineeringCalculationService
from .engineering_fact_extension_service import EngineeringFactExtensionService
from .models import (
    EngineeringCalculationDetail, EngineeringCalculationRecord,
    EngineeringDerivedFact, EngineeringOperationRequirement,
    EngineeringRuleDefinition, ProductionPlanOperationRequirementAllocation,
    RoutingStep, RoutingVersion, StandardCapacity,
)
from .operation_requirement_correction_service import OperationRequirementCorrectionService


class WorkloadReadBudgetPerformanceTests(TestCase):
    def setUp(self):
        # Keep the fixture TestCase local, so discovery does not rerun its suite.
        class Fixture(correction.Calc4RoutingCorrectionTests):
            def advance(self, obj, target, *, status_field="status"):
                if (isinstance(obj, EngineeringCalculationRecord)
                        and obj.scope == "order_engineering" and target == "completed"):
                    classified.ClassifiedFactEorTests.finish_source_hashes(
                        self, obj, list(obj.derived_facts.order_by("sequence")))
                if isinstance(obj, RoutingVersion) and target == "reviewed":
                    for sequence in range(2, 5):
                        RoutingStep.objects.create(
                            routing_version=obj, sequence=sequence,
                            operation=self.op_area,
                            operation_parameters={"applicability": {
                                "contractVersion": "PCE-ROUTING-STEP-APPLICABILITY-V1.0",
                                "mode": "MANDATORY",
                            }})
                return super().advance(obj, target, status_field=status_field)

        self.f = Fixture(methodName="runTest")
        self.f.setUp()
        self.f.correct()
        permission, _ = Permission.objects.get_or_create(
            code=operation.PLAN_VIEW,
            defaults={"name": operation.PLAN_VIEW, "module": "PRODUCTION"})
        RolePermission.objects.get_or_create(role=self.f.role, permission=permission)
        self.plan = legal.PlanLegalExtensionAdmissionTests.make_plan(SimpleNamespace(f=self.f))
        self.steps = list(RoutingStep.objects.filter(
            routing_version=self.f.version).order_by("sequence"))
        requirements = list(EngineeringOperationRequirement.objects.filter(
            source_calculation=self.f.source_calc,
            source_fact_id__in=[fact.pk for fact in self.f.facts],
            source_detail__rule=self.f.correct_rule,
        ).order_by("source_fact_id"))
        self.assertEqual(len(requirements), 3)
        self.assertEqual(len(self.steps), 4)
        self.assertEqual(sum((row.workload_quantity for row in requirements), Decimal(0)), Decimal(4))
        self.requirements_by_step = {self.f.step.pk: requirements}

    def requirements_for_step(self, step):
        if step.pk not in self.requirements_by_step:
            def context(spec):
                spec["manufacturing"]["routingContext"]["routingStepId"] = step.pk
                spec["sourceEvidence"]["formalRouting"] = self.f.route_evidence(self.f.version, step)

            rule = self.f.new_rule(context)
            rows = []
            for fact in self.f.facts:
                generated = self.f.generate(
                    fact=fact, rule=rule, key=f"sim-read-budget-eor-{step.pk}-{fact.pk}")
                rows.append(EngineeringOperationRequirement.objects.get(
                    pk=generated["operationRequirementId"]))
            self.requirements_by_step[step.pk] = rows
        return self.requirements_by_step[step.pk]

    def save_through(self, contribution_count):
        self.assertIn(contribution_count, (3, 6, 12))
        saved_steps = set(ProductionPlanOperationRequirementAllocation.objects.filter(
            production_plan=self.plan).values_list("routing_step_id", flat=True))
        contributions = []
        for step in self.steps[:contribution_count // 3]:
            if step.pk in saved_steps:
                continue
            contributions.extend({
                "operationRequirementId": req.pk, "routingStepId": step.pk,
                "idempotencyKey": f"sim-read-budget-allocation-{req.pk}",
            } for req in self.requirements_for_step(step))
        if contributions:
            operation.OperationRequirementService.allocate_group(
                user=self.f.user, production_plan_id=self.plan.pk,
                contributions=contributions, reason="SIMULATED_FOR_TEST read-budget fixture")
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.filter(
            production_plan=self.plan).count(), contribution_count)

    def snapshot(self):
        # Account credentials and session values are deliberately excluded.
        models = (
            SalesOrderItem, EngineeringCalculationRecord, EngineeringCalculationDetail,
            EngineeringDerivedFact, EngineeringOperationRequirement,
            EngineeringRuleDefinition, ProductionPlanOperationRequirementAllocation,
            ProductionPlan, StandardCapacity, OrganizationOperatingAuditRecord,
            BusinessStateTransition,
        )
        return {model._meta.label: list(model.objects.order_by("pk").values()) for model in models}

    def readonly(self, action):
        before = self.snapshot()
        queries = None
        try:
            with ExitStack() as stack:
                for owner, name in (
                    (operation.OperationRequirementService, "generate"),
                    (operation.OperationRequirementService, "allocate"),
                    (operation.OperationRequirementService, "allocate_group"),
                    (OperationRequirementCorrectionService, "correct"),
                    (EngineeringCalculationService, "execute"),
                    (EngineeringFactExtensionService, "derive"),
                    (EngineeringFactExtensionService, "configure"),
                ):
                    stack.enter_context(patch.object(owner, name, side_effect=AssertionError(
                        "An allocation read must not execute a business writer")))
                stack.enter_context(patch.object(operation, "evaluate_specification", side_effect=AssertionError(
                    "An allocation read must not reevaluate the saved engineering result")))
                queries = stack.enter_context(CaptureQueriesContext(connection))
                return action()
        finally:
            self.last_sql = [row["sql"] for row in queries] if queries is not None else []
            self.assertEqual([sql for sql in self.last_sql if sql.lstrip().split()[0].upper()
                              in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "REPLACE"}], [])
            self.assertEqual(self.snapshot(), before)

    def read(self, *, user=None):
        return self.readonly(lambda: operation.OperationRequirementService.read(
            user=user or self.f.user, production_plan_id=self.plan.pk))

    def scope_selects(self):
        # The main plan query also SELECTs this column. Only a scope-budget
        # query filters the allocation table by the source's order-line FK.
        table = ProductionPlanOperationRequirementAllocation._meta.db_table.lower()
        rows = []
        for sql in self.last_sql:
            if not sql.lstrip().upper().startswith("SELECT") or table not in sql.lower():
                continue
            where = re.split(r"\bWHERE\b", sql, maxsplit=1, flags=re.IGNORECASE)
            if len(where) == 2 and re.search(
                    r"[\"`]?sales_order_item_id[\"`]?\s*=", where[1], flags=re.IGNORECASE):
                rows.append(sql)
        return rows

    def assert_passed(self, result, expected_count):
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["resultCount"], expected_count)
        self.assertEqual(len(result["allocations"]), expected_count)
        self.assertEqual(result["businessWriteCount"], 0)
        surface = {key: value for key, value in result.items() if key not in {
            "apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"}}
        for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts"):
            self.assertEqual(result[key], surface)

    def expected_validated_requirements(self, saved_requirement_ids):
        saved_ids = set(saved_requirement_ids)
        predecessor_calculation_ids = set(EngineeringOperationRequirement.objects.filter(
            pk__in=saved_ids).exclude(calculation__supersedes_id=None)
            .values_list("calculation__supersedes_id", flat=True))
        predecessor_ids = set(EngineeringOperationRequirement.objects.filter(
            calculation_id__in=predecessor_calculation_ids).values_list("pk", flat=True))
        self.assertEqual(len(predecessor_ids), len(predecessor_calculation_ids),
                         "Each native correction must retain its unique original requirement")
        # The first-step fixture contains three formal replacements. Their
        # lifecycle proof legitimately validates all three predecessor EORs.
        self.assertEqual(predecessor_ids, set(self.f.old_ids))
        return saved_ids | predecessor_ids

    def raw_fixture_fault(self, obj, field, value):
        """Deliberate fault injection, only before reads in the test database."""
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        quote = connection.ops.quote_name
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {quote(obj._meta.db_table)} SET {quote(obj._meta.get_field(field).column)} = %s "
                f"WHERE {quote(obj._meta.pk.column)} = %s", [value, obj.pk])

    def other_plan(self):
        f = self.f
        # Demand.item, Requirement.demand and Plan.requirement are OneToOne.
        # Use another real line for the foreign plan; this is not evidence that
        # a second plan is legally available for the original order-line scope.
        item = SalesOrderItem.objects.create(
            sales_order=f.order, line_no=2, material=f.item.material,
            quantity=37, uom=f.pcs, required_date=date.today(), engineering_mode="STANDARD")
        demand = f.initial(
            Demand, "draft", demand_no="SIM-READ-BUDGET-OTHER-DEMAND", source_type="sales_order",
            source_document_type="SalesOrder", source_document_id=str(f.order.pk),
            source_document_no=f.order.order_no, sales_order_item=item,
            material=f.item.material, required_qty=37,
            required_date=date.today(), department=f.department, reason="SIMULATED_FOR_TEST",
            acceptance_marker="SIMULATED_FOR_TEST", created_by=f.user)
        f.advance(demand, "confirmed")
        requirement = f.initial(
            PlanningRequirement, "draft", requirement_no="SIM-READ-BUDGET-OTHER-REQUIREMENT",
            demand=demand, material=f.item.material, demand_qty=37, available_qty=0,
            net_required_qty=37, required_date=date.today(), supply_type="production",
            calculation_facts={"sourceKind": "SIMULATED_FOR_TEST"}, created_by=f.user)
        f.advance(requirement, "calculated")
        f.advance(requirement, "confirmed")
        plan = f.initial(
            ProductionPlan, "draft", plan_no="SIM-READ-BUDGET-OTHER-PLAN",
            planning_requirement=requirement, material=f.item.material, planned_qty=37,
            required_date=date.today(), source_id=str(requirement.pk), confirmed_by=f.user)
        f.advance(plan, "confirmed")
        return plan

    def test_three_six_twelve_contributions_have_one_scope_scan_and_near_linear_select_growth(self):
        totals = {}
        for count in (3, 6, 12):
            with self.subTest(contributions=count):
                # Fixed three independent objects per step isolates the budget
                # growth from within-step pairwise compatibility comparisons.
                self.save_through(count)
                with patch.object(operation, "_validate_requirement", wraps=operation._validate_requirement) as validate, \
                     patch.object(operation, "_check_audit", wraps=operation._check_audit) as audit:
                    result = self.read()
                self.assert_passed(result, count)
                saved = list(ProductionPlanOperationRequirementAllocation.objects.filter(production_plan=self.plan))
                self.assertEqual({row["allocationId"] for row in result["allocations"]}, {row.pk for row in saved})
                self.assertEqual({row["auditId"] for row in result["allocations"]}, {row.audit_record_id for row in saved})
                self.assertEqual({call.args[0].pk for call in validate.call_args_list},
                                 self.expected_validated_requirements(row.operation_requirement_id for row in saved))
                allocation_audits = {call.args[0].pk for call in audit.call_args_list
                                     if call.kwargs.get("target_type") == "ProductionPlan"}
                self.assertEqual(allocation_audits, {row.audit_record_id for row in saved})
                self.assertEqual({row.source_uom_id for row in saved}, {self.f.pcs.pk})
                self.assertEqual({row.source_quantity for row in saved}, {Decimal(37)})
                self.assertEqual(len(self.scope_selects()), 1, "Same company/order-line/basis-unit scope was rescanned")
                totals[count] = sum(sql.lstrip().upper().startswith("SELECT") for sql in self.last_sql)
        first_growth = totals[6] - totals[3]
        second_growth = totals[12] - totals[6]
        self.assertGreater(first_growth, 0, totals)
        # Doubling the added contributions should double their SQL cost. Allow
        # modest query-shape overhead, but reject the previous quadratic scan.
        self.assertLessEqual(second_growth, 2.5 * first_growth + 24, totals)

    def test_a_new_read_revalidates_every_requirement_and_allocation_audit(self):
        self.save_through(3)
        for _ in range(2):
            with patch.object(operation, "_validate_requirement", wraps=operation._validate_requirement) as validate, \
                 patch.object(operation, "_check_audit", wraps=operation._check_audit) as audit:
                result = self.read()
            self.assert_passed(result, 3)
            self.assertEqual({call.args[0].pk for call in validate.call_args_list},
                             self.expected_validated_requirements(
                                 req.pk for req in self.requirements_for_step(self.f.step)))
            self.assertEqual({call.args[0].pk for call in audit.call_args_list
                              if call.kwargs.get("target_type") == "ProductionPlan"},
                             set(ProductionPlanOperationRequirementAllocation.objects.filter(
                                 production_plan=self.plan).values_list("audit_record_id", flat=True)))
            self.assertEqual(len(self.scope_selects()), 1)

    def test_a_new_read_notices_changed_eor_result_hash(self):
        self.save_through(3)
        self.assert_passed(self.read(), 3)
        req = self.requirements_for_step(self.f.step)[0]
        self.raw_fixture_fault(req.calculation, "result_hash", "0" * 64)
        result = self.read()
        self.assertFalse(result["passed"], result)
        self.assertIn("OPERATION_FACT_CHANGED", {row["code"] for row in result["blockers"]})
        self.assertEqual(result["allocations"], [])

    def test_a_new_read_notices_changed_allocation_audit(self):
        self.save_through(3)
        self.assert_passed(self.read(), 3)
        row = ProductionPlanOperationRequirementAllocation.objects.filter(production_plan=self.plan).first()
        snapshot = deepcopy(row.audit_record.after_snapshot)
        snapshot["state"]["operationRequirementAllocation"]["allocatedQuantity"] = "99"
        self.raw_fixture_fault(row.audit_record, "after_snapshot", snapshot)
        result = self.read()
        self.assertFalse(result["passed"], result)
        self.assertIn("OPERATION_AUDIT_INCONSISTENT", {item["code"] for item in result["blockers"]})
        self.assertEqual(result["allocations"], [])

    def test_a_new_read_notices_inactive_formal_capacity(self):
        self.save_through(3)
        self.assert_passed(self.read(), 3)
        self.raw_fixture_fault(self.f.capacity, "is_active", False)
        result = self.read()
        self.assertFalse(result["passed"], result)
        self.assertIn("MANUFACTURING_CAPACITY_INVALID", {item["code"] for item in result["blockers"]})
        self.assertEqual(result["allocations"], [])

    def test_a_new_read_rechecks_planning_permission_before_any_source_proof(self):
        self.save_through(3)
        self.assert_passed(self.read(), 3)
        RolePermission.objects.filter(role=self.f.role, permission__code=operation.PLAN_VIEW).delete()
        with patch.object(operation, "_validate_requirement", wraps=operation._validate_requirement) as validate:
            with self.assertRaises(operation.OperationRequirementError):
                self.read()
        validate.assert_not_called()

    def test_cross_plan_scope_fault_is_not_omitted_or_cached_as_success(self):
        self.save_through(3)
        self.assert_passed(self.read(), 3)
        other = self.other_plan()
        external = ProductionPlanOperationRequirementAllocation.objects.filter(production_plan=self.plan).first()
        # Keep its immutable source/snapshot/audit unchanged: the order-line
        # budget scan must include this foreign-plan row and reject its source
        # mismatch while reading each of the original plan's other two rows.
        self.raw_fixture_fault(external, "production_plan", other.pk)
        with patch.object(operation, "_scope_budget", wraps=operation._scope_budget) as budget, \
             patch.object(operation, "_validate_requirement", wraps=operation._validate_requirement) as validate:
            result = self.read()
        self.assertFalse(result["passed"], result)
        self.assertEqual(result["resultCount"], 2)
        self.assertEqual(result["allocations"], [])
        self.assertEqual({row["code"] for row in result["blockers"]}, {"ALLOCATION_SOURCE_MISMATCH"})
        self.assertEqual(len(result["blockers"]), 2)
        self.assertEqual(budget.call_count, 2, "A failed full-scope proof must be retried for the next row")
        self.assertEqual(len(self.scope_selects()), 2)
        self.assertGreaterEqual(sum(call.args[0].pk == external.operation_requirement_id
                                   for call in validate.call_args_list), 2)

    def test_another_company_cannot_reuse_the_same_plan_scope_proof(self):
        self.save_through(3)
        self.assert_passed(self.read(), 3)
        company = Company.objects.create(
            code="SIM-READ-BUDGET-OTHER", name="SIMULATED_FOR_TEST other read-budget company")
        user = User.objects.create_user(username="sim_read_budget_other", company_id=company.pk)
        UserRoleScopeAssignment.objects.create(
            user=user, role=self.f.role, organization=company, scope_code="ORGANIZATION",
            active=True, business_hash="SIMULATED_FOR_TEST")
        with patch.object(operation, "_scope_budget", wraps=operation._scope_budget) as budget:
            with self.assertRaises(operation.OperationRequirementError) as caught:
                self.read(user=user)
        self.assertEqual(caught.exception.code, "PLAN_NOT_FOUND")
        budget.assert_not_called()
