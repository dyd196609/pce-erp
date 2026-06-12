import pandas as pd
from io import BytesIO
from django.http import HttpResponse
from django.db import models
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from .models import Supplier, PurchaseOrder, PurchaseOrderItem
from .serializers import SupplierSerializer, PurchaseOrderSerializer
from masterdata.models import Material
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import Coalesce
from decimal import Decimal
from datetime import date
from django.db.models import Sum, Count, Avg, Q, F


# ========== 供应商分页 ==========
class SupplierPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ========== 供应商视图集 ==========
class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SupplierPagination

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def export_template(self, request):
        df = pd.DataFrame(
            {
                "序号": [1],
                "供应商编码": ["SUP001"],
                "供应商名称": ["示例供应商"],
                "联系人": ["张三"],
                "联系电话": ["13800138000"],
                "邮箱": ["example@test.com"],
                "信用等级": ["B"],
                "状态": ["启用"],
            }
        )
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="供应商模板", index=False)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="supplier_template.xlsx"'
        )
        return response

    @action(detail=False, methods=["post"])
    def import_excel(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "请上传文件"}, status=status.HTTP_400_BAD_REQUEST)

        file_name = file.name.lower()
        try:
            if file_name.endswith(".csv"):
                df = pd.read_csv(file, encoding="utf-8")
            else:
                df = pd.read_excel(file, engine="openpyxl")
        except Exception as e:
            return Response(
                {"error": f"文件解析失败: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST
            )

        success_count = 0
        errors = []
        for index, row in df.iterrows():
            try:
                if pd.isna(row.get("供应商编码")) or pd.isna(row.get("供应商名称")):
                    errors.append(f"第{index+2}行：供应商编码、供应商名称不能为空")
                    continue
                if Supplier.objects.filter(code=row["供应商编码"]).exists():
                    errors.append(
                        f'第{index+2}行：供应商编码 {row["供应商编码"]} 已存在'
                    )
                    continue

                credit_value = row.get("信用等级", "B")
                if credit_value in ["A级", "A"]:
                    credit = "A"
                elif credit_value in ["B级", "B"]:
                    credit = "B"
                elif credit_value in ["C级", "C"]:
                    credit = "C"
                elif credit_value in ["D级", "D"]:
                    credit = "D"
                else:
                    credit = "B"

                status_value = row.get("状态", "启用")
                is_active = status_value in ["启用", "是", "true", "True", "1"]

                supplier = Supplier(
                    code=str(row["供应商编码"]).strip(),
                    name=str(row["供应商名称"]).strip(),
                    contact_person=(
                        str(row.get("联系人", ""))
                        if pd.notna(row.get("联系人"))
                        else ""
                    ),
                    contact_phone=(
                        str(row.get("联系电话", ""))
                        if pd.notna(row.get("联系电话"))
                        else ""
                    ),
                    contact_email=(
                        str(row.get("邮箱", "")) if pd.notna(row.get("邮箱")) else ""
                    ),
                    credit_rating=credit,
                    company_id=1,
                    is_active=is_active,
                )
                supplier.save()
                success_count += 1
            except Exception as e:
                errors.append(f"第{index+2}行：{str(e)}")
        return Response({"success": success_count, "errors": errors, "total": len(df)})

    @action(detail=False, methods=["get"])
    def export(self, request):
        queryset = self.get_queryset()
        data = []
        for index, sup in enumerate(queryset, start=1):
            data.append(
                {
                    "序号": index,
                    "供应商编码": sup.code,
                    "供应商名称": sup.name,
                    "联系人": sup.contact_person or "",
                    "联系电话": sup.contact_phone or "",
                    "邮箱": sup.contact_email or "",
                    "信用等级": sup.get_credit_rating_display(),
                    "状态": "启用" if sup.is_active else "禁用",
                }
            )
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="供应商列表", index=False)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="suppliers.xlsx"'
        return response


