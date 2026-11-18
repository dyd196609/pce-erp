"""RAM-only native allocation budgets for retained and independent sources.

The legacy operation fixture supplies synthetic upstream manufacturing records;
EOR generation, allocation/read/group, immutable snapshots, audits and budgets
are native. Separate real continuation/extension fixtures cover their proofs.
No fixture establishes the actual customer manufacturing or time result.
"""
from copy import copy
from decimal import Decimal
from unittest.mock import patch
from django.db import connection, IntegrityError, transaction
from django.db.models import QuerySet
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from planning.models import Demand, PlanningRequirement, ProductionPlan
from system.models import OrganizationOperatingAuditRecord
from . import operation_requirement_service as native
from . import tests_operation_requirement as fixture
from . import tests_plan_legal_extension_admission as extension_fixture
from . import tests_plan_step_source_continuation as continuation_fixture
from .models import (
    BOMVersion, EngineeringCalculationRecord, EngineeringDocumentVersion,
    EngineeringOperationRequirement, OrderEngineeringBaseline,
    ProductManufacturingOutput, ProductionPlanOperationRequirementAllocation,
)


class AllocationBudgetSourceVersionTests(TestCase):
    def setUp(self):
        self.f = fixture.OperationRequirementTests(methodName="runTest")
        self.f.setUp()
        f = self.f
        ProductionPlan.objects.filter(pk=f.plan.pk).update(planned_qty=Decimal("5"))
        PlanningRequirement.objects.filter(pk=f.plan.planning_requirement_id).update(
            net_required_qty=Decimal("5"), available_qty=Decimal("0"))
        f.plan.refresh_from_db()
        self.old_generated = f.generate()
        old = f.allocate(self.old_generated)
        self.old_allocation = ProductionPlanOperationRequirementAllocation.objects.get(pk=old["allocationId"])
        self._make_new_source()
        self.old_protected = self._old_rows()

    def _old_rows(self):
        f = self.f
        return {model.__name__: list(model.objects.filter(pk=pk).values()) for model, pk in (
            (ProductionPlan, f.plan.pk), (PlanningRequirement, f.plan.planning_requirement_id),
            (Demand, f.plan.planning_requirement.demand_id), (ProductManufacturingOutput, f.output.pk),
            (EngineeringOperationRequirement, self.old_generated["operationRequirementId"]),
            (ProductionPlanOperationRequirementAllocation, self.old_allocation.pk),
            (OrganizationOperatingAuditRecord, self.old_allocation.audit_record_id))}

    def _make_new_source(self):
        f = self.f
        old_main = f.source_calc
        main = f.initial(EngineeringCalculationRecord, "draft", company=f.company,
            scope="order_engineering", source_record=f.source, sales_order_item=f.item,
            engineering_instance=f.instance, calculation_no="SIM-INDEPENDENT-MAIN-2", revision=2,
            supersedes=old_main, rule_set_version=old_main.rule_set_version,
            input_hash=old_main.input_hash, rule_graph_hash=old_main.rule_graph_hash,
            result_hash=old_main.result_hash, trace={"sourceKind": "SIMULATED_FOR_TEST"})
        f.advance(main, "prepared")
        f.advance(main, "running")
        f.source_calc = main
        self.new_fact_area = f.make_source_fact(f.fact_area.rule, f.area, "source_area", "20", 1)
        self.new_fact_count = f.make_source_fact(f.fact_count.rule, f.pcs, "source_count", "12", 2)
        main.started_at, main.finished_at = timezone.now(), timezone.now()
        main.save(update_fields=("started_at", "finished_at"))
        f.advance(main, "completed")
        f.source_calc = old_main
        baseline = f.initial(OrderEngineeringBaseline, "draft", company=f.company,
            sales_order=f.order, baseline_no="SIM-INDEPENDENT-BASE-2", sequence=2,
            reason="RAM independent source", candidate_hash="1" * 64, snapshot_hash="2" * 64,
            scope_item_count=1, confirmable_item_count=1, blocker_count=0,
            blocker_summary={}, created_by=f.user)
        baseline.confirmed_by, baseline.confirmed_at = f.user, timezone.now()
        baseline.save(update_fields=("confirmed_by", "confirmed_at"))
        f.advance(baseline, "confirmed")
        bom = f.initial(BOMVersion, "draft", bom=f.bom, bom_version="SIM-INDEPENDENT-2",
            revision=2, bom_scope="order_specific", order_engineering_instance=f.instance,
            source_calculation=main)
        f.advance(bom, "reviewed")
        f.advance(bom, "released")
        document = f.initial(EngineeringDocumentVersion, "draft", document=f.document.document,
            document_name="RAM independent source", document_version="SIM-INDEPENDENT-2",
            release_subject_type="ORDER_ENGINEERED_PRODUCT", order_engineering_instance=f.instance,
            order_engineering_baseline=baseline, engineering_calculation=main,
            related_bom=bom, related_routing=f.version)
        f.advance(document, "reviewed")
        f.advance(document, "released")
        output = f.initial(ProductManufacturingOutput, "draft", status_field="release_status",
            revision=2, predecessor=f.output, release_subject_type="ORDER_ENGINEERED_PRODUCT",
            definition_mode="order_specific", engineering_status="ready", order_engineering_instance=f.instance,
            order_engineering_baseline=baseline, engineering_calculation=main, bom_version=bom,
            routing_version=f.version, engineering_document_version=document)
        f.advance(output, "engineering_review", status_field="release_status")
        f.advance(output, "released_to_manufacturing", status_field="release_status")
        demand = f.initial(Demand, "draft", demand_no="SIM-INDEPENDENT-DEMAND-2", source_type="sales_order",
            source_document_type="SalesOrderItem", source_document_id=str(f.item.pk), source_document_no=f.order.order_no,
            sales_order_item=f.item, manufacturing_output=output, material=f.material, required_qty=5,
            required_date=f.item.required_date, department=f.department, reason="RAM independent source", created_by=f.user)
        f.advance(demand, "confirmed")
        requirement = f.initial(PlanningRequirement, "draft", requirement_no="SIM-INDEPENDENT-REQ-2",
            demand=demand, material=f.material, demand_qty=5, available_qty=0, net_required_qty=5,
            required_date=f.item.required_date, supply_type="production", calculation_facts={}, created_by=f.user)
        f.advance(requirement, "calculated")
        f.advance(requirement, "confirmed")
        plan = f.initial(ProductionPlan, "draft", plan_no="SIM-INDEPENDENT-PLAN-2",
            planning_requirement=requirement, material=f.material, planned_qty=5,
            required_date=f.item.required_date, source_id=str(requirement.pk), confirmed_by=f.user)
        f.advance(plan, "confirmed")
        self.new_plan, self.new_output, self.new_main, self.new_baseline = plan, output, main, baseline
        self.new_requirements = []
        for fact, rule in ((self.new_fact_area, f.rule_area), (self.new_fact_count, f.rule_count)):
            saved = native.OperationRequirementService.generate(user=f.user, source_calculation_id=main.pk,
                source_fact_id=fact.pk, rule_id=rule.pk, idempotency_key=f"independent-eor-{fact.pk}",
                reason="RAM independent source")
            self.new_requirements.append(EngineeringOperationRequirement.objects.get(pk=saved["operationRequirementId"]))

    def contributions(self):
        return [{"operationRequirementId": req.pk, "routingStepId": step.pk,
            "idempotencyKey": f"source-budget-{req.pk}"} for req, step in
            zip(self.new_requirements, (self.f.step_area, self.f.step_count))]

    def save_new(self):
        return native.OperationRequirementService.allocate_group(user=self.f.user,
            production_plan_id=self.new_plan.pk, contributions=self.contributions(), reason="RAM source budget")

    def read(self, plan, **kwargs):
        return native.OperationRequirementService.read(user=self.f.user, production_plan_id=plan.pk, **kwargs)

    def test_01_old_and_new_full_source_groups_coexist_and_keep_old_frozen_rows(self):
        ready = native.OperationRequirementService.allocation_group_readiness(user=self.f.user,
            production_plan_id=self.new_plan.pk, contributions=self.contributions())
        self.assertTrue(ready["canSave"], ready)
        self.assertEqual(ready["groupChecks"]["quantityBudget"]["passed"], True)
        self.save_new()
        for plan, count in ((self.f.plan, 1), (self.new_plan, 2)):
            result = self.read(plan)
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["resultCount"], count)
        self.assertEqual(self.old_protected, self._old_rows())

    def test_02_same_source_parallel_plan_or_quantity_overflow_cannot_gain_a_new_budget(self):
        self.save_new()
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                self.f.initial(Demand, "draft", demand_no="DUPLICATE-SOURCE-DEMAND", source_type="sales_order",
                    source_document_type="SalesOrderItem", source_document_id=str(self.f.item.pk),
                    source_document_no=self.f.order.order_no, sales_order_item=self.f.item,
                    manufacturing_output=self.new_output, material=self.f.material, required_qty=1,
                    required_date=self.f.item.required_date, department=self.f.department,
                    reason="RAM duplicate rejected by original source uniqueness", created_by=self.f.user)
            transaction.set_rollback(True)
        # Defense at the budget component: changing a proposed plan identity
        # cannot replenish an already full exact-source budget.
        proposal = copy(self.new_plan)
        proposal.pk += 100000
        with self.assertRaises(native.OperationRequirementError) as caught:
            native._scope_budget(self.new_requirements[0], self.f.company.pk,
                proposed_plan=proposal, proposed_quantity=Decimal("1"))
        self.assertEqual(caught.exception.code, "ALLOCATION_SCOPE_EXCEEDED")
        self.assertEqual(self.old_protected, self._old_rows())

    def test_03_multiple_rules_count_source_plan_once_and_replay_is_zero_write(self):
        self.save_new()
        before = list(ProductionPlanOperationRequirementAllocation.objects.order_by("pk").values())
        audits = OrganizationOperatingAuditRecord.objects.count()
        again = self.save_new()
        self.assertTrue(again["idempotent"])
        self.assertEqual((again["businessWriteCount"], again["auditWriteCount"]), (0, 0))
        self.assertEqual(before, list(ProductionPlanOperationRequirementAllocation.objects.order_by("pk").values()))
        self.assertEqual(audits, OrganizationOperatingAuditRecord.objects.count())
        rows = list(ProductionPlanOperationRequirementAllocation.objects.filter(production_plan=self.new_plan))
        validated = native._validate_allocation(rows[0], self.f.company.pk, verify_budget=False)
        scope = native._allocation_budget_scope(rows[0].operation_requirement, self.f.company.pk, validated=validated)
        self.assertEqual(native._scope_budget(rows[0].operation_requirement, self.f.company.pk, source_scope=scope),
            {self.new_plan.pk: Decimal("5")})

    def test_04_cross_source_requirements_are_rejected_before_quantity_scoping(self):
        for plan, req in ((self.new_plan, EngineeringOperationRequirement.objects.get(
                pk=self.old_generated["operationRequirementId"])), (self.f.plan, self.new_requirements[0])):
            ready = native.OperationRequirementService.allocation_readiness(user=self.f.user,
                production_plan_id=plan.pk, operation_requirement_id=req.pk, routing_step_id=self.f.step_area.pk)
            self.assertFalse(ready["canSave"], ready)
            self.assertEqual(ready["blockers"][0]["code"], "ALLOCATION_SOURCE_MISMATCH")
        self.assertEqual(self.old_protected, self._old_rows())

    def test_05_corrupt_old_cross_plan_row_is_validated_before_source_exclusion(self):
        self.save_new()
        with connection.cursor() as cursor:
            cursor.execute('UPDATE "pde_production_plan_operation_requirement_allocation" '
                'SET production_plan_id=%s WHERE id=%s', [self.new_plan.pk, self.old_allocation.pk])
        changes = connection.connection.total_changes
        result = self.read(self.new_plan)
        self.assertFalse(result["passed"], result)
        self.assertEqual(result["allocations"], [])
        self.assertIn("ALLOCATION_SOURCE_MISMATCH", {row["code"] for row in result["blockers"]})
        self.assertEqual(changes, connection.connection.total_changes)

    def test_06_read_cache_separates_domains_and_same_block_write_invalidates_old_success(self):
        self.save_new()
        with transaction.atomic():
            cache = native._source_read_cache(self.f.user, None)
            self.assertTrue(self.read(self.f.plan, _read_cache=cache)["passed"])
            self.assertTrue(self.read(self.new_plan, _read_cache=cache)["passed"])
            self.assertEqual(len(cache.budget_proofs), 2)
            audit = self.old_allocation.audit_record
            changed = dict(audit.after_snapshot)
            changed["state"] = {**changed["state"], "operationRequirementAllocation": {}}
            OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).update(after_snapshot=changed)
            changes = connection.connection.total_changes
            result = self.read(self.new_plan, _read_cache=cache)
            self.assertFalse(result["passed"], result)
            self.assertIn("OPERATION_AUDIT_INCONSISTENT", {row["code"] for row in result["blockers"]})
            self.assertEqual(changes, connection.connection.total_changes)

    def test_budget_batch_source_relations_preserve_native_results_without_lazy_identity_reads(self):
        self.save_new()
        original_prefetch = QuerySet.prefetch_related
        original_scope = native._allocation_budget_scope

        def run(restore_old_reads):
            identity_queries = []
            def prefetch(query, *lookups):
                if restore_old_reads and query.model is ProductionPlanOperationRequirementAllocation:
                    # Restore only the former lazy source relation. The raw
                    # route reader now prefetches additional plan relations;
                    # those independent joins must not disable this contrast.
                    lookups = tuple(value for value in lookups if value !=
                        'operation_requirement__source_calculation__sales_order_item')
                return original_prefetch(query, *lookups)
            def observe(req, *args, **kwargs):
                with CaptureQueriesContext(connection) as queries:
                    result = original_scope(req, *args, **kwargs)
                if kwargs.get('validated') is not None:
                    identity_queries.extend(queries)
                return result
            changes = connection.connection.total_changes
            with patch.object(QuerySet, 'prefetch_related', prefetch), \
                    patch.object(native, '_allocation_budget_scope', side_effect=observe):
                results = [self.read(plan) for plan in (self.f.plan, self.new_plan)]
            self.assertTrue(all(result['passed'] for result in results), results)
            self.assertEqual(changes, connection.connection.total_changes)
            return results, identity_queries

        old, old_queries = run(True)
        current, current_queries = run(False)
        self.assertEqual(current, old)
        self.assertGreater(len(old_queries), 0)
        self.assertEqual(current_queries, [])
        self.assertEqual(self.old_protected, self._old_rows())


