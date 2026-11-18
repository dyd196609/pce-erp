from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from masterdata.models import CodeRule, Material, UnitOfMeasure
from pfm.models import Employee
from planning.models import Demand, PlanningRequirement, ProductionPlan, PurchasePlan
from procurement.models import InventoryBalance, InventoryTransaction
from sales.models import (
    Customer,
    SalesOrder,
    SalesOrderItem,
    SalesOrderItemEngineeringAttribute,
)
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Permission,
    Position,
    PositionResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)

from .engineering_calculation_service import (
    EngineeringCalculationError,
    EngineeringCalculationService,
)
from .models import (
    EngineeringCalculationDetail,
    EngineeringCalculationRecord,
    EngineeringDerivedFact,
    EngineeringRuleDefinition,
    EngineeringSourceRecord,
    OrderEngineeringInstance,
    ProductBOM,
    ProductCategory,
    ProductDefinition,
    ProductVersion,
    Routing,
)
from .production_foundation_service import ProductionFoundationError, ProductionFoundationService


def contract(name, source_type="ENGINEERING_INPUT", dimension="count"):
    return {
        "canonicalName": name,
        "valueType": "decimal",
        "unitDimension": dimension,
        "unitRequired": False,
        "required": True,
        "sourceType": source_type,
        "description": name,
    }


def spec(
    *, code="RULE_A", expression="x + y", inputs=None, output="a",
    dependencies=None, package="ABSTRACT_CALC", version="V1.0",
    output_dimension="count", unit="PCS", priority=100,
):
    return {
        "description": "DO-3抽象计算测试规则",
        "rulePackage": {"code": package, "version": version},
        "expression": expression,
        "inputs": inputs or [contract("x"), contract("y")],
        "outputs": [{
            "canonicalName": output,
            "valueType": "decimal",
            "unitDimension": output_dimension,
            "unit": unit,
            "resultDomain": "DERIVED_FACT",
            "description": output,
        }],
        "dependencies": dependencies or [],
        "applicability": {"scope": "validation"},
        "decimalPrecision": 18,
        "outputScale": 2,
        "roundingMode": "ROUND_HALF_UP",
        "priority": priority,
        "sourceEvidence": {"reference": "DO-3 controlled abstract test"},
    }


