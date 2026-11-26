"""Read-only APS daily facts: exact identities, resource pairing and blockers."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from masterdata.models import UnitOfMeasure
from system.models import Company, Process

from .daily_capacity_service import (
    DailyCapacityError,
    DailyCapacityReadinessService,
    capacity_fact,
    duration_days,
    work_center_capacity_facts,
    working_date_window,
)
from .models import (
    CapacityProductType,
    ManufacturingProcessType,
    ProductCategory,
    Routing,
    RoutingStep,
    RoutingVersion,
    StandardCapacity,
    WorkCenter,
    WorkCenterOperationCapability,
)
from .production_foundation_service import _clean_values, _snapshot
from .routing_manual_applicability_service import RoutingManualApplicabilityService
from .routing_planning_readiness_service import RoutingPlanningReadinessService


ON_DATE = date(2026, 10, 13)
CALENDAR = {
    "contractVersion": "PCE-MFG-CALENDAR-V1.0",
    "timezone": "Asia/Shanghai",
    "weeklyAvailableMinutes": {
        "MON": 600, "TUE": 600, "WED": 600, "THU": 600,
        "FRI": 600, "SAT": 0, "SUN": 0,
    },
    "exceptions": [],
}


class DailyCapacityReadinessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="DAY-READY", name="日产能准入测试公司")
        cls.other_company = Company.objects.create(code="DAY-FOREIGN", name="其他测试公司")
        cls.category = ProductCategory.objects.create(
            company=cls.company, code="READY-CAT", name="测试产品分类",
        )
        cls.process_type = ManufacturingProcessType.objects.create(
            company=cls.company, code="READY-TYPE", name="测试工艺类型",
        )
        cls.product_type = CapacityProductType.objects.create(
            company=cls.company, code="READY/SEMI", name="测试半成品类型",
            product_category=cls.category, manufacturing_process_type=cls.process_type,
        )
        cls.uom = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="READY-PCS", name="件", dimension="count",
        )
        cls.operation = Process.objects.create(
            company=cls.company, code="READY-OP", name="名称不能推断条件的测试工序",
            calculation_basis="count", calculation_uom=cls.uom,
            quantity_driver="BOM_OUTPUT_QUANTITY",
        )
        cls.work_center = WorkCenter.objects.create(
            company=cls.company, code="WC001", name="测试工作中心",
            capacity_policy={"calendar": deepcopy(CALENDAR)},
        )
        cls.relation = WorkCenterOperationCapability.objects.create(
            work_center=cls.work_center, operation=cls.operation, assignment_role="primary",
        )
        cls.routing = Routing.objects.create(
            company=cls.company, routing_code="READY/SEMI", name="测试半成品路线",
            applicability_scope="PRODUCT_CATEGORY", product_category=cls.category,
            manufacturing_process_type=cls.process_type,
        )
        cls.version = RoutingVersion.objects.create(
            routing=cls.routing, routing_version="V1.0", status="draft",
        )
        cls.step = RoutingStep.objects.create(
            routing_version=cls.version, sequence=10, operation=cls.operation,
            operation_parameters={"applicability": {"mode": "MANDATORY"}},
        )
        cls.capacity = StandardCapacity.objects.create(
            company=cls.company, code="READY-CAP", name="测试日产能事实",
            product_type=cls.product_type, work_center=cls.work_center, operation=cls.operation,
            resource_scope="composite", quantity=Decimal("100"), uom=cls.uom,
            measurement_status="measured", time_basis="day", time_basis_quantity=Decimal("1"),
            preparation_days=Decimal("0.25"), transfer_days=Decimal("0.5"),
            effective_from=ON_DATE,
        )

    def assess(self, **kwargs):
        return DailyCapacityReadinessService.assess(self.version, on_date=ON_DATE, **kwargs)

    def codes(self, result):
        return {row["code"] for row in result["blockers"]}

    def fresh_capacity(self):
        return StandardCapacity.objects.select_related(
            "product_type", "uom", "operation", "work_center",
        ).get(pk=self.capacity.pk)

    def test_complete_exact_daily_inputs_are_read_only_and_wrapper_uses_same_facts(self):
        before = {
            "steps": list(RoutingStep.objects.values()),
            "capacities": list(StandardCapacity.objects.values()),
            "centers": list(WorkCenter.objects.values()),
        }
        result = self.assess()
        self.assertTrue(result["planningReady"])
        self.assertFalse(result["steps"][0]["workloadReady"])
        self.assertEqual(result["productTypeId"], self.product_type.pk)
        self.assertEqual(result["requiredStepCount"], 1)
        self.assertEqual(result["steps"][0]["preparationDays"], "0.2500")
        self.assertEqual(result["steps"][0]["transferDays"], "0.5000")
        self.assertEqual(result["businessWriteCount"], 0)
        self.assertEqual(result["productionPlanCreatedCount"], 0)
        self.assertEqual(result["productionScheduleCreatedCount"], 0)
        self.assertEqual(result, RoutingPlanningReadinessService.assess(self.version, on_date=ON_DATE))
        self.assertEqual(before, {
            "steps": list(RoutingStep.objects.values()),
            "capacities": list(StandardCapacity.objects.values()),
            "centers": list(WorkCenter.objects.values()),
        })

    def test_same_dimensions_do_not_substitute_another_product_type_code(self):
        self.product_type.code = "OTHER/SEMI"
        self.product_type.save(update_fields=["code"])
        result = self.assess()
        self.assertFalse(result["planningReady"])
        self.assertIsNone(result["productTypeId"])
        self.assertIn("CAPACITY_PRODUCT_TYPE_MISSING", self.codes(result))
        self.assertEqual(result["steps"][0]["dailyCapacity"], [])

    def test_unrelated_type_with_same_dimensions_does_not_make_exact_type_ambiguous(self):
        CapacityProductType.objects.create(
            company=self.company, code="OTHER/SEMI", name="同维度的另一个半成品",
            product_category=self.category, manufacturing_process_type=self.process_type,
        )
        result = self.assess()
        self.assertTrue(result["planningReady"])
        self.assertEqual(result["productTypeId"], self.product_type.pk)

    def test_capacity_for_another_operation_is_never_borrowed_from_same_work_center(self):
        other_operation = Process.objects.create(
            company=self.company, code="READY-OTHER-OP", name="同资源的其他工序",
        )
        self.capacity.operation = other_operation
        self.capacity.save(update_fields=["operation"])
        result = self.assess()
        self.assertFalse(result["planningReady"])
        self.assertIn("DAILY_CAPACITY_MISSING", self.codes(result))
        self.assertEqual(result["steps"][0]["dailyCapacity"], [])

    def test_zero_capacity_is_not_usable_even_when_all_old_hour_fields_exist(self):
        self.capacity.quantity = Decimal("0")
        self.capacity.measurement_status = "zero_capacity"
        self.capacity.standard_hours = Decimal("1")
        self.capacity.save(update_fields=["quantity", "measurement_status", "standard_hours"])
        self.step.standard_hours = Decimal("1")
        self.step.setup_hours = Decimal("1")
        self.step.transfer_hours = Decimal("1")
        self.step.save()
        self.operation.standard_hours = Decimal("1")
        self.operation.save(update_fields=["standard_hours"])
        result = self.assess()
        self.assertFalse(result["planningReady"])
        self.assertIn("DAILY_CAPACITY_MISSING", self.codes(result))
        fact = result["steps"][0]["dailyCapacity"][0]
        self.assertFalse(fact["available"])
        self.assertEqual(Decimal(fact["capacityQuantity"]), Decimal("0"))

    def test_missing_day_times_stay_null_without_any_hour_fallback(self):
        self.capacity.preparation_days = None
        self.capacity.transfer_days = None
        self.capacity.standard_hours = Decimal("8")
        self.capacity.save(update_fields=["preparation_days", "transfer_days", "standard_hours"])
        self.step.setup_hours = Decimal("24")
        self.step.transfer_hours = Decimal("48")
        self.step.standard_hours = Decimal("1")
        self.step.save()
        result = self.assess()
        self.assertFalse(result["planningReady"])
        self.assertIsNone(result["steps"][0]["preparationDays"])
        self.assertIsNone(result["steps"][0]["transferDays"])
        self.assertTrue({"PREPARATION_DAYS_MISSING", "TRANSFER_DAYS_MISSING"}.issubset(self.codes(result)))
        self.assertNotIn("standardHours", result["steps"][0])

    def test_overlapping_capacity_facts_on_same_resource_block_ambiguity(self):
        StandardCapacity.objects.create(
            company=self.company, code="READY-CAP-SECOND", name="冲突的同期日产能",
            product_type=self.product_type, work_center=self.work_center, operation=self.operation,
            resource_scope="composite", quantity=Decimal("200"), uom=self.uom,
            time_basis="day", time_basis_quantity=Decimal("1"),
            preparation_days=Decimal("0.25"), transfer_days=Decimal("0.5"),
            effective_from=ON_DATE,
        )
        result = self.assess()
        self.assertFalse(result["planningReady"])
        self.assertIn("DAILY_CAPACITY_AMBIGUOUS", self.codes(result))

    def test_foreign_company_capability_cannot_supply_a_candidate(self):
        self.relation.delete()
        foreign_center = WorkCenter.objects.create(
            company=self.other_company, code="WC001", name="其他公司工作中心",
            capacity_policy={"calendar": deepcopy(CALENDAR)},
        )
        # Simulate a corrupt legacy relation in the isolated DB; read must fail closed.
        WorkCenterOperationCapability.objects.create(
            operation=self.operation, work_center=foreign_center, assignment_role="primary",
        )
        result = self.assess()
        self.assertFalse(result["planningReady"])
        self.assertIn("WORK_CENTER_CANDIDATE_MISSING", self.codes(result))
        self.assertEqual(result["steps"][0]["candidateWorkCenters"], [])

    def test_inactive_resource_and_inactive_operation_cannot_report_available_capacity(self):
        self.work_center.is_active = False
        self.work_center.save(update_fields=["is_active"])
        self.assertFalse(capacity_fact(self.fresh_capacity(), ON_DATE)["available"])
        self.assertFalse(work_center_capacity_facts(self.work_center, ON_DATE)[0]["available"])
        self.assertFalse(self.assess()["planningReady"])
        self.work_center.is_active = True
        self.work_center.save(update_fields=["is_active"])
        self.operation.is_active = False
        self.operation.save(update_fields=["is_active"])
        self.assertFalse(capacity_fact(self.fresh_capacity(), ON_DATE)["available"])
        self.assertFalse(self.assess()["planningReady"])

    def test_foreign_company_uom_is_not_a_valid_capacity_fact(self):
        foreign_uom = UnitOfMeasure.objects.create(
            company_id=self.other_company.pk, code="FOREIGN-PCS", name="其他公司件", dimension="count",
        )
        self.capacity.uom = foreign_uom
        self.capacity.save(update_fields=["uom"])
        self.assertFalse(capacity_fact(self.fresh_capacity(), ON_DATE)["available"])
        self.assertFalse(self.assess()["planningReady"])

    def test_capacity_and_calendar_must_belong_to_same_candidate(self):
        self.work_center.capacity_policy = {}
        self.work_center.save(update_fields=["capacity_policy"])
        calendar_only = WorkCenter.objects.create(
            company=self.company, code="WC002", name="只有日历的备选工作中心",
            capacity_policy={"calendar": deepcopy(CALENDAR)},
        )
        WorkCenterOperationCapability.objects.create(
            operation=self.operation, work_center=calendar_only, assignment_role="alternative",
        )
        result = self.assess()
        self.assertFalse(result["planningReady"])
        self.assertIn("MANUFACTURING_CALENDAR_MISSING", self.codes(result))

    def test_missing_effective_date_or_expired_capacity_and_type_are_not_usable(self):
        self.capacity.effective_from = None
        self.capacity.save(update_fields=["effective_from"])
        self.assertFalse(self.assess()["planningReady"])
        self.capacity.effective_from = ON_DATE
        self.capacity.save(update_fields=["effective_from"])
        self.capacity.effective_to = date(2026, 10, 12)
        self.capacity.save(update_fields=["effective_to"])
        self.assertFalse(self.assess()["planningReady"])
        self.capacity.effective_to = None
        self.capacity.save(update_fields=["effective_to"])
        self.product_type.effective_to = date(2026, 10, 12)
        self.product_type.save(update_fields=["effective_to"])
        result = self.assess()
        self.assertFalse(result["planningReady"])
        self.assertIn("CAPACITY_PRODUCT_TYPE_MISSING", self.codes(result))

    def test_pending_real_condition_never_evaluates_capacity_demand(self):
        self.step.operation_parameters = {"applicability": {
            "mode": "CONDITIONAL", "conditionCode": "DRAWING_ENGRAVING_REQUIRED",
        }}
        self.step.save(update_fields=["operation_parameters"])
        with patch.object(StandardCapacity.objects, "filter") as capacity_query:
            result = self.assess()
        # The new source manifest may read the type-wide SC collection, but a
        # pending step still must not perform an operation capacity lookup.
        self.assertTrue(all(not {'operation', 'operation_id'} & set(call.kwargs)
                            for call in capacity_query.call_args_list))
        self.assertFalse(result["planningReady"])
        self.assertEqual(result["pendingApplicabilityStepCount"], 1)
        self.assertEqual(result["steps"][0]["applicability"]["result"], "PENDING")
        self.assertFalse(result["steps"][0]["capacityDemandEvaluated"])
        self.assertIn("ROUTING_STEP_APPLICABILITY_PENDING", self.codes(result))

    def test_resolver_manual_no_skips_capacity_without_replacing_applicability_logic(self):
        self.step.operation_parameters = {"applicability": {
            "mode": "CONDITIONAL", "conditionCode": "DRAWING_ENGRAVING_REQUIRED",
        }}
        self.step.save(update_fields=["operation_parameters"])
        # Only the isolated audit boundary is simulated; the real resolver runs.
        manual_no = {
            "status": "RESOLVED", "decision": "NO", "decisionLabel": "否",
            "result": "NOT_APPLICABLE", "sourceLabel": "授权业务人员人工确认",
            "confirmedByUsername": "isolated-authorized-user", "confirmedAt": "2026-10-13T13:00:00+08:00",
            "auditId": 91,
        }
        with patch.object(RoutingManualApplicabilityService, "resolve_for_step", return_value=manual_no), patch.object(
            StandardCapacity.objects, "filter",
        ) as capacity_query:
            result = self.assess()
        self.assertTrue(all(not {'operation', 'operation_id'} & set(call.kwargs)
                            for call in capacity_query.call_args_list))
        self.assertEqual(result["steps"][0]["applicability"]["result"], "NOT_APPLICABLE")
        self.assertEqual(result["steps"][0]["applicability"]["manualDecision"], "NO")
        self.assertFalse(result["steps"][0]["capacityDemandEvaluated"])
        self.assertTrue(result["steps"][0]["planningReady"])

    def test_empty_route_reports_a_concrete_missing_fact(self):
        self.step.delete()
        result = self.assess()
        self.assertFalse(result["planningReady"])
        self.assertEqual(result["stepCount"], 0)
        self.assertTrue(result["blockers"])
        self.assertNotEqual(result["requiredHumanInputLabel"], "无")

    def test_foundation_snapshot_reuses_exact_server_capacity_fact(self):
        row = self.fresh_capacity()
        expected = capacity_fact(row)
        actual = _snapshot(row)
        self.assertEqual(actual["dailyCapacityFact"], expected)
        self.assertEqual(actual["statusLabel"], expected["statusLabel"])
        self.assertEqual(actual["preparationDays"], expected["preparationDays"])
        self.assertEqual(actual["transferDays"], expected["transferDays"])

    def test_shared_maintenance_cannot_mutate_archived_hour_or_unhashed_routing_day_fields(self):
        self.assertEqual(_clean_values("routing-steps", RoutingStep, {
            "standard_hours": "1", "setup_hours": "2", "transfer_hours": "3",
            "preparation_days": "4", "transfer_days": "5",
        }), {})
        self.assertEqual(_clean_values("standard-capacities", StandardCapacity, {
            "standard_hours": "1", "preparation_days": "2",
        }), {"preparation_days": "2"})

    def test_duration_rejects_missing_times_zero_capacity_and_unit_mismatch(self):
        kwargs = {
            "demand_quantity": Decimal("250"), "capacity_quantity": Decimal("100"),
            "demand_uom_id": self.uom.pk, "capacity_uom_id": self.uom.pk,
            "preparation_days": Decimal("0.25"), "transfer_days": Decimal("0.5"),
        }
        self.assertEqual(duration_days(**kwargs)["durationDays"], "3.25")
        for overrides, code in (
            ({"preparation_days": None}, "PREPARATION_DAYS_MISSING"),
            ({"transfer_days": None}, "TRANSFER_DAYS_MISSING"),
            ({"capacity_quantity": 0}, "DAILY_CAPACITY_INVALID"),
            ({"capacity_uom_id": self.uom.pk + 1}, "CAPACITY_UOM_MISMATCH"),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(DailyCapacityError) as caught:
                    duration_days(**{**kwargs, **overrides})
                self.assertEqual(caught.exception.code, code)

    def test_calendar_rejects_empty_or_structurally_wrong_weekly_data(self):
        for calendar in ({}, {**CALENDAR, "weeklyAvailableMinutes": list(CALENDAR["weeklyAvailableMinutes"])}):
            with self.subTest(calendar=calendar):
                with self.assertRaises(DailyCapacityError):
                    working_date_window(start_date=ON_DATE, duration=Decimal("1"), calendar=calendar)

    def test_working_dates_are_fractional_day_bookings_and_failures_do_not_reserve(self):
        bookings = {"2026-10-13": "0.75"}
        result = working_date_window(
            start_date=ON_DATE, duration=Decimal("1.25"), calendar=CALENDAR, daily_bookings=bookings,
        )
        self.assertEqual([(row["date"], Decimal(row["allocatedDays"])) for row in result["allocations"]], [
            ("2026-10-13", Decimal("0.25")),
            ("2026-10-14", Decimal("1")),
        ])
        self.assertEqual(result["businessWriteCount"], 0)
        previous = deepcopy(bookings)
        with self.assertRaises(DailyCapacityError):
            working_date_window(
                start_date=ON_DATE, duration=Decimal("100"), calendar=CALENDAR,
                daily_bookings=bookings, horizon_days=1,
            )
        self.assertEqual(bookings, previous)
