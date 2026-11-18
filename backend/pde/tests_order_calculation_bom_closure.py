from copy import deepcopy
from datetime import date, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from masterdata.models import CodeRule, Material, UnitOfMeasure
from pfm.models import Employee
from planning.models import Demand, PlanningRequirement, ProductionPlan, PurchasePlan
from procurement.models import InventoryBalance, InventoryTransaction
from sales.models import Customer, SalesOrder, SalesOrderItem, SalesOrderItemEngineeringAttribute
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment, Process,
)

from .engineering_calculation_service import (
    EngineeringCalculationError, EngineeringCalculationService,
    EngineeringMethodTrialService, OrderEngineeringClosureService,
)
from .manufacturing_structure_service import ManufacturingStructureError
from .models import (
    BOMItem, BOMItemSourceRequirement, BOMVersion, EngineeringCalculationRecord,
    EngineeringMaterialRequirement, EngineeringOperationRequirement,
    EngineeringRuleDefinition, EngineeringSourceRecord, ManufacturingApplicabilityScope,
    ManufacturingProcessType, OrderEngineeringInstance, ProductBOM, ProductCategory,
    ProductDefinition, ProductVersion, Routing, RoutingStep, RoutingVersion,
)
from .product_bom_detail_projection import (
    ProductBomDetailProjectionError,
    project_product_bom_material_detail,
)


def input_contract(name):
    return {
        "canonicalName": name, "valueType": "decimal", "unitDimension": "count",
        "unitRequired": False, "required": True, "sourceType": "ENGINEERING_INPUT",
        "description": name,
    }


def rule_spec(*, code, input_name, output_name, domain, unit="PCS", **metadata):
    output = {
        "canonicalName": output_name, "valueType": "decimal", "unitDimension": "count",
        "unit": unit, "resultDomain": domain, "description": output_name, **metadata,
    }
    return {
        "description": "订单工程闭环隔离测试规则",
        "rulePackage": {"code": "ORDER_BOM_CLOSURE", "version": "V1.0"},
        "expression": input_name, "inputs": [input_contract(input_name)],
        "outputs": [output], "dependencies": [],
        "applicability": {"scope": "order_engineering"},
        "decimalPrecision": 18, "outputScale": 6, "roundingMode": "ROUND_HALF_UP",
        "priority": 100, "sourceEvidence": {"reference": "isolated test only"},
    }


class OrderCalculationBomClosureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="OCB", name="订单核算隔离公司")
        cls.department = Department.objects.create(code="OCB-ENG", name="工程部", company=cls.company)
        cls.position = Position.objects.create(code="OCB-POS", name="工程核算岗", company=cls.company, department=cls.department)
        responsibility = Responsibility.objects.create(code="RESP_OCB", name="订单核算", status="ACTIVE", is_active=True)
        PositionResponsibility.objects.create(position=cls.position, responsibility=responsibility, is_primary=True, active=True)
        cls.user = User.objects.create_user(username="ocb_engineer", password="test", real_name="隔离工程员", company_id=cls.company.pk)
        Employee.objects.create(user=cls.user, employee_no="OCB-E1", full_name="隔离工程员", department_ref=cls.department, position_ref=cls.position, status="active")
        role = Role.objects.create(code="OCB_ROLE", name="订单核算与BOM草稿")
        for code in (
            "production.engineering.calculation.view",
            "production.engineering.calculation.execute",
            "production.master_data.bom.maintain",
        ):
            permission, _ = Permission.objects.get_or_create(
                code=code, defaults={"name": code, "module": "production"},
            )
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(user=cls.user, role=role, organization=cls.company, scope_code="ORGANIZATION", active=True, business_hash="ocb")
        CodeRule.objects.create(company_id=cls.company.pk, entity_type="production_engineering_calculation", prefix="EC-OCB-", date_format="", seq_length=4, current_seq=0)
        cls.pcs = UnitOfMeasure.objects.create(company_id=cls.company.pk, code="PCS", name="件", dimension="count", decimal_places=6)
        cls.finished = Material.objects.create(company_id=cls.company.pk, code="OCB-FG", name="按单成品", unit="件", base_uom=cls.pcs, material_type="finished", is_produced=True)
        cls.component = Material.objects.create(company_id=cls.company.pk, code="OCB-RM", name="正式组件", unit="件", base_uom=cls.pcs, material_type="raw", is_purchased=True)
        cls.operation = Process.objects.create(company=cls.company, code="CUT", name="开料", calculation_basis="count", calculation_uom=cls.pcs)
        cls.category = ProductCategory.objects.create(company=cls.company, code="OCB-CAT", name="按单产品", industry_type="general")
        cls.product = ProductDefinition.objects.create(company=cls.company, category=cls.category, material=cls.finished, product_code="OCB-P", product_name="按单工程产品", emd_material_code=cls.finished.code, manufacturing_definition_mode="order_engineered")
        cls.product_version = ProductVersion.objects.create(product=cls.product, version_no="V1")
        cls.customer = Customer.objects.create(company=cls.company, code="OCB-C", name="测试客户")
        cls.order = SalesOrder(
            company=cls.company,
            department=cls.department,
            customer=cls.customer,
            order_no="SO-OCB",
            order_date=date.today(),
            required_delivery_date=date.today() + timedelta(days=7),
            status="engineering",
            business_purpose=SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION,
            created_by=cls.user,
        )
        cls.order._business_state_initialization_authorized = True
        cls.order.save()
        cls.item = SalesOrderItem.objects.create(sales_order=cls.order, line_no=1, material=cls.finished, product_definition=cls.product, product_version=cls.product_version, engineering_mode="ORDER_ENGINEERED", quantity="3", uom=cls.pcs, required_date=cls.order.required_delivery_date)
        for sequence, (name, value) in enumerate((("unit_need", "2"), ("total_need", "1"), ("workload", "4")), 1):
            SalesOrderItemEngineeringAttribute.objects.create(sales_order_item=cls.item, sequence=sequence, raw_source="isolated", raw_field=name, raw_value=value, canonical_field=name, normalized_value=value, value_type="decimal", unit=cls.pcs, source_type="ENGINEERING_INPUT", created_by=cls.user)
        cls.source = EngineeringSourceRecord.objects.create(company=cls.company, source_no="OCB-SRC", source_name="订单工程来源", source_type="order_input", source_version="V1", source_payload={"salesOrderItemId": cls.item.pk}, content_hash="a" * 64, status="confirmed")
        cls.instance = OrderEngineeringInstance.objects.create(company=cls.company, instance_no="OEI-OCB", sales_order_item=cls.item, product=cls.product, baseline_product_version=cls.product_version, source_record=cls.source, status="source_confirmed")
        cls.rules = [
            EngineeringRuleDefinition.objects.create(company=cls.company, rule_code="MAT-PER", rule_name="单位物料", version="V1", rule_kind="formula", status="released", specification=rule_spec(code="MAT-PER", input_name="unit_need", output_name="component_per_unit", domain="MATERIAL_REQUIREMENT", materialId=cls.component.pk, quantityBasis="PER_SALES_ITEM_UNIT", itemRole="component", requirementType="manufacturing", supplyType="BUY")),
            EngineeringRuleDefinition.objects.create(company=cls.company, rule_code="MAT-TOTAL", rule_name="订单总量物料", version="V1", rule_kind="formula", status="released", specification=rule_spec(code="MAT-TOTAL", input_name="total_need", output_name="component_order_total", domain="MATERIAL_REQUIREMENT", materialId=cls.component.pk, quantityBasis="ORDER_TOTAL", itemRole="component", requirementType="manufacturing", supplyType="BUY")),
            EngineeringRuleDefinition.objects.create(company=cls.company, rule_code="OP-WORK", rule_name="工序作业量", version="V1", rule_kind="formula", status="released", specification=rule_spec(code="OP-WORK", input_name="workload", output_name="cut_workload", domain="OPERATION_REQUIREMENT", operationId=cls.operation.pk)),
        ]

    def execute(self):
        return EngineeringCalculationService.execute(user=self.user, scope="order_engineering", source_record_id=self.source.pk, rule_ids=[row.pk for row in self.rules], sales_order_item_id=self.item.pk, engineering_instance_id=self.instance.pk, reason="isolated closure test")

    def test_validation_is_explicit_and_read_only(self):
        before = EngineeringCalculationRecord.objects.count()
        result = OrderEngineeringClosureService.validate(user=self.user, sales_order_item_id=self.item.pk, engineering_instance_id=self.instance.pk, source_record_id=self.source.pk, rule_ids=[row.pk for row in self.rules])
        self.assertTrue(result["ready"])
        self.assertEqual(result["businessWriteSideEffectCount"], 0)
        self.assertEqual(EngineeringCalculationRecord.objects.count(), before)

    def test_quantity_basis_is_applied_exactly_once_and_requirements_persist(self):
        result = self.execute()
        calculation = EngineeringCalculationRecord.objects.get(pk=result["calculation"]["id"])
        self.assertEqual(list(calculation.material_requirements.values_list("net_quantity", flat=True)), [6, 1])
        self.assertEqual(calculation.material_requirements.filter(scrap_rate__isnull=True, gross_quantity__isnull=True, scrap_rate_status="not_maintained").count(), 2)
        self.assertEqual(EngineeringOperationRequirement.objects.get(calculation=calculation).workload_quantity, 4)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, "calculated")

    def test_calculation_and_bom_generation_are_idempotent(self):
        first = self.execute()
        second = self.execute()
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        calculation_id = first["calculation"]["id"]
        preview = OrderEngineeringClosureService.preview_bom(user=self.user, calculation_id=calculation_id)
        self.assertEqual(preview["businessWriteSideEffectCount"], 0)
        self.assertEqual(preview["rows"][0]["quantity"], "7.000000")
        generated = OrderEngineeringClosureService.generate_bom(user=self.user, calculation_id=calculation_id, preview_hash=preview["previewHash"])
        repeated = OrderEngineeringClosureService.generate_bom(user=self.user, calculation_id=calculation_id, preview_hash=preview["previewHash"])
        self.assertFalse(generated["idempotent"])
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(ProductBOM.objects.count(), 1)
        self.assertEqual(BOMVersion.objects.count(), 1)
        self.assertEqual(BOMItem.objects.get().quantity, 7)
        self.assertEqual(BOMItemSourceRequirement.objects.count(), 2)

    def test_stale_preview_and_mid_transaction_failure_leave_no_partial_bom(self):
        calculation_id = self.execute()["calculation"]["id"]
        with self.assertRaises(EngineeringCalculationError) as stale:
            OrderEngineeringClosureService.generate_bom(user=self.user, calculation_id=calculation_id, preview_hash="0" * 64)
        self.assertEqual(stale.exception.code, "STALE_BOM_PREVIEW")
        self.assertEqual(ProductBOM.objects.count(), 0)
        preview = OrderEngineeringClosureService.preview_bom(user=self.user, calculation_id=calculation_id)
        with patch.object(BOMItemSourceRequirement, "full_clean", side_effect=ValidationError("forced rollback")):
            with self.assertRaises(ValidationError):
                OrderEngineeringClosureService.generate_bom(user=self.user, calculation_id=calculation_id, preview_hash=preview["previewHash"])
        self.assertEqual(ProductBOM.objects.count(), 0)
        self.assertEqual(BOMVersion.objects.count(), 0)
        self.assertEqual(BOMItem.objects.count(), 0)

    def test_multi_line_mismatch_is_blocked_and_downstream_domains_stay_empty(self):
        other = SalesOrderItem.objects.create(sales_order=self.order, line_no=2, material=self.finished, product_definition=self.product, product_version=self.product_version, engineering_mode="ORDER_ENGINEERED", quantity="1", uom=self.pcs, required_date=self.order.required_delivery_date)
        result = OrderEngineeringClosureService.validate(user=self.user, sales_order_item_id=other.pk, engineering_instance_id=self.instance.pk, source_record_id=self.source.pk, rule_ids=[row.pk for row in self.rules])
        self.assertFalse(result["ready"])
        self.assertIn("ORDER_ENGINEERING_CONTEXT_MISMATCH", {row["code"] for row in result["blockers"]})
        self.execute()
        self.assertEqual(Routing.objects.count(), 0)
        self.assertEqual(Demand.objects.count(), 0)
        self.assertEqual(PlanningRequirement.objects.count(), 0)
        self.assertEqual(ProductionPlan.objects.count(), 0)
        self.assertEqual(PurchasePlan.objects.count(), 0)
        self.assertEqual(InventoryBalance.objects.count(), 0)
        self.assertEqual(InventoryTransaction.objects.count(), 0)

    def test_existing_bom_page_reads_generated_order_bom(self):
        calculation_id = self.execute()["calculation"]["id"]
        preview = OrderEngineeringClosureService.preview_bom(user=self.user, calculation_id=calculation_id)
        OrderEngineeringClosureService.generate_bom(user=self.user, calculation_id=calculation_id, preview_hash=preview["previewHash"])
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(reverse("pde-product-boms"), {"q": "SO-OCB"})
        self.assertEqual(response.status_code, 200)
        row = response.data["rows"][0]
        self.assertEqual(row["orderNo"], "SO-OCB")
        self.assertEqual(row["latestMaterialCount"], 1)
        self.assertEqual(row["sourceRequirementCount"], 2)
        self.assertEqual(len(row["bomMaterialDetails"]), 1)
        self.assertEqual(row["bomMaterialDetails"][0]["materialCode"], "OCB-RM")
        self.assertEqual(row["bomMaterialDetails"][0]["sourceRequirementCount"], 2)
        self.assertEqual(len(row["bomMaterialDetails"][0]["sourceRequirements"]), 2)
        self.assertEqual(row["sourceCalculationId"], calculation_id)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(action_code="production.master_data.bom.maintain").count(), 1)

    def test_bom_version_management_reuses_exact_formal_chain_read_only(self):
        calculation_id = self.execute()["calculation"]["id"]
        preview = OrderEngineeringClosureService.preview_bom(
            user=self.user, calculation_id=calculation_id,
        )
        generated = OrderEngineeringClosureService.generate_bom(
            user=self.user,
            calculation_id=calculation_id,
            preview_hash=preview["previewHash"],
        )
        bom = ProductBOM.objects.get(pk=generated["bomId"])
        version = BOMVersion.objects.get(pk=generated["bomVersionId"])
        calculation = EngineeringCalculationRecord.objects.get(pk=calculation_id)
        before = {
            "boms": ProductBOM.objects.count(),
            "versions": BOMVersion.objects.count(),
            "items": BOMItem.objects.count(),
            "links": BOMItemSourceRequirement.objects.count(),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
        }

        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(reverse("pde-bom-versions"), {"q": self.order.order_no})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["rows"]), 1)
        row = response.data["rows"][0]
        self.assertEqual(row["companyId"], self.company.pk)
        self.assertEqual(row["companyCode"], self.company.code)
        self.assertEqual(row["orderNo"], self.order.order_no)
        self.assertEqual(row["orderLineNo"], self.item.line_no)
        self.assertEqual(row["orderEngineeringInstanceId"], self.instance.pk)
        self.assertEqual(row["orderEngineeringInstanceNo"], self.instance.instance_no)
        self.assertEqual(row["productBomId"], bom.pk)
        self.assertEqual(row["bomCode"], bom.bom_code)
        self.assertEqual(row["bomVersionId"], version.pk)
        self.assertEqual(row["bomVersionNo"], version.bom_version)
        self.assertEqual(row["sourceCalculationId"], calculation.pk)
        self.assertEqual(row["sourceCalculationNo"], calculation.calculation_no)
        self.assertEqual(row["materialCount"], 1)
        self.assertEqual(row["sourceRequirementCount"], 2)
        self.assertEqual(row["sourceIntegrityLabel"], "1项物料 / 2条来源")
        self.assertEqual(row["identityCandidateCount"], 1)
        self.assertTrue(row["handoffAccepted"])
        self.assertEqual(row["handoffStatusLabel"], "已承接正式BOM版本")
        self.assertEqual(row["statusLabel"], "草稿")
        self.assertTrue(row["createdAt"])

        expected_handoff = response.data["bomVersionHandoffs"]
        self.assertEqual(expected_handoff[0]["productBomId"], bom.pk)
        self.assertEqual(expected_handoff[0]["bomVersionId"], version.pk)
        for surface in (
            "apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts",
        ):
            self.assertEqual(response.data[surface]["bomVersionHandoffs"], expected_handoff)
            self.assertEqual(response.data[surface]["formalHandoffCount"], 1)
            self.assertEqual(response.data[surface]["databaseBusinessWriteCount"], 0)

        after = {
            "boms": ProductBOM.objects.count(),
            "versions": BOMVersion.objects.count(),
            "items": BOMItem.objects.count(),
            "links": BOMItemSourceRequirement.objects.count(),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
        }
        self.assertEqual(after, before)

    def test_bom_version_management_fails_closed_on_relation_conflict(self):
        calculation_id = self.execute()["calculation"]["id"]
        preview = OrderEngineeringClosureService.preview_bom(
            user=self.user, calculation_id=calculation_id,
        )
        OrderEngineeringClosureService.generate_bom(
            user=self.user,
            calculation_id=calculation_id,
            preview_hash=preview["previewHash"],
        )
        client = APIClient()
        client.force_authenticate(self.user)
        with patch(
            "pde.views.project_product_bom_material_detail",
            side_effect=ProductBomDetailProjectionError("测试关系冲突"),
        ):
            response = client.get(reverse("pde-bom-versions"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["factLoadStatus"], "read_failed")
        self.assertEqual(
            response.data["error"]["code"],
            "BOM_VERSION_HANDOFF_SCOPE_INCONSISTENT",
        )
        self.assertIn("测试关系冲突", response.data["error"]["message"])
        self.assertIsNone(response.data["recordCount"])

    def _build_routing_management_handoff(self):
        calculation_id = self.execute()["calculation"]["id"]
        preview = OrderEngineeringClosureService.preview_bom(
            user=self.user, calculation_id=calculation_id,
        )
        generated = OrderEngineeringClosureService.generate_bom(
            user=self.user,
            calculation_id=calculation_id,
            preview_hash=preview["previewHash"],
        )
        process_type = ManufacturingProcessType.objects.create(
            company=self.company,
            code="OCB-PROCESS",
            name="隔离正式工艺类型",
        )
        self.instance.selected_process_type = process_type
        self.instance.save(update_fields=["selected_process_type"])
        routing = Routing.objects.create(
            applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
            product_category=self.category,
            manufacturing_process_type=process_type,
            company=self.company,
            routing_code="OCB-ROUTE",
            name="隔离正式工艺路线",
            status="released",
            is_active=True,
        )
        routing_version = RoutingVersion.objects.create(
            routing=routing,
            routing_version="OCB-R1",
            status="draft",
        )
        RoutingStep.objects.create(
            routing_version=routing_version,
            sequence=1,
            operation=self.operation,
            operation_parameters={"applicability": {"mode": "MANDATORY"}},
        )
        routing_version.status = "released"
        routing_version.save(update_fields=("status", "updated_at"))
        return {
            "calculation": EngineeringCalculationRecord.objects.get(pk=calculation_id),
            "bom": ProductBOM.objects.get(pk=generated["bomId"]),
            "bom_version": BOMVersion.objects.get(pk=generated["bomVersionId"]),
            "routing": routing,
            "routing_version": routing_version,
        }

    def test_routing_management_reuses_exact_formal_chain_read_only(self):
        facts = self._build_routing_management_handoff()
        before = {
            "boms": ProductBOM.objects.count(),
            "bom_versions": BOMVersion.objects.count(),
            "routings": Routing.objects.count(),
            "routing_versions": RoutingVersion.objects.count(),
            "routing_steps": RoutingStep.objects.count(),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
        }
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(reverse("pde-routings"), {"q": self.order.order_no})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["rows"]), 1)
        row = response.data["rows"][0]
        self.assertEqual(row["companyId"], self.company.pk)
        self.assertEqual(row["orderNo"], self.order.order_no)
        self.assertEqual(row["orderLineNo"], self.item.line_no)
        self.assertEqual(row["orderEngineeringInstanceId"], self.instance.pk)
        self.assertEqual(row["productBomId"], facts["bom"].pk)
        self.assertEqual(row["bomVersionId"], facts["bom_version"].pk)
        self.assertEqual(row["sourceCalculationId"], facts["calculation"].pk)
        self.assertEqual(row["routingId"], facts["routing"].pk)
        self.assertEqual(row["routingVersionId"], facts["routing_version"].pk)
        self.assertEqual(row["routingIdentityCandidateCount"], 1)
        self.assertEqual(row["stepCount"], 1)
        self.assertEqual(row["operationSequenceLabel"], "1 开料")
        self.assertTrue(row["handoffAccepted"])
        self.assertFalse(row["routingVersionManagementEligible"])
        self.assertEqual(row["planningReadiness"]["requiredStepCount"], 1)
        self.assertEqual(row["bomVersionStatusLabel"], "草稿")
        self.assertEqual(row["routingDefinitionStatusLabel"], "已发布")
        self.assertEqual(row["routingVersionStatusLabel"], "已发布")

        for surface in (
            "apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts",
        ):
            self.assertEqual(response.data[surface]["formalHandoffCount"], 1)
            self.assertEqual(response.data[surface]["databaseBusinessWriteCount"], 0)
            self.assertEqual(response.data[surface]["routingCreatedCount"], 0)
            self.assertEqual(response.data[surface]["routingVersionCreatedCount"], 0)
            self.assertEqual(response.data[surface]["routingStepCreatedCount"], 0)

        after = {
            "boms": ProductBOM.objects.count(),
            "bom_versions": BOMVersion.objects.count(),
            "routings": Routing.objects.count(),
            "routing_versions": RoutingVersion.objects.count(),
            "routing_steps": RoutingStep.objects.count(),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
        }
        self.assertEqual(after, before)

    def test_routing_management_fails_closed_when_resolution_is_ambiguous(self):
        self._build_routing_management_handoff()
        client = APIClient()
        client.force_authenticate(self.user)
        with patch(
            "pde.views.ManufacturingStructureService.resolve_effective_routing",
            side_effect=ManufacturingStructureError(
                "AMBIGUOUS_EFFECTIVE_ROUTING",
                "同一优先级存在多条同时有效工艺路线。",
                {"routingIds": [101, 102]},
            ),
        ):
            response = client.get(reverse("pde-routings"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["factLoadStatus"], "read_failed")
        self.assertEqual(
            response.data["error"]["code"],
            "AMBIGUOUS_EFFECTIVE_ROUTING",
        )
        self.assertIn("多条", response.data["error"]["message"])
        self.assertFalse(response.data["error"]["details"]["handoffAccepted"])
        self.assertEqual(response.data["error"]["details"]["databaseBusinessWriteCount"], 0)
        self.assertIsNone(response.data["recordCount"])

    def test_routing_version_management_reuses_exact_formal_chain_read_only(self):
        facts = self._build_routing_management_handoff()
        before = {
            "boms": ProductBOM.objects.count(),
            "bom_versions": BOMVersion.objects.count(),
            "routings": Routing.objects.count(),
            "routing_versions": RoutingVersion.objects.count(),
            "routing_steps": RoutingStep.objects.count(),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
        }
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(reverse("pde-routing-versions"), {"q": self.order.order_no})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["rows"]), 1)
        row = response.data["rows"][0]
        self.assertEqual(row["companyId"], self.company.pk)
        self.assertEqual(row["orderNo"], self.order.order_no)
        self.assertEqual(row["orderLineNo"], self.item.line_no)
        self.assertEqual(row["orderEngineeringInstanceId"], self.instance.pk)
        self.assertEqual(row["productBomId"], facts["bom"].pk)
        self.assertEqual(row["bomVersionId"], facts["bom_version"].pk)
        self.assertEqual(row["sourceCalculationId"], facts["calculation"].pk)
        self.assertEqual(row["definitionId"], facts["routing"].pk)
        self.assertEqual(row["versionId"], facts["routing_version"].pk)
        self.assertEqual(row["routingVersionNo"], facts["routing_version"].routing_version)
        self.assertEqual(row["revision"], 1)
        self.assertEqual(row["stepCount"], 1)
        self.assertEqual(len(row["steps"]), 1)
        self.assertTrue(row["routingVersionHandoffAccepted"])
        self.assertTrue(row["isCurrentlyEffective"])
        self.assertEqual(row["effectiveStatusLabel"], "当前订单行唯一有效版本")
        self.assertEqual(
            row["stepRelationshipSemanticsCode"],
            "VERSION_SCOPED_RELATIONAL_DEFINITION",
        )
        self.assertTrue(row["immutableSnapshotProven"])
        self.assertIn("终态版本步骤由服务端写保护", row["stepRelationshipSemanticsLabel"])
        self.assertIn("RoutingStep.routing_version_id", row["stepRelationLabel"])
        self.assertIn("未进入、未发布", row["engineeringDocumentReleaseEligibilityLabel"])

        for surface in (
            "apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts",
        ):
            self.assertEqual(response.data[surface]["formalHandoffCount"], 1)
            self.assertEqual(response.data[surface]["databaseBusinessWriteCount"], 0)
            self.assertEqual(response.data[surface]["routingCreatedCount"], 0)
            self.assertEqual(response.data[surface]["routingVersionCreatedCount"], 0)
            self.assertEqual(response.data[surface]["routingStepCreatedCount"], 0)
            self.assertEqual(response.data[surface]["engineeringDocumentCreatedCount"], 0)
            self.assertTrue(response.data[surface]["immutableSnapshotProven"])

        after = {
            "boms": ProductBOM.objects.count(),
            "bom_versions": BOMVersion.objects.count(),
            "routings": Routing.objects.count(),
            "routing_versions": RoutingVersion.objects.count(),
            "routing_steps": RoutingStep.objects.count(),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
        }
        self.assertEqual(after, before)

    def test_routing_version_management_fails_closed_when_current_version_is_ambiguous(self):
        self._build_routing_management_handoff()
        client = APIClient()
        client.force_authenticate(self.user)
        with patch(
            "pde.views.ManufacturingStructureService.resolve_effective_routing",
            side_effect=ManufacturingStructureError(
                "AMBIGUOUS_EFFECTIVE_VERSION",
                "同一工艺路线存在多个同时有效的已发布版本。",
                {"routingVersionIds": [201, 202]},
            ),
        ):
            response = client.get(reverse("pde-routing-versions"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["factLoadStatus"], "read_failed")
        self.assertEqual(response.data["error"]["code"], "AMBIGUOUS_EFFECTIVE_VERSION")
        self.assertIn("多个", response.data["error"]["message"])
        self.assertFalse(response.data["error"]["details"]["handoffAccepted"])
        self.assertEqual(response.data["error"]["details"]["databaseBusinessWriteCount"], 0)
        self.assertIsNone(response.data["recordCount"])

    def test_bom_detail_projects_five_materials_and_twenty_five_exact_requirement_links_read_only(self):
        specifications = ("30×40", "", "60×18", "宽25", "宽50")
        materials = [
            Material.objects.create(
                company_id=self.company.pk,
                code=f"OCB-TRACE-{material_index}",
                name=f"追溯物料{material_index}",
                specification=specification,
                unit="件",
                base_uom=self.pcs,
                material_type="raw",
                is_purchased=True,
            )
            for material_index, specification in enumerate(specifications, 1)
        ]
        rules = []
        for material_index, material in enumerate(materials, 1):
            for source_index in range(1, 6):
                code = f"TRACE-{material_index}-{source_index}"
                rules.append(EngineeringRuleDefinition.objects.create(
                    company=self.company,
                    rule_code=code,
                    rule_name=f"来源规则{material_index}-{source_index}",
                    version="V1",
                    rule_kind="formula",
                    status="released",
                    specification=rule_spec(
                        code=code,
                        input_name="unit_need",
                        output_name=f"trace_material_{material_index}_{source_index}",
                        domain="MATERIAL_REQUIREMENT",
                        materialId=material.pk,
                        quantityBasis="ORDER_TOTAL",
                        itemRole="material",
                        requirementType="manufacturing",
                        supplyType="BUY",
                    ),
                ))

        execution = EngineeringCalculationService.execute(
            user=self.user,
            scope="order_engineering",
            source_record_id=self.source.pk,
            rule_ids=[row.pk for row in rules],
            sales_order_item_id=self.item.pk,
            engineering_instance_id=self.instance.pk,
            reason="isolated five material trace projection test",
        )
        calculation = EngineeringCalculationRecord.objects.get(pk=execution["calculation"]["id"])
        for requirement in calculation.material_requirements.order_by("sequence"):
            requirement.trace = {
                **(requirement.trace or {}),
                "designItemId": requirement.sequence,
                "designItemNo": f"DES-TRACE-{requirement.sequence:02d}",
                "structureRole": f"ROLE-{((requirement.sequence - 1) // 5) + 1}",
                "mappingRuleId": requirement.source_detail.rule_id,
                "mappingRuleCode": requirement.source_detail.rule_code,
                "sourceFactId": 1000 + requirement.sequence,
            }
            requirement.save(update_fields=["trace"])

        preview = OrderEngineeringClosureService.preview_bom(
            user=self.user, calculation_id=calculation.pk,
        )
        OrderEngineeringClosureService.generate_bom(
            user=self.user,
            calculation_id=calculation.pk,
            preview_hash=preview["previewHash"],
        )
        bom = ProductBOM.objects.get()
        latest = bom.versions.order_by("-revision", "-pk").first()
        before = {
            "boms": ProductBOM.objects.count(),
            "versions": BOMVersion.objects.count(),
            "items": BOMItem.objects.count(),
            "links": BOMItemSourceRequirement.objects.count(),
            "requirements": EngineeringMaterialRequirement.objects.count(),
        }

        client = APIClient()
        client.force_authenticate(self.user)
        with patch.object(
            OrderEngineeringClosureService,
            "generate_bom",
            side_effect=AssertionError("BOM detail GET must never generate a BOM"),
        ) as generation:
            response = client.get(reverse("pde-product-boms"), {"q": "SO-OCB"})
        self.assertEqual(response.status_code, 200)
        generation.assert_not_called()
        row = response.data["rows"][0]

        self.assertEqual(row["orderNo"], "SO-OCB")
        self.assertEqual(row["orderLineNo"], 1)
        self.assertEqual(row["latestMaterialCount"], 5)
        self.assertEqual(row["sourceRequirementCount"], 25)
        self.assertEqual(len(row["bomMaterialDetails"]), 5)
        self.assertEqual(
            [item["materialCode"] for item in row["bomMaterialDetails"]],
            [material.code for material in materials],
        )
        self.assertEqual(
            [item["materialSpecificationLabel"] for item in row["bomMaterialDetails"]],
            ["30×40", "未维护", "60×18", "宽25", "宽50"],
        )
        self.assertEqual(
            [item["sourceRequirementCount"] for item in row["bomMaterialDetails"]],
            [5, 5, 5, 5, 5],
        )
        self.assertEqual(
            sum(len(item["sourceRequirements"]) for item in row["bomMaterialDetails"]),
            25,
        )
        projected_requirement_ids = [
            source["requirementId"]
            for item in row["bomMaterialDetails"]
            for source in item["sourceRequirements"]
        ]
        self.assertEqual(len(projected_requirement_ids), len(set(projected_requirement_ids)))
        self.assertEqual(
            set(projected_requirement_ids),
            set(calculation.material_requirements.values_list("pk", flat=True)),
        )
        for item in row["bomMaterialDetails"]:
            self.assertTrue(item["materialCode"])
            self.assertTrue(item["materialName"])
            self.assertTrue(item["quantity"])
            self.assertEqual(item["uomCode"], "PCS")
            for source in item["sourceRequirements"]:
                self.assertEqual(source["materialId"], item["materialId"])
                self.assertEqual(source["uomCode"], item["uomCode"])
                self.assertEqual(source["calculationId"], calculation.pk)
                self.assertEqual(source["companyId"], self.company.pk)
                self.assertEqual(source["orderNo"], "SO-OCB")
                self.assertEqual(source["orderLineNo"], 1)
                self.assertEqual(source["relationStatusCode"], "LINKED")
                self.assertTrue(source["designItemNo"].startswith("DES-TRACE-"))
                self.assertTrue(source["sourceDetailId"])
                self.assertTrue(source["mappingRuleCode"].startswith("TRACE-"))

        after = {
            "boms": ProductBOM.objects.count(),
            "versions": BOMVersion.objects.count(),
            "items": BOMItem.objects.count(),
            "links": BOMItemSourceRequirement.objects.count(),
            "requirements": EngineeringMaterialRequirement.objects.count(),
        }
        self.assertEqual(after, before)

        other_line = SalesOrderItem.objects.create(
            sales_order=self.order,
            line_no=2,
            material=self.finished,
            product_definition=self.product,
            product_version=self.product_version,
            engineering_mode="ORDER_ENGINEERED",
            quantity="1",
            uom=self.pcs,
            required_date=self.order.required_delivery_date,
        )
        with self.assertRaises(ProductBomDetailProjectionError):
            project_product_bom_material_detail(
                bom=bom, bom_version=latest, order_item=other_line,
            )

        second_company = Company.objects.create(code="OCB-OTHER", name="其它隔离公司")
        second_user = User.objects.create_user(
            username="ocb_other", password="test", company_id=second_company.pk,
        )
        client.force_authenticate(second_user)
        cross_company = client.get(reverse("pde-product-boms"), {"q": "SO-OCB"})
        self.assertEqual(cross_company.status_code, 200)
        self.assertEqual(cross_company.data["rows"], [])

        client.force_authenticate(self.user)
        unavailable = client.get(reverse("pde-product-boms"), {"q": "BOM-NOT-AVAILABLE"})
        self.assertEqual(unavailable.status_code, 200)
        self.assertEqual(unavailable.data["rows"], [])

        client.force_authenticate(user=None)
        unauthenticated = client.get(reverse("pde-product-boms"))
        self.assertIn(unauthenticated.status_code, {401, 403})

    def test_draft_method_trial_reuses_engine_and_is_zero_write(self):
        derived_spec = rule_spec(
            code="NET-BASE", input_name="unit_need", output_name="net_base",
            domain="DERIVED_FACT",
        )
        derived_spec["rulePackage"] = {"code": "ORDER_BOM_CLOSURE", "version": "V1.0"}
        derived = EngineeringRuleDefinition.objects.create(
            company=self.company, rule_code="NET-BASE", rule_name="净量基础",
            version="V1", rule_kind="formula", status="released", specification=derived_spec,
        )
        calculation = EngineeringCalculationService.execute(
            user=self.user, scope="order_engineering", source_record_id=self.source.pk,
            rule_ids=[row.pk for row in self.rules] + [derived.pk], sales_order_item_id=self.item.pk,
            engineering_instance_id=self.instance.pk, reason="isolated trial foundation",
        )["calculation"]
        trial_spec = {
            "description": "isolated draft method",
            "rulePackage": {"code": "NET_TRIAL", "version": "V0.1"},
            "expression": "net_base * order_quantity",
            "inputs": [
                input_contract("net_base"),
                {"canonicalName": "order_quantity", "valueType": "decimal", "unitDimension": "dimensionless", "unitRequired": False, "required": True, "sourceType": "SALES", "description": "quantity"},
            ],
            "outputs": [{"canonicalName": "trial_net", "valueType": "decimal", "unitDimension": "count", "unit": "PCS", "resultDomain": "DERIVED_FACT", "description": "trial"}],
            "dependencies": [], "applicability": {"scope": "non_production_method_trial"},
            "decimalPrecision": 18, "outputScale": 6, "roundingMode": "ROUND_HALF_UP", "priority": 100,
            "sourceEvidence": {"reference": "independent isolated reference", "verificationStatus": "CANDIDATE_METHOD"},
        }
        draft = EngineeringRuleDefinition.objects.create(
            company=self.company, rule_code="NET-TRIAL", rule_name="净量候选",
            version="V0.1", rule_kind="formula", status="draft", specification=trial_spec,
        )
        self.source.source_payload = {
            **self.source.source_payload,
            "methodTrialValidation": {
                "status": "INDEPENDENT_VERIFIED_SOURCE", "structureRole": None,
                "expectedResults": [{"canonicalField": "trial_net", "value": "6", "unit": "PCS", "cell": "T1", "verificationStatus": "VERIFIED_RESULT"}],
            },
        }
        self.source.save(update_fields=["source_payload", "updated_at"])
        before = {
            "calculations": EngineeringCalculationRecord.objects.count(),
            "materials": EngineeringMaterialRequirement.objects.count(),
            "operations": EngineeringOperationRequirement.objects.count(),
            "boms": ProductBOM.objects.count(),
        }
        with patch.dict("os.environ", {"PCE_NON_PRODUCTION_ACCEPTANCE": "0"}):
            with self.assertRaises(EngineeringCalculationError) as blocked:
                EngineeringMethodTrialService.execute(
                    user=self.user, sales_order_item_id=self.item.pk,
                    engineering_instance_id=self.instance.pk, source_record_id=self.source.pk,
                    rule_ids=[draft.pk],
                )
        self.assertEqual(blocked.exception.code, "NON_PRODUCTION_TRIAL_REQUIRED")
        with patch.dict("os.environ", {"PCE_NON_PRODUCTION_ACCEPTANCE": "1"}):
            result = EngineeringMethodTrialService.execute(
                user=self.user, sales_order_item_id=self.item.pk,
                engineering_instance_id=self.instance.pk, source_record_id=self.source.pk,
                rule_ids=[draft.pk],
            )
        self.assertEqual(result["trialStatus"], "PASS")
        self.assertEqual(result["rows"][0]["systemValue"], "6.000000")
        self.assertEqual(result["rows"][0]["difference"], "0.000000")
        self.assertFalse(result["expectedResultsUsedAsInputs"])
        self.assertEqual(result["businessWriteSideEffectCount"], 0)
        self.assertEqual(before, {
            "calculations": EngineeringCalculationRecord.objects.count(),
            "materials": EngineeringMaterialRequirement.objects.count(),
            "operations": EngineeringOperationRequirement.objects.count(),
            "boms": ProductBOM.objects.count(),
        })