# ========== 采购订单视图集 ==========
class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all().order_by("-id")
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SupplierPagination

    def perform_create(self, serializer):
        import datetime

        today = datetime.datetime.now().strftime("%Y%m%d")
        last_order = (
            PurchaseOrder.objects.filter(po_no__startswith=f"PO{today}")
            .order_by("-po_no")
            .first()
        )
        if last_order:
            last_seq = int(last_order.po_no[-4:])
            seq = str(last_seq + 1).zfill(4)
        else:
            seq = "0001"
        po_no = f"PO{today}{seq}"
        serializer.save(po_no=po_no, company_id=1, created_by=self.request.user.id)

    def perform_update(self, serializer):
        serializer.save()

    def get_queryset(self):
        queryset = super().get_queryset()

        # ========== 1. 全局搜索 ==========
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(po_no__icontains=search)
                | models.Q(supplier__name__icontains=search)
            )

        # ========== 2. 订单号筛选（单个） ==========
        po_no = self.request.query_params.get("po_no")
        if po_no:
            queryset = queryset.filter(po_no__icontains=po_no)

        # ========== 3. 订单号筛选（批量） ==========
        po_no_in = self.request.query_params.get("po_no__in")
        if po_no_in:
            values = [v.strip() for v in po_no_in.split(",") if v.strip()]
            if values:
                queryset = queryset.filter(po_no__in=values)

        # ========== 4. 供应商名称筛选（单个） ==========
        supplier_name = self.request.query_params.get("supplier_name")
        if supplier_name:
            queryset = queryset.filter(supplier__name__icontains=supplier_name)

        # ========== 5. 供应商名称筛选（批量） ==========
        supplier_name_in = self.request.query_params.get("supplier_name__in")
        if supplier_name_in:
            values = [v.strip() for v in supplier_name_in.split(",") if v.strip()]
            if values:
                queryset = queryset.filter(supplier__name__in=values)

        # ========== 6. 采购员筛选（单个） ==========
        buyer = self.request.query_params.get("buyer")
        if buyer:
            queryset = queryset.filter(buyer__icontains=buyer)

        # ========== 7. 采购员筛选（批量） ==========
        buyer_in = self.request.query_params.get("buyer__in")
        if buyer_in:
            values = [v.strip() for v in buyer_in.split(",") if v.strip()]
            if values:
                queryset = queryset.filter(buyer__in=values)

        # ========== 8. 状态筛选（单个） ==========
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # ========== 9. 总金额范围筛选 ==========
        total_amount_min = self.request.query_params.get("total_amount_min")
        if total_amount_min:
            queryset = queryset.filter(total_amount__gte=float(total_amount_min))
        total_amount_max = self.request.query_params.get("total_amount_max")
        if total_amount_max:
            queryset = queryset.filter(total_amount__lte=float(total_amount_max))

        # ========== 10. 下单日期范围筛选 ==========
        order_date_start = self.request.query_params.get("order_date_start")
        order_date_end = self.request.query_params.get("order_date_end")
        if order_date_start and order_date_end:
            queryset = queryset.filter(
                order_date__range=[order_date_start, order_date_end]
            )
        elif order_date_start:
            queryset = queryset.filter(order_date__gte=order_date_start)
        elif order_date_end:
            queryset = queryset.filter(order_date__lte=order_date_end)

        # ========== 11. 预计到货日期范围筛选 ==========
        expected_date_start = self.request.query_params.get("expected_date_start")
        expected_date_end = self.request.query_params.get("expected_date_end")
        if expected_date_start and expected_date_end:
            queryset = queryset.filter(
                expected_date__range=[expected_date_start, expected_date_end]
            )
        elif expected_date_start:
            queryset = queryset.filter(expected_date__gte=expected_date_start)
        elif expected_date_end:
            queryset = queryset.filter(expected_date__lte=expected_date_end)

        # ========== 12. 实际到货日期范围筛选 ==========
        actual_receive_date_start = self.request.query_params.get(
            "actual_receive_date_start"
        )
        actual_receive_date_end = self.request.query_params.get(
            "actual_receive_date_end"
        )
        if actual_receive_date_start and actual_receive_date_end:
            queryset = queryset.filter(
                actual_receive_date__range=[
                    actual_receive_date_start,
                    actual_receive_date_end,
                ]
            )
        elif actual_receive_date_start:
            queryset = queryset.filter(
                actual_receive_date__gte=actual_receive_date_start
            )
        elif actual_receive_date_end:
            queryset = queryset.filter(actual_receive_date__lte=actual_receive_date_end)

        # ========== 13. 紧急程度、是否达成、到期天数筛选（property字段） ==========
        # 先将 queryset 转为列表（因为 property 无法在数据库层筛选）
        result_list = list(queryset)

        # 13.1 紧急程度筛选
        urgency_level = self.request.query_params.get("urgency_level")
        if urgency_level:
            result_list = [p for p in result_list if p.urgency_level == urgency_level]

        # 13.2 是否达成筛选
        is_fulfilled = self.request.query_params.get("is_fulfilled")
        if is_fulfilled is not None:
            target = is_fulfilled.lower() == "true"
            result_list = [p for p in result_list if p.is_fulfilled == target]

        # 13.3 到期天数范围筛选
        days_min = self.request.query_params.get("days_to_expiry_min")
        days_max = self.request.query_params.get("days_to_expiry_max")
        if days_min or days_max:
            filtered = []
            for p in result_list:
                days = p.days_to_expiry
                if days is None:
                    continue
                if days_min and days < int(days_min):
                    continue
                if days_max and days > int(days_max):
                    continue
                filtered.append(p)
            result_list = filtered

        # 返回 ID 列表，保持分页功能
        ids = [p.id for p in result_list]
        queryset = queryset.filter(id__in=ids)

        # ========== 14. 排序 ==========
        ordering = self.request.query_params.get("ordering")
        if ordering:
            # 转换前端排序字段名为数据库字段名
            if ordering == "supplier_name":
                ordering = "supplier__name"
            elif ordering == "-supplier_name":
                ordering = "-supplier__name"
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by("-id")

        return queryset

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        order = self.get_object()
        if order.status != "draft":
            return Response({"error": "只有草稿状态才能提交"}, status=400)
        order.status = "submitted"
        order.save()
        return Response(
            {"status": order.status, "status_display": order.get_status_display()}
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        order = self.get_object()
        if order.status != "submitted":
            return Response({"error": "只有已提交状态才能审核"}, status=400)
        order.status = "approved"
        order.save()
        return Response(
            {"status": order.status, "status_display": order.get_status_display()}
        )

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        order = self.get_object()
        if order.status != "approved":
            return Response({"error": "只有已审核状态才能复核"}, status=400)
        order.status = "reviewed"
        order.save()
        return Response(
            {"status": order.status, "status_display": order.get_status_display()}
        )

    @action(detail=True, methods=["post"])
    def final_approve(self, request, pk=None):
        order = self.get_object()
        if order.status != "reviewed":
            return Response({"error": "只有已复核状态才能审批"}, status=400)
        order.status = "final_approved"
        order.save()
        return Response(
            {"status": order.status, "status_display": order.get_status_display()}
        )

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        order = self.get_object()
        if order.status != "final_approved":
            return Response({"error": "只有已审批状态才能收货"}, status=400)
        order.status = "received"
        order.save()
        return Response(
            {"status": order.status, "status_display": order.get_status_display()}
        )

    @action(detail=True, methods=["post"])
    def inspect(self, request, pk=None):
        order = self.get_object()
        if order.status != "received":
            return Response({"error": "只有已收货状态才能检验"}, status=400)
        order.status = "inspected"
        order.save()
        return Response(
            {"status": order.status, "status_display": order.get_status_display()}
        )

    @action(detail=True, methods=["post"])
    def store(self, request, pk=None):
        order = self.get_object()
        if order.status != "inspected":
            return Response({"error": "只有已检验状态才能入库"}, status=400)
        order.status = "stored"
        order.save()
        return Response(
            {"status": order.status, "status_display": order.get_status_display()}
        )

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        order = self.get_object()
        if order.status != "stored":
            return Response({"error": "只有已入库状态才能结案"}, status=400)
        order.status = "closed"
        order.save()
        return Response(
            {"status": order.status, "status_display": order.get_status_display()}
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status in ["closed", "cancelled"]:
            return Response({"error": "该订单已结案或已取消，无法取消"}, status=400)
        order.status = "cancelled"
        order.save()
        return Response(
            {"status": order.status, "status_display": order.get_status_display()}
        )

    @action(detail=True, methods=["post"])
    def restart(self, request, pk=None):
        order = self.get_object()
        if order.status != "cancelled":
            return Response({"error": "只有已取消的订单才能重启"}, status=400)
        order.status = "draft"
        order.save()
        return Response(
            {"status": order.status, "status_display": order.get_status_display()}
        )

    @action(detail=False, methods=["post"])
    def batch_delete(self, request):
        ids = request.data.get("ids", [])
        if not ids:
            return Response({"error": "请提供要删除的ID列表"}, status=400)
        PurchaseOrder.objects.filter(id__in=ids).delete()
        return Response({"success": True})

    @action(detail=False, methods=["post"])
    def batch_submit(self, request):
        ids = request.data.get("ids", [])
        if not ids:
            return Response({"error": "请提供要提交的ID列表"}, status=400)
        updated = PurchaseOrder.objects.filter(id__in=ids, status="draft").update(
            status="submitted"
        )
        return Response({"success": updated})

    @action(detail=False, methods=["post"])
    def batch_approve(self, request):
        ids = request.data.get("ids", [])
        if not ids:
            return Response({"error": "请选择订单"}, status=400)
        count = PurchaseOrder.objects.filter(id__in=ids, status="submitted").update(
            status="approved"
        )
        return Response({"success": count})

    @action(detail=False, methods=["post"])
    def batch_review(self, request):
        ids = request.data.get("ids", [])
        count = PurchaseOrder.objects.filter(id__in=ids, status="approved").update(
            status="reviewed"
        )
        return Response({"success": count})

    @action(detail=False, methods=["post"])
    def batch_final_approve(self, request):
        ids = request.data.get("ids", [])
        count = PurchaseOrder.objects.filter(id__in=ids, status="reviewed").update(
            status="final_approved"
        )
        return Response({"success": count})

    @action(detail=False, methods=["post"])
    def batch_receive(self, request):
        ids = request.data.get("ids", [])
        count = PurchaseOrder.objects.filter(
            id__in=ids, status="final_approved"
        ).update(status="received")
        return Response({"success": count})

    @action(detail=False, methods=["post"])
    def batch_inspect(self, request):
        ids = request.data.get("ids", [])
        count = PurchaseOrder.objects.filter(id__in=ids, status="received").update(
            status="inspected"
        )
        return Response({"success": count})

    @action(detail=False, methods=["post"])
    def batch_store(self, request):
        ids = request.data.get("ids", [])
        count = PurchaseOrder.objects.filter(id__in=ids, status="inspected").update(
            status="stored"
        )
        return Response({"success": count})

    @action(detail=False, methods=["post"])
    def batch_close(self, request):
        ids = request.data.get("ids", [])
        count = PurchaseOrder.objects.filter(id__in=ids, status="stored").update(
            status="closed"
        )
        return Response({"success": count})

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def export_template(self, request):
        df_order = pd.DataFrame(
            {
                "订单号": ["PO202605100001"],
                "供应商编码": ["SUP001"],
                "供应商名称": ["示例供应商"],
                "采购员": ["张三"],
                "下单日期": ["2026-05-01"],
                "预计到货日期": ["2026-05-10"],
                "实际到货日期": [""],
                "总金额": [1000.00],
                "状态": ["草稿"],
                "备注": [""],
            }
        )
        df_item = pd.DataFrame(
            {
                "订单号": ["PO202605100001"],
                "物料编码": ["MT001"],
                "物料名称": ["笔记本电脑"],
                "规格型号": ["ThinkPad X1 Carbon"],
                "计划数量": [1],
                "计划单价": [8500.00],
                "计划金额": [8500.00],
                "实际交货数量": [""],
                "实际交货单价": [""],
                "实际交货金额": [""],
                "实际到货日期": [""],
                "期望到货日期": ["2026-05-10"],
            }
        )
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_order.to_excel(writer, sheet_name="订单列表", index=False)
            df_item.to_excel(writer, sheet_name="商品明细", index=False)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="purchase_order_import_template.xlsx"'
        )
        return response

    @action(detail=False, methods=["get"])
    def export(self, request):
        queryset = self.get_queryset()
        ids_param = request.query_params.get("ids")
        if ids_param:
            ids = [int(i) for i in ids_param.split(",") if i.isdigit()]
            if ids:
                queryset = queryset.filter(id__in=ids)
        header_data = []
        for order in queryset:
            header_data.append(
                {
                    "订单号": order.po_no,
                    "供应商": order.supplier.name if order.supplier else "",
                    "采购员": order.buyer or "",
                    "下单日期": order.order_date,
                    "预计到货日期": order.expected_date or "",
                    "实际到货日期": order.actual_receive_date or "",
                    "状态": order.get_status_display(),
                    "总金额": float(order.total_amount),
                    "备注": order.remark or "",
                }
            )
        df_header = pd.DataFrame(header_data)
        detail_data = []
        for order in queryset:
            for item in order.items.all():
                detail_data.append(
                    {
                        "订单号": order.po_no,
                        "物料编码": item.material.code if item.material else "",
                        "物料名称": item.material.name if item.material else "",
                        "规格型号": item.specification,
                        "计划数量": item.quantity,
                        "计划单价": item.unit_price,
                        "计划金额": item.amount,
                        "实际交货数量": (
                            item.actual_quantity
                            if item.actual_quantity is not None
                            else ""
                        ),
                        "实际交货单价": (
                            item.actual_unit_price
                            if item.actual_unit_price is not None
                            else ""
                        ),
                        "实际交货金额": (
                            item.actual_amount if item.actual_amount is not None else ""
                        ),
                        "实际到货日期": (
                            item.actual_arrival_date.strftime("%Y-%m-%d")
                            if item.actual_arrival_date
                            else ""
                        ),
                        "期望到货日期": (
                            item.expected_date.strftime("%Y-%m-%d")
                            if item.expected_date
                            else ""
                        ),
                    }
                )
        df_detail = pd.DataFrame(detail_data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_header.to_excel(writer, sheet_name="订单列表", index=False)
            if detail_data:
                df_detail.to_excel(writer, sheet_name="商品明细", index=False)
            else:
                pd.DataFrame({"提示": ["所选订单无商品明细"]}).to_excel(
                    writer, sheet_name="商品明细", index=False
                )
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="purchase_orders.xlsx"'
        return response

    @action(detail=False, methods=["post"])
    def import_excel(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "请上传文件"}, status=status.HTTP_400_BAD_REQUEST)
        file_name = file.name.lower()
        try:
            if file_name.endswith(".csv"):
                df = pd.read_csv(file, encoding="utf-8")
                df_orders = df
                df_items = pd.DataFrame()
            else:
                excel_data = pd.read_excel(file, sheet_name=None, engine="openpyxl")
                if "订单列表" not in excel_data:
                    return Response(
                        {"error": "缺少【订单列表】sheet"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                df_orders = excel_data["订单列表"]
                df_items = excel_data.get("商品明细", pd.DataFrame())
        except Exception as e:
            return Response(
                {"error": f"文件解析失败: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST
            )
        status_map = {
            "草稿": "draft",
            "已提交": "submitted",
            "已审核": "approved",
            "已复核": "reviewed",
            "已审批": "final_approved",
            "已收货": "received",
            "已检验": "inspected",
            "已入库": "stored",
            "已结案": "closed",
            "已取消": "cancelled",
        }
        success_count = 0
        errors = []
        for idx, row in df_orders.iterrows():
            try:
                po_no = str(row.get("订单号", "")).strip()
                if not po_no:
                    errors.append(f"第{idx+2}行：订单号不能为空")
                    continue
                supplier_code = str(row.get("供应商编码", "")).strip()
                supplier_name = str(row.get("供应商名称", "")).strip()
                supplier_col = str(row.get("供应商", "")).strip()
                supplier = None
                if supplier_code:
                    supplier = Supplier.objects.filter(code=supplier_code).first()
                if not supplier and supplier_name:
                    supplier = Supplier.objects.filter(name=supplier_name).first()
                if not supplier and supplier_col:
                    supplier = Supplier.objects.filter(name=supplier_col).first()
                if not supplier:
                    errors.append(f"第{idx+2}行：找不到供应商，请确保供应商已录入系统")
                    continue
                order_date = (
                    row.get("下单日期") if pd.notna(row.get("下单日期")) else None
                )
                expected_date = (
                    row.get("预计到货日期")
                    if pd.notna(row.get("预计到货日期"))
                    else None
                )
                actual_receive_date = (
                    row.get("实际到货日期")
                    if pd.notna(row.get("实际到货日期"))
                    else None
                )
                status_value = str(row.get("状态", "草稿")).strip()
                order_status = status_map.get(status_value, "draft")
                total_amount = (
                    float(row.get("总金额", 0)) if pd.notna(row.get("总金额")) else 0
                )
                order, created = PurchaseOrder.objects.update_or_create(
                    po_no=po_no,
                    defaults={
                        "supplier": supplier,
                        "buyer": (
                            str(row.get("采购员", ""))
                            if pd.notna(row.get("采购员"))
                            else ""
                        ),
                        "order_date": order_date,
                        "expected_date": expected_date,
                        "actual_receive_date": actual_receive_date,
                        "total_amount": total_amount,
                        "status": order_status,
                        "remark": (
                            str(row.get("备注", ""))
                            if pd.notna(row.get("备注"))
                            else ""
                        ),
                        "company_id": 1,
                    },
                )
                if not df_items.empty:
                    order.items.all().delete()
                    order_items = df_items[df_items["订单号"].astype(str) == po_no]
                    for _, item_row in order_items.iterrows():
                        material_code = str(item_row.get("物料编码", "")).strip()
                        material = Material.objects.filter(code=material_code).first()
                        if not material:
                            errors.append(
                                f"订单 {po_no} 物料编码 {material_code} 不存在，跳过明细"
                            )
                            continue
                        quantity = (
                            float(item_row.get("计划数量", 0))
                            if pd.notna(item_row.get("计划数量"))
                            else 0
                        )
                        unit_price = (
                            float(item_row.get("计划单价", 0))
                            if pd.notna(item_row.get("计划单价"))
                            else 0
                        )
                        amount = (
                            float(item_row.get("计划金额", 0))
                            if pd.notna(item_row.get("计划金额"))
                            else quantity * unit_price
                        )
                        actual_quantity = (
                            float(item_row.get("实际交货数量", 0))
                            if pd.notna(item_row.get("实际交货数量"))
                            else None
                        )
                        actual_unit_price = (
                            float(item_row.get("实际交货单价", 0))
                            if pd.notna(item_row.get("实际交货单价"))
                            else None
                        )
                        actual_amount = (
                            float(item_row.get("实际交货金额", 0))
                            if pd.notna(item_row.get("实际交货金额"))
                            else (
                                actual_quantity * actual_unit_price
                                if actual_quantity and actual_unit_price
                                else None
                            )
                        )
                        actual_arrival_date = (
                            item_row.get("实际到货日期")
                            if pd.notna(item_row.get("实际到货日期"))
                            else None
                        )
                        PurchaseOrderItem.objects.create(
                            po=order,
                            material=material,
                            specification=str(item_row.get("规格型号", ""))[:200],
                            quantity=quantity,
                            unit_price=unit_price,
                            amount=amount,
                            actual_quantity=actual_quantity,
                            actual_unit_price=actual_unit_price,
                            actual_amount=actual_amount,
                            actual_arrival_date=actual_arrival_date,
                            expected_date=(
                                item_row.get("期望到货日期")
                                if pd.notna(item_row.get("期望到货日期"))
                                else None
                            ),
                        )
                    order.total_amount = sum(i.amount for i in order.items.all())
                    order.save()
                success_count += 1
            except Exception as e:
                errors.append(f"第{idx+2}行：{str(e)}")
        return Response(
            {"success": success_count, "errors": errors, "total": len(df_orders)}
        )


# ========== 采购报表视图 ==========
class ReportViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="department-purchase")
    def department_purchase_report(self, request):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        group_by = request.query_params.get("group_by", "department")

        queryset = PurchaseOrder.objects.filter(status__in=["received", "closed"])
        if start_date:
            queryset = queryset.filter(order_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(order_date__lte=end_date)

        # 筛选条件
        buyer = request.query_params.get("buyer")
        if buyer:
            queryset = queryset.filter(buyer=buyer)

        supplier_id = request.query_params.get("supplier_id")
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        department_id = request.query_params.get("department_id")
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        from system.models import Department

        if group_by == "require_department":
            dept_ids = queryset.values("require_department_id").distinct()
            filter_field = "require_department"
        else:
            dept_ids = queryset.values("department_id").distinct()
            filter_field = "department"

        departments = Department.objects.filter(id__in=dept_ids)
        total_amount_all = queryset.aggregate(
            total=Coalesce(Sum("total_amount"), Decimal("0"))
        )["total"]

        report_data = []
        for dept in departments:
            dept_orders = queryset.filter(**{filter_field: dept})
            total_amount = dept_orders.aggregate(
                total=Coalesce(Sum("total_amount"), Decimal("0"))
            )["total"]
            order_count = dept_orders.count()

            planned_total = Decimal("0")
            for order in dept_orders:
                planned_total += order.items.aggregate(
                    total=Coalesce(Sum("amount"), Decimal("0"))
                )["total"]

            amount_diff_rate = Decimal("0")
            if planned_total and planned_total > 0:
                amount_diff_rate = (
                    (total_amount - planned_total) / planned_total
                ) * Decimal("100")

            percentage = Decimal("0")
            if total_amount_all and total_amount_all > 0:
                percentage = (total_amount / total_amount_all) * Decimal("100")

            report_data.append(
                {
                    "department_id": dept.id,
                    "department_name": dept.name,
                    "total_amount": total_amount,
                    "order_count": order_count,
                    "amount_diff_rate": round(amount_diff_rate, 2),
                    "percentage": round(percentage, 2),
                }
            )

        report_data.sort(key=lambda x: x["total_amount"], reverse=True)
        summary = {
            "total_amount_all": total_amount_all,
            "total_order_count": queryset.count(),
            "department_count": len(report_data),
            "group_by": group_by,
        }
        return Response({"data": report_data, "summary": summary})

    @action(detail=False, methods=["get"], url_path="buyer-performance")
    def buyer_performance_report(self, request):
        from django.db.models import F

        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        queryset = PurchaseOrder.objects.filter(status__in=["received", "closed"])
        if start_date:
            queryset = queryset.filter(order_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(order_date__lte=end_date)

        # 筛选条件
        buyer = request.query_params.get("buyer")
        if buyer:
            queryset = queryset.filter(buyer=buyer)

        supplier_id = request.query_params.get("supplier_id")
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        department_id = request.query_params.get("department_id")
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        buyer_stats = (
            queryset.values("buyer")
            .annotate(
                total_amount=Coalesce(Sum("total_amount"), Decimal("0")),
                order_count=Count("id"),
            )
            .order_by("-total_amount")
        )

        total_amount_all = queryset.aggregate(
            total=Coalesce(Sum("total_amount"), Decimal("0"))
        )["total"]

        report_data = []
        for stat in buyer_stats:
            buyer_name = stat["buyer"] or "未分配"
            buyer_orders = queryset.filter(
                buyer=buyer_name if buyer_name != "未分配" else None
            )

            total_orders = buyer_orders.count()
            on_time_orders = buyer_orders.filter(
                actual_receive_date__isnull=False,
                expected_date__isnull=False,
                actual_receive_date__lte=F("expected_date"),
            ).count()
            on_time_rate = Decimal("0")
            if total_orders > 0:
                on_time_rate = (
                    Decimal(on_time_orders) / Decimal(total_orders) * Decimal("100")
                )

            from procurement.models import PurchaseOrderItem

            items = PurchaseOrderItem.objects.filter(po__in=buyer_orders)
            price_diff_sum = Decimal("0")
            amount_diff_sum = Decimal("0")
            item_count = 0
            for item in items:
                if item.unit_price and item.unit_price > 0:
                    planned_price = item.unit_price
                    actual_price = item.actual_unit_price or planned_price
                    price_diff_rate = (
                        (actual_price - planned_price) / planned_price * Decimal("100")
                    )
                    price_diff_sum += price_diff_rate

                    planned_amount = item.amount
                    actual_amount = item.actual_amount or planned_amount
                    amount_diff_rate = (
                        (actual_amount - planned_amount)
                        / planned_amount
                        * Decimal("100")
                        if planned_amount
                        else 0
                    )
                    amount_diff_sum += amount_diff_rate
                    item_count += 1

            avg_price_diff_rate = (
                price_diff_sum / item_count if item_count > 0 else Decimal("0")
            )
            avg_amount_diff_rate = (
                amount_diff_sum / item_count if item_count > 0 else Decimal("0")
            )

            avg_amount = Decimal("0")
            if stat["order_count"] > 0:
                avg_amount = stat["total_amount"] / stat["order_count"]

            percentage = Decimal("0")
            if total_amount_all > 0:
                percentage = (stat["total_amount"] / total_amount_all) * Decimal("100")

            report_data.append(
                {
                    "buyer_name": buyer_name,
                    "total_amount": stat["total_amount"],
                    "order_count": stat["order_count"],
                    "avg_amount": round(avg_amount, 2),
                    "on_time_rate": round(on_time_rate, 2),
                    "price_diff_rate": round(avg_price_diff_rate, 2),
                    "amount_diff_rate": round(avg_amount_diff_rate, 2),
                    "percentage": round(percentage, 2),
                }
            )

        return Response(
            {
                "data": report_data,
                "summary": {
                    "total_amount_all": total_amount_all,
                    "total_order_count": queryset.count(),
                    "buyer_count": len(report_data),
                },
            }
        )

    @action(detail=False, methods=["get"], url_path="supplier-performance")
    def supplier_performance_report(self, request):
        from django.db.models import F, Avg

        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        queryset = PurchaseOrder.objects.filter(status__in=["received", "closed"])
        if start_date:
            queryset = queryset.filter(order_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(order_date__lte=end_date)

        # 筛选条件
        buyer = request.query_params.get("buyer")
        if buyer:
            queryset = queryset.filter(buyer=buyer)

        supplier_id = request.query_params.get("supplier_id")
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        department_id = request.query_params.get("department_id")
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        supplier_stats = (
            queryset.values("supplier__id", "supplier__name")
            .annotate(
                total_amount=Coalesce(Sum("total_amount"), Decimal("0")),
                order_count=Count("id"),
            )
            .order_by("-total_amount")
        )

        total_orders = queryset.count()
        on_time_orders = queryset.filter(
            actual_receive_date__isnull=False,
            expected_date__isnull=False,
            actual_receive_date__lte=F("expected_date"),
        ).count()
        overall_on_time_rate = Decimal("0")
        if total_orders > 0:
            overall_on_time_rate = (
                Decimal(on_time_orders) / Decimal(total_orders) * Decimal("100")
            )

        total_amount_all = queryset.aggregate(
            total=Coalesce(Sum("total_amount"), Decimal("0"))
        )["total"]

        report_data = []
        for stat in supplier_stats:
            supplier_name = stat["supplier__name"] or "未知供应商"
            supplier_orders = queryset.filter(supplier_id=stat["supplier__id"])

            delivery_days = (
                supplier_orders.aggregate(
                    avg_days=Avg(
                        F("actual_receive_date") - F("order_date"),
                        output_field=models.FloatField(),
                    )
                )["avg_days"]
                or 0
            )

            sup_total_orders = supplier_orders.count()
            sup_on_time_orders = supplier_orders.filter(
                actual_receive_date__isnull=False,
                expected_date__isnull=False,
                actual_receive_date__lte=F("expected_date"),
            ).count()
            sup_on_time_rate = Decimal("0")
            if sup_total_orders > 0:
                sup_on_time_rate = (
                    Decimal(sup_on_time_orders)
                    / Decimal(sup_total_orders)
                    * Decimal("100")
                )

            from procurement.models import PurchaseOrderItem

            items = PurchaseOrderItem.objects.filter(po__in=supplier_orders)
            price_diff_sum = Decimal("0")
            item_count = 0
            for item in items:
                if item.unit_price and item.unit_price > 0:
                    planned = item.unit_price
                    actual = item.actual_unit_price or planned
                    diff_rate = (actual - planned) / planned * Decimal("100")
                    price_diff_sum += diff_rate
                    item_count += 1
            price_diff_rate = (
                price_diff_sum / item_count if item_count > 0 else Decimal("0")
            )

            avg_amount = Decimal("0")
            if stat["order_count"] > 0:
                avg_amount = stat["total_amount"] / stat["order_count"]

            percentage = Decimal("0")
            if total_amount_all > 0:
                percentage = (stat["total_amount"] / total_amount_all) * Decimal("100")

            report_data.append(
                {
                    "supplier_id": stat["supplier__id"],
                    "supplier_name": supplier_name,
                    "total_amount": stat["total_amount"],
                    "order_count": stat["order_count"],
                    "avg_amount": round(avg_amount, 2),
                    "on_time_rate": round(sup_on_time_rate, 2),
                    "avg_delivery_days": (
                        round(delivery_days, 1) if delivery_days else 0
                    ),
                    "price_diff_rate": round(price_diff_rate, 2),
                    "percentage": round(percentage, 2),
                }
            )

        return Response(
            {
                "data": report_data,
                "summary": {
                    "total_amount_all": total_amount_all,
                    "total_order_count": total_orders,
                    "supplier_count": len(report_data),
                    "on_time_rate": round(overall_on_time_rate, 2),
                },
            }
        )
