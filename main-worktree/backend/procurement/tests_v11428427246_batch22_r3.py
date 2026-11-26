from datetime import date

from django.test import TestCase

from masterdata.models import BudgetCategory, CostCenter, ExpenseCategory, Material, ProjectMaster
from pfm.models import Employee
from system.models import Company, Department

from .models import PurchaseInquiry, PurchaseRequestItem
from .purchase_inquiry_service import create_purchase_inquiry_from_request, eligible_purchase_request_rows
from .serializers import PurchaseRequestSerializer


class AgreedPricePurchaseRequestR3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(name="R3企业", code="R3")
        cls.request_department = Department.objects.create(name="R3申请部", code="R3-REQ", company=cls.company)
        cls.usage_department = Department.objects.create(name="R3使用部", code="R3-USE", company=cls.company)
        cls.purchase_department = Department.objects.create(name="R3采购部", code="R3-PROC", company=cls.company)
        cls.employee = Employee.objects.create(employee_no="R3-E01", full_name="R3申请人", status="active",
                                               department_id=cls.request_department.pk,
                                               department_name=cls.request_department.name)
        cls.cost_center = CostCenter.objects.create(code="R3-CC", name="R3成本中心", department=cls.request_department)
        cls.project = ProjectMaster.objects.create(code="R3-P", name="R3项目", stage="执行中",
                                                   department=cls.usage_department,
                                                   recommended_cost_center=cls.cost_center)
        cls.expense = ExpenseCategory.objects.create(code="R3-EXP", name="R3费用")
        cls.budget = BudgetCategory.objects.create(code="R3-BUD", name="R3预算")
        cls.materials = [Material.objects.create(code=f"R3-M{index}", name=f"R3物料{index}",
                                                 specification=f"规格{index}", unit="件", purchase_unit="件",
                                                 company_id=cls.company.pk, is_purchased=True)
                         for index in range(1, 4)]

    def payload(self):
        return {
            "requestDate": date.today().isoformat(), "purchaseMode": "AGREED_PRICE",
            "requesterEmployeeId": self.employee.pk, "departmentId": self.request_department.pk,
            "usageDepartmentId": self.usage_department.pk, "purchaseDepartmentId": self.purchase_department.pk,
            "projectId": self.project.pk, "costCenterId": self.cost_center.pk,
            "expenseCategoryId": self.expense.pk, "budgetCategoryId": self.budget.pk,
            "requestType": "production", "sourceType": "ManualRequest",
            "applicationReason": "既定价格采购测试", "purchasePurpose": "生产使用",
            "items": [{"materialId": material.pk, "quantity": str(index + 1),
                       "requiredDate": f"2026-09-0{index + 1}"}
                      for index, material in enumerate(self.materials)],
        }

    def test_agreed_price_creates_one_request_three_material_master_items_without_price(self):
        serializer = PurchaseRequestSerializer(data=self.payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        request = serializer.save(request_no="PR-R3-AGREED-001", status="draft")
        self.assertEqual(request.purchase_mode, "AGREED_PRICE")
        self.assertEqual(request.request_items.count(), 3)
        self.assertTrue(all(row.supplier_material_price_id is None for row in request.request_items.all()))
        self.assertEqual(set(request.request_items.values_list("material_id", flat=True)),
                         set(material.pk for material in self.materials))

    def test_approved_agreed_price_waits_for_price_confirmation_and_cannot_create_inquiry(self):
        serializer = PurchaseRequestSerializer(data=self.payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        request = serializer.save(request_no="PR-R3-AGREED-002", status="approved",
                                  approval_status="completed")
        facts = PurchaseRequestSerializer(request).data["inquiryEligibility"]
        self.assertFalse(facts["eligible"])
        self.assertEqual(facts["nextStatus"], "AGREED_PRICE_PURCHASE_REQUEST_READY_FOR_PRICE_CONFIRMATION")
        with self.assertRaisesMessage(ValueError, "PURCHASE_MODE_NOT_ELIGIBLE_FOR_INQUIRY"):
            create_purchase_inquiry_from_request(request.pk, actor="R3")
        self.assertFalse(any(row["requestId"] == request.pk for row in eligible_purchase_request_rows()))
        self.assertEqual(PurchaseInquiry.objects.count(), 0)
        self.assertEqual(PurchaseRequestItem.objects.filter(purchase_request=request).count(), 3)
