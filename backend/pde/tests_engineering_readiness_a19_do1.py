from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from masterdata.models import Material, UnitOfMeasure
from sales.models import SalesOrder, SalesOrderItem
from system.models import Company, OrganizationOperatingAuditRecord, Process, User

from .engineering_calculation_service import EngineeringCalculationReadinessService
from .models import (
    EngineeringCalculationDetail,
    EngineeringCalculationRecord,
    EngineeringDerivedFact,
    EngineeringRuleDefinition,
    EngineeringSourceRecord,
    OrderEngineeringInstance,
)


class EngineeringReadinessA19DO1Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="A19DO1", name="A1.9 DO-1只读验收公司")
        cls.user = User.objects.create_user(
            username="a19_do1_reader", password="test-only", real_name="A1.9只读验收员",
            company_id=cls.company.pk,
        )
        cls.mm = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="mm", name="毫米", decimal_places=3,
        )
        EngineeringRuleDefinition.objects.create(
            company=cls.company,
            rule_code="G1-TEST-OUTPUT",
            rule_name="G1当前单位只读验收",
            version="V1.0",
            rule_kind="formula",
            status="released",
            specification={
                "rulePackage": {"code": "A18_G1_DOOR_GOLDEN", "version": "V1.0"},
                "outputs": [{"canonicalName": "door_width", "unit": "mm"}],
            },
        )
        EngineeringSourceRecord.objects.create(
            company=cls.company,
            source_no="A18-LOCKED",
            source_name="A1.8 locked Golden source record",
            source_type="controlled_import",
            source_version="V1.0",
            source_payload={},
            content_hash="a" * 64,
            status="confirmed",
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @staticmethod
    def _business_counts():
        return {
            "orders": SalesOrder.objects.count(),
            "orderItems": SalesOrderItem.objects.count(),
            "materials": Material.objects.count(),
            "processes": Process.objects.count(),
            "instances": OrderEngineeringInstance.objects.count(),
            "calculations": EngineeringCalculationRecord.objects.count(),
            "details": EngineeringCalculationDetail.objects.count(),
            "facts": EngineeringDerivedFact.objects.count(),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
        }

    def test_readiness_get_exposes_five_gates_and_performs_zero_business_writes(self):
        before = self._business_counts()
        response = self.client.get(reverse("pde-engineering-calculation-readiness"))
        after = self._business_counts()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(before, after)
        self.assertEqual(response.data["pageCode"], "pde-order-engineering-calculation")
        self.assertEqual(response.data["businessObject"], "EngineeringCalculationRecord")
        self.assertEqual([gate["code"] for gate in response.data["gates"]], [
            "ORDER", "MATERIAL", "ENGINEERING UOM", "OPERATION", "SOURCE",
        ])
        self.assertEqual(response.data["candidateMethodAccess"]["status"], "READ_DENIED")
        self.assertIsNone(response.data["candidateMethodAccess"]["methodCount"])
        self.assertIn(
            "CALCULATION_METHOD_READ_PERMISSION_REQUIRED",
            response.data["execution"]["blockerCodes"],
        )
        self.assertEqual(response.data["businessWriteSideEffectCount"], 0)

    def test_current_empty_company_shows_real_blockers_without_creating_facts(self):
        response = self.client.get(reverse("pde-engineering-calculation-readiness"))
        gates = {gate["code"]: gate for gate in response.data["gates"]}

        self.assertEqual(gates["ORDER"]["status"], "BLOCKED")
        self.assertEqual(gates["MATERIAL"]["status"], "BLOCKED")
        self.assertEqual(gates["ENGINEERING UOM"]["status"], "PASS")
        self.assertEqual(gates["OPERATION"]["status"], "BLOCKED")
        self.assertEqual(gates["SOURCE"]["status"], "BLOCKED")
        self.assertEqual(response.data["overallStatus"], "BLOCKED")
        self.assertFalse(response.data["execution"]["enabled"])
        self.assertEqual(response.data["sourceReconciliation"]["classification"], "D")
        self.assertEqual(SalesOrder.objects.count(), 0)

    def test_unknown_material_uom_does_not_turn_into_identity_failure_reason(self):
        response = self.client.get(reverse("pde-engineering-calculation-readiness"))
        rows = response.data["materialBasePurchaseUom"]
        self.assertTrue(rows)
        self.assertTrue(all(row["unitStatus"] == "UNKNOWN" for row in rows))
        self.assertTrue(all(row["baseUom"] == "NULL" for row in rows))
        self.assertTrue(all(row["identityAffectedByUnknownUom"] is False for row in rows))

    def test_future_uoms_do_not_block_current_released_g1_mm(self):
        response = self.client.get(reverse("pde-engineering-calculation-readiness"))
        rows = {row["uom"]: row for row in response.data["engineeringRequiredUoms"]}
        self.assertEqual(rows["mm"]["status"], "PASS")
        self.assertEqual(rows["m"]["status"], "PENDING")
        self.assertEqual(rows["m²"]["status"], "PENDING")
        gate = next(gate for gate in response.data["gates"] if gate["code"] == "ENGINEERING UOM")
        self.assertEqual(gate["status"], "PASS")

    def test_source_classification_a_only_allows_formal_review_and_never_registers_hash(self):
        decision = EngineeringCalculationReadinessService.source_decision("A")
        self.assertEqual(decision["status"], "PASS")
        self.assertEqual(decision["executionEligibility"], "ELIGIBLE FOR FORMAL REVIEW")
        self.assertFalse(decision["formalHashRegistrationPerformed"])

    def test_authoritative_source_is_selected_from_governance_metadata_not_code_hash(self):
        source = EngineeringSourceRecord.objects.get(source_no="A18-LOCKED")
        source.source_payload = {
            "fileName": "controlled-engineering-source.xlsx",
            "capturedAt": "2026-09-01T10:00:00+08:00",
            "sourceDate": "2026-08-28",
            "governance": {"status": "AUTHORITATIVE", "supersedes": None},
            "validation": {"status": "PASS", "notes": "isolated test fixture"},
        }
        source.save(update_fields=["source_payload", "updated_at"])

        response = self.client.get(reverse("pde-engineering-calculation-readiness"))
        gate = next(g for g in response.data["gates"] if g["code"] == "SOURCE")
        reconciliation = response.data["sourceReconciliation"]
        self.assertEqual(gate["status"], "PASS")
        self.assertEqual(reconciliation["classification"], "A")
        self.assertEqual(reconciliation["authoritativeSource"]["sourceRecordId"], source.pk)
        self.assertNotIn("lockedHash", reconciliation)

    def test_endpoint_is_get_only(self):
        response = self.client.post(reverse("pde-engineering-calculation-readiness"), {})
        self.assertEqual(response.status_code, 405)

    def test_recovery_audit_exposes_existing_models_and_zero_write_boundary(self):
        before = self._business_counts()
        response = self.client.get(reverse("pde-engineering-calculation-readiness"))
        after = self._business_counts()

        self.assertEqual(before, after)
        self.assertEqual(response.data["existingEngineStatus"], "PARTIAL")
        statuses = {row["model"]: row for row in response.data["modelStatuses"]}
        self.assertEqual(set(statuses), {
            "EngineeringRuleDefinition", "EngineeringCalculationRecord",
            "CalculationDetail", "EngineeringDerivedFact",
        })
        self.assertTrue(statuses["EngineeringRuleDefinition"]["developed"])
        self.assertEqual(statuses["EngineeringRuleDefinition"]["recordCount"], 1)
        self.assertEqual(len(response.data["calculationReadinessMatrix"]), 11)
        missing_rows = [row for row in response.data["calculationReadinessMatrix"] if row["formalRuleStatus"] == "MISSING"]
        self.assertEqual(len(missing_rows), 10)
        self.assertTrue(all(row["currentStatus"] == "USER_INPUT_REQUIRED" for row in missing_rows))
        definition = response.data["materialRuleDefinition"]
        self.assertEqual(definition["structureCardCount"], 31)
        self.assertEqual(definition["sourceRowCount"], 71)
        self.assertEqual(
            [row["sequence"] for row in definition["firstBatchTemplates"]],
            ["M01", "M02", "M03", "M04"],
        )
        self.assertTrue(all(row["formalWriteAllowed"] is False for row in definition["firstBatchTemplates"]))
        self.assertTrue(all(row["userValidationStatus"] == "PENDING" for row in definition["firstBatchTemplates"]))
        self.assertIn("合页", [row["name"] for row in definition["secondBatch"]])
        self.assertEqual(definition["productionRealRuleWrite"], 0)
        self.assertFalse(response.data["sourceAuthority"]["linkageTo08Required"])
        self.assertEqual(response.data["group3C"]["structureLayer"], "USER_VALIDATED")
        self.assertEqual(response.data["group3C"]["calculationLayer"], "NOT_READY")
        self.assertEqual(response.data["productionBusinessWrite"], 0)
