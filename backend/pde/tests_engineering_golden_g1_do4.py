"""A1.8 DO-4 G1 exact Golden validation acceptance matrix."""

from copy import deepcopy

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from masterdata.models import CodeRule, UnitOfMeasure
from pfm.models import Employee
from planning.models import Demand, PlanningRequirement, ProductionPlan, PurchasePlan
from procurement.models import InventoryBalance, InventoryTransaction
from sales.models import SalesOrder
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment,
)

from .engineering_calculation_service import (
    EngineeringCalculationError, EngineeringCalculationService,
)
from .models import (
    EngineeringBreakdownItem, EngineeringCalculationRecord, EngineeringDerivedFact,
    EngineeringRuleDefinition, EngineeringSourceRecord,
)
from .production_foundation_service import ProductionFoundationService


WORKBOOK_HASH = "26334A8ABF6CEF2BA165CF8BFE2CEAFC9E198E6785EBC668122E1F3E9E61D744"


def input_contract(name, source_type):
    return {
        "canonicalName": name, "valueType": "decimal", "unitDimension": "length",
        "unitRequired": True, "required": True, "sourceType": source_type,
        "description": name,
    }


def rule_spec(code, expression, input_name, output_name, cell, formula, *, dependency=None, priority=10):
    return {
        "description": "A1.8 DO-4 G1真实Golden Case受控规则",
        "rulePackage": {"code": "A18_G1_DOOR_GOLDEN", "version": "V1.0"},
        "expression": expression,
        "inputs": [input_contract(input_name, "ENGINEERING_DERIVED" if dependency else "SITE_MEASUREMENT")],
        "outputs": [{
            "canonicalName": output_name, "valueType": "decimal", "unitDimension": "length",
            "unit": "mm", "resultDomain": "DERIVED_FACT", "description": output_name,
        }],
        "dependencies": [dependency] if dependency else [],
        "applicability": {
            "scope": "validation", "validationClass": "GOLDEN",
            "productCategory": "door", "productName": "single_leaf_door",
            "paintProcess": "clear_closed",
        },
        "decimalPrecision": 18, "outputScale": 0,
        "roundingMode": "ROUND_HALF_UP", "priority": priority,
        "sourceEvidence": {
            "reference": f"工程拆单及订单排产数据核算方式.xlsx/房门单!{cell}: {formula}",
            "workbookSha256": WORKBOOK_HASH, "verificationStatus": "VERIFIED_SOURCE",
            "purpose": "Golden Validation",
        },
    }