class EngineeringCalculationClosureDO3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="DO3", name="DO-3验收公司")
        cls.department = Department.objects.create(
            code="DO3-ENG", name="工程技术部", company=cls.company,
        )
        cls.position = Position.objects.create(
            code="DO3-ENGINEER", name="工程计算岗", company=cls.company,
            department=cls.department,
        )
        cls.responsibility = Responsibility.objects.create(
            code="RESP_DO3_CALC", name="工程计算执行",
            status="ACTIVE", is_active=True,
        )
        PositionResponsibility.objects.create(
            position=cls.position, responsibility=cls.responsibility,
            is_primary=True, active=True,
        )
        cls.user = User.objects.create_user(
            username="do3_engineer", password="test-only", real_name="DO-3工程员",
            company_id=cls.company.pk,
        )
        Employee.objects.create(
            user=cls.user, employee_no="DO3-E001", full_name="DO-3工程员",
            department_ref=cls.department, position_ref=cls.position, status="active",
        )
        cls.role = Role.objects.create(code="DO3_CALC_ROLE", name="DO-3工程计算角色")
        for code in (
            "production.engineering.calculation.view",
            "production.engineering.calculation.execute",
        ):
            RolePermission.objects.create(
                role=cls.role, permission=Permission.objects.get(code=code),
            )
        UserRoleScopeAssignment.objects.create(
            user=cls.user, role=cls.role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, business_hash="do3-authorized",
        )
        cls.denied_user = User.objects.create_user(
            username="do3_denied", password="test-only", real_name="无工程计算权限",
            company_id=cls.company.pk,
        )
        Employee.objects.create(
            user=cls.denied_user, employee_no="DO3-E002", full_name="无工程计算权限",
            department_ref=cls.department, position_ref=cls.position, status="active",
        )
        denied_role = Role.objects.create(code="DO3_DENIED_ROLE", name="无工程计算权限角色")
        UserRoleScopeAssignment.objects.create(
            user=cls.denied_user, role=denied_role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, business_hash="do3-denied",
        )
        CodeRule.objects.create(
            company_id=cls.company.pk,
            entity_type="production_engineering_calculation",
            prefix="EC-DO3-", date_format="", seq_length=4, current_seq=0,
        )
        cls.pcs = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="PCS", name="件", decimal_places=2,
        )
        cls.kg = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="KG", name="千克", decimal_places=3,
        )
        cls.source = EngineeringSourceRecord.objects.create(
            company=cls.company, source_no="VAL-DO3", source_name="受控抽象验证来源",
            source_type="manual_confirmed", source_version="V1.0",
            source_payload={"canonicalInputs": {"x": "10", "y": "2"}},
            content_hash="1" * 64, status="confirmed",
        )
        cls.rule_a = EngineeringRuleDefinition.objects.create(
            company=cls.company, rule_code="RULE_A", rule_name="抽象加法",
            version="V1.0", rule_kind="formula", specification=spec(), status="released",
        )
        cls.rule_b = EngineeringRuleDefinition.objects.create(
            company=cls.company, rule_code="RULE_B", rule_name="抽象乘法",
            version="V1.0", rule_kind="formula",
            specification=spec(
                code="RULE_B", expression="a * 2",
                inputs=[contract("a", "ENGINEERING_DERIVED")], output="b",
                dependencies=["RULE_A"], priority=1,
            ),
            status="released",
        )
        cls.fail_rule = EngineeringRuleDefinition.objects.create(
            company=cls.company, rule_code="RULE_FAIL", rule_name="除零失败规则",
            version="V1.0", rule_kind="formula",
            specification=spec(
                code="RULE_FAIL", expression="x / zero",
                inputs=[contract("x"), contract("zero")], output="invalid_result",
                package="FAILURE_PACKAGE",
            ),
            status="released",
        )
        cls.weight_rule = EngineeringRuleDefinition.objects.create(
            company=cls.company, rule_code="WEIGHT_RULE", rule_name="理论重量",
            version="V1.0", rule_kind="formula",
            specification=spec(
                code="WEIGHT_RULE", expression="length * unit_weight",
                inputs=[
                    contract("length", dimension="length"),
                    contract("unit_weight", "MASTER_DATA", "mass_per_length"),
                ],
                output="theoretical_weight", package="GENERAL_METAL",
                output_dimension="mass", unit="KG",
            ),
            status="released",
        )

        cls.material = Material.objects.create(
            company_id=cls.company.pk, code="DO3-FG", name="按单工程测试物料",
            unit="件", base_uom=cls.pcs, material_type="finished",
            is_purchased=False, is_produced=True,
        )
        cls.category = ProductCategory.objects.create(
            company=cls.company, code="DO3-CAT", name="行业中立按单产品",
            industry_type="general",
        )
        cls.product = ProductDefinition.objects.create(
            company=cls.company, category=cls.category, material=cls.material,
            product_code="DO3-P", product_name="按单工程产品",
            emd_material_code=cls.material.code,
            manufacturing_definition_mode="order_engineered",
        )
        cls.product_version = ProductVersion.objects.create(
            product=cls.product, version_no="V1.0",
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="DO3-CUSTOMER", name="DO-3测试客户",
        )
        cls.order = SalesOrder(
            company=cls.company, department=cls.department, customer=cls.customer,
            order_no="SO-DO3", order_date=date.today(),
            required_delivery_date=date.today() + timedelta(days=7),
            status="confirmed", created_by=cls.user,
        )
        cls.order._business_state_initialization_authorized = True
        cls.order.save()
        cls.order_item = SalesOrderItem.objects.create(
            sales_order=cls.order, line_no=1, material=cls.material,
            product_definition=cls.product, quantity="1", uom=cls.pcs,
            required_date=cls.order.required_delivery_date,
        )
        for sequence, (name, value) in enumerate((("x", "10"), ("y", "2")), 1):
            SalesOrderItemEngineeringAttribute.objects.create(
                sales_order_item=cls.order_item, sequence=sequence,
                raw_source="DO-3 order input", raw_field=name, raw_value=value,
                canonical_field=name, normalized_value=value,
                value_type="decimal", unit=cls.pcs,
                source_type="ENGINEERING_INPUT", created_by=cls.user,
            )
        cls.order_source = EngineeringSourceRecord.objects.create(
            company=cls.company, source_no="ORDER-DO3", source_name="订单工程来源",
            source_type="order_input", source_version="V1.0",
            source_payload={"salesOrderItemId": cls.order_item.pk},
            content_hash="2" * 64, status="confirmed",
        )
        cls.order_instance = OrderEngineeringInstance.objects.create(
            company=cls.company, instance_no="OEI-DO3",
            sales_order_item=cls.order_item, product=cls.product,
            baseline_product_version=cls.product_version,
            source_record=cls.order_source, status="source_confirmed",
        )

    def execute_validation(self, *, inputs=None, rules=None, source=None):
        return EngineeringCalculationService.execute(
            user=self.user,
            scope="validation",
            source_record_id=(source or self.source).pk,
            rule_ids=[rule.pk for rule in (rules or [self.rule_b, self.rule_a])],
            canonical_inputs=inputs or {"x": "10", "y": "2"},
            reason="DO-3抽象验证",
        )

    def test_01_existing_calculation_and_derived_fact_models_are_reused(self):
        self.assertEqual(EngineeringCalculationRecord._meta.db_table, "pde_engineering_calculation_record")
        self.assertEqual(EngineeringDerivedFact._meta.db_table, "pde_engineering_derived_fact")

    def test_02_only_approved_detail_model_is_added(self):
        self.assertEqual(EngineeringCalculationDetail._meta.db_table, "pde_engineering_calculation_detail")

    def test_03_validation_calculation_is_persisted(self):
        result = self.execute_validation()
        calculation = EngineeringCalculationRecord.objects.get(pk=result["calculation"]["id"])
        self.assertEqual(calculation.scope, "validation")
        self.assertEqual(calculation.status, "completed")

    def test_04_validation_is_isolated_from_order_context(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        self.assertIsNone(calculation.sales_order_item_id)
        self.assertIsNone(calculation.engineering_instance_id)
        self.assertEqual(calculation.source_record_id, self.source.pk)

    def test_05_order_engineering_requires_complete_context(self):
        with self.assertRaises(EngineeringCalculationError) as caught:
            EngineeringCalculationService.execute(
                user=self.user, scope="order_engineering",
                source_record_id=self.order_source.pk,
                rule_ids=[self.rule_a.pk],
            )
        self.assertEqual(caught.exception.code, "ORDER_ENGINEERING_CONTEXT_REQUIRED")

    def test_06_validation_rejects_order_context(self):
        with self.assertRaises(EngineeringCalculationError) as caught:
            EngineeringCalculationService.execute(
                user=self.user, scope="validation", source_record_id=self.source.pk,
                rule_ids=[self.rule_a.pk], canonical_inputs={"x": "10", "y": "2"},
                sales_order_item_id=self.order_item.pk,
            )
        self.assertEqual(caught.exception.code, "VALIDATION_CONTEXT_INVALID")

    def test_07_order_engineering_reads_do1_canonical_attributes(self):
        result = EngineeringCalculationService.execute(
            user=self.user, scope="order_engineering",
            source_record_id=self.order_source.pk,
            rule_ids=[self.rule_b.pk, self.rule_a.pk],
            sales_order_item_id=self.order_item.pk,
            engineering_instance_id=self.order_instance.pk,
            reason="订单工程抽象闭环",
        )
        calculation = EngineeringCalculationRecord.objects.get(pk=result["calculation"]["id"])
        self.assertEqual(calculation.sales_order_item_id, self.order_item.pk)
        self.assertEqual(calculation.trace["canonicalInputSnapshot"]["x"]["value"], "10")

    def test_08_one_calculation_executes_multiple_rules(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        self.assertEqual(calculation.details.count(), 2)

    def test_09_calculation_detail_sequence_is_stable(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        self.assertEqual(
            list(calculation.details.values_list("sequence", "rule_code")),
            [(1, "RULE_A"), (2, "RULE_B")],
        )

    def test_10_intermediate_result_becomes_next_rule_input(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        second = calculation.details.get(sequence=2)
        self.assertEqual(second.input_snapshot["a"]["value"], "12.00")
        self.assertEqual(second.output_value, {"decimal": "24.00"})

    def test_11_derived_facts_are_generated_for_successful_steps(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        self.assertEqual(
            list(calculation.derived_facts.values_list("canonical_field", flat=True)),
            ["a", "b"],
        )

    def test_12_decimal_values_are_never_stored_as_float(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        self.assertEqual(calculation.derived_facts.get(canonical_field="b").value, {"decimal": "24.00"})

    def test_13_uom_is_persisted_on_detail_and_fact(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        self.assertTrue(all(row.uom_id == self.pcs.pk for row in calculation.details.all()))
        self.assertTrue(all(row.uom_id == self.pcs.pk for row in calculation.derived_facts.all()))

    def test_14_rule_version_snapshot_is_frozen(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        self.assertEqual(list(calculation.details.values_list("rule_version", flat=True)), ["V1.0", "V1.0"])

    def test_15_expression_snapshot_is_frozen(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        self.assertEqual(calculation.details.get(sequence=1).expression_snapshot, "x + y")

    def test_16_input_snapshot_preserves_source_and_canonical_values(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        self.assertEqual(calculation.trace["inputSnapshot"], self.source.source_payload)
        self.assertEqual(calculation.trace["canonicalInputSnapshot"], {"x": "10", "y": "2"})

    def test_17_rule_graph_snapshot_and_hash_are_frozen(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        self.assertEqual(len(calculation.trace["ruleGraphSnapshot"]), 2)
        self.assertEqual(len(calculation.rule_graph_hash), 64)

    def test_18_execution_order_is_stable_despite_reverse_input_ids(self):
        calculation = EngineeringCalculationRecord.objects.get(pk=self.execute_validation()["calculation"]["id"])
        self.assertEqual(calculation.trace["executionOrder"], ["RULE_A", "RULE_B"])

    def test_19_identical_execution_returns_existing_calculation(self):
        first = self.execute_validation()
        second = self.execute_validation()
        self.assertTrue(second["idempotent"])
        self.assertEqual(first["calculation"]["id"], second["calculation"]["id"])

    def test_20_replay_creates_no_duplicate_details_or_facts(self):
        self.execute_validation()
        self.execute_validation()
        self.assertEqual(EngineeringCalculationRecord.objects.count(), 1)
        self.assertEqual(EngineeringCalculationDetail.objects.count(), 2)
        self.assertEqual(EngineeringDerivedFact.objects.count(), 2)

    def test_21_input_change_creates_new_revision(self):
        first = self.execute_validation()
        second = self.execute_validation(inputs={"x": "11", "y": "2"})
        self.assertNotEqual(first["calculation"]["id"], second["calculation"]["id"])
        self.assertEqual(second["calculation"]["revision"], 2)
        self.assertEqual(second["calculation"]["supersedesId"], first["calculation"]["id"])

    def test_22_rule_version_change_creates_new_calculation(self):
        first = self.execute_validation(rules=[self.rule_a])
        next_spec = deepcopy(self.rule_a.specification)
        next_spec["rulePackage"]["version"] = "V1.1"
        replacement = EngineeringRuleDefinition.objects.create(
            company=self.company, rule_code="RULE_A", rule_name="抽象加法",
            version="V1.1", rule_kind="formula", specification=next_spec, status="released",
        )
        second = self.execute_validation(rules=[replacement])
        self.assertNotEqual(first["calculation"]["id"], second["calculation"]["id"])
        self.assertEqual(second["calculation"]["ruleSetVersion"], "ABSTRACT_CALC@V1.1")

    def test_23_successful_revision_supersedes_but_does_not_delete_history(self):
        first = self.execute_validation()
        self.execute_validation(inputs={"x": "12", "y": "2"})
        old = EngineeringCalculationRecord.objects.get(pk=first["calculation"]["id"])
        self.assertEqual(old.status, "superseded")
        self.assertEqual(old.details.count(), 2)
        self.assertTrue(all(row.status == "superseded" for row in old.derived_facts.all()))

    def test_24_failed_rule_marks_calculation_failed(self):
        result = self.execute_validation(
            rules=[self.fail_rule], inputs={"x": "10", "zero": "0"},
        )
        self.assertEqual(result["calculation"]["status"], "failed")
        self.assertEqual(result["calculation"]["errorCode"], "DIVISION_BY_ZERO")

    def test_25_failed_detail_preserves_error_trace(self):
        result = self.execute_validation(
            rules=[self.fail_rule], inputs={"x": "10", "zero": "0"},
        )
        detail = EngineeringCalculationDetail.objects.get(calculation_id=result["calculation"]["id"])
        self.assertEqual(detail.status, "failed")
        self.assertEqual(detail.error_code, "DIVISION_BY_ZERO")
        self.assertIsNone(detail.output_value)

    def test_26_failed_calculation_creates_no_success_derived_fact(self):
        result = self.execute_validation(
            rules=[self.fail_rule], inputs={"x": "10", "zero": "0"},
        )
        self.assertFalse(EngineeringDerivedFact.objects.filter(calculation_id=result["calculation"]["id"]).exists())

    def test_27_authorization_allowed_is_recorded(self):
        result = self.execute_validation()
        self.assertTrue(result["authorization"]["allowed"])
        self.assertEqual(result["authorization"]["actionCode"], "production.engineering.calculation.execute")

    def test_28_authorization_denied_creates_no_calculation(self):
        with self.assertRaises(EngineeringCalculationError) as caught:
            EngineeringCalculationService.execute(
                user=self.denied_user, scope="validation", source_record_id=self.source.pk,
                rule_ids=[self.rule_a.pk], canonical_inputs={"x": "10", "y": "2"},
            )
        self.assertEqual(caught.exception.code, "PERMISSION_DENIED")
        self.assertEqual(EngineeringCalculationRecord.objects.count(), 0)
        denied_audit = OrganizationOperatingAuditRecord.objects.get(
            pk=caught.exception.details["auditId"],
        )
        self.assertEqual(denied_audit.after_snapshot["decision"], "DENIED")

    def test_29_audit_contains_identity_hashes_decision_and_chain(self):
        result = self.execute_validation()
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"])
        state = audit.after_snapshot["state"]
        self.assertEqual(audit.action_code, "production.engineering.calculation.execute")
        self.assertEqual(state["input_hash"], result["calculation"]["inputHash"])
        self.assertEqual(state["rule_graph_hash"], result["calculation"]["ruleGraphHash"])
        self.assertEqual(state["decision"], "SUCCEEDED")
        self.assertEqual(audit.after_snapshot["executionChain"]["employeeNo"], "DO3-E001")

    def test_30_validation_creates_no_manufacturing_or_planning_downstream(self):
        before = {
            "demand": Demand.objects.count(),
            "requirement": PlanningRequirement.objects.count(),
            "purchasePlan": PurchasePlan.objects.count(),
            "productionPlan": ProductionPlan.objects.count(),
            "inventoryBalance": InventoryBalance.objects.count(),
            "inventoryTransaction": InventoryTransaction.objects.count(),
            "bom": ProductBOM.objects.count(),
            "routing": Routing.objects.count(),
        }
        self.execute_validation()
        after = {
            "demand": Demand.objects.count(),
            "requirement": PlanningRequirement.objects.count(),
            "purchasePlan": PurchasePlan.objects.count(),
            "productionPlan": ProductionPlan.objects.count(),
            "inventoryBalance": InventoryBalance.objects.count(),
            "inventoryTransaction": InventoryTransaction.objects.count(),
            "bom": ProductBOM.objects.count(),
            "routing": Routing.objects.count(),
        }
        self.assertEqual(before, after)

    def test_31_order_engineering_cannot_omit_sales_order_item(self):
        with self.assertRaises(EngineeringCalculationError) as caught:
            EngineeringCalculationService.execute(
                user=self.user, scope="order_engineering",
                source_record_id=self.order_source.pk,
                rule_ids=[self.rule_a.pk], engineering_instance_id=self.order_instance.pk,
            )
        self.assertEqual(caught.exception.code, "ORDER_ENGINEERING_CONTEXT_REQUIRED")

    def test_32_multi_industry_weight_calculation_is_neutral(self):
        result = self.execute_validation(
            rules=[self.weight_rule],
            inputs={"length": "10", "unit_weight": "2.5"},
        )
        fact = EngineeringDerivedFact.objects.get(calculation_id=result["calculation"]["id"])
        self.assertEqual(fact.canonical_field, "theoretical_weight")
        self.assertEqual(fact.value, {"decimal": "25.00"})
        self.assertEqual(fact.uom_id, self.kg.pk)

    def test_33_legacy_calculation_without_do3_fields_remains_readable(self):
        legacy = EngineeringCalculationRecord.objects.create(
            engineering_instance=self.order_instance,
            calculation_no="LEGACY-CALC", rule_set_version="V1",
            trace={"legacy": True},
        )
        self.assertEqual(EngineeringCalculationRecord.objects.get(pk=legacy.pk).trace, {"legacy": True})

    def test_34_calculation_trace_page_uses_server_not_localstorage(self):
        page = Path(settings.BASE_DIR).parent / "frontend" / "src" / "meta" / "pages" / "ProductionFoundationA1Page.vue"
        content = page.read_text(encoding="utf-8")
        self.assertIn("Engineering Calculation Trace", content)
        self.assertNotIn("localStorage.", content)

    def test_35_api_reads_calculation_detail_and_derived_facts(self):
        result = self.execute_validation()
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(reverse(
            "pde-engineering-calculation-detail",
            kwargs={"object_id": result["calculation"]["id"]},
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["calculation"]["details"]), 2)
        self.assertEqual(len(response.data["calculation"]["derivedFacts"]), 2)

    def test_36_api_execution_and_idempotent_replay(self):
        client = APIClient()
        client.force_authenticate(self.user)
        payload = {
            "scope": "validation", "sourceRecordId": self.source.pk,
            "ruleIds": [self.rule_b.pk, self.rule_a.pk],
            "canonicalInputs": {"x": "10", "y": "2"},
            "reason": "API DO-3验证",
        }
        first = client.post(reverse("pde-engineering-calculation-execute"), payload, format="json")
        second = client.post(reverse("pde-engineering-calculation-execute"), payload, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["idempotent"])

    def test_37_api_view_permission_denied(self):
        client = APIClient()
        client.force_authenticate(self.denied_user)
        response = client.get(reverse("pde-engineering-calculation-list"))
        self.assertEqual(response.status_code, 403)

    def test_38_generic_foundation_write_cannot_bypass_calculation_service(self):
        with self.assertRaises(ProductionFoundationError) as caught:
            ProductionFoundationService.save(
                "engineering-calculation-records", user=self.user,
                payload={"calculation_no": "BYPASS", "rule_set_version": "V1"},
            )
        self.assertEqual(caught.exception.code, "CALCULATION_EXECUTION_SERVICE_REQUIRED")

    def test_39_success_state_and_result_are_transactionally_complete(self):
        result = self.execute_validation()
        calculation = EngineeringCalculationRecord.objects.get(pk=result["calculation"]["id"])
        self.assertEqual(calculation.status, "completed")
        self.assertEqual(calculation.details.filter(status="succeeded").count(), 2)
        self.assertEqual(calculation.derived_facts.count(), 2)
        self.assertEqual(len(calculation.result_hash), 64)
