"""Mocked API/read-only preview boundaries; no database is opened by these tests."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .daily_capacity_service import DailyCapacityError, capacity_fact
from .daily_capacity_views import (
    DailyCapacityDatePreviewView, process_demand_for_plan as persisted_process_demand,
    production_plan_date_preview as atomic_date_preview, validate_capability_window,
)

# Unit tests exercise the underlying pure logic; the production entry retains
# its real read-only transaction and is explicitly checked in setUp below.
production_plan_date_preview = atomic_date_preview.__wrapped__


MODULE = "pde.daily_capacity_views"
START = date(2026, 10, 13)
PATH = "/api/pde/aps/daily-capacity/date-preview/"
CALENDAR = {
    "contractVersion": "PCE-MFG-CALENDAR-V1.0", "timezone": "Asia/Shanghai",
    "weeklyAvailableMinutes": dict(MON=600, TUE=600, WED=600, THU=600, FRI=600, SAT=0, SUN=0),
    "exceptions": [],
}


def plan_fixture():
    owner = SimpleNamespace(pk=71, company_id=21, sales_order_item_id=82)
    route = SimpleNamespace(pk=31, company_id=21, routing_code="READY/SEMI")
    version = SimpleNamespace(pk=32, status="released", routing_id=31, routing=route, product=None)
    bom = SimpleNamespace(pk=41, bom=SimpleNamespace(company_id=21), product=None)
    output = SimpleNamespace(
        pk=61, routing_version_id=32, routing_version=version,
        bom_version=bom, engineering_calculation=None, engineering_document_version=None,
        order_engineering_instance=owner, order_engineering_instance_id=71,
        order_engineering_baseline=SimpleNamespace(company_id=21, status="confirmed"),
        product=None, product_id=None, release_status="released_to_manufacturing",
    )
    order = SimpleNamespace(pk=81, company_id=21, status="confirmed")
    item = SimpleNamespace(pk=82, id=82, sales_order=order, sales_order_id=81, uom_id=1)
    demand = SimpleNamespace(
        pk=91, manufacturing_output=output, manufacturing_output_id=61,
        sales_order_item=item, sales_order_item_id=82,
        department=SimpleNamespace(company_id=21),
    )
    requirement = SimpleNamespace(pk=92, demand=demand)
    return SimpleNamespace(
        pk=42, plan_no="MP-MOCK-001", planned_qty=Decimal("100"), status="confirmed",
        planning_requirement=requirement, material=SimpleNamespace(company_id=21),
    )


def capacity_fixture(capacity_id=1, *, center_id=10, quantity="100", uom_id=1):
    work_center = SimpleNamespace(
        pk=center_id, company_id=21, code=f"WC{center_id:03}", name="模拟工作中心",
        is_active=True, effective_from=None, effective_to=None,
        capacity_policy={"calendar": deepcopy(CALENDAR)},
    )
    uom = SimpleNamespace(pk=uom_id, company_id=21, code="PCS", name="件", is_active=True)
    product_type = SimpleNamespace(
        pk=31, company_id=21, code="READY/SEMI", name="模拟半成品类型",
        is_active=True, effective_from=None, effective_to=None,
    )
    operation = SimpleNamespace(
        pk=15, company_id=21, name="模拟工序", is_active=True, effective_from=None, effective_to=None,
    )
    return SimpleNamespace(
        pk=capacity_id, id=capacity_id, code=f"CAP-{capacity_id}", name="模拟日产能",
        company_id=21, work_center_id=center_id, work_center=work_center,
        operation_id=15, operation=operation, product_type_id=31, product_type=product_type,
        quantity=Decimal(quantity), uom_id=uom_id, uom=uom,
        time_basis="day", time_basis_quantity=Decimal("1"), time_unit="DAY",
        measurement_status="measured", is_active=True, effective_from=START, effective_to=None,
        preparation_days=Decimal("0"), transfer_days=Decimal("0"),
    )


def step_fixture(sequence, *, predecessors=(), state="REQUIRED", capacity_id=1, center_id=10):
    return {
        "stepId": sequence + 100, "sequence": sequence, "operationId": 15,
        "predecessorSequences": list(predecessors), "applicability": {"result": state},
        "preparationDays": "0", "transferDays": "0",
        "candidateWorkCenters": [{"id": center_id, "source": "Process.work_center", "role": "default"}],
        "dailyCapacity": [capacity_fact(capacity_fixture(capacity_id, center_id=center_id), START)]
        if state == "REQUIRED" else [],
    }


def readiness_fixture(*steps, ready=True):
    return {
        "planningReady": ready, "steps": list(steps), "productTypeId": 31,
        "routingVersionId": 32, "factSource": "server", "blockers": [],
    }


class DailyCapacityDatePreviewTests(SimpleTestCase):
    def setUp(self):
        self.assertTrue(hasattr(atomic_date_preview, "__wrapped__"))
        bindings = patch('pde.models.PlanStepVersionBinding.objects.filter')
        bindings.start().return_value.exists.return_value = False
        self.addCleanup(bindings.stop)
        # These pre-existing algorithm fixtures have no ORM source or object
        # proof. Native binding/allocation/coverage is tested separately with
        # persisted fixtures; do not make this pure unit test query a database.
        coverage = patch('pde.daily_capacity_service._validate_applicable_demand_objects')
        coverage.start()
        self.addCleanup(coverage.stop)
        self.plan = plan_fixture()
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(pk=11, username="isolated-reader", company_id=21, is_authenticated=True)
        # Algorithm-only tests receive explicitly isolated process workload facts.
        # The real persisted-demand resolver is exercised separately below and
        # currently blocks because plan allocation/basis is absent from schema.
        self.process_quantity = Decimal('100')
        self.process_uom_id = 1
        self.process_resolver = patch(f'{MODULE}.process_demand_for_plan', side_effect=lambda *args, **kwargs: {
            'quantity': self.process_quantity, 'uomId': self.process_uom_id,
        })
        self.process_resolver.start()
        self.addCleanup(self.process_resolver.stop)

    def response(self, *, params=None, user=None):
        request = self.factory.get(PATH, params or {"productionPlanId": 42, "startDate": START.isoformat()})
        force_authenticate(request, user=user or self.user)
        return DailyCapacityDatePreviewView.as_view()(request)

    def cap_query(self, rows):
        query = MagicMock()
        query.get.side_effect = lambda *, pk: rows[pk]
        return query

    def assert_read_failed_contract(self, response):
        self.assertEqual(response.data["factLoadStatus"], "read_failed")
        for key in ("apiUrl", "httpStatus", "errorCode", "errorMessage", "loadedAt", "tenantId", "batchId"):
            self.assertTrue(response.data[key])
        self.assertFalse(response.data["strictFacts"]["passed"])

    def test_unauthenticated_request_never_reads_plan(self):
        request = self.factory.get(PATH, {"productionPlanId": 42, "startDate": START.isoformat()})
        with patch(f"{MODULE}.AuthorizationService.decide") as authorize, patch(
            f"{MODULE}.ProductionPlan.objects.filter",
        ) as lookup:
            response = DailyCapacityDatePreviewView.as_view()(request)
        self.assertIn(response.status_code, {401, 403})
        authorize.assert_not_called()
        lookup.assert_not_called()

    def test_missing_planning_permission_never_reads_plan(self):
        with patch(f"{MODULE}.AuthorizationService.decide", return_value={
            "allowed": False, "decisionCode": "DUTY_NOT_GRANTED", "reason": "未获计划读取权限",
        }) as authorize, patch(f"{MODULE}.ProductionPlan.objects.filter") as lookup:
            response = self.response()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(authorize.call_args.kwargs["action_code"], "planning.view")
        self.assertEqual(authorize.call_args.kwargs["organization_id"], 21)
        lookup.assert_not_called()
        self.assert_read_failed_contract(response)

    def test_plan_lookup_is_bound_to_order_company_and_missing_plan_returns_404(self):
        query = MagicMock()
        query.first.return_value = None
        with patch(f"{MODULE}.AuthorizationService.decide", return_value={"allowed": True}), patch(
            f"{MODULE}.ProductionPlan.objects.filter", return_value=query,
        ) as lookup:
            response = self.response()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(lookup.call_args.kwargs["pk"], 42)
        self.assertEqual(
            lookup.call_args.kwargs["planning_requirement__demand__sales_order_item__sales_order__company_id"], 21,
        )
        self.assert_read_failed_contract(response)

    def test_reader_without_company_cannot_fall_back_to_null_company_scope(self):
        user = SimpleNamespace(pk=12, company_id=None, is_authenticated=True)
        with patch(f"{MODULE}.AuthorizationService.decide", return_value={"allowed": True}), patch(
            f"{MODULE}.ProductionPlan.objects.filter",
        ) as lookup:
            response = self.response(user=user)
        self.assertEqual(response.status_code, 403)
        lookup.assert_not_called()

    def test_invalid_input_returns_complete_read_failed_contract(self):
        with patch(f"{MODULE}.AuthorizationService.decide", return_value={"allowed": True}), patch(
            f"{MODULE}.ProductionPlan.objects.filter",
        ) as lookup:
            response = self.response(params={"productionPlanId": "not-an-id", "startDate": "2026-02-30"})
        self.assertEqual(response.status_code, 400)
        lookup.assert_not_called()
        self.assert_read_failed_contract(response)

    def test_missing_fixed_routing_source_is_an_explicit_blocker(self):
        self.plan.planning_requirement.demand.manufacturing_output = None
        with self.assertRaises(DailyCapacityError) as caught:
            production_plan_date_preview(self.plan, start_date=START)
        self.assertEqual(caught.exception.code, "PLAN_ROUTING_SOURCE_MISSING")

    def test_unconfirmed_plan_or_unreleased_source_never_reads_capacity_for_dates(self):
        output = self.plan.planning_requirement.demand.manufacturing_output
        for obj, field, blocked, valid in (
            (self.plan, "status", "draft", "confirmed"),
            (output, "release_status", "draft", "released_to_manufacturing"),
            (output.routing_version, "status", "draft", "released"),
        ):
            with self.subTest(field=field):
                setattr(obj, field, blocked)
                with patch(f"{MODULE}.DailyCapacityReadinessService.assess", return_value=readiness_fixture(
                    step_fixture(10),
                )), patch(f"{MODULE}.StandardCapacity.objects.select_related") as read:
                    result = production_plan_date_preview(self.plan, start_date=START)
                self.assertFalse(result["previewReady"])
                self.assertTrue(result["sourceStatusBlocker"])
                self.assertEqual(result["dates"], [])
                read.assert_not_called()
                setattr(obj, field, valid)

    def test_foreign_routing_fixed_to_same_company_order_is_rejected_before_assessment(self):
        self.plan.planning_requirement.demand.manufacturing_output.routing_version.routing.company_id = 22
        with patch(f"{MODULE}.DailyCapacityReadinessService.assess") as assess:
            with self.assertRaises(DailyCapacityError):
                production_plan_date_preview(self.plan, start_date=START)
        assess.assert_not_called()

    def test_blocked_readiness_returns_its_facts_without_any_capacity_date_read(self):
        readiness = readiness_fixture(step_fixture(10), ready=False)
        with patch(f"{MODULE}.DailyCapacityReadinessService.assess", return_value=readiness), patch(
            f"{MODULE}.StandardCapacity.objects.select_related",
        ) as read:
            result = production_plan_date_preview(self.plan, start_date=START)
        self.assertFalse(result["previewReady"])
        self.assertEqual(result["readiness"], readiness)
        self.assertEqual(result["dates"], [])
        self.assertEqual(result["businessWriteCount"], 0)
        self.assertEqual(result["productionScheduleCreatedCount"], 0)
        self.assertEqual(result["mrpRunCount"], 0)
        read.assert_not_called()

    def test_skipped_condition_inherits_required_ancestor_before_successor(self):
        readiness = readiness_fixture(
            step_fixture(10), step_fixture(20, predecessors=(10,), state="NOT_APPLICABLE"),
            step_fixture(30, predecessors=(20,)),
        )
        query = self.cap_query({1: capacity_fixture()})
        with patch(f"{MODULE}.DailyCapacityReadinessService.assess", return_value=readiness), patch(
            f"{MODULE}.StandardCapacity.objects.select_related", return_value=query,
        ):
            result = production_plan_date_preview(self.plan, start_date=START)
        self.assertTrue(result["previewReady"])
        self.assertEqual([row["sequence"] for row in result["dates"]], [10, 30])
        self.assertEqual(result["dates"][0]["endDate"], "2026-10-13")
        self.assertEqual(result["dates"][1]["startDate"], "2026-10-14")
        self.assertEqual(query.get.call_count, 2)

    def test_auxiliary_zero_step_creates_no_independent_demand_or_date_and_preserves_dependency(self):
        auxiliary = step_fixture(20, predecessors=(10,), capacity_id=2)
        auxiliary['capacityDateMode'] = 'AUXILIARY_NO_INDEPENDENT_DATE'
        auxiliary['dailyCapacity'][0].update(quantity='0', capacityQuantity='0', measurementStatus='zero_capacity', available=False)
        readiness = readiness_fixture(step_fixture(10), auxiliary, step_fixture(30, predecessors=(20,)))
        query = self.cap_query({1: capacity_fixture()})

        def isolated_confirmed_demand(plan, output, item, step, **kwargs):
            self.assertNotEqual(step['sequence'], 20, '配套工序不能读取独立需求量')
            return {'quantity': Decimal('100'), 'uomId': 1}

        with patch(f'{MODULE}.process_demand_for_plan', side_effect=isolated_confirmed_demand) as demand_read, patch(
            f'{MODULE}.DailyCapacityReadinessService.assess', return_value=readiness,
        ), patch(f'{MODULE}.StandardCapacity.objects.select_related', return_value=query):
            result = production_plan_date_preview(self.plan, start_date=START)
        self.assertTrue(result['previewReady'])
        self.assertEqual([row['sequence'] for row in result['dates']], [10, 30])
        self.assertEqual(result['dates'][1]['startDate'], '2026-10-14')
        self.assertEqual(query.get.call_count, 2)
        self.assertEqual(demand_read.call_count, 2)

    def test_all_auxiliary_route_does_not_fabricate_a_date_or_independent_workload(self):
        step = step_fixture(10)
        step['capacityDateMode'] = 'AUXILIARY_NO_INDEPENDENT_DATE'
        with patch(f'{MODULE}.process_demand_for_plan') as demand_read, patch(
            f'{MODULE}.DailyCapacityReadinessService.assess', return_value=readiness_fixture(step),
        ), patch(f'{MODULE}.StandardCapacity.objects.select_related') as capacity_read:
            result = production_plan_date_preview(self.plan, start_date=START)
        self.assertFalse(result['previewReady'])
        self.assertEqual(result['dates'], [])
        self.assertNotIn('endDate', result)
        demand_read.assert_not_called()
        capacity_read.assert_not_called()

    def test_parallel_steps_share_finite_resource_without_exceeding_one_day(self):
        self.plan.planned_qty = Decimal("900")
        self.process_quantity = Decimal("75")
        readiness = readiness_fixture(step_fixture(10), step_fixture(20))
        query = self.cap_query({1: capacity_fixture()})
        with patch(f"{MODULE}.DailyCapacityReadinessService.assess", return_value=readiness), patch(
            f"{MODULE}.StandardCapacity.objects.select_related", return_value=query,
        ):
            result = production_plan_date_preview(self.plan, start_date=START)
        self.assertTrue(result["previewReady"])
        by_date = {}
        for row in result["dates"]:
            for allocation in row["allocations"]:
                key = allocation["date"]
                by_date[key] = by_date.get(key, Decimal("0")) + Decimal(allocation["allocatedDays"])
        self.assertEqual(by_date, {"2026-10-13": Decimal("1"), "2026-10-14": Decimal("0.5")})
        self.assertTrue(all(amount <= 1 for amount in by_date.values()))
        self.assertEqual(result["businessWriteCount"], 0)

    def test_merge_waits_for_latest_of_all_required_predecessors(self):
        readiness = readiness_fixture(step_fixture(10),
            step_fixture(20, capacity_id=2, center_id=20),
            step_fixture(30, predecessors=(10, 20), capacity_id=3, center_id=30))
        def demand(plan, output, item, step, **kwargs):
            return {'quantity': Decimal('200' if step['sequence'] == 20 else '100'), 'uomId': 1}
        with patch(f'{MODULE}.DailyCapacityReadinessService.assess', return_value=readiness), patch(
            f'{MODULE}.process_demand_for_plan', side_effect=demand), patch(
            f'{MODULE}.StandardCapacity.objects.select_related', return_value=self.cap_query({
                1: capacity_fixture(), 2: capacity_fixture(2, center_id=20),
                3: capacity_fixture(3, center_id=30)})):
            result = production_plan_date_preview(self.plan, start_date=START)
        self.assertTrue(result['previewReady'])
        rows = {row['sequence']: row for row in result['dates']}
        self.assertEqual(rows[10]['endDate'], '2026-10-13')
        self.assertEqual(rows[20]['endDate'], '2026-10-14')
        self.assertEqual(rows[30]['startDate'], '2026-10-15')

    def test_contribution_total_has_one_preparation_and_one_transfer(self):
        step = step_fixture(10)
        step.update(preparationDays='0.1', transferDays='0.1')
        with patch(f'{MODULE}.DailyCapacityReadinessService.assess', return_value=readiness_fixture(step)), patch(
            f'{MODULE}.process_demand_for_plan', return_value={'quantity': Decimal('300'), 'uomId': 1,
                'contributions': [{'quantity': '100'}, {'quantity': '100'}, {'quantity': '100'}]}), patch(
            f'{MODULE}.StandardCapacity.objects.select_related', return_value=self.cap_query({1: capacity_fixture()})):
            result = production_plan_date_preview(self.plan, start_date=START)
        self.assertEqual(len(result['dates']), 1)
        row = result['dates'][0]
        self.assertEqual(Decimal(row['productionDays']), Decimal('3'))
        self.assertEqual(Decimal(row['preparationDays']), Decimal('.1'))
        self.assertEqual(Decimal(row['transferDays']), Decimal('.1'))
        self.assertEqual(Decimal(row['durationDays']), Decimal('3.2'))

    def test_mixed_step_missing_allocation_never_queries_anchor_workload(self):
        item = self.plan.planning_requirement.demand.sales_order_item
        output = self.plan.planning_requirement.demand.manufacturing_output
        with patch('pde.operation_requirement_service.process_demand_for_plan', return_value=None), patch(
            f'{MODULE}.EngineeringOperationRequirement.objects.filter') as old_workload:
            with self.assertRaises(DailyCapacityError) as caught:
                persisted_process_demand(self.plan, output, item, step_fixture(10),
                    company_id=21, user=self.user, require_saved=True)
        self.assertEqual(caught.exception.code, 'PROCESS_DEMAND_PLAN_ALLOCATION_MISSING')
        old_workload.assert_not_called()

    def operation_requirement_fixture(self, *, quantity='250', uom_id=2):
        output = self.plan.planning_requirement.demand.manufacturing_output
        output.engineering_calculation = SimpleNamespace(
            pk=51, company_id=21, scope='order_engineering', status='completed',
            sales_order_item_id=82, engineering_instance_id=71,
        )
        return SimpleNamespace(
            pk=52, calculation_id=51, operation_id=15, workload_quantity=Decimal(quantity), uom_id=uom_id,
            operation=SimpleNamespace(company_id=21, calculation_uom_id=uom_id),
            uom=SimpleNamespace(company_id=21, is_active=True),
            source_detail=SimpleNamespace(pk=53, calculation_id=51, status='succeeded', uom_id=uom_id,
                                         output_value={'decimal': quantity}),
            trace={'resultDomain': 'OPERATION_REQUIREMENT', 'detailId': 53},
        )

    def requirement_query(self, rows):
        query = MagicMock()
        query.select_related.return_value.order_by.return_value = rows
        return query

    def test_persisted_demand_query_requires_same_calculation_and_operation_and_never_falls_back_to_plan_qty(self):
        self.operation_requirement_fixture()
        output = self.plan.planning_requirement.demand.manufacturing_output
        item = self.plan.planning_requirement.demand.sales_order_item
        with patch(f'{MODULE}.EngineeringOperationRequirement.objects.filter', return_value=self.requirement_query([])) as lookup:
            with self.assertRaises(DailyCapacityError) as caught:
                persisted_process_demand(self.plan, output, item, step_fixture(10), company_id=21)
        self.assertEqual(caught.exception.code, 'PROCESS_DEMAND_QUANTITY_MISSING')
        self.assertEqual(lookup.call_args.kwargs, {'calculation_id': 51, 'operation_id': 15})

    def test_valid_engineering_workload_without_plan_allocation_basis_blocks_before_capacity_dates(self):
        requirement = self.operation_requirement_fixture(quantity='250', uom_id=2)
        self.plan.planned_qty = Decimal('100')
        with patch(f'{MODULE}.process_demand_for_plan', side_effect=persisted_process_demand), patch(
            f'{MODULE}.EngineeringOperationRequirement.objects.filter', return_value=self.requirement_query([requirement]),
        ), patch(f'{MODULE}.DailyCapacityReadinessService.assess', return_value=readiness_fixture(step_fixture(10))), patch(
            f'{MODULE}.StandardCapacity.objects.select_related',
        ) as capacity_read:
            result = production_plan_date_preview(self.plan, start_date=START)
        self.assertFalse(result['previewReady'])
        self.assertEqual(result['dates'], [])
        self.assertEqual(result['processDemandBlockers'][0]['code'], 'PROCESS_DEMAND_PLAN_QUANTITY_BASIS_MISSING')
        self.assertEqual(result['processDemandFacts'][0]['workloadQuantity'], '250')
        self.assertEqual(result['processDemandFacts'][0]['uomId'], 2)
        capacity_read.assert_not_called()

    def test_missing_process_uom_or_different_detail_calculation_is_rejected(self):
        requirement = self.operation_requirement_fixture()
        output = self.plan.planning_requirement.demand.manufacturing_output
        item = self.plan.planning_requirement.demand.sales_order_item
        for field, invalid, valid, code in (
            ('calculation_uom_id', None, 2, 'PROCESS_DEMAND_UOM_MISSING'),
            ('calculation_id', 99, 51, 'PROCESS_DEMAND_SOURCE_MISMATCH'),
        ):
            target = requirement.operation if field == 'calculation_uom_id' else requirement.source_detail
            setattr(target, field, invalid)
            with patch(f'{MODULE}.EngineeringOperationRequirement.objects.filter', return_value=self.requirement_query([requirement])):
                with self.assertRaises(DailyCapacityError) as caught:
                    persisted_process_demand(self.plan, output, item, step_fixture(10), company_id=21)
            self.assertEqual(caught.exception.code, code)
            setattr(target, field, valid)

    def test_multiple_persisted_workloads_are_not_summed_without_a_formal_step_allocation(self):
        requirement = self.operation_requirement_fixture()
        output = self.plan.planning_requirement.demand.manufacturing_output
        item = self.plan.planning_requirement.demand.sales_order_item
        with patch(f'{MODULE}.EngineeringOperationRequirement.objects.filter', return_value=self.requirement_query([requirement, requirement])):
            with self.assertRaises(DailyCapacityError) as caught:
                persisted_process_demand(self.plan, output, item, step_fixture(10), company_id=21)
        self.assertEqual(caught.exception.code, 'PROCESS_DEMAND_QUANTITY_AMBIGUOUS')

    def test_malformed_json_workload_provenance_is_a_blocker_instead_of_an_unhandled_error(self):
        requirement = self.operation_requirement_fixture()
        output = self.plan.planning_requirement.demand.manufacturing_output
        item = self.plan.planning_requirement.demand.sales_order_item
        for target, field, malformed, restored, code in (
            (requirement, 'trace', ['not-an-object'], requirement.trace, 'PROCESS_DEMAND_SOURCE_MISMATCH'),
            (requirement.source_detail, 'output_value', ['250'], requirement.source_detail.output_value, 'PROCESS_DEMAND_QUANTITY_MISSING'),
            (requirement.source_detail, 'output_value', {'decimal': 'sNaN'}, requirement.source_detail.output_value, 'PROCESS_DEMAND_SOURCE_MISMATCH'),
        ):
            setattr(target, field, malformed)
            with patch(f'{MODULE}.EngineeringOperationRequirement.objects.filter', return_value=self.requirement_query([requirement])):
                with self.assertRaises(DailyCapacityError) as caught:
                    persisted_process_demand(self.plan, output, item, step_fixture(10), company_id=21)
            self.assertEqual(caught.exception.code, code)
            setattr(target, field, restored)

    def test_capability_effective_period_covers_all_allocation_dates(self):
        step = step_fixture(10)
        step['candidateWorkCenters'][0]['source'] = 'WorkCenterOperationCapability:77'
        relation = SimpleNamespace(is_active=True, effective_from=START, effective_to=START)
        query = MagicMock()
        query.first.return_value = relation
        with patch(f'{MODULE}.WorkCenterOperationCapability.objects.filter', return_value=query) as lookup:
            with self.assertRaises(DailyCapacityError) as caught:
                validate_capability_window(step, capacity_fixture(), [
                    {'date': '2026-10-13', 'allocatedDays': '1'}, {'date': '2026-10-14', 'allocatedDays': '0.25'},
                ])
        self.assertEqual(caught.exception.code, 'RESOURCE_CAPABILITY_EFFECTIVE_WINDOW_MISMATCH')
        self.assertEqual(lookup.call_args.kwargs, {'pk': 77, 'operation_id': 15, 'work_center_id': 10})

    def test_direct_or_default_fk_authority_does_not_require_an_unrelated_capability_row(self):
        for source in ('RoutingStep.work_center', 'Process.work_center'):
            step = step_fixture(10)
            step['candidateWorkCenters'][0]['source'] = source
            with patch(f'{MODULE}.WorkCenterOperationCapability.objects.filter') as lookup:
                validate_capability_window(step, capacity_fixture(), [{'date': '2026-10-13', 'allocatedDays': '1'}])
            lookup.assert_not_called()

    def test_expired_relation_candidate_does_not_win_over_a_valid_alternative(self):
        step = step_fixture(10)
        step['candidateWorkCenters'][0]['source'] = 'WorkCenterOperationCapability:77'
        second = capacity_fixture(2, center_id=20)
        step['candidateWorkCenters'].append({'id': 20, 'source': 'Process.work_center', 'role': 'default'})
        step['dailyCapacity'].append(capacity_fact(second, START))
        relation_query = MagicMock()
        relation_query.first.return_value = SimpleNamespace(is_active=True, effective_from=START, effective_to=START)
        self.process_quantity = Decimal('125')
        with patch(f'{MODULE}.DailyCapacityReadinessService.assess', return_value=readiness_fixture(step)), patch(
            f'{MODULE}.StandardCapacity.objects.select_related', return_value=self.cap_query({1: capacity_fixture(), 2: second}),
        ), patch(f'{MODULE}.WorkCenterOperationCapability.objects.filter', return_value=relation_query):
            result = production_plan_date_preview(self.plan, start_date=START)
        self.assertTrue(result['previewReady'])
        self.assertEqual(result['dates'][0]['standardCapacityId'], 2)
        self.assertEqual(result['dates'][0]['processDemandQuantity'], '125')

    def test_unit_mismatch_does_not_invent_conversion_or_create_dates(self):
        readiness = readiness_fixture(step_fixture(10))
        readiness["steps"][0]["dailyCapacity"][0]["uomId"] = 2
        query = self.cap_query({1: capacity_fixture(uom_id=2)})
        with patch(f"{MODULE}.DailyCapacityReadinessService.assess", return_value=readiness), patch(
            f"{MODULE}.StandardCapacity.objects.select_related", return_value=query,
        ):
            with self.assertRaises(DailyCapacityError) as caught:
                production_plan_date_preview(self.plan, start_date=START)
        self.assertEqual(caught.exception.code, "CAPACITY_UOM_MISMATCH")

    def test_capacity_changed_after_readiness_cannot_produce_dates_from_different_facts(self):
        readiness = readiness_fixture(step_fixture(10))
        query = self.cap_query({1: capacity_fixture(quantity="50")})
        with patch(f"{MODULE}.DailyCapacityReadinessService.assess", return_value=readiness), patch(
            f"{MODULE}.StandardCapacity.objects.select_related", return_value=query,
        ):
            with self.assertRaises(DailyCapacityError):
                production_plan_date_preview(self.plan, start_date=START)

    def test_skipped_dependency_cycle_is_rejected(self):
        readiness = readiness_fixture(
            step_fixture(10, predecessors=(20,)),
            step_fixture(20, predecessors=(30,), state="NOT_APPLICABLE"),
            step_fixture(30, predecessors=(20,), state="NOT_APPLICABLE"),
        )
        with patch(f"{MODULE}.DailyCapacityReadinessService.assess", return_value=readiness):
            with self.assertRaises(DailyCapacityError) as caught:
                production_plan_date_preview(self.plan, start_date=START)
        self.assertEqual(caught.exception.code, "ROUTING_DEPENDENCY_CYCLE")

    def test_successful_api_response_reports_server_fact_load_and_no_business_writes(self):
        query = MagicMock()
        query.first.return_value = self.plan
        result = {
            "previewReady": False, "dates": [], "factSource": "server",
            "productionPlanId": 42, "businessWriteCount": 0, "productionScheduleCreatedCount": 0,
        }
        with patch(f"{MODULE}.AuthorizationService.decide", return_value={"allowed": True}), patch(
            f"{MODULE}.ProductionPlan.objects.filter", return_value=query,
        ), patch(f"{MODULE}.production_plan_date_preview", return_value=result):
            response = self.response()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["factLoadStatus"], "loaded")
        self.assertEqual(response.data["factSource"], "server")
        self.assertEqual(response.data["businessWriteCount"], 0)
        self.assertEqual(response.data["productionScheduleCreatedCount"], 0)


class EffectiveDateScopeCompositionTests(SimpleTestCase):
    """SIMULATED_FOR_TEST composition only; native proofs have a separate suite."""

    def test_successor_numbering_cannot_replace_original_dependency_keys(self):
        from .daily_capacity_service import DailyCapacityReadinessService
        plan = plan_fixture()
        original = plan.planning_requirement.demand.manufacturing_output
        original.bom_version_id = original.bom_version.pk
        roots = [SimpleNamespace(pk=110, sequence=10, predecessor_sequences=[], operation_id=15),
            SimpleNamespace(pk=120, sequence=20, predecessor_sequences=[10], operation_id=15)]
        original.routing_version.steps = MagicMock()
        original.routing_version.steps.order_by.return_value = roots
        selected = deepcopy(original)
        selected.routing_version_id = 33
        selected.routing_version.pk = 33
        contexts = {}
        for root in roots:
            actual = SimpleNamespace(pk=root.pk + 1000, sequence=root.sequence + 1000,
                predecessor_sequences=[value + 1000 for value in root.predecessor_sequences],
                operation_id=15, routing_version_id=33, routing_version=selected.routing_version)
            contexts[root.pk] = {'plan': plan, 'originalOutput': original, 'output': selected,
                'root_step': root, 'step': actual, 'base': None, 'baseline': None,
                'routing_version': selected.routing_version, 'sourceProof': None, 'bindingProof': None}
        bindings = MagicMock()
        bindings.exists.return_value = True
        bindings.values_list.return_value = [(21, 110), (21, 120)]
        def scoped(version, **kwargs):
            actual = next(context['step'] for context in contexts.values()
                if context['step'].pk == kwargs['routing_step_id'])
            row = step_fixture(actual.sequence)
            row.update(stepId=actual.pk, predecessorSequences=actual.predecessor_sequences,
                planningReady=True, blockerCodes=[], blockerLabels=[])
            return {'steps': [row], 'scopeReady': True, 'planningReady': False, 'productTypeId': 31}
        with patch('pde.models.PlanStepVersionBinding.objects.filter', return_value=bindings), patch(
            'system.authorization.AuthorizationService.decide', return_value={'allowed': True}), patch(
            'pde.plan_step_context_service.resolve_step_context', side_effect=lambda plan, step_id, **kw: contexts[step_id]), patch(
            'pde.plan_step_context_service.version_fact', return_value={'isolatedCompositionOnly': True}), patch.object(
            DailyCapacityReadinessService, 'assess', side_effect=scoped):
            readiness, scopes = DailyCapacityReadinessService.assess_plan_date_scope(plan,
                company_id=21, on_date=START, user=SimpleNamespace(pk=11, company_id=21))
        self.assertTrue(readiness['planningReady'])
        self.assertEqual(set(scopes), {10, 20})
        self.assertEqual([row['stepId'] for row in readiness['steps']], [1110, 1120])
        self.assertEqual([row['sequence'] for row in readiness['steps']], [10, 20])
        self.assertEqual([row['effectiveSequence'] for row in readiness['steps']], [1010, 1020])
        self.assertEqual(readiness['steps'][1]['predecessorSequences'], [10])
        self.assertEqual(readiness['steps'][1]['effectivePredecessorSequences'], [1010])
