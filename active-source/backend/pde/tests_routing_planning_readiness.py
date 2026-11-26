from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from masterdata.models import UnitOfMeasure
from system.models import Company, Department, Process, Workshop

from .models import (
    ManufacturingProcessType,
    ProductCategory,
    Routing,
    RoutingStep,
    RoutingVersion,
    StandardCapacity,
    WorkCenter,
    WorkCenterOperationCapability,
)
from .routing_planning_readiness_service import RoutingPlanningReadinessService


class RoutingPlanningReadinessTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="PLAN", name="计划承接测试公司")
        self.department = Department.objects.create(
            company=self.company, code="PLAN-MFG", name="制造部",
            department_type=Department.DepartmentType.PRODUCTION,
        )
        self.workshop = Workshop.objects.create(
            company=self.company, department=self.department,
            code="PLAN-WS", name="测试车间",
        )
        self.uom = UnitOfMeasure.objects.create(
            company_id=self.company.pk, code="PLAN-PCS", name="件", dimension="count",
        )
        self.category = ProductCategory.objects.create(
            company=self.company, code="PLAN-CAT", name="通用测试分类",
            industry_type="general",
        )
        self.process_type = ManufacturingProcessType.objects.create(
            company=self.company, code="PLAN-PROC", name="通用测试工艺",
        )
        self.routing = Routing.objects.create(
            company=self.company,
            applicability_scope="PRODUCT_CATEGORY",
            product_category=self.category,
            manufacturing_process_type=self.process_type,
            routing_code="PLAN-ROUTE", name="计划承接测试路线", status="released",
        )
        self.version = RoutingVersion.objects.create(
            routing=self.routing, routing_version="V1", revision=1, status="draft",
        )
        self.operation = Process.objects.create(
            company=self.company, workshop=self.workshop,
            code="PLAN-OP", name="计划承接工序",
            calculation_basis=Process.CalculationBasis.COUNT,
            calculation_uom=self.uom,
            quantity_driver="BOM_OUTPUT_QUANTITY",
        )
        self.step = RoutingStep.objects.create(
            routing_version=self.version, sequence=10, operation=self.operation,
            predecessor_sequences=[], setup_hours=Decimal("0.2500"),
            transfer_hours=Decimal("0.1000"),
            operation_parameters={"applicability": {"mode": "MANDATORY"}},
        )

    def test_missing_formal_time_resource_capacity_and_calendar_block(self):
        result = RoutingPlanningReadinessService.assess(self.version)
        self.assertFalse(result["planningReady"])
        self.assertEqual(result["statusCode"], "BLOCKED_MISSING_FORMAL_PLANNING_DATA")
        codes = {row["code"] for row in result["blockers"]}
        self.assertEqual(codes, {
            "STANDARD_TIME_MISSING",
            "WORK_CENTER_CANDIDATE_MISSING",
            "CAPACITY_FACT_MISSING",
            "MANUFACTURING_CALENDAR_MISSING",
        })
        self.assertEqual(result["productionPlanCreatedCount"], 0)
        self.assertEqual(result["businessWriteCount"], 0)

    def test_complete_formal_inputs_are_stable_planning_handoff(self):
        calendar = {
            "contractVersion": "PCE-MFG-CALENDAR-V1.0",
            "timezone": "Asia/Shanghai",
            "weeklyAvailableMinutes": {
                "MON": 480, "TUE": 480, "WED": 480, "THU": 480,
                "FRI": 480, "SAT": 0, "SUN": 0,
            },
            "exceptions": [{"date": "2026-10-01", "availableMinutes": 0}],
        }
        work_center = WorkCenter(
            company=self.company, department=self.department, workshop=self.workshop,
            code="PLAN-WC", name="计划承接工作中心",
            capacity_policy={"calendar": calendar},
        )
        work_center.full_clean()
        work_center.save()
        WorkCenterOperationCapability.objects.create(
            work_center=work_center, operation=self.operation,
            assignment_role="primary", capability_code="PLAN-CAP",
        )
        self.operation.standard_hours = Decimal("1.5000")
        self.operation.save(update_fields=["standard_hours"])
        StandardCapacity.objects.create(
            company=self.company, code="PLAN-CAPACITY", name="计划承接产能",
            resource_scope=StandardCapacity.ResourceScope.COMPOSITE,
            work_center=work_center, operation=self.operation,
            measurement_status=StandardCapacity.MeasurementStatus.MEASURED,
            quantity=Decimal("20"), uom=self.uom,
            time_basis=StandardCapacity.TimeBasis.HOUR,
            time_basis_quantity=Decimal("1"),
        )
        result = RoutingPlanningReadinessService.assess(self.version)
        self.assertTrue(result["planningReady"])
        self.assertEqual(result["statusCode"], "READY_FOR_PRODUCTION_PLANNING")
        self.assertEqual(result["steps"][0]["standardHoursSource"], "Process.standard_hours")
        self.assertEqual(result["steps"][0]["candidateWorkCenters"][0]["role"], "primary")
        foundation = RoutingPlanningReadinessService.foundation_assessment(self.company.pk)
        by_code = {row["code"]: row for row in foundation["capabilities"]}
        self.assertEqual(by_code["ALTERNATIVE_WORK_CENTERS"]["classificationCode"], "DEVELOPED_USABLE")
        self.assertEqual(by_code["MEASURED_CAPACITY"]["classificationCode"], "DEVELOPED_USABLE")
        self.assertEqual(by_code["MANUFACTURING_CALENDAR"]["classificationCode"], "DEVELOPED_USABLE")

    def test_calendar_and_yield_contracts_fail_closed(self):
        work_center = WorkCenter(
            company=self.company, department=self.department, workshop=self.workshop,
            code="PLAN-BAD-WC", name="错误日历工作中心",
            capacity_policy={"calendar": {"contractVersion": "unknown"}},
        )
        with self.assertRaises(ValidationError):
            work_center.full_clean()
        self.step.operation_parameters = {"yieldRate": 0, "executionMode": "unknown"}
        with self.assertRaises(ValidationError):
            self.step.full_clean()

    def test_dependency_graph_reports_branch_and_merge(self):
        for sequence, predecessors in ((20, [10]), (30, [10]), (40, [20, 30])):
            RoutingStep.objects.create(
                routing_version=self.version, sequence=sequence,
                operation=self.operation, predecessor_sequences=predecessors,
                operation_parameters={"applicability": {"mode": "MANDATORY"}},
            )
        topology = RoutingPlanningReadinessService.assess(self.version)["dependencyTopology"]
        self.assertEqual(topology["rootStepCount"], 1)
        self.assertEqual(topology["branchStepCount"], 1)
        self.assertEqual(topology["mergeStepCount"], 1)
        self.assertTrue(topology["dependencyReferenceIntegrity"])
