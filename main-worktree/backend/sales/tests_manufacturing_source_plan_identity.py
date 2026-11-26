"""Synthetic in-memory tests for version-specific Demand/Requirement/Plan.

Native output generation/release and plan services execute. The established
upstream fixture supplies synthetic source documents; its document proof stubs
and the consumer's MAKE/actor stubs are not formal business authorization.
No existing database is migrated or written by this file.
"""
from copy import deepcopy
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from pde import tests_engineering_version_handoff_upstream as upstream
from pde.models import ProductManufacturingOutput
from pde.tests_manufacturing_output_generation import SCOPE
from planning.models import Demand, PlanningRequirement, ProductionPlan
from planning.services import calculate_requirement, confirm_supply_plan
from sales.manufacturing_input import ManufacturingInputError, resolve_order_engineered_input
from sales.models import SalesOrderItem
from sales.services import SalesBusinessError, generate_demand
from sales.views import SalesOrderDemandView, planning_source_rows, single_planning_source
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE)
class ManufacturingSourcePlanIdentityTests(TestCase):
    _generate = upstream.EngineeringVersionHandoffUpstreamTests._generate
    _release = upstream.EngineeringVersionHandoffUpstreamTests._release
    _successor_sources = upstream.EngineeringVersionHandoffUpstreamTests._successor_sources

    def setUp(self):
        upstream.EngineeringVersionHandoffUpstreamTests.setUp(self)
        self.make = patch("sales.supply_admission_service.supply_admission_facts", return_value={
            "status": "CONFIRMED", "supplyBranch": "MAKE", "factId": None,
            "factSource": "SIMULATED_FOR_TEST", "confirmedBy": None,
            "auditId": None, "stateMachineConsistent": True, "statusTransitionCount": 0,
        })
        self.actor = patch("sales.services._workflow_actor")
        for stub in (self.make, self.actor):
            stub.start()
            self.addCleanup(stub.stop)
        self.root, _ = self._generate()
        self._release(self.root, "identity-root-release")

    def _demand(self, output=None):
        kwargs = {} if output is None else {
            "sales_order_item_id": self.order_item.pk,
            "manufacturing_output_ids": {self.order_item.pk: output.pk},
        }
        demands, audits = generate_demand(user=self.executor, order_id=self.order.pk,
            authorization={"source": "SIMULATED_FOR_TEST"}, return_all=True, **kwargs)
        return demands[0], audits

    def _successor(self):
        document = self._successor_sources()[-1]
        successor, _ = self._generate(document, self.root, "identity-successor-output")
        self._release(successor, "identity-successor-release")
        return successor

    def _plan(self, demand):
        requirement, _ = calculate_requirement(user=self.executor, demand_id=demand.pk,
            authorization={"source": "SIMULATED_FOR_TEST"})
        plan, _ = confirm_supply_plan(user=self.executor, requirement_id=requirement.pk,
            authorization={"source": "SIMULATED_FOR_TEST"})
        return requirement, plan

    def _counts(self):
        return tuple(model.objects.count() for model in (
            Demand, PlanningRequirement, ProductionPlan,
            OrganizationOperatingAuditRecord, BusinessStateTransition,
        ))

    def test_old_new_sources_coexist_and_native_plan_chain_is_idempotent(self):
        old, _ = self._demand()
        old_requirement, old_plan = self._plan(old)
        old_rows = [type(row).objects.values().get(pk=row.pk)
                    for row in (old, old_requirement, old_plan)]
        old_audits = list(OrganizationOperatingAuditRecord.objects.values().order_by("pk"))
        successor = self._successor()
        new, _ = self._demand(successor)
        new_requirement, new_plan = self._plan(new)
        self.assertNotEqual(new.pk, old.pk)
        self.assertNotEqual(new_requirement.pk, old_requirement.pk)
        self.assertNotEqual(new_plan.pk, old_plan.pk)
        self.assertEqual(new.sales_order_item_id, old.sales_order_item_id)
        self.assertEqual((new.manufacturing_output_id, old.manufacturing_output_id),
                         (successor.pk, self.root.pk))
        self.assertEqual(new_plan.planning_requirement.demand.manufacturing_output_id, successor.pk)
        before = self._counts()
        repeated, audits = self._demand(successor)
        repeated_requirement, repeated_plan = self._plan(repeated)
        self.assertEqual((repeated.pk, repeated_requirement.pk, repeated_plan.pk),
                         (new.pk, new_requirement.pk, new_plan.pk))
        self.assertEqual(audits, [])
        self.assertEqual(before, self._counts())
        for row, snapshot in zip((old, old_requirement, old_plan), old_rows):
            self.assertEqual(type(row).objects.values().get(pk=row.pk), snapshot)
        self.assertEqual(old_audits, list(OrganizationOperatingAuditRecord.objects.filter(
            pk__in=[row["id"] for row in old_audits]).values().order_by("pk")))

    def test_multiple_outputs_without_selection_refuse_even_when_old_demand_exists(self):
        old, _ = self._demand()
        self._successor()
        before = self._counts()
        with self.assertRaises(ManufacturingInputError) as caught:
            resolve_order_engineered_input(self.order_item)
        self.assertEqual(caught.exception.code, "ORDER_ENGINEERING_OUTPUT_NOT_UNIQUE")
        with self.assertRaises(SalesBusinessError) as caught:
            self._demand()
        self.assertEqual(caught.exception.code, "SALES_ORDER_MANUFACTURING_SOURCE_SELECTION_REQUIRED")
        self.assertEqual(caught.exception.data["blockedLines"][0]["engineeringBlockerCode"],
                         "ORDER_ENGINEERING_OUTPUT_NOT_UNIQUE")
        request = APIRequestFactory().post("/api/sales/orders/demand/", {}, format="json")
        force_authenticate(request, user=self.executor)
        with patch("sales.views.AuthorizationService.decide", return_value={"allowed": True}):
            response = SalesOrderDemandView.as_view()(request, order_id=self.order.pk)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "SALES_ORDER_MANUFACTURING_SOURCE_SELECTION_REQUIRED")
        self.assertIn("明确选择", response.data["error"]["message"])
        self.assertEqual(before, self._counts())
        self.assertEqual(Demand.objects.get(pk=old.pk).manufacturing_output_id, self.root.pk)

    def test_read_projection_lists_both_sources_without_fabricated_default(self):
        old, _ = self._demand()
        successor = self._successor()
        new, _ = self._demand(successor)
        item = SalesOrderItem.objects.get(pk=self.order_item.pk)
        self.assertIsNone(single_planning_source(item))
        rows = planning_source_rows(item)
        self.assertEqual({row["demandId"] for row in rows}, {old.pk, new.pk})
        self.assertEqual({row["manufacturingOutputId"] for row in rows}, {self.root.pk, successor.pk})
        self.assertTrue(all(row["engineeringCalculationId"] and row["orderEngineeringBaselineId"] for row in rows))

    def test_selected_output_foreign_item_and_invalid_ids_refuse_before_writes(self):
        other = SalesOrderItem.objects.create(sales_order=self.order, line_no=2,
            material=self.finished, engineering_mode="ORDER_ENGINEERED", quantity=1,
            uom=self.uom, required_date=self.order_item.required_date)
        before = self._counts()
        for item_id, selection in ((other.pk, self.root.pk), (self.order_item.pk, 999999)):
            with self.subTest(item=item_id):
                with self.assertRaises(SalesBusinessError):
                    generate_demand(user=self.executor, order_id=self.order.pk,
                        authorization={"source": "SIMULATED_FOR_TEST"}, sales_order_item_id=item_id,
                        manufacturing_output_ids={item_id: selection})
                self.assertEqual(before, self._counts())
        for selection in (None, True, 0, "invalid"):
            with self.subTest(selection=selection):
                with self.assertRaises(SalesBusinessError):
                    generate_demand(user=self.executor, order_id=self.order.pk,
                        authorization={"source": "SIMULATED_FOR_TEST"},
                        manufacturing_output_ids={self.order_item.pk: selection})
                self.assertEqual(before, self._counts())

    def test_frozen_release_snapshot_and_cross_calculation_are_not_bypassed(self):
        successor = self._successor()
        original = ProductManufacturingOutput.objects.values().get(pk=successor.pk)
        before = self._counts()
        for field, wrong in (("engineering_calculation_id", self.calculation.pk),
                             ("order_engineering_baseline_id", self.baseline.pk)):
            with self.subTest(field=field):
                ProductManufacturingOutput.objects.filter(pk=successor.pk).update(**{field: wrong})
                with self.assertRaises(SalesBusinessError):
                    self._demand(successor)
                self.assertEqual(before, self._counts())
                ProductManufacturingOutput.objects.filter(pk=successor.pk).update(**{field: original[field]})
        proof = resolve_order_engineered_input(self.order_item, output_id=successor.pk)["facts"]
        audit_id = proof["releaseReadback"]["auditId"]
        audit = OrganizationOperatingAuditRecord.objects.get(pk=audit_id)
        snapshot = deepcopy(audit.after_snapshot)
        snapshot["sourceSnapshot"]["engineering_calculation_id"] = self.calculation.pk
        OrganizationOperatingAuditRecord.objects.filter(pk=audit_id).update(after_snapshot=snapshot)
        with self.assertRaises(SalesBusinessError):
            self._demand(successor)
        self.assertEqual(before, self._counts())

    def test_database_uniqueness_keeps_one_demand_per_exact_source(self):
        demand, _ = self._demand()
        fields = {field.attname: getattr(demand, field.attname)
                  for field in Demand._meta.concrete_fields if not field.primary_key}
        fields["demand_no"] = "IDENTITY-DUPLICATE-SOURCE"
        fields["status"] = "draft"
        with self.assertRaises(IntegrityError), transaction.atomic():
            Demand.objects.create(**fields)
        self.assertEqual(Demand.objects.filter(sales_order_item=self.order_item).count(), 1)
