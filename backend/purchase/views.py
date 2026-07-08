from datetime import datetime
from django.db import models
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import AllowAny

from .models import PurchaseOrder, PurchaseApprovalRecord, PurchaseOrderItem
from .serializers import PurchaseOrderSerializer
from pfm.models import Employee
from system.models import Department
from masterdata.models import Material
from procurement.models import Supplier


def _date_value(value):
    return value.isoformat() if value else None


def _decimal_value(value):
    return float(value or 0)


def _order_to_v6_row(order):
    return {
        "id": order.id,
        "po_no": order.po_no,
        "apply_dept": order.purchase_department,
        "request_dept": order.require_department,
        "buyer": order.buyer_name,
        "amount": _decimal_value(order.total_plan_amount),
        "plan_arrival_date": _date_value(order.expected_date),
        "actual_arrival_date": _date_value(order.actual_receive_date),
        "actual_amount": _decimal_value(order.total_actual_amount),
        "urgency": order.urgency_level,
        "status": order.document_status,
        "progress": order.progress_status,
    }


def _item_to_v6_row(item):
    return {
        "id": item.id,
        "order_no": item.order.po_no,
        "material_code": item.material_code,
        "material_name": item.material_name,
        "spec": item.specification,
        "plan_qty": _decimal_value(item.plan_quantity),
        "plan_price": _decimal_value(item.plan_unit_price),
        "plan_amount": _decimal_value(item.plan_amount),
        "actual_qty": _decimal_value(item.actual_quantity),
        "actual_price": _decimal_value(item.actual_unit_price),
        "actual_amount": _decimal_value(item.actual_amount),
        "actual_date": _date_value(item.actual_delivery_date),
        "expected_date": _date_value(item.plan_delivery_date),
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def purchase_order_v6_list(request):
    queryset = PurchaseOrder.objects.all().order_by("-id")

    return Response(
        {
            "success": True,
            "data": [_order_to_v6_row(order) for order in queryset],
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def purchase_order_v6_detail(request):
    queryset = PurchaseOrderItem.objects.select_related("order").all().order_by("-id")
    order_id = request.query_params.get("id")

    if order_id:
        queryset = queryset.filter(order_id=order_id)

    return Response(
        {
            "success": True,
            "data": [_item_to_v6_row(item) for item in queryset],
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def purchase_order_detail(request, pk):
    try:
        obj = PurchaseOrder.objects.get(id=pk)
    except PurchaseOrder.DoesNotExist:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = PurchaseOrderSerializer(obj)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([AllowAny])
def purchase_order_create(request):
    serializer = PurchaseOrderSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT"])
@permission_classes([AllowAny])
def purchase_order_update(request, pk):
    try:
        obj = PurchaseOrder.objects.get(id=pk)
    except PurchaseOrder.DoesNotExist:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = PurchaseOrderSerializer(obj, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([AllowAny])
def purchase_order_delete(request, pk):
    try:
        obj = PurchaseOrder.objects.get(id=pk)
    except PurchaseOrder.DoesNotExist:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)

    obj.delete()
    return Response({"success": True})


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

    def get_queryset(self):
        queryset = PurchaseOrder.objects.all()

        supplier_name = self.request.query_params.get("supplier_name")
        buyer_name = self.request.query_params.get("buyer_name")
        document_status = self.request.query_params.get("document_status")
        progress_status = self.request.query_params.get("progress_status")

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        min_amount = self.request.query_params.get("min_amount")
        max_amount = self.request.query_params.get("max_amount")

        keyword = self.request.query_params.get("keyword")

        if supplier_name:
            queryset = queryset.filter(supplier_name=supplier_name)

        if buyer_name:
            queryset = queryset.filter(buyer_name=buyer_name)

        if document_status:
            queryset = queryset.filter(document_status=document_status)

        if progress_status:
            queryset = queryset.filter(progress_status=progress_status)

        if start_date:
            queryset = queryset.filter(order_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(order_date__lte=end_date)

        if min_amount:
            queryset = queryset.filter(total_plan_amount__gte=min_amount)

        if max_amount:
            queryset = queryset.filter(total_plan_amount__lte=max_amount)

        if keyword:
            queryset = queryset.filter(
                models.Q(po_no__icontains=keyword)
                | models.Q(supplier_name__icontains=keyword)
                | models.Q(buyer_name__icontains=keyword)
            )

        return queryset

    def perform_create(self, serializer):
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"PO{today}"

        count = PurchaseOrder.objects.filter(po_no__startswith=prefix).count() + 1
        po_no = f"{prefix}{count:04d}"

        serializer.save(po_no=po_no, document_status="draft")

    def _change_document_status(
        self,
        request,
        pk,
        allowed_statuses,
        target_status,
        approval_level=None,
        approval_result="passed",
    ):
        order = self.get_object()

        if order.document_status not in allowed_statuses:
            return Response(
                {
                    "success": False,
                    "message": f"当前状态 {order.document_status} 不允许执行该动作",
                    "current_status": order.document_status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.document_status = target_status
        order.save(update_fields=["document_status", "updated_at"])

        if approval_level:
            PurchaseApprovalRecord.objects.create(
                order=order,
                approval_level=approval_level,
                approver_name=request.data.get("approver_name", "管理员"),
                approval_result=approval_result,
                approval_comment=request.data.get("approval_comment", ""),
                approved_at=timezone.now(),
            )

        serializer = self.get_serializer(order)

        return Response(
            {
                "success": True,
                "message": "状态更新成功",
                "data": serializer.data,
            }
        )

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        return self._change_document_status(
            request=request,
            pk=pk,
            allowed_statuses=["draft", "rejected"],
            target_status="submitted",
        )

    @action(detail=True, methods=["post"], url_path="audit")
    def audit(self, request, pk=None):
        return self._change_document_status(
            request=request,
            pk=pk,
            allowed_statuses=["submitted"],
            target_status="audited",
            approval_level="audit",
        )

    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        return self._change_document_status(
            request=request,
            pk=pk,
            allowed_statuses=["audited"],
            target_status="reviewed",
            approval_level="review",
        )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        return self._change_document_status(
            request=request,
            pk=pk,
            allowed_statuses=["reviewed"],
            target_status="approved",
            approval_level="approve",
        )

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return self._change_document_status(
            request=request,
            pk=pk,
            allowed_statuses=["submitted", "audited", "reviewed"],
            target_status="rejected",
            approval_level="audit",
            approval_result="rejected",
        )

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        return self._change_document_status(
            request=request,
            pk=pk,
            allowed_statuses=["draft", "submitted", "audited", "reviewed", "approved"],
            target_status="cancelled",
        )

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        return self._change_document_status(
            request=request,
            pk=pk,
            allowed_statuses=["approved"],
            target_status="closed",
        )

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
