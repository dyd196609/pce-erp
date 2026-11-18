from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import Material, UnitOfMeasure
from pfm.models import Employee
from sales.models import Customer, SalesOrder
from sales.services import SalesBusinessError, confirm_order, create_order, generate_demand
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionResponsibility, PositionWorkflowResponsibility, Process, Responsibility,
    Role, RolePermission, User, UserRoleScopeAssignment, Workshop,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition

from .models import (
    BOMItem, BOMVersion, EngineeringBreakdownItem, EngineeringCalculationRecord,
    EngineeringDerivedFact, EngineeringDocument, EngineeringDocumentVersion,
    EngineeringRuleDefinition, EngineeringSourceRecord, OrderEngineeringInstance,
    ProductBOM, ProductCategory, ProductDefinition, ProductManufacturingOutput,
    ProductVersion, Routing, RoutingStep, RoutingVersion, StandardCapacity, WorkCenter,
)
from .production_foundation_service import EngineeringLifecycleService, ProductionFoundationService


class ProductionFoundationA17Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="A17", name="A1.7验收公司")
        cls.department = Department.objects.create(
            code="A17-ENG", name="工程技术部", company=cls.company,
        )
        cls.user = User.objects.create_superuser(
            username="a17_engineer", password="test-only", real_name="A1.7工程员",
            company_id=cls.company.pk,
        )
        cls.responsibility, _ = Responsibility.objects.update_or_create(
            code="RESP_A17_ENGINEERING",
            defaults={"name": "生产工程资料维护", "status": "ACTIVE", "is_active": True},
        )
        cls.position = Position.objects.create(
            code="A17-ENGINEER", name="A1.7生产工程岗", company=cls.company,
            department=cls.department,
        )
        PositionResponsibility.objects.create(
            position=cls.position, responsibility=cls.responsibility,
            is_primary=True, active=True,
        )
        Employee.objects.create(
            user=cls.user, employee_no="A17-E001", full_name="A1.7工程员",
            department_ref=cls.department, position_ref=cls.position, status="active",
        )
        cls.role = Role.objects.create(code="A17_ENGINEER_ROLE", name="A1.7工程维护角色")
        for permission in Permission.objects.filter(code__startswith="production."):
            RolePermission.objects.get_or_create(role=cls.role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=cls.user, role=cls.role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, business_hash="a17-formal-authority",
        )
        process_definition, _ = ProcessDefinition.objects.update_or_create(
            definition_code="SALES_ORDER_TO_SUPPLY_PLAN",
            defaults={
                "definition_name": "销售订单到供应计划", "business_domain": "SALES",
                "document_type": "SalesOrder", "version": 1, "active": True,
                "definition_hash": "a17",
            },
        )
        sales_responsibility, _ = Responsibility.objects.update_or_create(
            code="RESP_SALES_ORDER_002",
            defaults={"name": "销售需求与订单协调", "status": "ACTIVE", "is_active": True},
        )
        PositionResponsibility.objects.get_or_create(
            position=cls.position, responsibility=sales_responsibility,
            defaults={"active": True},
        )
        for sequence, (node_code, action) in enumerate((
            ("CREATE", "sales.order.create"),
            ("CONFIRM", "sales.order.confirm"),
            ("DEMAND", "sales.order.generate_demand"),
        ), 1):
            node, _ = WorkflowNodeDefinition.objects.update_or_create(
                process_definition=process_definition, node_code=node_code,
                defaults={
                    "node_name": node_code, "sequence": sequence,
                    "business_action_code": action, "active": True,
                },
            )
            PositionWorkflowResponsibility.objects.update_or_create(
                position=cls.position, workflow_code="SALES_ORDER_TO_SUPPLY_PLAN",
                node_code=node_code, ownership_type="OWNER",
                defaults={
                    "responsibility": sales_responsibility,
                    "workflow_node": node, "active": True,
                },
            )

        cls.uom = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="PCS-A17", name="件",
        )
        cls.finished = Material.objects.create(
            code="A17-FG", name="A1.7按单工程成品", unit="件", base_uom=cls.uom,
            material_type="finished", company_id=cls.company.pk,
            is_produced=True, is_purchased=False,
        )
        cls.raw = Material.objects.create(
            code="A17-RM", name="A1.7通用原料", unit="件", base_uom=cls.uom,
            material_type="raw", company_id=cls.company.pk,
            is_purchased=True, is_produced=False,
        )
        cls.category = ProductCategory.objects.create(
            company=cls.company, code="A17-CAT", name="可配置产品族",
            industry_type="configurable-manufacturing",
        )
        cls.product = ProductDefinition.objects.create(
            company=cls.company, category=cls.category, material=cls.finished,
            product_code="A17-P", product_name="按单工程产品",
            emd_material_code=cls.finished.code,
            manufacturing_definition_mode="order_engineered",
        )
        cls.product_version = ProductVersion.objects.create(
            product=cls.product, version_no="BASE-V1",
        )
        cls.workshop = Workshop.objects.create(
            company=cls.company, department=cls.department,
            code="A17-WS", name="A1.7正式车间",
        )
        cls.work_center = WorkCenter.objects.create(
            company=cls.company, department=cls.department,
            workshop=cls.workshop, code="A17-WC", name="通用工作中心",
        )
        cls.operation = Process.objects.create(
            company=cls.company, workshop=cls.workshop, work_center=cls.work_center,
            code="A17-OP", name="通用工序", standard_hours=None,
        )
        cls.bom = ProductBOM.objects.create(
            company=cls.company, product=cls.product,
            bom_code="A17-BOM", name="统一BOM主表",
        )
        cls.routing = Routing.objects.create(
            company=cls.company, product=cls.product,
            routing_code="A17-ROUTE", name="通用工艺路线",
        )
        cls.routing_version = RoutingVersion.objects.create(
            routing=cls.routing, product=cls.product,
            product_version=cls.product_version, routing_version="V1",
        )
        cls.document = EngineeringDocument.objects.create(
            document_no="A17-DOC", document_name="按单工程资料",
            document_type="technical", product=cls.product,
            product_bom=cls.bom, routing=cls.routing,
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="A17-CUSTOMER", name="工程订单客户",
        )

    def _order_payload(self):
        return {
            "customerId": self.customer.pk,
            "departmentId": self.department.pk,
            "requiredDate": (date.today() + timedelta(days=10)).isoformat(),
            "deliveryInformation": {"businessPurpose": "FORMAL_SALE"},
            "items": [{
                "materialId": self.finished.pk,
                "productDefinitionId": self.product.pk,
                "quantity": "1",
            }],
        }

    def test_01_standard_capacity_separates_quantity_time_basis_and_hours(self):
        result = ProductionFoundationService.save(
            "standard-capacities", user=self.user,
            payload={
                "code": "CAP-A17", "name": "时间基准待维护产能", "resource_scope": "operation",
                "operation_id": self.operation.pk, "quantity": "12",
                "uom_id": self.uom.pk, "time_basis": "not_maintained",
                "standard_hours": None, "conditions": {"source": "confirmed-master-data"},
                "reason": "A1.7标准产能语义验收",
            },
        )
        row = StandardCapacity.objects.get(pk=result["row"]["id"])
        self.assertIsNone(row.time_basis_quantity)
        self.assertIsNone(row.standard_hours)
        self.assertEqual(row.quantity, 12)
        self.assertTrue(OrganizationOperatingAuditRecord.objects.filter(pk=result["auditId"]).exists())

    def test_02_operation_and_routing_step_allow_not_maintained_hours(self):
        self.assertIsNone(self.operation.standard_hours)
        version = RoutingVersion.objects.create(
            routing=self.routing, product=self.product,
            product_version=self.product_version, routing_version="NULL-HOURS",
        )
        step = RoutingStep(
            routing_version=version, sequence=10, operation=self.operation,
            work_center=self.work_center, standard_hours=None,
        )
        step.full_clean()
        step.save()
        self.assertIsNone(step.standard_hours)

    def test_02b_capacity_distinguishes_not_determinable_from_not_applicable(self):
        result = ProductionFoundationService.save(
            "standard-capacities", user=self.user,
            payload={
                "code": "CAP-A17-ND", "name": "经过工序但产能无法确定",
                "measurement_status": "not_determinable",
                "resource_scope": "operation", "operation_id": self.operation.pk,
                "quantity": None, "uom_id": self.uom.pk,
                "time_basis": "day", "time_basis_quantity": "1",
                "standard_hours": None, "conditions": {"workdayHours": 10},
                "reason": "真实行业资料确认：0表示适用但无法确定，空格表示不经过",
            },
        )
        row = StandardCapacity.objects.get(pk=result["row"]["id"])
        self.assertEqual(row.measurement_status, "not_determinable")
        self.assertIsNone(row.quantity)
        self.assertEqual(row.conditions["workdayHours"], 10)
        invalid = StandardCapacity(
            company=self.company, code="CAP-A17-ZERO", name="禁止零值冒充未知",
            measurement_status="not_determinable", resource_scope="operation",
            operation=self.operation, quantity=0, uom=self.uom,
            time_basis="day", time_basis_quantity=1,
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_02c_material_unit_unknown_is_explicit_and_not_derived_from_engineering_uom(self):
        result = ProductionFoundationService.save(
            "materials", user=self.user,
            payload={
                "code": "A17-UNIT-PENDING", "name": "来源单位待维护半成品板材",
                "unit": "", "unit_status": "not_confirmed", "material_type": "semi",
                "is_purchased": False, "is_produced": True, "is_active": True,
                "reason": "真实05表单位为空；不得用门面板张数反推Material单位",
            },
        )
        material = Material.objects.get(pk=result["row"]["id"])
        self.assertEqual(material.unit_status, "not_confirmed")
        self.assertEqual(material.unit, "")
        self.assertIsNone(material.base_uom_id)
        invalid = Material(
            code="A17-UNIT-GUESSED", name="禁止猜填单位", unit="张",
            unit_status="not_confirmed", material_type="semi",
            company_id=self.company.pk, is_produced=True,
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_02d_workshop_is_distinct_and_route_step_allows_unmaintained_work_center(self):
        operation_result = ProductionFoundationService.save(
            "operations", user=self.user,
            payload={
                "code": "A17-OP-WS", "name": "只确认车间的工序",
                "workshop_id": self.workshop.pk, "work_center_id": None,
                "standard_hours": None, "reason": "01表只确认Workshop，未提供WorkCenter",
            },
        )
        operation = Process.objects.get(pk=operation_result["row"]["id"])
        self.assertEqual(operation.workshop_id, self.workshop.pk)
        self.assertIsNone(operation.work_center_id)
        version = RoutingVersion.objects.create(
            routing=self.routing, product=self.product,
            product_version=self.product_version, routing_version="WORKSHOP-ONLY",
        )
        step = RoutingStep(
            routing_version=version, sequence=10, operation=operation,
            work_center=None, standard_hours=None,
        )
        step.full_clean()
        step.save()
        self.assertIsNone(step.work_center_id)

    def test_02e_bom_uncertainty_does_not_default_to_zero_or_confirmed_none(self):
        version = BOMVersion.objects.create(
            bom=self.bom, product=self.product, product_version=self.product_version,
            bom_version="UNCERTAINTY-V1", bom_scope="standard",
        )
        item = BOMItem(
            bom_version=version, line_no=1, material=self.raw,
            quantity=1, uom=self.uom,
            scrap_rate_status="not_maintained", scrap_rate=None,
            substitute_status="not_maintained",
        )
        item.full_clean()
        item.save()
        self.assertIsNone(item.scrap_rate)
        self.assertEqual(item.substitute_status, "not_maintained")
        self.assertEqual(item.substitutes.count(), 0)
        invalid = BOMItem(
            bom_version=version, line_no=2, material=self.raw,
            quantity=1, uom=self.uom,
            scrap_rate_status="not_maintained", scrap_rate=0,
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_02f_first_engineering_versions_are_generated_by_system(self):
        product = ProductDefinition.objects.create(
            company=self.company, category=self.category, material=self.finished,
            product_code="A17-AUTO-VERSION", product_name="自动首版产品",
            emd_material_code=self.finished.code,
            manufacturing_definition_mode="order_engineered",
        )
        product_result = ProductionFoundationService.save(
            "product-versions", user=self.user,
            payload={
                "product_id": product.pk,
                "change_reason": "首次正式建档",
                "reason": "版本号属于系统治理事实",
            },
        )
        self.assertEqual(product_result["row"]["version_no"], "V1.0")
        product_version = ProductVersion.objects.get(pk=product_result["row"]["id"])
        bom = ProductBOM.objects.create(
            company=self.company, product=product,
            bom_code="A17-AUTO-BOM", name="自动首版BOM",
        )
        bom_result = ProductionFoundationService.save(
            "bom-versions", user=self.user,
            payload={
                "product_id": product.pk, "product_version_id": product_version.pk,
                "bom_id": bom.pk, "bom_scope": "standard",
                "reason": "首次正式建档",
            },
        )
        self.assertEqual(bom_result["row"]["bom_version"], "V1.0")
        routing = Routing.objects.create(
            company=self.company, product=product,
            routing_code="A17-AUTO-ROUTE", name="自动首版路线",
        )
        routing_result = ProductionFoundationService.save(
            "routing-versions", user=self.user,
            payload={
                "product_id": product.pk, "product_version_id": product_version.pk,
                "routing_id": routing.pk, "reason": "首次正式建档",
            },
        )
        self.assertEqual(routing_result["row"]["routing_version"], "V1.0")
        document = EngineeringDocument.objects.create(
            document_no="A17-AUTO-DOC", document_name="自动首版工程资料",
            document_type="technical", product=product,
            product_bom=bom, routing=routing,
        )
        document_result = ProductionFoundationService.save(
            "engineering-document-versions", user=self.user,
            payload={
                "document_id": document.pk, "document_name": "自动首版工程资料",
                "product_version_id": product_version.pk,
                "related_product_id": product.pk,
                "related_bom_id": bom_result["row"]["id"],
                "related_routing_id": routing_result["row"]["id"],
                "reason": "首次正式建档",
            },
        )
        self.assertEqual(document_result["row"]["document_version"], "V1.0")

    def test_03_core_schema_contains_no_industry_specific_fields(self):
        models = [
            ProductDefinition, ProductBOM, BOMVersion, Routing, RoutingVersion,
            RoutingStep, StandardCapacity, OrderEngineeringInstance,
        ]
        forbidden = {"wood_type", "cabinet_only", "door_panel_only", "printing_only"}
        for model in models:
            self.assertTrue(forbidden.isdisjoint({field.name for field in model._meta.fields}))

    def test_04_order_engineered_sales_item_can_precede_manufacturing_definition(self):
        order, item, _ = create_order(
            user=self.user, payload=self._order_payload(), authorization={"allowed": True},
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
        )
        self.assertEqual(order.status, "draft")
        self.assertEqual(item.product_definition_id, self.product.pk)
        self.assertIsNone(item.manufacturing_output_id)

    def test_05_unreleased_order_engineering_cannot_enter_demand(self):
        order, _, _ = create_order(
            user=self.user, payload=self._order_payload(), authorization={"allowed": True},
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
        )
        confirm_order(user=self.user, order_id=order.pk, authorization={"allowed": True})
        with self.assertRaisesMessage(SalesBusinessError, "尚未形成并发布正式制造定义"):
            generate_demand(user=self.user, order_id=order.pk, authorization={"allowed": True})

    def test_06_order_engineering_lineage_releases_one_unified_output(self):
        order, item, _ = create_order(
            user=self.user, payload=self._order_payload(), authorization={"allowed": True},
            business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE,
        )
        confirm_order(user=self.user, order_id=order.pk, authorization={"allowed": True})
        source = EngineeringSourceRecord.objects.create(
            company=self.company, source_no="SRC-A17", source_name="订单工程来源",
            source_type="order_input", source_version="V1",
            source_payload={"salesOrderItemId": item.pk, "dimensions": {"source": "user"}},
            content_hash="a" * 64,
        )
        EngineeringLifecycleService.transition(
            "engineering-source-records", object_id=source.pk,
            target_status="confirmed", user=self.user,
        )
        instance = OrderEngineeringInstance.objects.create(
            company=self.company, instance_no="OEI-A17", sales_order_item=item,
            product=self.product, baseline_product_version=self.product_version,
            source_record=source,
        )
        instance.full_clean()
        EngineeringLifecycleService.transition(
            "order-engineering-instances", object_id=instance.pk,
            target_status="source_confirmed", user=self.user,
        )
        rule = EngineeringRuleDefinition.objects.create(
            company=self.company, rule_code="RULE-A17", rule_name="通用数量映射",
            version="V1", rule_kind="mapping", specification={"input": "quantity"},
        )
        calculation = EngineeringCalculationRecord.objects.create(
            engineering_instance=instance, calculation_no="CALC-A17",
            rule_set_version="V1", trace={"engineExecuted": False, "recordOnly": True},
        )
        breakdown = EngineeringBreakdownItem.objects.create(
            calculation=calculation, line_no=1, item_type="component",
            item_code="COMP-001", item_name="通用派生部件",
        )
        EngineeringDerivedFact.objects.create(
            calculation=calculation, breakdown_item=breakdown, rule=rule,
            fact_code="COMPONENT_QUANTITY", sequence=1, value={"decimal": "1"},
            uom=self.uom, source_path="source_payload.quantity",
            trace={"ruleVersion": "V1"},
        )
        EngineeringLifecycleService.transition(
            "engineering-calculation-records", object_id=calculation.pk,
            target_status="completed", user=self.user,
        )
        EngineeringLifecycleService.transition(
            "order-engineering-instances", object_id=instance.pk,
            target_status="calculated", user=self.user,
        )
        bom_version = BOMVersion(
            bom=self.bom, product=self.product, product_version=self.product_version,
            bom_version="ORDER-V1", bom_scope="order_specific",
            order_engineering_instance=instance,
        )
        bom_version.full_clean()
        bom_version.save()
        BOMItem.objects.create(
            bom_version=bom_version, line_no=1, material=self.raw,
            quantity=1, uom=self.uom,
        )
        document_version = EngineeringDocumentVersion.objects.create(
            document=self.document, document_name="按单工程资料", document_version="ORDER-V1",
            product_version=self.product_version, related_product=self.product,
            related_bom=bom_version, related_routing=self.routing_version,
        )
        output = ProductManufacturingOutput(
            product=self.product, product_version=self.product_version,
            bom_version=bom_version, routing_version=self.routing_version,
            engineering_document_version=document_version,
            engineering_status="ready", definition_mode="order_specific",
            order_engineering_instance=instance,
        )
        output.full_clean()
        output.save()
        for entity, row in (
            ("product-versions", self.product_version),
            ("bom-versions", bom_version),
            ("routing-versions", self.routing_version),
            ("engineering-document-versions", document_version),
        ):
            EngineeringLifecycleService.transition(
                entity, object_id=row.pk, target_status="reviewed", user=self.user,
            )
            EngineeringLifecycleService.transition(
                entity, object_id=row.pk, target_status="released", user=self.user,
            )
        EngineeringLifecycleService.transition(
            "manufacturing-outputs", object_id=output.pk,
            target_status="engineering_review", user=self.user,
        )
        result = EngineeringLifecycleService.transition(
            "manufacturing-outputs", object_id=output.pk,
            target_status="released_to_manufacturing", user=self.user,
        )
        item.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(item.manufacturing_output_id, output.pk)
        self.assertEqual(instance.status, "released")
        self.assertEqual(len(result["relatedAuditIds"]), 1)
        demand, _ = generate_demand(
            user=self.user, order_id=order.pk, authorization={"allowed": True},
        )
        self.assertEqual(demand.manufacturing_output_id, output.pk)

    def test_07_a17_permissions_and_code_rules_are_migration_owned(self):
        codes = {
            "production.master_data.material.maintain",
            "production.master_data.capacity.maintain",
            "production.engineering.source.maintain",
            "production.engineering.rule.maintain",
            "production.engineering.order.maintain",
            "production.engineering.calculation.record",
        }
        self.assertEqual(set(Permission.objects.filter(code__in=codes).values_list("code", flat=True)), codes)
        migration = (Path(settings.BASE_DIR) / "pde/migrations/0013_production_unified_model_permissions_a17.py").read_text(encoding="utf-8")
        self.assertIn("production_standard_capacity", migration)
        self.assertIn("production_order_engineering", migration)

    def test_08_foundation_route_uses_unified_server_maintenance_entry(self):
        root = Path(settings.BASE_DIR).parent
        router = (root / "frontend/src/router/index.js").read_text(encoding="utf-8")
        wrapper = (root / "frontend/src/meta/pages/EnterpriseFoundationUnifiedPage.vue").read_text(encoding="utf-8")
        component = (root / "frontend/src/meta/components/ProductionFoundationMaintenance.vue").read_text(encoding="utf-8")
        self.assertIn("EnterpriseFoundationUnifiedPage.vue", router)
        self.assertIn("foundationEntryGroups", wrapper)
        self.assertIn("loadMasterDataStatisticsRuntime", wrapper)
        self.assertIn("/foundation/master-data/", router)
        self.assertIn("ProductionFoundationMaintenance.vue", router)
        self.assertIn("productionFoundationA1", component)
        self.assertIn("saveProductionFoundation", component)
        self.assertNotIn("localStorage.", component)
        self.assertIn("单位状态", component)
        self.assertIn("车间 / 生产区域", component)
        self.assertIn("工作中心（可待维护）", component)
        self.assertIn("损耗率维护状态", component)
        self.assertIn("替代料维护状态", component)

    def test_09_gate_reports_ready_for_industry_master_data_without_a2(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get("/api/pde/a1-foundation/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["gate"], "PCE-PRODUCTION-A1.7-V1.0")
        self.assertEqual(response.data["result"], "READY_FOR_INDUSTRY_MASTER_DATA")
        self.assertEqual(response.data["a1Status"], "TECHNICAL_PASS_NOT_CLOSED")
        self.assertEqual(response.data["a2Status"], "NOT_ENTERED")
        self.assertEqual(response.data["legacyLocalStorageFormalFactCount"], 0)
        self.assertEqual(len(response.data["industryDataEntryGate"]), 20)
