"""SIMULATED_FOR_TEST: formal DAY maintenance and its native read consumers.

Run only through the named, guarded disposable-database runner. The employee,
position, responsibility and organization grants are real isolated fixtures;
neither authorization nor successful persistence/readiness is mocked.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.test import TestCase

from system.models import Permission, Process, RolePermission, User
from . import daily_capacity_service as capacity
from . import tests_classified_fact_eor as snapshot_fixtures
from . import tests_production_foundation_a1 as foundation_fixtures
from .models import (
    CapacityProductType, ManufacturingProcessType, ProductCategory,
    Routing, RoutingStep, RoutingVersion, StandardCapacity, WorkCenter,
    WorkCenterOperationCapability,
)
from .production_foundation_service import ProductionFoundationError, ProductionFoundationService


ON_DATE = date(2026, 10, 13)
DAY_ACTION = "production.master_data.capacity.maintain"


class DayTimeMaintenancePersistenceTests(TestCase):
    def setUp(self):
        self.fixture = foundation_fixtures.ProductionFoundationA1Tests(methodName="runTest")
        self.fixture.setUp()
        self.company, self.user = self.fixture.company, self.fixture.user
        permission, _ = Permission.objects.get_or_create(
            code=DAY_ACTION, defaults={"name": DAY_ACTION, "module": "PRODUCTION"})
        RolePermission.objects.get_or_create(role=self.fixture.role, permission=permission)
        authority = ProductionFoundationService.maintenance_authorization(
            "standard-capacities", user=self.user)
        self.assertTrue(authority["allowed"], authority)
        self.assertTrue(authority["executionChainComplete"], authority)
        self.category = ProductCategory.objects.create(
            company=self.company, code="SIM-DAY-CAT", name="SIMULATED_FOR_TEST")
        self.process_type = ManufacturingProcessType.objects.create(
            company=self.company, code="SIM-DAY-TYPE", name="SIMULATED_FOR_TEST")
        self.product_type = CapacityProductType.objects.create(
            company=self.company, code="SIM-DAY/FLEX", name="SIMULATED_FOR_TEST",
            product_category=self.category, manufacturing_process_type=self.process_type)
        self.operation = Process.objects.create(
            company=self.company, code="SIM-DAY-OP", name="Abstract DAY operation",
            calculation_basis="count", calculation_uom=self.fixture.uom)
        self.center = WorkCenter.objects.create(
            company=self.company, code="SIM-DAY-WC", name="SIMULATED_FOR_TEST")
        WorkCenterOperationCapability.objects.create(
            work_center=self.center, operation=self.operation, assignment_role="primary")
        self.route = Routing.objects.create(
            company=self.company, routing_code=self.product_type.code,
            name="SIMULATED_FOR_TEST", applicability_scope="PRODUCT_CATEGORY",
            product_category=self.category, manufacturing_process_type=self.process_type)
        self.version = RoutingVersion.objects.create(
            routing=self.route, routing_version="SIM-V1", status="draft")
        self.step = RoutingStep.objects.create(
            routing_version=self.version, sequence=10, operation=self.operation,
            operation_parameters={"applicability": {
                "contractVersion": "PCE-ROUTING-STEP-APPLICABILITY-V1.0", "mode": "MANDATORY"}})
        result = ProductionFoundationService.write("standard-capacities", user=self.user,
            payload={"company_id": self.company.pk, "code": "SIM-DAY-SC",
                "name": "SIMULATED_FOR_TEST", "resource_scope": "composite",
                "work_center_id": self.center.pk, "operation_id": self.operation.pk,
                "product_type_id": self.product_type.pk, "uom_id": self.fixture.uom.pk,
                "measurement_status": "measured", "quantity": "100",
                "time_basis": "day", "time_basis_quantity": "1", "time_unit": "DAY",
                "preparation_days": "0.1", "transfer_days": "0.1",
                "effective_from": ON_DATE.isoformat(), "conditions": self.conditions("0.1", "0.1"),
                "reason": "SIMULATED_FOR_TEST formal DAY fixture"},
            idempotency_key="sim-day-create", source_identity={
                "sourceSystem": "SIMULATED_FOR_TEST", "sourceType": "DAY_MAINTENANCE_TEST",
                "sourceObjectType": "StandardCapacity", "externalId": "sim-day-create"})
        self.assertTrue(result["authorization"]["allowed"], result)
        self.assertTrue(result["auditId"])
        self.capacity_id = result["row"]["id"]
        self.write_number = 0

    def snapshot(self):
        return snapshot_fixtures.ClassifiedFactEorTests.full_database_snapshot(self)

    def conditions(self, preparation, transfer):
        manifest = {"contractVersion": capacity.SOURCE_RULES_CONTRACT,
            "sourceSha256": "a1" * 32, "productTypeCode": self.product_type.code,
            "effectiveDate": ON_DATE.isoformat(), "applicableOperationIds": [self.operation.pk],
            "nonApplicableOperationIds": [], "auxiliaryOperationIds": [],
            "preparationDays": preparation, "transferDays": transfer,
            "businessFactReference": "SIMULATED_FOR_TEST configured DAY facts"}
        return {"sourceSha256": manifest["sourceSha256"],
            "sourceProductTypeCode": self.product_type.code, "apsSourceRules": manifest}

    def write(self, payload, *, user=None):
        self.write_number += 1
        return ProductionFoundationService.write("standard-capacities", user=user or self.user,
            object_id=self.capacity_id, payload={**payload,
                "reason": "SIMULATED_FOR_TEST formal DAY maintenance"},
            idempotency_key=f"sim-day-maintain-{self.write_number}", source_identity=None)

    def write_times(self, preparation, transfer):
        result = self.write({"preparation_days": preparation, "transfer_days": transfer,
            "conditions": self.conditions(preparation, transfer)})
        self.assertTrue(result["authorization"]["allowed"], result)
        self.assertTrue(result["executionChain"])
        self.assertTrue(result["auditId"])
        return result

    def step_times(self, preparation, transfer):
        # Only the disposable draft fixture is changed; released routes and
        # the formal SC maintenance service are never bypassed.
        self.step.preparation_days, self.step.transfer_days = preparation, transfer
        self.step.save(update_fields=("preparation_days", "transfer_days"))

    def read(self):
        before = self.snapshot()
        try:
            listed = ProductionFoundationService.list(
                "standard-capacities", organization_id=self.company.pk)
            persisted = next(row for row in listed if row["id"] == self.capacity_id)
            result = capacity.DailyCapacityReadinessService.assess(self.version, on_date=ON_DATE)
            self.assertEqual(result["businessWriteCount"], 0)
            self.assertEqual(result["productionPlanCreatedCount"], 0)
            self.assertEqual(result["productionScheduleCreatedCount"], 0)
            self.assertEqual(result["sourceRulesFact"]["status"], "VALID", result)
            step, = result["steps"]
            fact, = step["dailyCapacity"]
            self.assertEqual(fact["id"], self.capacity_id)
            self.assertEqual(persisted["dailyCapacityFact"], capacity.capacity_fact(
                StandardCapacity.objects.get(pk=self.capacity_id), ON_DATE))
            return persisted, step, fact
        finally:
            self.assertEqual(self.snapshot(), before,
                "Native list/readiness must preserve rows, audits, statuses and numbering")

    def duration(self, step, fact):
        return capacity.duration_days(demand_quantity="4", capacity_quantity=fact["quantity"],
            demand_uom_id=self.fixture.uom.pk, capacity_uom_id=fact["uomId"],
            preparation_days=step["preparationDays"], transfer_days=step["transferDays"])

    def assert_selected(self, step, preparation, transfer):
        for field, expected in (("preparationDays", preparation), ("transferDays", transfer)):
            if expected is None:
                self.assertIsNone(step[field])
            else:
                self.assertEqual(Decimal(step[field]), Decimal(str(expected)))

    def test_formal_nondefault_save_reaches_matching_step_read_and_native_duration(self):
        saved = self.write_times("0.2", "0.2")
        self.step_times(Decimal("0.2"), Decimal("0.2"))
        persisted, step, fact = self.read()
        self.assertEqual(persisted["id"], saved["row"]["id"])
        self.assert_selected(step, "0.2", "0.2")
        self.assertNotIn("APS_SOURCE_RULES_INVALID", step["blockerCodes"])
        result = self.duration(step, fact)
        self.assertEqual(Decimal(result["productionDays"]), Decimal("0.04"))
        self.assertEqual(Decimal(result["durationDays"]), Decimal("0.44"))
        self.assertEqual(result["timeUnit"], "DAY")

    def test_null_step_falls_back_to_same_formally_saved_sc_for_nondefault_and_zero(self):
        for value, expected_duration in (("0.2", "0.44"), ("0", "0.04")):
            with self.subTest(days=value):
                self.write_times(value, value)
                persisted, step, fact = self.read()
                self.assertIsNone(self.step.preparation_days)
                self.assertIsNone(self.step.transfer_days)
                self.assert_selected(step, value, value)
                self.assertEqual(Decimal(persisted["preparationDays"]), Decimal(value))
                self.assertEqual(Decimal(persisted["transferDays"]), Decimal(value))
                self.assertNotIn("PREPARATION_DAYS_MISSING", step["blockerCodes"])
                self.assertNotIn("TRANSFER_DAYS_MISSING", step["blockerCodes"])
                self.assertEqual(Decimal(self.duration(step, fact)["durationDays"]), Decimal(expected_duration))

    def test_explicit_step_conflict_with_nonnull_manifest_still_blocks_without_rewriting(self):
        self.step_times(Decimal("0.2"), Decimal("0.1"))
        before = deepcopy(self.step.preparation_days)
        _, step, _ = self.read()
        self.assertIn("APS_SOURCE_RULES_INVALID", step["blockerCodes"])
        self.assertIn("未修改路线", step["sourceRulesConflictLabel"])
        self.step.refresh_from_db()
        self.assertEqual(self.step.preparation_days, before)

    def test_null_manifest_keeps_explicit_legal_step_precedence(self):
        self.write_times(None, None)
        self.step_times(Decimal("0.2"), Decimal("0.3"))
        persisted, step, fact = self.read()
        self.assertIsNone(persisted["preparationDays"])
        self.assertIsNone(persisted["transferDays"])
        self.assert_selected(step, "0.2", "0.3")
        self.assertNotIn("APS_SOURCE_RULES_INVALID", step["blockerCodes"])
        self.assertNotIn("PREPARATION_DAYS_MISSING", step["blockerCodes"])
        self.assertNotIn("TRANSFER_DAYS_MISSING", step["blockerCodes"])
        self.assertEqual(Decimal(self.duration(step, fact)["durationDays"]), Decimal("0.54"))

    def test_explicit_zero_and_null_remain_distinct_when_saved_source_days_are_null(self):
        self.write_times(None, None)
        self.step_times(Decimal("0"), Decimal("0"))
        _, step, fact = self.read()
        self.assert_selected(step, "0", "0")
        self.assertNotIn("APS_SOURCE_RULES_INVALID", step["blockerCodes"])
        self.assertEqual(Decimal(self.duration(step, fact)["durationDays"]), Decimal("0.04"))
        self.step_times(None, None)
        persisted, step, fact = self.read()
        self.assertIsNone(persisted["preparationDays"])
        self.assertIsNone(persisted["transferDays"])
        self.assert_selected(step, None, None)
        self.assertTrue({"PREPARATION_DAYS_MISSING", "TRANSFER_DAYS_MISSING"}.issubset(step["blockerCodes"]))
        with self.assertRaises(capacity.DailyCapacityError) as raised:
            self.duration(step, fact)
        self.assertEqual(raised.exception.code, "PREPARATION_DAYS_MISSING")

    def test_invalid_bool_negative_nonfinite_and_hour_writes_preserve_original_configuration(self):
        cases = [{field: value} for field in ("preparation_days", "transfer_days")
            for value in (True, False, "not-a-number", "NaN", "Infinity", "-0.01",
                          "0.00001", "123456789.0000")]
        cases.append({"time_unit": "HOUR"})
        for payload in cases:
            with self.subTest(payload=payload):
                before = self.snapshot()
                with self.assertRaises(ProductionFoundationError):
                    self.write(payload)
                self.assertEqual(self.snapshot(), before,
                    "Rejected maintenance must roll back SC, identity, audit, state and numbering writes")

    def test_existing_permission_and_employee_chain_are_required_without_success_mocks(self):
        denied = User.objects.create_user(username="sim_day_denied", company_id=self.company.pk)
        authority = ProductionFoundationService.maintenance_authorization(
            "standard-capacities", user=denied)
        self.assertFalse(authority["allowed"], authority)
        before = self.snapshot()
        with self.assertRaises(ProductionFoundationError):
            self.write({"preparation_days": "0.2"}, user=denied)
        self.assertEqual(self.snapshot(), before)
