from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from masterdata.models import Material
from pfm.models import Employee
from procurement.models import InventoryBalance, PurchaseRequest, Warehouse
from system.models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Permission,
    Position,
    PositionWorkflowResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition

from .models import Demand, PlanningRequirement, ProductionPlan, PurchasePlan
from .views import (
    DemandCreateView,
    PlanningFactsView,
    PlanningTraceView,
    PlanningValidationView,
    PurchasePlanConvertView,
    RequirementCalculateView,
    SupplyPlanConfirmView,
)


class PlanningMainChainV1Tests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.company = Company.objects.create(code="PCE", name="PCE测试公司")
        self.department = Department.objects.create(
            company=self.company, code="JHWKB", name="计划物控部", is_active=True
        )
        self.user = User.objects.create_user(
            username="pce_plan_test", password="test-only", real_name="计划验收员",
            company_id=self.company.pk, is_active=True,
        )
        role = Role.objects.create(code="PLAN_OPERATOR_TEST", name="计划运行测试角色")
        for code in (
            "planning.view",
            "planning.demand.create",
            "planning.requirement.calculate",
            "planning.purchase_plan.confirm",
            "planning.production_plan.confirm",
        ):
            permission, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"name": f"测试权限 {code}", "module": "PLAN"},
            )
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=self.user, role=role, organization=self.company,
            scope_code="ORGANIZATION", active=True, version=1, business_hash="test",
        )
        self.material = Material.objects.create(
            code="MT-PLAN-P", name="计划采购件", unit="件", material_type="auxiliary",
            company_id=self.company.pk, is_active=True, is_purchased=True, is_produced=False,
        )
        self.warehouse = Warehouse.objects.create(
            code="WH-PLAN", name="计划测试仓", company_id=self.company.pk, is_active=True
        )
        self.balance = InventoryBalance.objects.create(
            warehouse=self.warehouse, material=self.material, quantity=Decimal("2")
        )

    def request(self, method, path, data=None):
        request = getattr(self.factory, method)(path, data or {}, format="json")
        force_authenticate(request, user=self.user)
        return request

    def test_purchase_plan_chain_uses_inventory_without_changing_it(self):
        create_response = DemandCreateView.as_view()(self.request("post", "/api/planning/demands/", {
            "materialId": self.material.pk,
            "departmentId": self.department.pk,
            "requiredQty": "5",
            "requiredDate": "2026-09-15",
            "reason": "系统流程验收数据",
            "acceptanceMarker": "PCE-PLAN-V1",
        }))
        self.assertEqual(create_response.status_code, 200)
        demand_id = create_response.data["data"]["demand"]["id"]

        calculation_response = RequirementCalculateView.as_view()(
            self.request("post", f"/api/planning/demands/{demand_id}/calculate/"),
            demand_id=demand_id,
        )
        self.assertEqual(calculation_response.status_code, 200)
        requirement = calculation_response.data["data"]["requirement"]
        self.assertEqual(requirement["demandQty"], "5.0000")
        self.assertEqual(requirement["availableQty"], "2.0000")
        self.assertEqual(requirement["netRequiredQty"], "3.0000")
        self.assertEqual(requirement["supplyType"], "purchase")

        confirmation_response = SupplyPlanConfirmView.as_view()(
            self.request("post", f"/api/planning/requirements/{requirement['id']}/confirm-plan/"),
            requirement_id=requirement["id"],
        )
        self.assertEqual(confirmation_response.status_code, 200)
        self.assertEqual(confirmation_response.data["data"]["plan"]["type"], "PurchasePlan")
        self.assertEqual(PurchasePlan.objects.get().net_required_qty, Decimal("3"))
        self.assertEqual(ProductionPlan.objects.count(), 0)

        self.balance.refresh_from_db()
        self.assertEqual(self.balance.quantity, Decimal("2"))

        validation_response = PlanningValidationView.as_view()(
            self.request("get", f"/api/planning/requirements/{requirement['id']}/validate/"),
            requirement_id=requirement["id"],
        )
        self.assertEqual(validation_response.status_code, 200)
        validation = validation_response.data["data"]["validation"]
        self.assertTrue(all(validation[key] for key in (
            "sourceComplete", "materialValid", "inventoryRead", "netRequirementCorrect",
            "supplyTypeValid", "planQuantityCorrect", "sourceTraceComplete", "readOnly",
        )))
        self.assertEqual(validation_response.data["data"]["facts"]["businessWriteCount"], 0)

        trace_response = PlanningTraceView.as_view()(
            self.request("get", "/api/planning/trace/", {"reference": PurchasePlan.objects.get().plan_no})
        )
        self.assertEqual(trace_response.status_code, 200)
        self.assertEqual(len(trace_response.data["data"]["traces"]), 1)
        self.assertTrue(trace_response.data["data"]["traces"][0]["bidirectional"])
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(
            action_code__startswith="planning."
        ).count(), 4)

    def test_ambiguous_supply_facts_do_not_guess_a_plan(self):
        material = Material.objects.create(
            code="MT-PLAN-A", name="供应属性歧义件", unit="件", material_type="finished",
            company_id=self.company.pk, is_active=True, is_purchased=False, is_produced=False,
        )
        demand = Demand.objects.create(
            demand_no="DM-AMB", source_type="manual_demand", source_document_type="ManualDemand",
            source_document_id="1", source_document_no="DM-AMB", material=material,
            required_qty=Decimal("4"), required_date="2026-09-15", department=self.department,
            reason="供应属性歧义测试", status="confirmed", created_by=self.user,
        )
        requirement = PlanningRequirement.objects.create(
            requirement_no="REQ-AMB", demand=demand, material=material,
            demand_qty=Decimal("4"), available_qty=Decimal("0"), net_required_qty=Decimal("4"),
            required_date="2026-09-15", supply_type="ambiguous", status="calculated",
            calculation_facts={"inventorySource": "procurement.InventoryBalance"}, created_by=self.user,
        )
        response = SupplyPlanConfirmView.as_view()(
            self.request("post", f"/api/planning/requirements/{requirement.pk}/confirm-plan/"),
            requirement_id=requirement.pk,
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "SUPPLY_TYPE_AMBIGUOUS")
        self.assertEqual(PurchasePlan.objects.count(), 0)
        self.assertEqual(ProductionPlan.objects.count(), 0)

    def test_confirmed_purchase_plan_converts_once_through_formal_procurement_authority(self):
        demand = Demand.objects.create(
            demand_no="DM-PP-PR", source_type="manual_demand", source_document_type="ManualDemand",
            source_document_id="101", source_document_no="DM-PP-PR", material=self.material,
            required_qty=Decimal("5"), required_date="2026-09-15", department=self.department,
            reason="计划转采购申请测试", status="confirmed", created_by=self.user,
        )
        requirement = PlanningRequirement.objects.create(
            requirement_no="REQ-PP-PR", demand=demand, material=self.material,
            demand_qty=Decimal("5"), available_qty=Decimal("2"), net_required_qty=Decimal("3"),
            required_date="2026-09-15", supply_type="purchase", status="confirmed",
            calculation_facts={"inventorySource": "procurement.InventoryBalance", "inventoryWriteCount": 0},
            created_by=self.user,
        )
        plan = PurchasePlan.objects.create(
            plan_no="PP-PP-PR", planning_requirement=requirement, material=self.material,
            required_qty=Decimal("5"), available_qty=Decimal("2"), net_required_qty=Decimal("3"),
            required_date="2026-09-15", source_id=str(requirement.pk), status="confirmed",
            confirmed_by=self.user,
        )
        purchase_department = Department.objects.create(
            company=self.company, code="CGB-T", name="采购测试部", is_active=True,
        )
        permission, _ = Permission.objects.get_or_create(
            code="procurement.purchase_request.create",
            defaults={"name": "测试权限 procurement.purchase_request.create", "module": "PROCUREMENT"},
        )
        buyer_role = Role.objects.create(code="PLAN_PR_BUYER_TEST", name="计划转申请采购员测试角色")
        RolePermission.objects.create(role=buyer_role, permission=permission)
        position = Position.objects.create(
            company=self.company, department=purchase_department,
            code="PP-PR-BUYER", name="计划转申请采购员测试岗位", default_role=buyer_role,
        )
        buyer = User.objects.create_user(
            username="pce_plan_pr_buyer_test", password="test-only", real_name="采购测试员",
            company_id=self.company.pk, is_active=True,
        )
        Employee.objects.create(
            user=buyer, employee_no="EMP-PP-PR", full_name="采购测试员", status="active",
            department_ref=purchase_department, department_name=purchase_department.name,
            position_ref=position, position=position.name,
        )
        UserRoleScopeAssignment.objects.create(
            user=buyer, role=buyer_role, organization=self.company,
            scope_code="ORGANIZATION", active=True, version=1, business_hash="plan-pr-test",
        )
        process, _ = ProcessDefinition.objects.get_or_create(
            definition_code="PROCUREMENT_PURCHASE_REQUEST_TO_ORDER",
            defaults={
                "definition_name": "采购申请至采购订单测试流程", "business_domain": "SCM",
                "document_type": "PurchaseRequest", "version": 1, "active": True,
                "definition_hash": "plan-pr-test",
            },
        )
        node, _ = WorkflowNodeDefinition.objects.get_or_create(
            process_definition=process, node_code="CREATE_PURCHASE_REQUEST",
            defaults={
                "node_name": "创建采购申请", "sequence": 10,
                "business_action_code": "procurement.purchase_request.create", "active": True,
            },
        )
        responsibility = Responsibility.objects.create(
            code="PLAN_PR_RESP_TEST", name="计划转申请测试职责",
            status=Responsibility.Status.ACTIVE, is_active=True,
        )
        PositionWorkflowResponsibility.objects.create(
            position=position, responsibility=responsibility, workflow_node=node,
            workflow_code=node.process_definition.definition_code, node_code=node.node_code,
            ownership_type=PositionWorkflowResponsibility.OwnershipType.EXECUTOR, active=True,
        )

        denied_request = self.request(
            "post", f"/api/planning/purchase-plans/{plan.pk}/convert-to-purchase-request/"
        )
        denied = PurchasePlanConvertView.as_view()(denied_request, purchase_plan_id=plan.pk)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(PurchaseRequest.objects.count(), 0)

        request = self.factory.post(
            f"/api/planning/purchase-plans/{plan.pk}/convert-to-purchase-request/", {}, format="json"
        )
        force_authenticate(request, user=buyer)
        response = PurchasePlanConvertView.as_view()(request, purchase_plan_id=plan.pk)
        self.assertEqual(response.status_code, 200)
        purchase_request = PurchaseRequest.objects.get(source_purchase_plan=plan)
        self.assertEqual(purchase_request.quantity, Decimal("3"))
        self.assertEqual(purchase_request.request_items.get().quantity, Decimal("3"))
        self.assertEqual(purchase_request.source_type, "PurchasePlan")
        self.assertEqual(purchase_request.status, "draft")
        plan.refresh_from_db()
        self.assertEqual(plan.status, "released")
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.quantity, Decimal("2"))

        repeated_request = self.factory.post(
            f"/api/planning/purchase-plans/{plan.pk}/convert-to-purchase-request/", {}, format="json"
        )
        force_authenticate(repeated_request, user=buyer)
        repeated = PurchasePlanConvertView.as_view()(repeated_request, purchase_plan_id=plan.pk)
        self.assertEqual(repeated.status_code, 409)
        self.assertEqual(repeated.data["error"]["code"], "PURCHASE_PLAN_ALREADY_CONVERTED")
        self.assertEqual(PurchaseRequest.objects.filter(source_purchase_plan=plan).count(), 1)
        audit = OrganizationOperatingAuditRecord.objects.get(
            action_code="procurement.purchase_request.create", target_id=purchase_request.pk,
        )
        self.assertEqual(audit.actor, buyer)
        self.assertEqual(audit.after_snapshot["state"]["remainingQty"], "0.0000")