class EngineeringGoldenG1DO4Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="DO4", name="DO-4 Golden验收公司")
        cls.department = Department.objects.create(code="DO4-PLAN", name="计划部", company=cls.company)
        cls.position = Position.objects.create(
            code="DO4-PLAN", name="计划工程岗", company=cls.company, department=cls.department,
        )
        cls.responsibility = Responsibility.objects.create(
            code="RESP_DO4_GOLDEN", name="Golden验证", status="ACTIVE", is_active=True,
        )
        PositionResponsibility.objects.create(
            position=cls.position, responsibility=cls.responsibility, is_primary=True, active=True,
        )
        cls.user = User.objects.create_user(
            username="do4_planner", password="test-only", real_name="DO-4计划员",
            company_id=cls.company.pk,
        )
        Employee.objects.create(
            user=cls.user, employee_no="DO4-E001", full_name="DO-4计划员",
            department_ref=cls.department, position_ref=cls.position, status="active",
        )
        cls.role = Role.objects.create(code="DO4_GOLDEN_ROLE", name="DO-4 Golden角色")
        for code in (
            "production.engineering.calculation.view",
            "production.engineering.calculation.execute",
            "production.engineering.rule.create",
            "production.engineering.rule.release",
            "production.engineering.source.maintain",
        ):
            RolePermission.objects.create(role=cls.role, permission=Permission.objects.get(code=code))
        UserRoleScopeAssignment.objects.create(
            user=cls.user, role=cls.role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, business_hash="do4-authorized",
        )
        cls.denied = User.objects.create_user(
            username="do4_denied", password="test-only", real_name="无Golden权限",
            company_id=cls.company.pk,
        )
        Employee.objects.create(
            user=cls.denied, employee_no="DO4-E002", full_name="无Golden权限",
            department_ref=cls.department, position_ref=cls.position, status="active",
        )
        denied_role = Role.objects.create(code="DO4_DENIED_ROLE", name="无Golden权限角色")
        UserRoleScopeAssignment.objects.create(
            user=cls.denied, role=denied_role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, business_hash="do4-denied",
        )
        CodeRule.objects.create(
            company_id=cls.company.pk, entity_type="production_engineering_calculation",
            prefix="EC-DO4-", date_format="", seq_length=4, current_seq=0,
        )
        CodeRule.objects.create(
            company_id=cls.company.pk, entity_type="production_engineering_source",
            prefix="SRC-DO4-", date_format="", seq_length=4, current_seq=0,
        )
        cls.mm = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="mm", name="毫米", decimal_places=0,
        )
        cls.payload = {
            "validationClass": "GOLDEN",
            "goldenValidation": {
                "caseCode": "G1-DOOR-SINGLE-LEAF", "caseName": "次卧-单开门",
                "rulePackageCode": "A18_G1_DOOR_GOLDEN",
                "sourceFile": "工程拆单及订单排产数据核算方式.xlsx",
                "sourceWorkbookSha256": WORKBOOK_HASH, "sourceSheet": "房门单", "sourceRow": 11,
                "expectedResults": [
                    {"canonicalField": "casing_height", "value": "2035", "unit": "mm", "cell": "N11", "verificationStatus": "VERIFIED_RESULT"},
                    {"canonicalField": "casing_width", "value": "918", "unit": "mm", "cell": "O11", "verificationStatus": "VERIFIED_RESULT"},
                    {"canonicalField": "door_height", "value": "2002", "unit": "mm", "cell": "R11", "verificationStatus": "VERIFIED_RESULT"},
                    {"canonicalField": "door_width", "value": "866", "unit": "mm", "cell": "S11", "verificationStatus": "VERIFIED_RESULT"},
                ],
            },
            "rawFacts": [
                {"rawSource": "用户真实工作簿", "rawSheet": "房门单", "rawField": "洞高", "rawCell": "J11", "rawValue": "2045", "canonicalField": "opening_height", "normalizedValue": "2045", "valueType": "decimal", "unit": "mm", "sourceType": "SITE_MEASUREMENT", "verificationStatus": "VERIFIED_SOURCE"},
                {"rawSource": "用户真实工作簿", "rawSheet": "房门单", "rawField": "洞宽", "rawCell": "K11", "rawValue": "938", "canonicalField": "opening_width", "normalizedValue": "938", "valueType": "decimal", "unit": "mm", "sourceType": "SITE_MEASUREMENT", "verificationStatus": "VERIFIED_SOURCE"},
            ],
            "canonicalInputs": {
                "opening_height": {"value": "2045", "unit": "mm", "unitDimension": "length", "sourceType": "SITE_MEASUREMENT"},
                "opening_width": {"value": "938", "unit": "mm", "unitDimension": "length", "sourceType": "SITE_MEASUREMENT"},
            },
        }
        cls.source = EngineeringSourceRecord.objects.create(
            company=cls.company, source_no="G1-DO4", source_name="G1次卧单开门Golden来源",
            source_type="controlled_import", source_version="V1.0", source_payload=cls.payload,
            content_hash=WORKBOOK_HASH.lower(), status="confirmed",
        )
        definitions = (
            ("G1-CASING-HEIGHT", "门套高", "opening_height - 10", "opening_height", "casing_height", "N11", "J11-10", None, 10),
            ("G1-CASING-WIDTH", "门套宽", "opening_width - 20", "opening_width", "casing_width", "O11", "K11-20", None, 20),
            ("G1-DOOR-HEIGHT", "门高", "casing_height - 33", "casing_height", "door_height", "R11", "N11-33", "G1-CASING-HEIGHT", 30),
            ("G1-DOOR-WIDTH", "门宽", "casing_width - 52", "casing_width", "door_width", "S11", "O11-52", "G1-CASING-WIDTH", 40),
        )
        cls.rules = []
        for code, name, expression, input_name, output, cell, formula, dependency, priority in definitions:
            cls.rules.append(EngineeringRuleDefinition.objects.create(
                company=cls.company, rule_code=code, rule_name=name, version="V1.0",
                rule_kind="formula",
                specification=rule_spec(code, expression, input_name, output, cell, formula, dependency=dependency, priority=priority),
                status="released",
            ))

    def execute(self, **overrides):
        args = {
            "user": self.user, "scope": "validation", "source_record_id": self.source.pk,
            "rule_ids": [row.pk for row in self.rules], "reason": "DO-4 G1 Golden正式验算",
        }
        args.update(overrides)
        return EngineeringCalculationService.execute(**args)

    def test_01_source_file_locked(self):
        self.assertEqual(self.payload["goldenValidation"]["sourceFile"], "工程拆单及订单排产数据核算方式.xlsx")

    def test_02_source_hash_locked(self):
        self.assertEqual(self.payload["goldenValidation"]["sourceWorkbookSha256"], WORKBOOK_HASH)

    def test_03_source_sheet_and_row_locked(self):
        self.assertEqual((self.payload["goldenValidation"]["sourceSheet"], self.payload["goldenValidation"]["sourceRow"]), ("房门单", 11))

    def test_04_raw_values_are_verified_source(self):
        self.assertTrue(all(row["verificationStatus"] == "VERIFIED_SOURCE" for row in self.payload["rawFacts"]))

    def test_05_expected_values_are_verified_result(self):
        self.assertTrue(all(row["verificationStatus"] == "VERIFIED_RESULT" for row in self.payload["goldenValidation"]["expectedResults"]))

    def test_06_expected_results_are_not_inputs(self):
        expected = {row["canonicalField"] for row in self.payload["goldenValidation"]["expectedResults"]}
        self.assertFalse(expected & set(self.payload["canonicalInputs"]))

    def test_07_exactly_four_unambiguous_rules(self):
        self.assertEqual(len(self.rules), 4)

    def test_08_all_rules_are_v1(self):
        self.assertEqual({row.version for row in self.rules}, {"V1.0"})

    def test_09_all_rules_are_released(self):
        self.assertEqual({row.status for row in self.rules}, {"released"})

    def test_10_rule_source_evidence_is_verified(self):
        self.assertTrue(all(row.specification["sourceEvidence"]["verificationStatus"] == "VERIFIED_SOURCE" for row in self.rules))

    def test_11_true_dag_dependencies(self):
        self.assertEqual(self.rules[2].specification["dependencies"], ["G1-CASING-HEIGHT"])
        self.assertEqual(self.rules[3].specification["dependencies"], ["G1-CASING-WIDTH"])

    def test_12_exact_values(self):
        result = self.execute()["calculation"]
        actual = {row["canonicalField"]: row["value"]["decimal"] for row in result["derivedFacts"]}
        self.assertEqual(actual, {"casing_height": "2035", "casing_width": "918", "door_height": "2002", "door_width": "866"})

    def test_13_all_outputs_use_formal_mm(self):
        self.assertEqual({row["uomCode"] for row in self.execute()["calculation"]["derivedFacts"]}, {"mm"})

    def test_14_golden_overall_pass(self):
        comparison = self.execute()["calculation"]["trace"]["goldenComparison"]
        self.assertEqual(comparison["result"], "PASS")

    def test_15_each_difference_is_exact_zero(self):
        rows = self.execute()["calculation"]["trace"]["goldenComparison"]["rows"]
        self.assertEqual({row["difference"] for row in rows}, {"0"})

    def test_16_comparison_declares_no_expected_input(self):
        comparison = self.execute()["calculation"]["trace"]["goldenComparison"]
        self.assertFalse(comparison["expectedResultsUsedAsInputs"])

    def test_17_four_execution_details(self):
        self.assertEqual(len(self.execute()["calculation"]["details"]), 4)

    def test_18_four_derived_facts(self):
        self.assertEqual(len(self.execute()["calculation"]["derivedFacts"]), 4)

    def test_19_execution_order_is_stable(self):
        order = self.execute()["calculation"]["trace"]["executionOrder"]
        self.assertEqual(order, ["G1-CASING-HEIGHT", "G1-CASING-WIDTH", "G1-DOOR-HEIGHT", "G1-DOOR-WIDTH"])

    def test_20_idempotent_repeat_creates_no_duplicate(self):
        first = self.execute()
        second = self.execute()
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(first["calculation"]["id"], second["calculation"]["id"])
        self.assertEqual(EngineeringCalculationRecord.objects.count(), 1)

    def test_21_missing_input_creates_failed_calculation_without_facts(self):
        payload = deepcopy(self.payload)
        del payload["canonicalInputs"]["opening_height"]
        source = EngineeringSourceRecord.objects.create(
            company=self.company, source_no="G1-MISSING", source_name="G1缺项验证",
            source_type="controlled_import", source_version="V1.0", source_payload=payload,
            content_hash="a" * 64, status="confirmed",
        )
        result = self.execute(source_record_id=source.pk, rule_ids=[self.rules[0].pk])
        self.assertEqual(result["calculation"]["status"], "failed")
        self.assertEqual(result["calculation"]["errorCode"], "UNKNOWN_VARIABLE")
        self.assertEqual(len(result["calculation"]["derivedFacts"]), 0)

    def test_22_denied_account_is_rejected(self):
        with self.assertRaises(EngineeringCalculationError) as context:
            self.execute(user=self.denied)
        self.assertIn(context.exception.code, {"PERMISSION_DENIED", "SCOPE_DENIED"})

    def test_23_execute_audit_exists(self):
        result = self.execute()
        self.assertTrue(OrganizationOperatingAuditRecord.objects.filter(pk=result["auditId"], action_code="production.engineering.calculation.execute").exists())

    def test_24_execution_chain_is_complete(self):
        chain = self.execute()["executionChain"]
        self.assertEqual((chain["account"], chain["employeeNo"], chain["positionCode"], chain["responsibilityCode"]), ("do4_planner", "DO4-E001", "DO4-PLAN", "RESP_DO4_GOLDEN"))

    def test_25_readback_is_server_and_localstorage_zero(self):
        row = self.execute()["calculation"]
        self.assertEqual((row["factSource"], row["localStorageFormalFactCount"]), ("server", 0))

    def test_26_no_breakdown_or_downstream_requirement(self):
        self.execute()
        self.assertEqual(EngineeringBreakdownItem.objects.count(), 0)

    def test_27_zero_business_transactions(self):
        before = (SalesOrder.objects.count(), Demand.objects.count(), PlanningRequirement.objects.count(), PurchasePlan.objects.count(), ProductionPlan.objects.count(), InventoryBalance.objects.count(), InventoryTransaction.objects.count())
        self.execute()
        after = (SalesOrder.objects.count(), Demand.objects.count(), PlanningRequirement.objects.count(), PurchasePlan.objects.count(), ProductionPlan.objects.count(), InventoryBalance.objects.count(), InventoryTransaction.objects.count())
        self.assertEqual(before, after)

    def test_28_golden_value_mismatch_is_fail_not_tolerance(self):
        payload = deepcopy(self.payload)
        payload["goldenValidation"]["expectedResults"][0]["value"] = "2035.0001"
        source = EngineeringSourceRecord.objects.create(
            company=self.company, source_no="G1-MISMATCH", source_name="G1精准差异验证",
            source_type="controlled_import", source_version="V1.0", source_payload=payload,
            content_hash="b" * 64, status="confirmed",
        )
        result = self.execute(source_record_id=source.pk)["calculation"]["trace"]["goldenComparison"]
        self.assertEqual(result["result"], "FAIL")
        self.assertEqual(result["rows"][0]["difference"], "-0.0001")

    def test_29_rule_first_version_is_system_generated(self):
        payload = {
            "rule_code": "G1-AUTO-VERSION", "rule_name": "首版治理验证", "rule_kind": "formula",
            "specification": rule_spec("G1-AUTO-VERSION", "x - 1", "x", "y", "TEST", "x-1"),
            "reason": "DO-4首版治理验证",
        }
        row = ProductionFoundationService.save("engineering-rule-definitions", user=self.user, payload=payload)["row"]
        self.assertEqual(row["version"], "V1.0")

    def test_30_api_detail_readback_contains_golden_comparison(self):
        calculation_id = self.execute()["calculation"]["id"]
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(reverse("pde-engineering-calculation-detail", kwargs={"object_id": calculation_id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["calculation"]["trace"]["goldenComparison"]["result"], "PASS")

    def test_31_nullable_blank_date_is_saved_as_null(self):
        payload = {
            "source_name": "空日期规范化验证", "source_type": "controlled_import",
            "source_version": "V1.0", "source_payload": {"validationClass": "GOLDEN"},
            "content_hash": "c" * 64, "effective_date": "", "reason": "DO-4空日期兼容验证",
        }
        row = ProductionFoundationService.save(
            "engineering-source-records", user=self.user, payload=payload,
        )["row"]
        self.assertIsNone(row["effective_date"])
