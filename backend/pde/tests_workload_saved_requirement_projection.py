"""SIMULATED_FOR_TEST: saved original-source EORs in the existing read projection.

Every source/rule/EOR/allocation below is created in the disposable Django test
database.  The reader uses the real source and allocation proofs; PURPOSES and
proof results are never patched.  Fixture writers are disabled during each read.
"""

from contextlib import ExitStack
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from system.models import (
    Company, OrganizationOperatingAuditRecord, Permission, Role, RolePermission,
    User, UserRoleScopeAssignment,
)
from workflow_runtime.models import BusinessStateTransition
from . import engineering_workload_review as review
from . import operation_requirement_service as operation
from . import tests_calc4_routing_correction as correction
from . import tests_classified_fact_eor as classified
from . import tests_engineering_fact_extension as extension_fixtures
from . import tests_operation_requirement as original
from . import tests_plan_legal_extension_admission as legal
from .engineering_calculation_service import EngineeringCalculationService
from .engineering_fact_extension_service import (
    CONTRACT as EXTENSION_CONTRACT, EngineeringFactExtensionService,
)
from .engineering_workload_summary import FACT_SURFACES, build_engineering_workload_summary
from .manufacturing_configuration_service import CREATE, RELEASE
from .models import (
    EngineeringCalculationDetail, EngineeringCalculationRecord,
    EngineeringDerivedFact, EngineeringFactInput, EngineeringOperationRequirement,
    EngineeringRuleDefinition, OrderEngineeringInstance,
    ProductionPlanOperationRequirementAllocation, RoutingStep, RoutingVersion,
)
from .operation_requirement_correction_service import OperationRequirementCorrectionService
from planning.models import ProductionPlan
from sales.models import SalesOrder, SalesOrderItem


