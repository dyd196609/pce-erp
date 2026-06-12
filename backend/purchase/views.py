from datetime import datetime
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import AllowAny

from .models import PurchaseOrder
from .serializers import PurchaseOrderSerializer
from pfm.models import Employee
from system.models import Department
from masterdata.models import Material
from procurement.models import Supplier


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all()
    serializer_class = PurchaseOrderSerializer
    permission_classes = [AllowAny]

    filter_backends = [OrderingFilter]
    ordering_fields = [
        "po_no",
        "order_date",
        "total_plan_amount",
        "total_actual_amount",
        "document_status",
        "progress_status",
        "urgency_level",
    ]
    ordering = ["-id"]

    def perform_create(self, serializer):
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"PO{today}"

        count = PurchaseOrder.objects.filter(po_no__startswith=prefix).count() + 1

        po_no = f"{prefix}{count:04d}"

        serializer.save(po_no=po_no)

    @action(detail=False, methods=["get"], url_path="base-options")
    def base_options(self, request):
        employees = Employee.objects.filter(status="active").order_by("employee_no")
        departments = Department.objects.filter(is_active=True).order_by("id")
        suppliers = Supplier.objects.all().order_by("id")
        materials = Material.objects.filter(is_active=True).order_by("code")

        employee_options = []
        for employee in employees:
            employee_options.append(
                {
                    "id": employee.id,
                    "employee_no": employee.employee_no,
                    "full_name": employee.full_name,
                    "label": f"{employee.employee_no} - {employee.full_name}",
                    "value": employee.full_name,
                }
            )

        department_options = []
        for department in departments:
            department_options.append(
                {
                    "id": department.id,
                    "code": department.code,
                    "name": department.name,
                    "label": department.name,
                    "value": department.name,
                }
            )

        supplier_options = []
        for supplier in suppliers:
            supplier_options.append(
                {
                    "id": supplier.id,
                    "code": getattr(supplier, "code", ""),
                    "name": getattr(supplier, "name", ""),
                    "label": f"{getattr(supplier, 'code', '')} - {getattr(supplier, 'name', '')}",
                    "value": getattr(supplier, "name", ""),
                }
            )

        material_options = []
        for material in materials:
            material_options.append(
                {
                    "id": material.id,
                    "code": material.code,
                    "name": material.name,
                    "specification": material.specification or "",
                    "unit": material.unit or "",
                    "price": float(material.price or 0),
                    "label": f"{material.name}（{material.code}）",
                    "value": material.id,
                }
            )

        return Response(
            {
                "success": True,
                "employees": employee_options,
                "departments": department_options,
                "materials": material_options,
                "suppliers": supplier_options,
            }
        )

    @action(detail=False, methods=["post"], url_path="batch-delete")
    def batch_delete(self, request):
        ids = request.data.get("ids", [])

        if not ids:
            return Response(
                {"success": False, "error": "ids required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted, _ = PurchaseOrder.objects.filter(id__in=ids).delete()

        return Response(
            {
                "success": True,
                "deleted_count": deleted,
            }
        )
