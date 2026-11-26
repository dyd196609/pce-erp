from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from procurement.purchase_request_api import PurchaseRequestReferenceView
from purchase.views import PurchaseOrderViewSet
from system.models import Company, Department, Position, User

from .formal_employee import (
    employee_archive_queryset,
    formal_employee_queryset,
    organization_complete_employee_queryset,
)
from .models import Employee
from .serializers import EmployeeSerializer
from .views import EmployeeViewSet


class FormalEmployeeQuerysetTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="FEMP-C1", name="正式员工测试公司")
        self.other_company = Company.objects.create(code="FEMP-C2", name="正式员工测试公司二")
        self.department = Department.objects.create(
            code="FEMP-D1", name="正式部门", company=self.company, is_active=True
        )
        self.other_department = Department.objects.create(
            code="FEMP-D2", name="其他部门", company=self.other_company, is_active=True
        )
        self.position = Position.objects.create(
            code="FEMP-P1", name="正式员工测试岗位一", company=self.company,
            department=self.department, is_active=True,
        )
        self.other_position = Position.objects.create(
            code="FEMP-P2", name="正式员工测试岗位二", company=self.other_company,
            department=self.other_department, is_active=True,
        )
        self.user = User.objects.create(
            username="formal-employee-test-admin", real_name="正式员工测试管理员",
            company_id=self.company.pk, is_active=True, is_superuser=True,
        )
        self.request_factory = APIRequestFactory()

    def _employee(self, employee_no, **overrides):
        values = {
            "employee_no": employee_no,
            "full_name": employee_no,
            "status": "active",
            "department_ref": self.department,
            "position_ref": self.position,
        }
        values.update(overrides)
        return Employee.objects.create(**values)

    def test_only_complete_consistent_active_chain_is_formal(self):
        formal = self._employee("FEMP-001")
        self._employee("FEMP-002", department_ref=None)
        self._employee("FEMP-003", position_ref=None)
        self._employee("FEMP-004", position_ref=self.other_position)
        self._employee("FEMP-005", status="inactive")

        self.assertEqual(
            list(formal_employee_queryset().values_list("pk", flat=True)),
            [formal.pk],
        )

    def test_archive_is_complete_while_organization_and_candidate_sets_are_separate(self):
        formal = self._employee("FEMP-A01")
        missing_department = self._employee("FEMP-A02", department_ref=None)
        missing_position = self._employee("FEMP-A03", position_ref=None)
        inactive = self._employee("FEMP-A04", status="inactive")

        self.assertEqual(
            list(employee_archive_queryset().order_by("pk").values_list("pk", flat=True)),
            [formal.pk, missing_department.pk, missing_position.pk, inactive.pk],
        )
        self.assertEqual(
            list(organization_complete_employee_queryset().order_by("pk").values_list("pk", flat=True)),
            [formal.pk, inactive.pk],
        )
        self.assertEqual(
            list(formal_employee_queryset().order_by("pk").values_list("pk", flat=True)),
            [formal.pk],
        )

    def test_company_scope_is_part_of_the_shared_boundary(self):
        formal = self._employee("FEMP-006")
        self._employee(
            "FEMP-007", department_ref=self.other_department, position_ref=self.other_position
        )

        self.assertEqual(
            list(formal_employee_queryset(company_id=self.company.pk).values_list("pk", flat=True)),
            [formal.pk],
        )

    def test_active_employee_write_requires_formal_relations(self):
        serializer = EmployeeSerializer(data={
            "employee_no": "FEMP-008",
            "full_name": "缺失正式岗位",
            "status": "active",
            "department_ref": self.department.pk,
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("position_ref", serializer.errors)

    def test_employee_archive_view_includes_nonformal_rows_but_candidates_exclude_them(self):
        formal = self._employee("FEMP-009")
        ghost = self._employee("FEMP-010", position_ref=None)

        employee_request = self.request_factory.get(
            "/api/pfm/employees/?view=all&page_size=100"
        )
        force_authenticate(employee_request, user=self.user)
        employee_response = EmployeeViewSet.as_view({"get": "list"})(employee_request)
        self.assertEqual(employee_response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in employee_response.data["results"]],
            [formal.pk, ghost.pk],
        )

        purchase_request = self.request_factory.get("/api/purchase/orders/base-options/")
        force_authenticate(purchase_request, user=self.user)
        purchase_response = PurchaseOrderViewSet.as_view({"get": "base_options"})(purchase_request)
        self.assertEqual(purchase_response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in purchase_response.data["employees"]], [formal.pk]
        )

        reference_request = self.request_factory.get(
            "/api/procurement/purchase-requests/references/employees/?limit=200"
        )
        force_authenticate(reference_request, user=self.user)
        reference_response = PurchaseRequestReferenceView.as_view()(
            reference_request, reference_type="employees"
        )
        self.assertEqual(reference_response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in reference_response.data["data"]["results"]],
            [formal.pk],
        )
        self.assertNotEqual(formal.pk, ghost.pk)

    def test_default_employee_query_remains_formal_for_legacy_business_consumers(self):
        formal = self._employee("FEMP-013")
        self._employee("FEMP-014", department_ref=None)
        self._employee("FEMP-015", position_ref=None)
        self._employee("FEMP-016", status="inactive")

        request = self.request_factory.get("/api/pfm/employees/?page_size=100")
        force_authenticate(request, user=self.user)
        response = EmployeeViewSet.as_view({"get": "list"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in response.data["results"]],
            [formal.pk],
        )

    def test_history_view_is_explicit_and_read_only(self):
        self._employee("FEMP-011")
        ghost = self._employee("FEMP-012", position_ref=None)

        history_request = self.request_factory.get(
            "/api/pfm/employees/?view=history&page_size=100"
        )
        force_authenticate(history_request, user=self.user)
        history_response = EmployeeViewSet.as_view({"get": "list"})(history_request)
        self.assertEqual(
            [row["id"] for row in history_response.data["results"]], [ghost.pk]
        )

        update_request = self.request_factory.patch(
            f"/api/pfm/employees/{ghost.pk}/?view=history", {"full_name": "禁止写入"},
            format="json",
        )
        force_authenticate(update_request, user=self.user)
        update_response = EmployeeViewSet.as_view({"patch": "partial_update"})(
            update_request, pk=ghost.pk
        )
        self.assertEqual(update_response.status_code, 409)
