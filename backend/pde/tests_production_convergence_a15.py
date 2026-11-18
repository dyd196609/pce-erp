from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import Material, UnitOfMeasure
from pfm.models import Employee
from planning.models import Demand, PlanningRequirement, PurchasePlan
from procurement.models import InventoryBalance, InventoryLot, Warehouse, WarehouseLocation
from sales.models import Customer, SalesOrder, SalesOrderItem
from sales.services import confirm_order, create_order, generate_demand
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Position,
    PositionResponsibility, PositionWorkflowResponsibility, Responsibility, User,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition
from workflow_runtime.state_transitions import create_business_object_with_initial_state

from .models import (
    BOMVersion, EngineeringDocument, EngineeringDocumentVersion,
    ManufacturingInputReference, ProductBOM, ProductCategory, ProductDefinition,
    ProductEngineeringReadiness, ProductManufacturingOutput, ProductVersion,
    Routing, RoutingVersion,
)
from .production_foundation_service import (
    EngineeringLifecycleService, ProductionFoundationError, ProductionFoundationService,
)


class ProductionConvergenceA15Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="A15", name="A1.5验收公司")
        cls.department = Department.objects.create(code="A15-TECH", name="技术部", company=cls.company)
        cls.user = User.objects.create_superuser(
            username="a15_engineer", password="test-only", real_name="A1.5工程维护员",
            company_id=cls.company.pk,
        )
        cls.responsibility, _ = Responsibility.objects.update_or_create(
            code="RESP_SALES_ORDER_002",
            defaults={"name": "销售与生产工程正式维护", "status": "ACTIVE", "is_active": True},
        )
        cls.position = Position.objects.create(
            code="A15-ENGINEER", name="生产工程维护岗", company=cls.company,
            department=cls.department,
        )
        PositionResponsibility.objects.create(
            position=cls.position, responsibility=cls.responsibility, is_primary=True, active=True,
        )
        Employee.objects.create(
            user=cls.user, employee_no="A15-E001", full_name="A1.5工程维护员",
            department_ref=cls.department, position_ref=cls.position, status="active",
        )
        process, _ = ProcessDefinition.objects.update_or_create(
            definition_code="SALES_ORDER_TO_SUPPLY_PLAN",
            defaults={"definition_name": "销售至需求", "business_domain": "SALES",
                      "document_type": "SalesOrder", "version": 1, "active": True,
                      "definition_hash": "a15"},
        )
        for sequence, (node_code, action) in enumerate((
            ("CREATE", "sales.order.create"), ("CONFIRM", "sales.order.confirm"),
            ("DEMAND", "sales.order.generate_demand"),
        ), 1):
            node, _ = WorkflowNodeDefinition.objects.update_or_create(
                process_definition=process, node_code=node_code,
                defaults={"node_name": node_code, "sequence": sequence,
                          "business_action_code": action, "active": True},
            )
            PositionWorkflowResponsibility.objects.update_or_create(
                position=cls.position, workflow_code="SALES_ORDER_TO_SUPPLY_PLAN",
                node_code=node_code, ownership_type="OWNER",
                defaults={"responsibility": cls.responsibility, "workflow_node": node, "active": True},
            )
        cls.uom = UnitOfMeasure.objects.create(company_id=cls.company.pk, code="PCS-A15", name="件")
        cls.finished = Material.objects.create(
            code="A15-FG", name="A1.5成品", unit="件", base_uom=cls.uom,
            material_type="finished", company_id=cls.company.pk,
            is_produced=True, is_purchased=False,
        )
        cls.raw = Material.objects.create(
            code="A15-RM", name="A1.5采购件", unit="件", base_uom=cls.uom,
            material_type="raw", company_id=cls.company.pk,
            is_produced=False, is_purchased=True,
        )
        cls.category = ProductCategory.objects.create(
            company=cls.company, code="A15-CAT", name="通用制造分类",
        )
        cls.product = ProductDefinition.objects.create(
            company=cls.company, category=cls.category, material=cls.finished,
            product_code="A15-P001", product_name="A1.5结构产品",
            emd_material_code=cls.finished.code,
        )
        cls.product_version = ProductVersion.objects.create(product=cls.product, version_no="V1")
        cls.bom = ProductBOM.objects.create(
            company=cls.company, product=cls.product, bom_code="A15-BOM", name="A1.5 BOM",
        )
        cls.bom_version = BOMVersion.objects.create(
            bom=cls.bom, product=cls.product, product_version=cls.product_version, bom_version="V1",
        )
        cls.routing = Routing.objects.create(
            company=cls.company, product=cls.product, routing_code="A15-ROUTE", name="A1.5路线",
        )
        cls.routing_version = RoutingVersion.objects.create(
            routing=cls.routing, product=cls.product,
            product_version=cls.product_version, routing_version="V1",
        )
        cls.document = EngineeringDocument.objects.create(
            document_no="A15-DOC", document_name="A1.5工程资料", document_type="technical",
            product=cls.product, product_bom=cls.bom, routing=cls.routing,
        )
        cls.document_version = EngineeringDocumentVersion.objects.create(
            document=cls.document, document_name="A1.5工程资料", document_version="V1",
            product_version=cls.product_version, related_product=cls.product,
            related_bom=cls.bom_version, related_routing=cls.routing_version,
        )
        cls.output = ProductManufacturingOutput.objects.create(
            product=cls.product, product_version=cls.product_version,
            bom_version=cls.bom_version, routing_version=cls.routing_version,
            engineering_document_version=cls.document_version, engineering_status="ready",
        )
        cls.customer = Customer.objects.create(company=cls.company, code="A15-C", name="验收客户")
        cls.warehouse = Warehouse.objects.create(
            code="A15-WH", name="A1.5正式仓库", company_id=cls.company.pk,
        )

    def _release_engineering(self):
        for entity, value in (
            ("product-versions", self.product_version),
            ("bom-versions", self.bom_version),
            ("routing-versions", self.routing_version),
            ("engineering-document-versions", self.document_version),
        ):
            EngineeringLifecycleService.transition(
                entity, object_id=value.pk, target_status="reviewed", user=self.user,
            )
            EngineeringLifecycleService.transition(
                entity, object_id=value.pk, target_status="released", user=self.user,
            )
        EngineeringLifecycleService.transition(
            "manufacturing-outputs", object_id=self.output.pk,
            target_status="engineering_review", user=self.user,
        )
        EngineeringLifecycleService.transition(
            "manufacturing-outputs", object_id=self.output.pk,
            target_status="released_to_manufacturing", user=self.user,
        )
        self.output.refresh_from_db()

    def _order_payload(self, items):
        return {
            "customerId": self.customer.pk, "departmentId": self.department.pk,
            "requiredDate": (date.today() + timedelta(days=10)).isoformat(),
            "items": items,
        }

    def test_01_static_bom_fixture_is_not_formal_fact(self):
        client = APIClient(); client.force_authenticate(self.user)
        response = client.get("/api/masterdata/enterprise/boms/facts/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["demoFixtureIncluded"])
        self.assertEqual(response.data["dataSource"], "pde.BOMVersion/BOMItem")
        self.assertNotIn("MD-BOM-001", str(response.data["rows"]))

    def test_02_static_routing_fixture_is_not_formal_fact(self):
        client = APIClient(); client.force_authenticate(self.user)
        response = client.get("/api/masterdata/enterprise/routings/facts/")
        self.assertEqual(response.data["dataSource"], "pde.RoutingVersion/RoutingStep")
        self.assertNotIn("MD-ROUTING-001", str(response.data["rows"]))

    def test_03_static_warehouse_fixture_is_not_formal_fact(self):
        client = APIClient(); client.force_authenticate(self.user)
        response = client.get("/api/masterdata/enterprise/warehouses/facts/")
        self.assertEqual(response.data["dataSource"], "procurement.Warehouse/WarehouseLocation")
        self.assertNotIn("MD-WAREHOUSE-001", str(response.data["rows"]))

    def test_04_formal_wms_route_does_not_load_legacy_store_page(self):
        root = Path(settings.BASE_DIR).parent
        router = (root / "frontend/src/router/index.js").read_text(encoding="utf-8")
        formal_block = router[router.index("path: 'wms'"):router.index("path: 'demo/wms'")]
        self.assertNotIn("WmsPage.vue", formal_block)
        page = (root / "frontend/src/meta/pages/FormalExecutionPage.vue").read_text(encoding="utf-8")
        self.assertNotIn("localStorage.", page)

    def test_05_formal_qms_route_does_not_load_legacy_store_page(self):
        root = Path(settings.BASE_DIR).parent
        router = (root / "frontend/src/router/index.js").read_text(encoding="utf-8")
        formal_block = router[router.index("path: 'qms'"):router.index("path: 'demo/wms'")]
        self.assertNotIn("QmsPage.vue", formal_block)

    def test_06_product_version_formal_write_is_authorized_and_audited(self):
        result = ProductionFoundationService.save(
            "product-versions", user=self.user,
            payload={"product_id": self.product.pk, "version_no": "V2", "change_reason": "A1.5测试"},
        )
        self.assertTrue(result["authorization"]["allowed"])
        self.assertEqual(result["executionChain"]["positionCode"], self.position.code)
        self.assertTrue(OrganizationOperatingAuditRecord.objects.filter(pk=result["auditId"]).exists())

    def test_07_engineering_release_has_four_complete_version_references(self):
        self._release_engineering()
        output = ProductManufacturingOutput.objects.get(pk=self.output.pk)
        self.assertEqual(output.release_status, "released_to_manufacturing")
        self.assertTrue(all((output.product_version_id, output.bom_version_id,
                             output.routing_version_id, output.engineering_document_version_id)))
        self.product.refresh_from_db(); self.document.refresh_from_db()
        self.assertEqual(self.product.version, "V1")
        self.assertEqual(self.document.version, "V1")

    def test_08_unreleased_or_incomplete_output_cannot_enter_manufacturing(self):
        incomplete = ProductManufacturingOutput.objects.create(
            product=self.product, product_version=self.product_version,
            bom_version=self.bom_version, routing_version=self.routing_version,
            engineering_status="ready",
        )
        EngineeringLifecycleService.transition(
            "manufacturing-outputs", object_id=incomplete.pk,
            target_status="engineering_review", user=self.user,
        )
        with self.assertRaises(ProductionFoundationError):
            EngineeringLifecycleService.transition(
                "manufacturing-outputs", object_id=incomplete.pk,
                target_status="released_to_manufacturing", user=self.user,
            )

    def test_09_sales_item_accepts_stable_released_engineering_references(self):
        self._release_engineering()
        item = SalesOrderItem(
            sales_order=self._create_direct_order_header("SO-A15-REF"), line_no=1,
            material=self.finished, product_definition=self.product,
            product_version=self.product_version, manufacturing_output=self.output,
            quantity=1, required_date=date.today(),
        )
        item.full_clean()

    def test_10_historical_material_only_sales_item_remains_valid(self):
        item = SalesOrderItem(
            sales_order=self._create_direct_order_header("SO-A15-HISTORY"), line_no=1,
            material=self.raw, quantity=1, required_date=date.today(),
        )
        item.full_clean()

    def test_11_multi_line_sales_order_generates_one_demand_per_item(self):
        payload = self._order_payload([
            {"materialId": self.raw.pk, "quantity": "2"},
            {"materialId": self.raw.pk, "quantity": "3"},
        ])
        order, _, _ = create_order(user=self.user, payload=payload, authorization={"allowed": True}, business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE)
        confirm_order(user=self.user, order_id=order.pk, authorization={"allowed": True})
        demands, _ = generate_demand(
            user=self.user, order_id=order.pk, authorization={"allowed": True}, return_all=True,
        )
        self.assertEqual(len(demands), 2)
        self.assertEqual({value.sales_order_item_id for value in demands},
                         set(order.items.values_list("id", flat=True)))

    def test_12_readiness_and_input_reference_use_stable_foreign_keys(self):
        self._release_engineering()
        payload = self._order_payload([{
            "materialId": self.finished.pk, "quantity": "1",
            "productDefinitionId": self.product.pk,
            "productVersionId": self.product_version.pk,
            "manufacturingOutputId": self.output.pk,
        }])
        order, item, _ = create_order(user=self.user, payload=payload, authorization={"allowed": True}, business_purpose=SalesOrder.BusinessPurpose.FORMAL_SALE)
        confirm_order(user=self.user, order_id=order.pk, authorization={"allowed": True})
        demand, _ = generate_demand(user=self.user, order_id=order.pk, authorization={"allowed": True})
        readiness = ProductEngineeringReadiness.objects.get(sales_order_item=item)
        reference = ManufacturingInputReference.objects.get(target_demand=demand)
        self.assertEqual(readiness.sales_order_id, order.pk)
        self.assertEqual(reference.source_manufacturing_output_id, self.output.pk)

    def test_13_direct_planning_history_has_explicit_compatibility_metadata(self):
        demand = Demand.objects.create(
            demand_no="DM-A15-H", source_type="manual_demand",
            source_document_type="ManualDemand", source_document_id="H", source_document_no="H",
            material=self.raw, required_qty=2, required_date=date.today(),
            department=self.department, reason="历史兼容", created_by=self.user,
        )
        requirement = PlanningRequirement.objects.create(
            requirement_no="REQ-A15-H", demand=demand, material=self.raw,
            demand_qty=2, available_qty=0, net_required_qty=2,
            required_date=date.today(), supply_type="purchase", created_by=self.user,
        )
        plan = PurchasePlan(
            plan_no="PP-A15-H", planning_requirement=requirement, material=self.raw,
            required_qty=2, available_qty=0, net_required_qty=2,
            required_date=date.today(), source_id=str(requirement.pk), confirmed_by=self.user,
            planning_engine="DIRECT_V1", run_batch="DIRECT-H", source_version="DIRECT-V1",
        )
        plan.full_clean(); plan.save()
        self.assertEqual(plan.planning_engine, "DIRECT_V1")
        self.assertFalse(plan.mps_source_id or plan.mrp_source_id)

    def test_14_legacy_inventory_balance_remains_dimensionless_and_readable(self):
        balance = InventoryBalance.objects.create(
            warehouse=self.warehouse, material=self.raw, quantity=Decimal("7"),
        )
        balance.full_clean()
        self.assertIsNone(balance.location_id)
        self.assertIsNone(balance.lot_id)

    def test_15_location_and_lot_are_traceable_in_same_inventory_balance(self):
        location = WarehouseLocation.objects.create(
            warehouse=self.warehouse, code="A15-L01", name="验收库位",
        )
        lot = InventoryLot(
            lot_no="A15-LOT", material=self.raw, company_id=self.company.pk,
            warehouse=self.warehouse,
        )
        lot.full_clean(); lot.save()
        balance = InventoryBalance(
            warehouse=self.warehouse, material=self.raw, location=location,
            lot=lot, quantity=Decimal("3"),
        )
        balance.full_clean(); balance.save()
        client = APIClient(); client.force_authenticate(self.user)
        response = client.get("/api/procurement/formal-inventory-facts/")
        row = next(value for value in response.data["balances"] if value["id"] == balance.pk)
        self.assertEqual((row["locationCode"], row["lotNo"]), ("A15-L01", "A15-LOT"))

    def test_16_unprivileged_maintenance_is_rejected_before_write(self):
        denied = User.objects.create_user(
            username="a15_denied", password="test-only", company_id=self.company.pk,
        )
        with self.assertRaises(ProductionFoundationError):
            ProductionFoundationService.save(
                "product-categories", user=denied,
                payload={"company_id": self.company.pk, "code": "DENIED", "name": "禁止写入"},
            )
        self.assertFalse(ProductCategory.objects.filter(code="DENIED").exists())

    def test_17_formal_quality_facts_have_zero_browser_inventory_writes(self):
        client = APIClient(); client.force_authenticate(self.user)
        response = client.get("/api/procurement/formal-quality-facts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["localStorageFormalWriteCount"], 0)
        self.assertFalse(response.data["demoFixtureIncluded"])

    def test_18_industry_data_gate_preserves_a15_and_adds_a17_checks(self):
        client = APIClient(); client.force_authenticate(self.user)
        response = client.get("/api/pde/a1-foundation/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["industryDataEntryGate"]), 20)
        self.assertEqual(
            [row["id"] for row in response.data["industryDataEntryGate"]],
            list(range(1, 21)),
        )
        self.assertEqual(response.data["legacyLocalStorageFormalFactCount"], 0)
        self.assertEqual(response.data["a2Status"], "NOT_ENTERED")

    def _create_direct_order_header(self, number):
        from sales.models import SalesOrder
        return create_business_object_with_initial_state(
            model=SalesOrder, initial_state="draft",
            company=self.company, department=self.department, customer=self.customer,
            order_no=number, order_date=date.today(), required_delivery_date=date.today(),
            created_by=self.user,
        )
