from django.test import TestCase
from rest_framework.test import APIClient
import datetime
import jwt
from django.conf import settings

from masterdata.models import (
    BudgetCategory,
    CostCenter,
    ExpenseCategory,
    Material,
    ProjectMaster,
)
from pfm.models import Employee
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Role, RolePermission, User,
    UserRoleScopeAssignment,
)

from .models import PurchaseInquiry, PurchaseOrder, PurchaseRequest
from .serializers import PurchaseRequestSerializer


class PurchaseRequestOrganizationRelationshipV417Tests(TestCase):
    """V1.14.2.8.4.17/18：三类组织独立，组织差异只提示审批风险。"""

    @classmethod
    def setUpTestData(cls):
        company = Company.objects.create(name="V417制造企业", code="V417")
        cls.finance = Department.objects.create(name="财务部", code="FIN", company=company)
        cls.production = Department.objects.create(name="生产部", code="MFG", company=company)
        cls.procurement = Department.objects.create(name="采购部", code="PROC", company=company)
        cls.research = Department.objects.create(name="研发部", code="RND", company=company)
        cls.lab = Department.objects.create(name="实验室", code="LAB", company=company)
        cls.group_procurement = Department.objects.create(
            name="集团采购中心", code="GPROC", company=company
        )
        cls.hr_admin = Department.objects.create(
            name="人力行政部", code="HR", company=company
        )
        cls.finance_employee = Employee.objects.create(
            employee_no="V417-E-FIN",
            full_name="财务申请人",
            status="active",
            department_id=cls.finance.pk,
            department_name=cls.finance.name,
        )
        cls.research_employee = Employee.objects.create(
            employee_no="V417-E-RND",
            full_name="研发申请人",
            status="active",
            department_id=cls.research.pk,
            department_name=cls.research.name,
        )
        cls.procurement_employee = Employee.objects.create(
            employee_no="V417-E-PROC",
            full_name="采购申请人",
            status="active",
            department_id=cls.procurement.pk,
            department_name=cls.procurement.name,
        )
        cls.hr_employee = Employee.objects.create(
            employee_no="V418-E-HR",
            full_name="行政申请人",
            status="active",
            department_id=cls.hr_admin.pk,
            department_name=cls.hr_admin.name,
        )
        cls.approval_user = User.objects.create_user(
            username="v418-approver",
            password="test-only",
            real_name="V418审批测试用户",
            company_id=company.pk,
        )
        role = Role.objects.create(name="V417采购全流程测试角色", code="v417-purchase-flow")
        for code in (
            "procurement.purchase_request.create",
            "purchase_request.submit",
            "purchase_request.approve",
        ):
            permission, _ = Permission.objects.get_or_create(
                code=code, defaults={"name": code, "module": "SCM"}
            )
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=cls.approval_user,
            role=role,
            organization=company,
            scope_code=UserRoleScopeAssignment.ScopeCode.ORGANIZATION,
            active=True,
        )
        cls.cost_center = CostCenter.objects.create(
            code="V417-CC", name="V417成本中心", department=cls.finance
        )
        cls.project = ProjectMaster.objects.create(
            code="V417-PROJECT",
            name="V417项目",
            stage="执行中",
            department=cls.research,
            recommended_cost_center=cls.cost_center,
        )
        cls.expense_category = ExpenseCategory.objects.create(
            code="V417-EXP", name="生产费用"
        )
        cls.budget_category = BudgetCategory.objects.create(
            code="V417-BUD", name="年度预算"
        )
        cls.material = Material.objects.create(
            code="V417-MAT",
            name="V417测试物料",
            specification="标准规格",
            unit="件",
            purchase_unit="件",
            company_id=company.pk,
            is_purchased=True,
        )

    def _payload(self, employee, request_department, usage_department, purchase_department):
        return {
            "requestDate": "2026-08-02",
            "requesterEmployeeId": employee.pk,
            "departmentId": request_department.pk,
            "usageDepartmentId": usage_department.pk,
            "purchaseDepartmentId": purchase_department.pk,
            "projectId": self.project.pk,
            "costCenterId": self.cost_center.pk,
            "expenseCategoryId": self.expense_category.pk,
            "budgetCategoryId": self.budget_category.pk,
            "requestType": "production",
            "purchaseMode": "AGREED_PRICE",
            "sourceType": "ManualRequest",
            "items": [{
                "materialId": self.material.pk,
                "quantity": "1",
                "requiredDate": "2026-08-10",
            }],
        }

    def _save(self, request_no, payload):
        serializer = PurchaseRequestSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer, serializer.save(request_no=request_no, status="draft")

    def test_finance_request_production_usage_procurement_execution_can_save(self):
        serializer, instance = self._save(
            "PR-V417-CASE-1",
            self._payload(
                self.finance_employee,
                self.finance,
                self.production,
                self.procurement,
            ),
        )

        self.assertEqual(instance.department_master, self.finance)
        self.assertEqual(instance.usage_department_master, self.production)
        self.assertEqual(instance.purchase_department_master, self.procurement)
        self.assertEqual(serializer.data["organizationRisk"]["level"], "none")
        self.assertFalse(instance.inquiries.exists())

    def test_research_request_lab_usage_group_procurement_can_save(self):
        serializer, instance = self._save(
            "PR-V417-CASE-2",
            self._payload(
                self.research_employee,
                self.research,
                self.lab,
                self.group_procurement,
            ),
        )

        self.assertEqual(instance.department_master, self.research)
        self.assertEqual(instance.usage_department_master, self.lab)
        self.assertEqual(instance.purchase_department_master, self.group_procurement)
        self.assertEqual(serializer.data["organizationRisk"]["level"], "none")
        self.assertFalse(instance.inquiries.exists())

    def test_same_non_procurement_department_can_save_and_submit_with_warning(self):
        serializer, instance = self._save(
            "PR-V418-CASE-2",
            self._payload(
                self.hr_employee,
                self.hr_admin,
                self.hr_admin,
                self.hr_admin,
            ),
        )

        save_risk = serializer.data["organizationRisk"]
        self.assertEqual(save_risk["code"], "NON_STANDARD_PURCHASE_ORGANIZATION")
        self.assertEqual(save_risk["level"], "warning")
        self.assertFalse(save_risk["blocking"])
        client = APIClient()
        client.force_authenticate(user=self.approval_user)
        response = client.post(
            f"/api/procurement/purchase-requests/{instance.pk}/submit/",
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "submitted")
        self.assertEqual(
            response.data["organizationRisk"]["code"],
            "NON_STANDARD_PURCHASE_ORGANIZATION",
        )
        instance.refresh_from_db()
        self.assertEqual(instance.status, "submitted")
        self.assertFalse(instance.inquiries.exists())

    def test_v11428781_target_draft_request_submits_with_authenticated_user(self):
        _, instance = self._save(
            "PR202608020008",
            self._payload(
                self.finance_employee,
                self.finance,
                self.production,
                self.procurement,
            ),
        )
        client = APIClient()
        client.force_authenticate(user=self.approval_user)

        response = client.post(
            f"/api/procurement/purchase-requests/{instance.pk}/submit/",
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["requestNo"], "PR202608020008")
        self.assertEqual(response.data["status"], "submitted")
        instance.refresh_from_db()
        self.assertEqual(instance.status, "submitted")
        self.assertEqual(instance.approval_records.filter(action="submit").count(), 1)
        self.assertFalse(instance.inquiries.exists())

    def test_v11428782_target_request_completes_submit_and_approve_closure(self):
        _, instance = self._save(
            "PR202608020008",
            self._payload(self.finance_employee, self.finance, self.production, self.procurement),
        )
        client = APIClient()
        client.force_authenticate(user=self.approval_user)

        submit_response = client.post(f"/api/procurement/purchase-requests/{instance.pk}/submit/", format="json")
        approve_response = client.post(f"/api/procurement/purchase-requests/{instance.pk}/approve/", format="json")

        self.assertEqual(submit_response.status_code, 200, submit_response.data)
        self.assertEqual(submit_response.data["status"], "submitted")
        self.assertEqual(approve_response.status_code, 200, approve_response.data)
        self.assertEqual(approve_response.data["status"], "approved")
        self.assertEqual(approve_response.data["approvalStatus"], "completed")
        instance.refresh_from_db()
        self.assertEqual(instance.status, "approved")
        self.assertEqual(instance.approval_status, "completed")
        self.assertEqual(instance.approval_records.count(), 2)
        self.assertEqual(
            OrganizationOperatingAuditRecord.objects.filter(
                target_type="PurchaseRequest",
                target_id=instance.pk,
                action_code__in=["purchase_request.submit", "purchase_request.approve"],
            ).count(),
            2,
        )
        self.assertFalse(instance.inquiries.exists())

    def test_v11428818_authenticated_create_returns_complete_purchase_request_and_is_listed(self):
        client = APIClient()
        token = jwt.encode({
            "user_id": self.approval_user.pk,
            "username": self.approval_user.username,
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10),
        }, settings.JWT_SECRET_KEY, algorithm="HS256")
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = client.post(
            "/api/procurement/purchase-requests/",
            self._payload(self.finance_employee, self.finance, self.production, self.procurement),
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["requestNo"].startswith("PR"))
        self.assertEqual(response.data["status"], "draft")
        self.assertEqual(response.data["requester"], self.finance_employee.full_name)
        self.assertEqual(response.data["department"], self.finance.name)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(
            OrganizationOperatingAuditRecord.objects.filter(
                action_code="procurement.purchase_request.create",
                target_type="PurchaseRequest",
                target_id=response.data["id"],
            ).count(),
            1,
        )
        listed = client.get("/api/procurement/purchase-requests/")
        self.assertEqual(listed.status_code, 200)
        listed_rows = listed.data.get("results", listed.data)
        self.assertTrue(any(row["requestNo"] == response.data["requestNo"] for row in listed_rows))

    def test_v11428782_batch_three_submit_and_approve_through_protected_endpoints(self):
        instances = [
            self._save(
                f"PR-V11428782-BATCH-{index}",
                self._payload(self.finance_employee, self.finance, self.production, self.procurement),
            )[1]
            for index in range(1, 4)
        ]
        client = APIClient()
        client.force_authenticate(user=self.approval_user)

        submit_responses = [client.post(f"/api/procurement/purchase-requests/{row.pk}/submit/", format="json") for row in instances]
        approve_responses = [client.post(f"/api/procurement/purchase-requests/{row.pk}/approve/", format="json") for row in instances]

        self.assertTrue(all(response.status_code == 200 and response.data["status"] == "submitted" for response in submit_responses))
        self.assertTrue(all(response.status_code == 200 and response.data["status"] == "approved" for response in approve_responses))
        self.assertTrue(all(response.data["approvalStatus"] == "completed" for response in approve_responses))
        for instance in instances:
            instance.refresh_from_db()
            self.assertEqual(instance.status, "approved")
            self.assertEqual(instance.approval_records.count(), 2)
            self.assertFalse(instance.inquiries.exists())

    def test_v11428782_draft_cannot_approve_directly(self):
        _, instance = self._save(
            "PR-V11428782-DIRECT-APPROVE-BLOCKED",
            self._payload(self.finance_employee, self.finance, self.production, self.procurement),
        )
        client = APIClient()
        client.force_authenticate(user=self.approval_user)

        response = client.post(f"/api/procurement/purchase-requests/{instance.pk}/approve/", format="json")

        self.assertEqual(response.status_code, 409, response.data)
        instance.refresh_from_db()
        self.assertEqual(instance.status, "draft")
        self.assertEqual(instance.approval_records.count(), 0)

    def test_unrelated_requester_department_warns_but_does_not_block(self):
        serializer, instance = self._save(
            "PR-V417-CASE-3",
            self._payload(
                self.procurement_employee,
                self.finance,
                self.production,
                self.procurement,
            ),
        )

        risk = serializer.data["organizationRisk"]
        self.assertEqual(risk["code"], "REQUESTER_DEPARTMENT_MISMATCH")
        self.assertEqual(risk["level"], "warning")
        self.assertFalse(risk["blocking"])
        self.assertTrue(risk["requiresApprovalAttention"])
        self.assertEqual(instance.status, "draft")
        self.assertFalse(instance.inquiries.exists())

    def test_invalid_or_missing_department_master_is_still_rejected(self):
        for field in ("departmentId", "usageDepartmentId", "purchaseDepartmentId"):
            with self.subTest(field=field, condition="missing"):
                payload = self._payload(
                    self.finance_employee,
                    self.finance,
                    self.production,
                    self.procurement,
                )
                payload.pop(field)
                self.assertFalse(PurchaseRequestSerializer(data=payload).is_valid())
            with self.subTest(field=field, condition="invalid"):
                payload = self._payload(
                    self.finance_employee,
                    self.finance,
                    self.production,
                    self.procurement,
                )
                payload[field] = 99999999
                self.assertFalse(PurchaseRequestSerializer(data=payload).is_valid())
        self.assertEqual(PurchaseRequest.objects.count(), 0)
        self.assertEqual(PurchaseInquiry.objects.count(), 0)
        self.assertEqual(PurchaseOrder.objects.count(), 0)
