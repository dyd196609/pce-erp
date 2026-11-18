from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from masterdata.models import Material, SupplierMaterialPrice
from pfm.models import Employee
from procurement.models import Supplier
from system.authorization import BusinessPermissionAuthorization, authority_scope_code
from system.models import Company, Department, Permission, Position, Role, RolePermission, User
from workflow_runtime.models import UserOrganizationRoleAuthority


class ErpAccessFoundationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(code="ERP-AUTH", name="ERP权限测试公司")
        cls.department = Department.objects.create(
            code="ERP-PUR", name="采购部", company=cls.company,
        )
        cls.position = Position.objects.create(
            code="ERP-BUYER", name="ERP测试采购员", company=cls.company,
            department=cls.department,
        )
        cls.manual_permission, _ = Permission.objects.get_or_create(
            code="masterdata.supplier_material_price.manual_maintain",
            defaults={"name": "人工维护供应商物料价格", "module": "MASTERDATA"},
        )
        cls.buyer_role = Role.objects.create(code="erp_buyer", name="ERP普通采购员")
        cls.direct_role = Role.objects.create(code="erp_direct", name="ERP直接采购授权人员")
        RolePermission.objects.create(role=cls.direct_role, permission=cls.manual_permission)
        cls.buyer = User.objects.create_user(
            username="erp-buyer", password="test", real_name="普通采购员", company_id=cls.company.pk,
        )
        cls.direct = User.objects.create_user(
            username="erp-direct", password="test", real_name="直接采购授权人员", company_id=cls.company.pk,
        )
        cls.admin = User.objects.create_superuser(
            username="erp-admin", password="test", real_name="管理员", company_id=cls.company.pk,
        )
        cls.buyer_employee = Employee.objects.create(
            user=cls.buyer, employee_no="ERP-E01", full_name="普通采购员",
            department_id=cls.department.pk, department_name=cls.department.name,
            position=cls.position.name, department_ref=cls.department,
            position_ref=cls.position, status="active",
        )
        cls.direct_employee = Employee.objects.create(
            user=cls.direct, employee_no="ERP-E02", full_name="直接采购授权人员",
            department_id=cls.department.pk, department_name=cls.department.name,
            position=cls.position.name, department_ref=cls.department,
            position_ref=cls.position, status="active",
        )
        cls.buyer_authority = UserOrganizationRoleAuthority.objects.create(
            user=cls.buyer, role_code=cls.buyer_role.code,
            legal_entity_id=str(cls.company.pk), department_id="SELF",
            active=True, version=1, business_hash="buyer",
        )
        cls.direct_authority = UserOrganizationRoleAuthority.objects.create(
            user=cls.direct, role_code=cls.direct_role.code,
            legal_entity_id=str(cls.company.pk), department_id="",
            active=True, version=1, business_hash="direct",
        )
        cls.supplier = Supplier.objects.create(
            code="ERP-SUP", name="ERP权限测试供应商", company_id=cls.company.pk, is_active=True,
        )
        cls.material = Material.objects.create(
            code="ERP-MAT", name="ERP权限测试物料", unit="件", company_id=cls.company.pk,
            is_active=True, is_purchased=True,
        )

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_t01_user_is_uniquely_linked_to_employee(self):
        self.assertEqual(self.buyer.employee_profile.pk, self.buyer_employee.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Employee.objects.create(
                user=self.buyer, employee_no="ERP-DUP", full_name="重复关联", status="active",
            )

    def test_t02_employee_has_formal_department(self):
        self.assertEqual(self.buyer_employee.department_ref, self.department)

    def test_t03_employee_has_formal_position(self):
        self.assertEqual(self.buyer_employee.position_ref, self.position)
        self.assertEqual(self.position.department, self.department)

    def test_t04_role_permission_is_persisted_and_unique(self):
        self.assertTrue(RolePermission.objects.filter(
            role=self.direct_role, permission=self.manual_permission,
        ).exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            RolePermission.objects.create(role=self.direct_role, permission=self.manual_permission)

    def test_t05_ordinary_buyer_lacks_manual_price_permission(self):
        decision = BusinessPermissionAuthorization.decide(
            self.buyer, self.manual_permission.code, self.company.pk,
        )
        self.assertFalse(decision["allowed"])

    def test_t06_unauthorized_manual_price_api_returns_403(self):
        response = self.client_for(self.buyer).post(
            "/api/masterdata/prices/supplier-material-prices/runtime/manual-maintenance/",
            {"supplierId": self.supplier.pk, "materialId": self.material.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["errorCode"], "SUPPLIER_MATERIAL_PRICE_MANUAL_NOT_AUTHORIZED")

    def test_t07_authorized_user_can_write_audited_manual_price(self):
        response = self.client_for(self.direct).post(
            "/api/masterdata/prices/supplier-material-prices/runtime/manual-maintenance/",
            {
                "supplierId": self.supplier.pk,
                "materialId": self.material.pk,
                "unitPrice": "12.50",
                "taxRate": "13",
                "currency": "CNY",
                "effectiveDate": date.today().isoformat(),
                "expiryDate": (date.today() + timedelta(days=30)).isoformat(),
                "maintenanceReason": "ERP权限专项自动测试",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(SupplierMaterialPrice.objects.filter(
            supplier=self.supplier, material=self.material,
            price_source_type="MANUAL_MAINTENANCE",
        ).exists())

    def test_t08_admin_keeps_all_permissions(self):
        decision = BusinessPermissionAuthorization.decide(
            self.admin, "any.formal.permission", self.company.pk,
        )
        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["scopeCodes"], ["ALL"])

    def test_t09_scope_is_derived_from_formal_authority(self):
        self.assertEqual(authority_scope_code(self.buyer_authority), "SELF")
        self.assertEqual(authority_scope_code(self.direct_authority), "ORGANIZATION")
        buyer_response = self.client_for(self.buyer).get("/api/pfm/employees/?page_size=100")
        self.assertEqual(buyer_response.status_code, 200)
        self.assertEqual([row["id"] for row in buyer_response.data["results"]], [self.buyer_employee.pk])
        admin_response = self.client_for(self.admin).get("/api/pfm/employees/?page_size=100")
        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(len(admin_response.data["results"]), 2)

    def test_t10_buyer_endpoint_returns_formal_employee_data(self):
        response = self.client_for(self.direct).get("/api/pfm/employees/?status=active&page_size=100")
        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.data["results"] if item["id"] == self.buyer_employee.pk)
        self.assertEqual(row["formal_department_name"], self.department.name)
        self.assertEqual(row["formal_position_name"], self.position.name)