class AllocationBudgetLegalExtensionScopeTests(TestCase):
    def test_07_direct_and_legal_extension_use_the_same_formal_main_budget_domain(self):
        e = extension_fixture.PlanLegalExtensionAdmissionTests(methodName="runTest")
        e.setUp()
        f = e.f
        direct = f.generate(fact=f.facts[0], rule=f.correct_rule, key="budget-direct-main")
        scopes = []
        for req_id in (direct["operationRequirementId"], e.requirements[0].pk):
            context = {}
            ready = native.OperationRequirementService.allocation_readiness(user=f.user,
                production_plan_id=e.plan.pk, operation_requirement_id=req_id, routing_step_id=f.step.pk,
                _context_out=context)
            self.assertTrue(ready["canSave"], ready)
            scopes.append(native._allocation_budget_scope(context["req"], f.company.pk, plan=context["plan"]))
        self.assertEqual(scopes[0], scopes[1])
        self.assertEqual(scopes[0][2:], (f.output.pk, f.source_calc.pk, f.baseline.pk))


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE={
    "companyCode": "LIA", "orderNo": "SO-LIA-001", "lineNo": 1})
class AllocationBudgetContinuationScopeTests(TestCase):
    _adopt = continuation_fixture.PlanStepSourceContinuationTests._adopt
    args = continuation_fixture.PlanStepSourceContinuationTests.args
    execute_main = continuation_fixture.PlanStepSourceContinuationTests.execute_main
    numeric_fixture = continuation_fixture.PlanStepSourceContinuationTests.numeric_fixture
    _make_original_output_and_plan = continuation_fixture.PlanStepSourceContinuationTests._make_original_output_and_plan
    handoff_arguments = continuation_fixture.PlanStepSourceContinuationTests.handoff_arguments
    activate = continuation_fixture.PlanStepSourceContinuationTests.activate
    _consumer_type = continuation_fixture.PlanStepSourceContinuationTests._consumer_type
    _direct_requirement = continuation_fixture.PlanStepSourceContinuationTests._direct_requirement
    setUp = continuation_fixture.PlanStepSourceContinuationTests.setUp

    @classmethod
    def setUpClass(cls):
        # The established adoption fixture needs one historical cutoff. The
        # RAM runner syncs models without migrations, so create only this test
        # recorder input before TestCase opens its atomic block. No migration
        # or deployment proof is produced, and every connection is RAM-guarded.
        name = str(connection.settings_dict["NAME"])
        assert name == ":memory:" or (name.startswith("file:memorydb_") and "mode=memory" in name)
        recorder = MigrationRecorder(connection)
        recorder.ensure_schema()
        from .legacy_inflight_order_adoption import MODEL_CUTOFF_MIGRATIONS
        for migration in MODEL_CUTOFF_MIGRATIONS:
            if not recorder.migration_qs.filter(app="pde", name=migration).exists():
                recorder.record_applied("pde", migration)
        super().setUpClass()

    @classmethod
    def setUpTestData(cls):
        continuation_fixture.PlanStepSourceContinuationTests.setUpTestData.__func__(cls)

    def test_08_native0046_frozen_row_uses_effective_main_baseline_not_old_output_anchor(self):
        self.activate()
        _, _, _, req = self._direct_requirement()
        result = native.OperationRequirementService.allocate(user=self.actor,
            production_plan_id=self.plan.pk, operation_requirement_id=req.pk, routing_step_id=self.step.pk,
            idempotency_key="budget-continuation-native-allocation", reason="RAM native0046 budget")
        row = ProductionPlanOperationRequirementAllocation.objects.get(pk=result["allocationId"])
        validated = native._validate_allocation(row, self.company.pk, verify_budget=False)
        scope = native._allocation_budget_scope(req, self.company.pk, validated=validated)
        self.assertEqual(scope, (self.company.pk, self.items[0].pk, self.anchor.pk,
            self.main.pk, self.new_baseline.pk))
        self.assertNotEqual(scope[-2:], (self.anchor.engineering_calculation_id,
            self.anchor.order_engineering_baseline_id))
        self.assertEqual(row.source_snapshot["planStepVersionBinding"]["sourceSelection"]["mainCalculationId"], self.main.pk)
        self.assertTrue(native.OperationRequirementService.read(user=self.actor,
            production_plan_id=self.plan.pk)["passed"])
        self.assertEqual(self.original_plan, ProductionPlan.objects.values().get(pk=self.plan.pk))
        self.assertEqual(self.original_demand, Demand.objects.values().get(pk=self.plan.planning_requirement.demand_id))