class SavedRequirementProjectionTests(TestCase):
    def setUp(self):
        # Keep the derived TestCase local: unittest must not discover and rerun
        # the routing fixture's existing suite through this module.
        class DirectSourceFixture(correction.Calc4RoutingCorrectionTests):
            def make_rule(self, process, unit, source_name, **kwargs):
                if source_name == "opaque_area":
                    source_name = "W"
                return super().make_rule(process, unit, source_name, **kwargs)

            def original_fact(self, producer, value, sequence, object_index):
                fact = original.OperationRequirementTests.make_source_fact(
                    self, producer, self.area, "W", value, sequence)
                item = self.baseline_items[object_index]
                detail = fact.source_detail
                detail.input_snapshot["object"] = deepcopy(
                    self.source_calc.trace["objectInputSnapshot"][object_index]["input"])
                detail.save(update_fields=("input_snapshot",))
                fact.trace.update(
                    resultScope="original", baselineId=self.baseline.pk,
                    baselineItemId=item.pk, designItemId=item.design_item_id,
                    sourceAttributeId=item.source_attribute_id,
                    baselineContentHash=item.content_hash,
                )
                fact.save(update_fields=("trace",))
                return fact

            def make_fact(self, value, sequence):
                return self.original_fact(self.producer, value, sequence, sequence - 1)

            def advance(self, obj, target, *, status_field="status"):
                if (isinstance(obj, EngineeringCalculationRecord)
                        and obj.scope == "order_engineering" and target == "completed"):
                    # An extra same-name/unit W has a different producer and no
                    # manufacturing mapping.  Broad W discovery would add 99.
                    producer = self.make_rule(
                        self.op_area, self.area, "W", output_domain="DERIVED_FACT")
                    self.unmapped_fact = self.original_fact(producer, "99", 4, 0)
                    classified.ClassifiedFactEorTests.finish_source_hashes(
                        self, obj, list(obj.derived_facts.order_by("sequence")))
                if isinstance(obj, RoutingVersion) and target == "reviewed":
                    RoutingStep.objects.create(
                        routing_version=obj, sequence=2, operation=self.op_area,
                        predecessor_sequences=[1], operation_parameters={"applicability": {
                            "contractVersion": "PCE-ROUTING-STEP-APPLICABILITY-V1.0",
                            "mode": "MANDATORY",
                        }})
                return super().advance(obj, target, status_field=status_field)

        fixture = DirectSourceFixture(methodName="runTest")
        fixture.setUp()
        fixture.correct()
        self.f = fixture
        self.requirements = list(EngineeringOperationRequirement.objects.filter(
            source_calculation=fixture.source_calc,
            source_fact_id__in=[fact.pk for fact in fixture.facts],
            source_detail__rule=fixture.correct_rule,
        ).order_by("source_fact_id"))
        self.assertEqual(len(self.requirements), 3)
        self.assertEqual(sum((req.workload_quantity for req in self.requirements), Decimal(0)), Decimal(4))
        self.assertEqual({fact.canonical_field for fact in fixture.facts}, {"W"})
        self.assertEqual(fixture.source_calc.status, "completed")
        self.assertIn("resultSnapshot", fixture.source_calc.trace)
        permission, _ = Permission.objects.get_or_create(
            code=operation.PLAN_VIEW, defaults={"name": operation.PLAN_VIEW, "module": "PRODUCTION"})
        RolePermission.objects.get_or_create(role=fixture.role, permission=permission)
        self.plan = legal.PlanLegalExtensionAdmissionTests.make_plan(SimpleNamespace(f=fixture))
        self.second_step = RoutingStep.objects.get(routing_version=fixture.version, sequence=2)

    def save(self, requirements=None, *, step=None, prefix="sim-saved-projection"):
        rows = [{"operationRequirementId": req.pk, "routingStepId": (step or self.f.step).pk,
                 "idempotencyKey": f"{prefix}:{req.pk}"}
                for req in (self.requirements if requirements is None else requirements)]
        return operation.OperationRequirementService.allocate_group(
            user=self.f.user, production_plan_id=self.plan.pk, contributions=rows,
            reason="SIMULATED_FOR_TEST saved-projection fixture")

    def snapshot(self):
        # No account, password or session values are part of this comparison.
        models = (
            EngineeringCalculationRecord, EngineeringCalculationDetail, EngineeringDerivedFact,
            EngineeringFactInput, EngineeringOperationRequirement, EngineeringRuleDefinition,
            ProductionPlanOperationRequirementAllocation, ProductionPlan,
            OrganizationOperatingAuditRecord, BusinessStateTransition,
        )
        return {model._meta.label: list(model.objects.order_by("pk").values()) for model in models}

    def read(self, *, user=None, calculations=None, summary=False):
        before = self.snapshot()
        denied = AssertionError("projection must not execute a writer")
        writers = (
            (operation.OperationRequirementService, "generate"),
            (operation.OperationRequirementService, "allocate"),
            (operation.OperationRequirementService, "allocate_group"),
            (OperationRequirementCorrectionService, "correct"),
            (EngineeringCalculationService, "execute"),
            (EngineeringFactExtensionService, "derive"),
            (EngineeringFactExtensionService, "configure"),
        )
        with ExitStack() as stack:
            for owner, name in writers:
                stack.enter_context(patch.object(owner, name, side_effect=denied))
            with CaptureQueriesContext(connection) as captured:
                if summary:
                    result = build_engineering_workload_summary(
                        user=user or self.f.user, source_calculation_ids=[self.f.source_calc.pk])
                else:
                    result = review.build_purpose_review(
                        user=user or self.f.user,
                        calculations=[self.f.source_calc] if calculations is None else calculations)
        writes = [row["sql"] for row in captured
                  if row["sql"].lstrip().split()[0].upper()
                  in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "REPLACE"}]
        self.assertEqual(writes, [])
        self.assertEqual(self.snapshot(), before)
        self.last_read_queries = [row["sql"] for row in captured]
        return result

    def target_load(self, result, *, step=None):
        rows = [row for row in result["operationLoads"]
                if row["dimensions"]["routingStepId"] == (step or self.f.step).pk
                and set(row["requirementIds"]) & {req.pk for req in self.requirements}]
        self.assertEqual(len(rows), 1, result)
        return rows[0]

    def test_three_saved_original_w_contributions_keep_exact_allocation_and_source_identity(self):
        self.save()
        result = self.read()
        load = self.target_load(result)
        saved = list(ProductionPlanOperationRequirementAllocation.objects.filter(
            production_plan=self.plan, operation_requirement__in=self.requirements).order_by("pk"))
        self.assertEqual(load["effectiveQuantity"], "4")
        self.assertEqual(load["allocatedQuantity"], "4")
        self.assertEqual(load["allocationStatusLabel"], "已保存且通过原服务校验的计划负荷")
        self.assertEqual(set(load["requirementIds"]), {req.pk for req in self.requirements})
        self.assertEqual({row["allocationId"] for row in load["allocations"]}, {row.pk for row in saved})
        self.assertEqual({row["auditId"] for row in load["allocations"]}, {row.audit_record_id for row in saved})
        self.assertEqual({row["productionPlanId"] for row in load["allocations"]}, {self.plan.pk})
        contributions = load["contributions"]
        self.assertEqual(len(contributions), 3)
        self.assertEqual({row["sourceFactId"] for row in contributions}, {fact.pk for fact in self.f.facts})
        self.assertEqual({row["designItemId"] for row in contributions},
                         {item.design_item_id for item in self.f.baseline_items})
        self.assertEqual({row["baselineItemId"] for row in contributions},
                         {item.pk for item in self.f.baseline_items})
        for row in contributions:
            allocation = next(saved_row for saved_row in saved
                              if saved_row.operation_requirement_id == row["operationRequirementId"])
            self.assertEqual(row["sourceCalculationId"], self.f.source_calc.pk)
            self.assertEqual(row["salesOrderItemId"], self.f.item.pk)
            self.assertEqual(len(row["allocations"]), 1)
            self.assertEqual(row["allocations"][0]["allocationId"], allocation.pk)
            self.assertEqual(row["allocations"][0]["auditId"], allocation.audit_record_id)
        self.assertEqual(result["counts"]["effectiveRequirementCount"], 3)

    def test_same_step_raw_select_does_not_grow_with_saved_contributions_or_cross_requests(self):
        def step_select_count():
            table = connection.ops.quote_name(RoutingStep._meta.db_table)
            operation_column = f'{table}.{connection.ops.quote_name("operation_id")}'
            version_column = f'{table}.{connection.ops.quote_name("routing_version_id")}'
            # Match the real raw list query, excluding the native ID-based
            # step proof. Native proofs and all contribution quantities run.
            return sum(
                1 for sql in self.last_read_queries
                if f'FROM {table} WHERE ' in sql and " LIMIT " not in sql
                and f'{operation_column} =' in sql.split(" WHERE ", 1)[-1]
                and f'{version_column} =' in sql.split(" WHERE ", 1)[-1])

        self.save(self.requirements[:1], prefix="sim-step-cache-one")
        first = self.target_load(self.read())
        self.assertEqual(first["requirementIds"], [self.requirements[0].pk])
        self.assertEqual(Decimal(first["allocatedQuantity"]), self.requirements[0].workload_quantity)
        one_count = step_select_count()
        self.assertEqual(one_count, 1)

        self.save(self.requirements[1:], prefix="sim-step-cache-additional")
        expanded = self.target_load(self.read())
        self.assertEqual(set(expanded["requirementIds"]), {req.pk for req in self.requirements})
        self.assertEqual(expanded["allocatedQuantity"], "4")
        self.assertEqual(len(expanded["contributions"]), 3)
        self.assertEqual(step_select_count(), one_count)

        # A second request performs its own raw SELECT rather than reusing an
        # ORM row list from the preceding request's expired atomic context.
        self.assertEqual(self.target_load(self.read())["allocatedQuantity"], "4")
        self.assertEqual(step_select_count(), one_count)

    def test_unallocated_nonpurpose_w_eors_are_not_newly_discovered_or_shown_as_zero(self):
        result = self.read()
        self.assertEqual(result["operationLoads"], [])
        self.assertEqual(result["counts"]["effectiveRequirementCount"], 0)
        self.assertFalse(any(row["purposeCode"] in {"CUTTING", "PAINTING"} for row in result["groups"]))
        self.assertEqual(ProductionPlanOperationRequirementAllocation.objects.count(), 0)

    def test_same_named_unmapped_w_is_not_added_to_saved_workload_or_candidates(self):
        self.save()
        result = self.read()
        load = self.target_load(result)
        self.assertEqual(load["effectiveQuantity"], "4")
        self.assertEqual(load["allocatedQuantity"], "4")
        self.assertNotIn(self.f.unmapped_fact.pk, {row["sourceFactId"] for row in load["contributions"]})
        self.assertFalse(EngineeringOperationRequirement.objects.filter(source_fact=self.f.unmapped_fact).exists())
        self.assertFalse(any(row["purposeCode"] in {"CUTTING", "PAINTING"} for row in result["groups"]))

    def test_same_fact_saved_at_another_formal_step_keeps_independent_eor_load(self):
        self.save()
        def second_context(spec):
            spec["manufacturing"]["routingContext"]["routingStepId"] = self.second_step.pk
            spec["sourceEvidence"]["formalRouting"] = self.f.route_evidence(self.f.version, self.second_step)
        rule = self.f.new_rule(second_context)
        generated = self.f.generate(fact=self.f.facts[0], rule=rule, key="sim-saved-second-step")
        requirement = EngineeringOperationRequirement.objects.get(pk=generated["operationRequirementId"])
        self.save([requirement], step=self.second_step, prefix="sim-saved-other-occurrence")
        result = self.read()
        original_load = self.target_load(result)
        second = next(row for row in result["operationLoads"]
                      if row["dimensions"]["routingStepId"] == self.second_step.pk)
        self.assertEqual(original_load["effectiveQuantity"], "4")
        self.assertEqual(second["effectiveQuantity"], "1.5")
        self.assertEqual(second["allocatedQuantity"], "1.5")
        self.assertEqual(second["requirementIds"], [requirement.pk])
        self.assertEqual(second["contributions"][0]["sourceFactId"], self.f.facts[0].pk)
        self.assertEqual(len(second["allocations"]), 1)
        self.assertEqual(len(result["operationLoads"]), 2)

    def viewer(self, *, company=None, planning=False):
        company = company or self.f.company
        role = Role.objects.create(code=f"SIM-SAVED-VIEW-{company.pk}", name="SIMULATED_FOR_TEST viewer")
        codes = [operation.VIEW, *([operation.PLAN_VIEW] if planning else [])]
        for code in codes:
            permission, _ = Permission.objects.get_or_create(
                code=code, defaults={"name": code, "module": "PRODUCTION"})
            RolePermission.objects.create(role=role, permission=permission)
        user = User.objects.create_user(username=f"sim_saved_view_{company.pk}", company_id=company.pk)
        UserRoleScopeAssignment.objects.create(
            user=user, role=role, organization=company, scope_code="ORGANIZATION",
            active=True, business_hash="SIMULATED_FOR_TEST")
        return user

    def test_no_planning_permission_does_not_discover_saved_w_or_read_allocations(self):
        self.save()
        result = self.read(user=self.viewer())
        self.assertFalse(result["planningAccess"]["allowed"])
        self.assertEqual(result["operationLoads"], [])
        self.assertTrue(all(row["confirmedPlan"]["quantity"] is None for row in result["groups"]))
        self.assertFalse(any("pde_production_plan_operation_requirement_allocation" in sql
                             for sql in self.last_read_queries))

    def test_foreign_company_and_unselected_order_scope_cannot_recover_saved_rows(self):
        self.save()
        company = Company.objects.create(code="SIM-SAVED-FOREIGN", name="SIMULATED_FOR_TEST other company")
        foreign = self.read(user=self.viewer(company=company, planning=True))
        self.assertEqual(foreign["operationLoads"], [])
        self.assertEqual(foreign["groups"], [])
        other_order = self.f.initial(
            SalesOrder, "draft", company=self.f.company, department=self.f.department,
            customer=self.f.order.customer, order_no="SO-SIM-UNSELECTED-SAVED",
            order_date=self.f.order.order_date, required_delivery_date=self.f.order.required_delivery_date,
            created_by=self.f.user,
            delivery_information={"businessPurpose": "DEVELOPMENT_VALIDATION", "source": "SIMULATED_FOR_TEST"})
        self.f.advance(other_order, "confirmed")
        item = SalesOrderItem.objects.create(
            sales_order=other_order, line_no=1, material=self.f.item.material,
            quantity=37, uom=self.f.pcs, required_date=self.f.item.required_date,
            engineering_mode="ORDER_ENGINEERED")
        instance = self.f.initial(
            OrderEngineeringInstance, "draft", company=self.f.company,
            instance_no="SIM-SAVED-UNSELECTED-INSTANCE", sales_order_item=item,
            product_category=self.f.category, selected_process_type=self.f.kind, source_record=self.f.source)
        # This other scope deliberately lacks a manufacturing-output proof.
        # It must report that omission, never borrow the selected scope's rows.
        calculation = self.f.initial(
            EngineeringCalculationRecord, "running", company=self.f.company,
            scope="order_engineering", source_record=self.f.source,
            sales_order_item=item, engineering_instance=instance,
            calculation_no="SIM-SAVED-UNSELECTED-CALC", rule_set_version="SIM-V1",
            input_hash=operation._digest("unselected"), result_hash=operation._digest([]),
            rule_graph_hash=operation._digest([]))
        original.OperationRequirementTests.advance(self.f, calculation, "completed")
        unselected = self.read(calculations=[calculation])
        self.assertEqual(unselected["operationLoads"], [])
        self.assertIn("FIXED_OUTPUT_UNPROVEN", {row["code"] for row in unselected["missingReasons"]})

    def test_invalid_saved_source_reports_native_blocker_without_reusing_stale_quantity(self):
        self.save()
        self.assertEqual(self.target_load(self.read())["allocatedQuantity"], "4")
        # Deliberate corruption is confined to this disposable fixture.
        fact = self.f.facts[0]
        fact.value = {"decimal": "999"}
        fact.save(update_fields=("value",))
        result = self.read()
        self.assertTrue(result["missingReasons"], result)
        self.assertFalse(any(row["operationRequirementId"] == self.requirements[0].pk
                             for load in result["operationLoads"] for row in load["contributions"]))
        self.assertFalse(any(row.get("allocatedQuantity") == "4" for row in result["operationLoads"]))

    def extension(self, field, *, grouped):
        f = self.f
        for code in (CREATE, RELEASE):
            permission, _ = Permission.objects.get_or_create(
                code=code, defaults={"name": code, "module": "PRODUCTION"})
            RolePermission.objects.get_or_create(role=f.role, permission=permission)
        binding = extension_fixtures.EngineeringFactExtensionTests.binding(
            f, "area_quantity", "W", f.producer, f.area, f.area)
        config = {"strategy": "GROUP_SUM" if grouped else "SCOPE_SUM", "bindings": [binding]}
        if grouped:
            identities = ["baselineId", "baselineItemId", "designItemId", "sourceAttributeId"]
            config.update(groupKeys=identities, metadataBindings=[
                {"name": name, "sourceType": "FORMAL_SOURCE_IDENTITY", "valueField": name}
                for name in identities])
        spec = extension_fixtures.EngineeringFactExtensionTests.spec(
            f, [{"canonicalName": "area_quantity", "valueType": "decimal", "unit": f.area.code,
                 "unitDimension": "area", "sourceType": "AGGREGATED", "required": True,
                 "unitRequired": True}], field, "area_quantity", config)
        configured = EngineeringFactExtensionService.configure(
            user=f.user, package={"contractVersion": EXTENSION_CONTRACT, "companyId": f.company.pk,
                "rules": [{"ruleCode": f"SIM-SAVED-{field}", "ruleName": "SIMULATED_FOR_TEST final purpose",
                           "version": "V1", "specification": spec}]}, reason="SIMULATED_FOR_TEST")
        result = EngineeringFactExtensionService.derive(
            user=f.user, source_calculation_id=f.source_calc.pk, rule_ids=configured["ruleIds"],
            idempotency_key=f"sim-saved-extension:{field}", reason="SIMULATED_FOR_TEST")
        facts = list(EngineeringDerivedFact.objects.filter(pk__in=result["factIds"]).order_by("pk"))
        rule = f.make_mapping(
            facts[0], f.op_area, f.area, mode=f.mode, capacity=f.capacity,
            dynamic_source_basis=True, release=False)
        rule.specification["manufacturing"]["sourceSelector"]["traceEquals"] = {
            "contractVersion": EXTENSION_CONTRACT}
        if grouped:
            rule.specification["manufacturing"]["routingContext"] = {
                "contractVersion": correction.ROUTE_CONTRACT, "routingId": f.route.pk,
                "routingVersionId": f.version.pk, "routingStepId": self.second_step.pk}
            rule.specification["sourceEvidence"]["formalRouting"] = f.route_evidence(f.version, self.second_step)
        # SCOPE_SUM deliberately has no one-object baselineId trace.  Keep its
        # established extension route contract: allocation proves the fixed
        # baseline through the formal input links and original route resolver.
        # Do not fabricate a single-object identity or patch that proof.
        rule.save(update_fields=("specification",))
        f.advance(rule, "reviewed")
        f.advance(rule, "released")
        requirements = []
        for fact in facts:
            generated = operation.OperationRequirementService.generate(
                user=f.user, source_calculation_id=fact.calculation_id, source_fact_id=fact.pk,
                rule_id=rule.pk, idempotency_key=f"sim-saved-final:{fact.pk}", reason="SIMULATED_FOR_TEST")
            requirements.append(EngineeringOperationRequirement.objects.get(pk=generated["operationRequirementId"]))
        return requirements

    def test_original_cutting_painting_candidates_and_already_discovered_saved_eor_are_preserved(self):
        board = self.extension("BoardNetAreaSummary", grouped=False)
        self.extension("PaintingProcessAreaQuantity", grouped=True)
        self.save(board, step=self.second_step, prefix="sim-saved-existing-final")
        before = self.read()
        old_loads = {row["key"]: deepcopy(row) for row in before["operationLoads"]}
        self.assertEqual({row["purposeCode"] for row in before["groups"] if row["purposeCode"] != "PHYSICAL_SOURCE"},
                         {"CUTTING", "PAINTING", "FINISH_AREA", "CABINET_AREA"})
        for purpose in ("CUTTING", "PAINTING"):
            group = next(row for row in before["groups"] if row["purposeCode"] == purpose)
            self.assertEqual(group["engineeringCandidate"]["quantity"], "4")
        self.save()
        after = self.read()
        self.assertEqual(after["groups"], before["groups"])
        for key, row in old_loads.items():
            self.assertEqual(next(load for load in after["operationLoads"] if load["key"] == key), row)
        self.assertEqual(self.target_load(after)["allocatedQuantity"], "4")
        board_load = next(row for row in after["operationLoads"] if board[0].pk in row["requirementIds"])
        self.assertEqual(board_load["requirementIds"], [board[0].pk])
        self.assertEqual(board_load["effectiveQuantity"], "4")
        self.assertEqual(board_load["allocatedQuantity"], "4")
        self.assertEqual(len(board_load["contributions"]), 1)
        # A saved final-purpose EOR is reachable by both discovery paths.  The
        # supplemental path must not count it or its allocation a second time.
        self.assertEqual(sum(row["requirementIds"].count(board[0].pk) for row in after["operationLoads"]), 1)

    def test_summary_preserves_original_fact_surfaces_and_adds_the_same_saved_projection(self):
        self.save()
        summary = self.read(summary=True)
        surface = {key: value for key, value in summary.items() if key not in FACT_SURFACES}
        for key in FACT_SURFACES:
            self.assertEqual(summary[key], surface)
        self.assertEqual(summary["counts"]["formalFactCount"], len(summary["formalSavedFacts"]))
        self.assertEqual(self.target_load(summary["purposeReview"])["allocatedQuantity"], "4")
        self.assertEqual(summary["businessWriteCount"], 0)

    def test_summary_shares_one_live_typed_cache_and_discards_it_before_the_next_read(self):
        self.save()
        seen = []
        original_read = operation.OperationRequirementService.read
        original_conversion = operation.OperationRequirementService.read_source_conversion

        def record(method):
            def call(*args, **kwargs):
                cache = kwargs.get("_read_cache")
                self.assertIsInstance(cache, operation._ReadOnlyProofCache)
                self.assertEqual(cache.user_id, self.f.user.pk)
                self.assertTrue(cache.is_current(self.f.company.pk))
                seen.append(cache)
                return method(*args, **kwargs)
            return call

        with patch.object(operation.OperationRequirementService, "read", side_effect=record(original_read)), \
                patch.object(operation.OperationRequirementService, "read_source_conversion",
                             side_effect=record(original_conversion)):
            first = self.read(summary=True)
            boundary = len(seen)
            self.assertGreaterEqual(boundary, 2)
            self.assertTrue(all(cache is seen[0] for cache in seen))
            self.assertFalse(seen[0].is_current(self.f.company.pk))
            second = self.read(summary=True)
        self.assertGreater(len(seen), boundary)
        self.assertTrue(all(cache is seen[boundary] for cache in seen[boundary:]))
        self.assertIsNot(seen[0], seen[boundary])
        self.assertFalse(seen[boundary].is_current(self.f.company.pk))
        self.assertEqual(first["formalSavedFacts"], second["formalSavedFacts"])
        self.assertEqual(self.target_load(second["purposeReview"])["allocatedQuantity"], "4")

    def test_extension_plan_source_proof_receives_the_same_native_read_cache(self):
        board = self.extension("BoardNetAreaSummary", grouped=False)
        self.save(board, step=self.second_step, prefix="sim-request-cache-extension")
        caches, native_caches = [], []
        source_proof = review._plan_source_consistency
        native_read = operation.OperationRequirementService.read

        def prove(*args, **kwargs):
            caches.append(kwargs.get("read_cache"))
            return source_proof(*args, **kwargs)

        def read(*args, **kwargs):
            native_caches.append(kwargs.get("_read_cache"))
            return native_read(*args, **kwargs)

        with patch.object(review, "_plan_source_consistency", side_effect=prove), \
                patch.object(operation.OperationRequirementService, "read", side_effect=read):
            result = self.read()
        self.assertTrue(caches)
        self.assertTrue(native_caches)
        self.assertIsInstance(native_caches[0], operation._ReadOnlyProofCache)
        self.assertTrue(all(cache is native_caches[0] for cache in caches))
        load = next(row for row in result["operationLoads"] if board[0].pk in row["requirementIds"])
        self.assertEqual(load["allocatedQuantity"], "4")
        self.assertFalse(native_caches[0].is_current(self.f.company.pk))
