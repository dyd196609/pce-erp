from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from masterdata.models import Material, UnitOfMeasure
from pde.models import (
    BOMItem, BOMVersion, EngineeringDocument, EngineeringDocumentVersion,
    ProductBOM, ProductCategory, ProductDefinition, ProductManufacturingOutput,
    ProductVersion, Routing, RoutingVersion,
)
from pfm.models import Employee
from procurement.models import InventoryBalance, PurchaseOrder, PurchaseRequest, Warehouse
from sales.models import Customer, SalesOrder, SalesOrderItem
from sales.services import ORDER_ALLOWED_TRANSITIONS, SalesBusinessError, generate_demand
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position,
    PositionWorkflowResponsibility, Responsibility, Role, RolePermission, User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state, transition_business_object,
)

from .models import (
    Demand, MPSDemandAllocation, MasterProductionScheduleLine,
    MaterialRequirementProposal, MaterialRequirementsPlanningRun,
    PlanningRequirement, ProductionPlan, PurchasePlan,
)
from .services import generate_mps_proposal, generate_mrp_proposal
from .views import MPSGenerateView, MRPGenerateView, PlanningFactsView


class OrderPlanningChainV1Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="OPV1", name="订单计划测试公司")
        cls.department = Department.objects.create(
            company=cls.company, code="PLAN-OPV1", name="订单计划部", is_active=True,
        )
        cls.position = Position.objects.create(
            company=cls.company, department=cls.department,
            code="PLAN-OPV1", name="订单计划岗", is_active=True,
        )
        cls.user = User.objects.create_user(
            username="order_planner_v1", password="test-only", real_name="订单计划员",
            company_id=cls.company.pk, is_active=True,
        )
        cls.denied_user = User.objects.create_user(
            username="order_planner_denied_v1", password="test-only", real_name="无计划权限用户",
            company_id=cls.company.pk, is_active=True,
        )
        Employee.objects.create(
            user=cls.user, employee_no="EMP-OPV1", full_name="订单计划员", status="active",
            department_ref=cls.department, position_ref=cls.position,
        )
        role = Role.objects.create(code="ORDER_PLAN_TEST", name="订单计划测试角色")
        for code in ("planning.view", "planning.mps.generate", "planning.mrp.generate"):
            permission, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"name": f"测试权限 {code}", "module": "PLAN"},
            )
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=cls.user, role=role, organization=cls.company,
            scope_code="ORGANIZATION", active=True, version=1, business_hash="order-plan-test",
        )
        process, _ = ProcessDefinition.objects.update_or_create(
            definition_code="SALES_ORDER_TO_SUPPLY_PLAN",
            defaults={
                "definition_name": "订单计划测试流程", "business_domain": "SALES/PLAN",
                "document_type": "SalesOrder", "version": 1, "active": True,
                "definition_hash": "order-plan-v1",
            },
        )
        responsibility, _ = Responsibility.objects.update_or_create(
            code="RESP_SALES_ORDER_002",
            defaults={"name": "销售需求与订单协调", "status": "ACTIVE", "is_active": True},
        )
        node, _ = WorkflowNodeDefinition.objects.update_or_create(
            process_definition=process, node_code="ORDER_DEMAND_OPV1",
            defaults={
                "node_name": "形成订单计划需求", "sequence": 500,
                "business_action_code": "sales.order.generate_demand", "active": True,
            },
        )
        PositionWorkflowResponsibility.objects.create(
            position=cls.position, responsibility=responsibility, workflow_node=node,
            workflow_code=process.definition_code, node_code=node.node_code,
            ownership_type="OWNER", active=True,
        )
        cls.uom = UnitOfMeasure.objects.create(
            company_id=cls.company.pk, code="EA-OPV1", name="件", is_active=True,
        )
        cls.finished = Material.objects.create(
            code="FG-OPV1", name="订单计划成品", unit="件", base_uom=cls.uom,
            material_type="finished", company_id=cls.company.pk, is_active=True,
            is_purchased=False, is_produced=True,
        )
        cls.buy = Material.objects.create(
            code="BUY-OPV1", name="外购材料", unit="件", base_uom=cls.uom,
            material_type="raw", company_id=cls.company.pk, is_active=True,
            is_purchased=True, is_produced=False,
        )
        cls.make = Material.objects.create(
            code="MAKE-OPV1", name="自制部件", unit="件", base_uom=cls.uom,
            material_type="semi", company_id=cls.company.pk, is_active=True,
            is_purchased=False, is_produced=True,
        )
        cls.unresolved = Material.objects.create(
            code="UNRES-OPV1", name="待定部件", unit="件", base_uom=cls.uom,
            material_type="semi", company_id=cls.company.pk, is_active=True,
            is_purchased=False, is_produced=False,
        )
        category = ProductCategory.objects.create(
            company=cls.company, code="CAT-OPV1", name="订单计划产品",
        )
        cls.product = ProductDefinition.objects.create(
            company=cls.company, category=category, material=cls.finished,
            product_code="PROD-OPV1", product_name="订单计划产品",
            emd_material_code=cls.finished.code, manufacturing_definition_mode="standard",
            status="released",
        )
        cls.product_version = ProductVersion.objects.create(
            product=cls.product, version_no="V1", version_status="released",
        )
        bom = ProductBOM.objects.create(
            company=cls.company, product=cls.product, bom_code="BOM-OPV1",
            name="订单计划BOM", status="released",
        )
        cls.bom_version = BOMVersion.objects.create(
            product=cls.product, product_version=cls.product_version, bom=bom,
            bom_version="V1", status="released",
        )
        for line_no, material, quantity, supply_type in (
            (10, cls.buy, "2", "BUY"),
            (20, cls.make, "3", "MAKE"),
            (30, cls.unresolved, "1", "MAKE_OR_BUY"),
        ):
            BOMItem.objects.create(
                bom_version=cls.bom_version, line_no=line_no, material=material,
                quantity=Decimal(quantity), uom=cls.uom, supply_type=supply_type,
                scrap_rate_status="maintained", scrap_rate=Decimal("0"),
            )
        routing = Routing.objects.create(
            company=cls.company, product=cls.product, routing_code="ROUTE-OPV1",
            name="订单计划工艺", status="released",
        )
        routing_version = RoutingVersion.objects.create(
            product=cls.product, product_version=cls.product_version,
            routing=routing, routing_version="V1", status="released",
        )
        document = EngineeringDocument.objects.create(
            document_no="DOC-OPV1", document_name="订单计划工程资料",
            document_type="technical", product=cls.product, product_bom=bom,
            routing=routing, status="released",
        )
        document_version = EngineeringDocumentVersion.objects.create(
            document=document, document_name=document.document_name, document_version="V1",
            product_version=cls.product_version, related_product=cls.product,
            related_bom=cls.bom_version, related_routing=routing_version, status="released",
        )
        cls.output = ProductManufacturingOutput.objects.create(
            product=cls.product, product_version=cls.product_version,
            bom_version=cls.bom_version, routing_version=routing_version,
            engineering_document_version=document_version, definition_mode="standard",
            engineering_status="ready", release_status="released_to_manufacturing",
        )
        cls.customer = Customer.objects.create(
            company=cls.company, code="CUST-OPV1", name="订单计划客户",
        )
        warehouse = Warehouse.objects.create(
            company_id=cls.company.pk, code="WH-OPV1", name="订单计划仓", is_active=True,
        )
        InventoryBalance.objects.create(
            warehouse=warehouse, material=cls.buy, quantity=Decimal("1"),
        )

    def make_order(self, no, quantity, *, ready=True):
        required_date = date.today() + timedelta(days=14)
        with transaction.atomic():
            order = create_business_object_with_initial_state(
                model=SalesOrder, initial_state="draft", company=self.company,
                department=self.department, customer=self.customer, order_no=no,
                order_date=date.today(), required_delivery_date=required_date,
                created_by=self.user,
            )
            for source, target in (
                ("draft", "confirmed"), ("confirmed", "engineering"),
                ("engineering", "manufacturing_ready"),
            ):
                transition_business_object(
                    business_object=order, object_type="SalesOrder",
                    source_state=source, target_state=target,
                    action_code=f"test.{target}", operator=self.user,
                    reason="订单计划隔离测试", audit_reference=f"test:{no}:{target}",
                    allowed_transitions=ORDER_ALLOWED_TRANSITIONS,
                )
        item = SalesOrderItem.objects.create(
            sales_order=order, line_no=10, material=self.finished,
            product_definition=self.product, product_version=self.product_version,
            manufacturing_output=self.output if ready else None,
            engineering_mode="STANDARD", quantity=Decimal(quantity), uom=self.uom,
            required_date=required_date,
        )
        return order, item

    def test_unready_order_is_blocked_before_demand(self):
        order, _ = self.make_order("SO-OPV1-BLOCK", "1", ready=False)
        with self.assertRaisesMessage(SalesBusinessError, "制造准备未就绪"):
            generate_demand(user=self.user, order_id=order.pk, authorization={"allowed": True})
        self.assertEqual(Demand.objects.count(), 0)

    def test_ready_demands_aggregate_to_mps_and_explode_to_traceable_mrp(self):
        order_a, item_a = self.make_order("SO-OPV1-A", "2")
        order_b, item_b = self.make_order("SO-OPV1-B", "3")
        demand_a, _ = generate_demand(
            user=self.user, order_id=order_a.pk, authorization={"allowed": True},
        )
        demand_b, _ = generate_demand(
            user=self.user, order_id=order_b.pk, authorization={"allowed": True},
        )
        repeated, repeated_audit = generate_demand(
            user=self.user, order_id=order_a.pk, authorization={"allowed": True},
        )
        self.assertEqual(repeated.pk, demand_a.pk)
        self.assertIsNone(repeated_audit)
        self.assertEqual(demand_a.sales_order_item_id, item_a.pk)
        self.assertEqual(demand_b.sales_order_item_id, item_b.pk)

        mps, mps_audit, idempotent = generate_mps_proposal(
            user=self.user,
            payload={"requestId": "REQ-MPS-1", "idempotencyKey": "IDEM-MPS-1"},
            authorization={"allowed": True},
        )
        self.assertFalse(idempotent)
        self.assertEqual(mps.lines.count(), 1)
        line = MasterProductionScheduleLine.objects.get(run=mps)
        self.assertEqual(line.total_qty, Decimal("5"))
        self.assertEqual(MPSDemandAllocation.objects.filter(mps_line=line).count(), 2)
        repeated_mps, no_audit, idempotent = generate_mps_proposal(
            user=self.user,
            payload={"requestId": "REQ-MPS-1", "idempotencyKey": "IDEM-MPS-1"},
            authorization={"allowed": True},
        )
        self.assertTrue(idempotent)
        self.assertEqual(repeated_mps.pk, mps.pk)
        self.assertIsNone(no_audit)

        mrp, mrp_audit, idempotent = generate_mrp_proposal(
            user=self.user, mps_run_id=mps.pk,
            payload={"requestId": "REQ-MRP-1", "idempotencyKey": "IDEM-MRP-1"},
            authorization={"allowed": True},
        )
        self.assertFalse(idempotent)
        self.assertEqual(mrp.status, "blocked")
        proposals = MaterialRequirementProposal.objects.filter(mrp_run=mrp)
        self.assertEqual(proposals.count(), 6)
        self.assertEqual(set(proposals.values_list("supply_type", flat=True)), {"MAKE", "BUY", "UNRESOLVED"})
        self.assertTrue(all(value.source_bom_version_id == self.bom_version.pk for value in proposals))
        self.assertTrue(all(value.trace_facts["salesOrderItemId"] in {item_a.pk, item_b.pk} for value in proposals))
        self.assertEqual(InventoryBalance.objects.get(material=self.buy).quantity, Decimal("1"))
        self.assertEqual(PurchaseOrder.objects.count(), 0)
        self.assertEqual(PurchaseRequest.objects.count(), 0)
        self.assertIsNotNone(mps_audit)
        self.assertIsNotNone(mrp_audit)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(
            action_code__in=["planning.mps.generate", "planning.mrp.generate"],
        ).count(), 2)

        repeated_mrp, no_audit, idempotent = generate_mrp_proposal(
            user=self.user, mps_run_id=mps.pk,
            payload={"requestId": "REQ-MRP-1", "idempotencyKey": "IDEM-MRP-1"},
            authorization={"allowed": True},
        )
        self.assertTrue(idempotent)
        self.assertEqual(repeated_mrp.pk, mrp.pk)
        self.assertIsNone(no_audit)
        self.assertEqual(MaterialRequirementsPlanningRun.objects.count(), 1)

    def test_mps_api_denies_user_without_formal_permission(self):
        request = APIRequestFactory().post(
            "/api/planning/mps/runs/",
            {"requestId": "DENIED", "idempotencyKey": "DENIED"}, format="json",
        )
        force_authenticate(request, user=self.denied_user)
        response = MPSGenerateView.as_view()(request)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "PERMISSION_DENIED")

    def test_planning_facts_use_formal_permission_and_project_two_order_lines_once(self):
        order_a, item_a = self.make_order("SO-OPV1-FACT-A", "2")
        order_b, item_b = self.make_order("SO-OPV1-FACT-B", "3")
        demand_a, _ = generate_demand(
            user=self.user, order_id=order_a.pk, authorization={"allowed": True},
        )
        demand_b, _ = generate_demand(
            user=self.user, order_id=order_b.pk, authorization={"allowed": True},
        )
        requirement_a = PlanningRequirement.objects.create(
            requirement_no="REQ-OPV1-FACT-A", demand=demand_a, material=self.product.material,
            demand_qty=Decimal("2"), available_qty=Decimal("0"), net_required_qty=Decimal("2"),
            required_date=demand_a.required_date, supply_type="purchase", status="confirmed",
            calculation_facts={"inventorySource": "procurement.InventoryBalance"}, created_by=self.user,
        )
        requirement_b = PlanningRequirement.objects.create(
            requirement_no="REQ-OPV1-FACT-B", demand=demand_b, material=self.product.material,
            demand_qty=Decimal("3"), available_qty=Decimal("0"), net_required_qty=Decimal("3"),
            required_date=demand_b.required_date, supply_type="production", status="confirmed",
            calculation_facts={"inventorySource": "procurement.InventoryBalance"}, created_by=self.user,
        )
        PurchasePlan.objects.create(
            plan_no="PP-OPV1-FACT-A", planning_requirement=requirement_a,
            material=self.product.material, required_qty=Decimal("2"), available_qty=Decimal("0"),
            net_required_qty=Decimal("2"), required_date=demand_a.required_date,
            source_id=str(requirement_a.pk), status="released", confirmed_by=self.user,
        )
        ProductionPlan.objects.create(
            plan_no="MP-OPV1-FACT-B", planning_requirement=requirement_b,
            material=self.product.material, planned_qty=Decimal("3"), required_date=demand_b.required_date,
            source_id=str(requirement_b.pk), status="confirmed", confirmed_by=self.user,
        )

        denied_request = APIRequestFactory().get("/api/planning/facts/")
        force_authenticate(denied_request, user=self.denied_user)
        denied = PlanningFactsView.as_view()(denied_request)
        self.assertEqual(denied.status_code, 403)

        request = APIRequestFactory().get("/api/planning/facts/")
        force_authenticate(request, user=self.user)
        response = PlanningFactsView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["factLoadFacts"]["factLoadStatus"], "loaded")
        order_demands = [row for row in data["demands"] if row["sourceType"] == "sales_order"]
        self.assertEqual(len(order_demands), 2)
        self.assertEqual({row["salesOrderItemId"] for row in order_demands}, {item_a.pk, item_b.pk})
        self.assertEqual({row["uomCode"] for row in order_demands}, {self.uom.code})
        self.assertEqual({row["planType"] for row in order_demands}, {"PurchasePlan", "ProductionPlan"})
        self.assertEqual({row["plannedQty"] for row in order_demands}, {"2.0000", "3.0000"})
        self.assertEqual({row["pendingPlanQty"] for row in order_demands}, {"0.0000"})
        self.assertEqual({row["planStatus"] for row in order_demands}, {"released", "confirmed"})

    def test_mps_and_mrp_success_api_preserve_proposal_only_boundary(self):
        order, _ = self.make_order("SO-OPV1-API", "2")
        generate_demand(
            user=self.user, order_id=order.pk, authorization={"allowed": True},
        )
        request = APIRequestFactory().post(
            "/api/planning/mps/runs/",
            {"requestId": "REQ-MPS-API", "idempotencyKey": "IDEM-MPS-API"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = MPSGenerateView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        mps_run_id = response.data["data"]["mpsRun"]["id"]

        request = APIRequestFactory().post(
            f"/api/planning/mps/runs/{mps_run_id}/mrp/",
            {"requestId": "REQ-MRP-API", "idempotencyKey": "IDEM-MRP-API"},
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = MRPGenerateView.as_view()(request, mps_run_id=mps_run_id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["mrpRun"]["proposals"])
        self.assertEqual(PurchaseOrder.objects.count(), 0)
        self.assertEqual(PurchaseRequest.objects.count(), 0)
