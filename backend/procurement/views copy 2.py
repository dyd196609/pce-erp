import pandas as pd
from io import BytesIO
from openpyxl import Workbook
from django.http import HttpResponse
from django.db import models
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from .models import Supplier, PurchaseOrder, PurchaseOrderItem
from .serializers import SupplierSerializer, PurchaseOrderSerializer
from masterdata.models import Material
from rest_framework.permissions import IsAuthenticated


# ========== 供应商分页 ==========
class SupplierPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ========== 供应商视图集 ==========
class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SupplierPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(code__icontains=search) |
                models.Q(name__icontains=search)
            )

        code = self.request.query_params.get('code')
        name = self.request.query_params.get('name')
        contact_person = self.request.query_params.get('contact_person')
        contact_phone = self.request.query_params.get('contact_phone')
        contact_email = self.request.query_params.get('contact_email')
        credit_rating = self.request.query_params.get('credit_rating')
        is_active = self.request.query_params.get('is_active')

        code_in = self.request.query_params.get('code__in')
        name_in = self.request.query_params.get('name__in')
        contact_person_in = self.request.query_params.get('contact_person__in')
        contact_phone_in = self.request.query_params.get('contact_phone__in')
        contact_email_in = self.request.query_params.get('contact_email__in')
        credit_rating_in = self.request.query_params.get('credit_rating__in')
        is_active_in = self.request.query_params.get('is_active__in')

        if code_in:
            values = [v.strip() for v in code_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(code__in=values)
        elif code:
            queryset = queryset.filter(code__icontains=code)

        if name_in:
            values = [v.strip() for v in name_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(name__in=values)
        elif name:
            queryset = queryset.filter(name__icontains=name)

        if contact_person_in:
            values = [v.strip()
                      for v in contact_person_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(contact_person__in=values)
        elif contact_person:
            queryset = queryset.filter(
                contact_person__icontains=contact_person)

        if contact_phone_in:
            values = [v.strip()
                      for v in contact_phone_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(contact_phone__in=values)
        elif contact_phone:
            queryset = queryset.filter(contact_phone__icontains=contact_phone)

        if contact_email_in:
            values = [v.strip()
                      for v in contact_email_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(contact_email__in=values)
        elif contact_email:
            queryset = queryset.filter(contact_email__icontains=contact_email)

        if credit_rating_in:
            values = [v.strip()
                      for v in credit_rating_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(credit_rating__in=values)
        elif credit_rating:
            queryset = queryset.filter(credit_rating=credit_rating)

        if is_active_in:
            values = [v.strip() for v in is_active_in.split(',') if v.strip()]
            if values:
                active_values = [v.lower() == 'true' for v in values]
                queryset = queryset.filter(is_active__in=active_values)
        elif is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def export_template(self, request):
        df = pd.DataFrame({
            '序号': [1],
            '供应商编码': ['SUP001'],
            '供应商名称': ['示例供应商'],
            '联系人': ['张三'],
            '联系电话': ['13800138000'],
            '邮箱': ['example@test.com'],
            '信用等级': ['B'],
            '状态': ['启用']
        })
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='供应商模板', index=False)
        response = HttpResponse(output.getvalue(
        ), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="supplier_template.xlsx"'
        return response

    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        from rest_framework import status
        file = request.FILES.get('file')
        if not file:
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        file_name = file.name.lower()
        try:
            if file_name.endswith('.csv'):
                df = pd.read_csv(file, encoding='utf-8')
            else:
                df = pd.read_excel(file, engine='openpyxl')
        except Exception as e:
            return Response({'error': f'文件解析失败: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        success_count = 0
        errors = []
        for index, row in df.iterrows():
            try:
                if pd.isna(row.get('供应商编码')) or pd.isna(row.get('供应商名称')):
                    errors.append(f'第{index+2}行：供应商编码、供应商名称不能为空')
                    continue
                if Supplier.objects.filter(code=row['供应商编码']).exists():
                    errors.append(f'第{index+2}行：供应商编码 {row["供应商编码"]} 已存在')
                    continue

                credit_value = row.get('信用等级', 'B')
                if credit_value in ['A级', 'A']:
                    credit = 'A'
                elif credit_value in ['B级', 'B']:
                    credit = 'B'
                elif credit_value in ['C级', 'C']:
                    credit = 'C'
                elif credit_value in ['D级', 'D']:
                    credit = 'D'
                else:
                    credit = 'B'

                status_value = row.get('状态', '启用')
                is_active = status_value in ['启用', '是', 'true', 'True', '1']

                supplier = Supplier(
                    code=str(row['供应商编码']).strip(),
                    name=str(row['供应商名称']).strip(),
                    contact_person=str(row.get('联系人', '')) if pd.notna(
                        row.get('联系人')) else '',
                    contact_phone=str(row.get('联系电话', '')) if pd.notna(
                        row.get('联系电话')) else '',
                    contact_email=str(row.get('邮箱', '')) if pd.notna(
                        row.get('邮箱')) else '',
                    credit_rating=credit,
                    company_id=1,
                    is_active=is_active,
                )
                supplier.save()
                success_count += 1
            except Exception as e:
                errors.append(f'第{index+2}行：{str(e)}')
        return Response({'success': success_count, 'errors': errors, 'total': len(df)})

    @action(detail=False, methods=['get'])
    def export(self, request):
        queryset = self.get_queryset()
        data = []
        for index, sup in enumerate(queryset, start=1):
            data.append({
                '序号': index,
                '供应商编码': sup.code,
                '供应商名称': sup.name,
                '联系人': sup.contact_person or '',
                '联系电话': sup.contact_phone or '',
                '邮箱': sup.contact_email or '',
                '信用等级': sup.get_credit_rating_display(),
                '状态': '启用' if sup.is_active else '禁用'
            })
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='供应商列表', index=False)
        response = HttpResponse(output.getvalue(
        ), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="suppliers.xlsx"'
        return response


# ========== 采购订单视图集 ==========
class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all().order_by('-id')
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SupplierPagination  # 复用分页类

    def perform_create(self, serializer):
        import datetime
        today = datetime.datetime.now().strftime('%Y%m%d')
        last_order = PurchaseOrder.objects.filter(
            po_no__startswith=f'PO{today}').order_by('-po_no').first()
        if last_order:
            last_seq = int(last_order.po_no[-4:])
            seq = str(last_seq + 1).zfill(4)
        else:
            seq = '0001'
        po_no = f'PO{today}{seq}'
        serializer.save(po_no=po_no, company_id=1,
                        created_by=self.request.user.id)

    def perform_update(self, serializer):
        serializer.save()

    def get_queryset(self):
        queryset = super().get_queryset()

        # 全局搜索
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(po_no__icontains=search) |
                models.Q(supplier__name__icontains=search)
            )

        # 订单号（单个）
        po_no = self.request.query_params.get('po_no')
        if po_no:
            queryset = queryset.filter(po_no__icontains=po_no)

        # 订单号（批量）
        po_no_in = self.request.query_params.get('po_no__in')
        if po_no_in:
            values = [v.strip() for v in po_no_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(po_no__in=values)

        # 供应商名称（单个）
        supplier_name = self.request.query_params.get('supplier_name')
        if supplier_name:
            queryset = queryset.filter(supplier__name__icontains=supplier_name)

        # 供应商名称（批量）
        supplier_name_in = self.request.query_params.get('supplier_name__in')
        if supplier_name_in:
            values = [v.strip()
                      for v in supplier_name_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(supplier__name__in=values)

        # 采购员（单个）
        buyer = self.request.query_params.get('buyer')
        if buyer:
            queryset = queryset.filter(buyer__icontains=buyer)

        # 采购员（批量）
        buyer_in = self.request.query_params.get('buyer__in')
        if buyer_in:
            values = [v.strip() for v in buyer_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(buyer__in=values)

        # 状态（单个）
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # 状态（批量）
        status_in = self.request.query_params.get('status__in')
        if status_in:
            values = [v.strip() for v in status_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(status__in=values)

        # 总金额范围
        total_amount_min = self.request.query_params.get('total_amount_min')
        if total_amount_min:
            queryset = queryset.filter(
                total_amount__gte=float(total_amount_min))
        total_amount_max = self.request.query_params.get('total_amount_max')
        if total_amount_max:
            queryset = queryset.filter(
                total_amount__lte=float(total_amount_max))

        # 下单日期范围
        order_date_start = self.request.query_params.get('order_date_start')
        order_date_end = self.request.query_params.get('order_date_end')
        if order_date_start and order_date_end:
            queryset = queryset.filter(
                order_date__range=[order_date_start, order_date_end])
        elif order_date_start:
            queryset = queryset.filter(order_date__gte=order_date_start)
        elif order_date_end:
            queryset = queryset.filter(order_date__lte=order_date_end)

        # 预计到货日期范围
        expected_date_start = self.request.query_params.get(
            'expected_date_start')
        expected_date_end = self.request.query_params.get('expected_date_end')
        if expected_date_start and expected_date_end:
            queryset = queryset.filter(expected_date__range=[
                                       expected_date_start, expected_date_end])
        elif expected_date_start:
            queryset = queryset.filter(expected_date__gte=expected_date_start)
        elif expected_date_end:
            queryset = queryset.filter(expected_date__lte=expected_date_end)

        # 实际到货日期范围
        actual_receive_date_start = self.request.query_params.get(
            'actual_receive_date_start')
        actual_receive_date_end = self.request.query_params.get(
            'actual_receive_date_end')
        if actual_receive_date_start and actual_receive_date_end:
            queryset = queryset.filter(actual_receive_date__range=[
                                       actual_receive_date_start, actual_receive_date_end])
        elif actual_receive_date_start:
            queryset = queryset.filter(
                actual_receive_date__gte=actual_receive_date_start)
        elif actual_receive_date_end:
            queryset = queryset.filter(
                actual_receive_date__lte=actual_receive_date_end)

        # 排序（如有）
        ordering = self.request.query_params.get('ordering')
        if ordering:
            # 供应商排序字段映射（前端传 supplier_name，实际需 supplier__name）
            if ordering == 'supplier_name':
                ordering = 'supplier__name'
            elif ordering == '-supplier_name':
                ordering = '-supplier__name'
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-id')

        return queryset

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        order = self.get_object()
        if order.status == 'draft':
            order.status = 'submitted'
            order.save()
            return Response({'status': 'submitted'})
        return Response({'error': '只能提交草稿状态的订单'}, status=400)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        order = self.get_object()
        if order.status == 'submitted':
            order.status = 'approved'
            order.save()
            return Response({'status': 'approved'})
        return Response({'error': '只能审核已提交的订单'}, status=400)

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        order = self.get_object()
        if order.status == 'approved':
            order.status = 'received'
            order.save()
            return Response({'status': 'received'})
        return Response({'error': '只能收货已审核的订单'}, status=400)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status in ['draft', 'submitted']:
            order.status = 'cancelled'
            order.save()
            return Response({'status': 'cancelled'})
        return Response({'error': '只能取消草稿或已提交的订单'}, status=400)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        order = self.get_object()
        if order.status == 'submitted':
            order.status = 'draft'
            order.save()
            return Response({'status': 'draft'})
        return Response({'error': '只能驳回已提交的订单'}, status=400)

    @action(detail=False, methods=['post'])
    def batch_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请提供要删除的ID列表'}, status=400)
        PurchaseOrder.objects.filter(id__in=ids).delete()
        return Response({'success': True})

    @action(detail=False, methods=['post'])
    def batch_submit(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请提供要提交的ID列表'}, status=400)
        updated = PurchaseOrder.objects.filter(
            id__in=ids, status='draft').update(status='submitted')
        return Response({'success': updated})

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def export_template(self, request):
        df_order = pd.DataFrame({
            '序号': [1],
            '订单号': ['PO202605100001'],
            '供应商编码': ['SUP001'],
            '供应商名称': ['示例供应商'],
            '采购员': ['张三'],
            '下单日期': ['2026-05-01'],
            '预计到货日期': ['2026-05-10'],
            '实际到货日期': [''],
            '总金额': [1000.00],
            '状态': ['草稿'],
            '备注': ['']
        })
        df_item = pd.DataFrame({
            '订单号': ['PO202605100001'],
            '物料编码': ['MT001'],
            '物料名称': ['笔记本电脑'],
            '规格型号': ['ThinkPad X1 Carbon'],
            '数量': [1],
            '单价': [8500.00],
            '金额': [8500.00],
            '期望到货日期': ['2026-05-10']
        })
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_order.to_excel(writer, sheet_name='订单列表', index=False)
            df_item.to_excel(writer, sheet_name='商品明细', index=False)
        response = HttpResponse(output.getvalue(
        ), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="purchase_order_import_template.xlsx"'
        return response

    @action(detail=False, methods=['get'])
    def export(self, request):
        queryset = self.get_queryset()
        ids_param = request.query_params.get('ids')
        if ids_param:
            ids = [int(i) for i in ids_param.split(',') if i.isdigit()]
            if ids:
                queryset = queryset.filter(id__in=ids)

        header_data = []
        for order in queryset:
            header_data.append({
                '订单号': order.po_no,
                '供应商': order.supplier.name if order.supplier else '',
                '采购员': order.buyer or '',
                '下单日期': order.order_date,
                '预计到货日期': order.expected_date or '',
                '实际到货日期': order.actual_receive_date or '',
                '状态': order.get_status_display(),
                '总金额': float(order.total_amount),
                '备注': order.remark or ''
            })
        df_header = pd.DataFrame(header_data)

        detail_data = []
        for order in queryset:
            for item in order.items.all():
                detail_data.append({
                    '订单号': order.po_no,
                    '物料编码': item.material.code if item.material else '',
                    '物料名称': item.material.name if item.material else '',
                    '规格型号': item.specification,
                    '数量': item.quantity,
                    '单价': item.unit_price,
                    '金额': item.amount,
                    '期望到货日期': item.expected_date or ''
                })
        df_detail = pd.DataFrame(detail_data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_header.to_excel(writer, sheet_name='订单列表', index=False)
            if detail_data:
                df_detail.to_excel(writer, sheet_name='商品明细', index=False)
            else:
                pd.DataFrame({'提示': ['所选订单无商品明细']}).to_excel(
                    writer, sheet_name='商品明细', index=False)

        response = HttpResponse(output.getvalue(
        ), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="purchase_orders.xlsx"'
        return response

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消订单"""
        order = self.get_object()
        if order.status in ['closed', 'cancelled']:
            return Response({'error': '该订单已结案或已取消，无法取消'}, status=400)
        order.status = 'cancelled'
        order.save()  # 必须执行保存
        return Response({'status': order.status, 'status_display': order.get_status_display()})

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """草稿 -> 提交"""
        order = self.get_object()
        if order.status != 'draft':
            return Response({'error': '只有草稿状态才能提交'}, status=400)
        order.status = 'submitted'
        order.save()
        return Response({'status': order.status, 'status_display': order.get_status_display()})

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """已提交 -> 审核"""
        order = self.get_object()
        if order.status != 'submitted':
            return Response({'error': '只有已提交状态才能审核'}, status=400)
        order.status = 'approved'
        order.save()
        return Response({'status': order.status, 'status_display': order.get_status_display()})

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """已审核 -> 复核"""
        order = self.get_object()
        if order.status != 'approved':
            return Response({'error': '只有已审核状态才能复核'}, status=400)
        order.status = 'reviewed'
        order.save()
        return Response({'status': order.status, 'status_display': order.get_status_display()})

    @action(detail=True, methods=['post'])
    def final_approve(self, request, pk=None):
        """已复核 -> 审批"""
        order = self.get_object()
        if order.status != 'reviewed':
            return Response({'error': '只有已复核状态才能审批'}, status=400)
        order.status = 'final_approved'
        order.save()
        return Response({'status': order.status, 'status_display': order.get_status_display()})

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """已审批 -> 收货"""
        order = self.get_object()
        if order.status != 'final_approved':
            return Response({'error': '只有已审批状态才能收货'}, status=400)
        order.status = 'received'
        order.save()
        return Response({'status': order.status, 'status_display': order.get_status_display()})

    @action(detail=True, methods=['post'])
    def inspect(self, request, pk=None):
        """已收货 -> 检验"""
        order = self.get_object()
        if order.status != 'received':
            return Response({'error': '只有已收货状态才能检验'}, status=400)
        order.status = 'inspected'
        order.save()
        return Response({'status': order.status, 'status_display': order.get_status_display()})

    @action(detail=True, methods=['post'])
    def store(self, request, pk=None):
        """已检验 -> 入库"""
        order = self.get_object()
        if order.status != 'inspected':
            return Response({'error': '只有已检验状态才能入库'}, status=400)
        order.status = 'stored'
        order.save()
        return Response({'status': order.status, 'status_display': order.get_status_display()})

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """已入库 -> 结案"""
        order = self.get_object()
        if order.status != 'stored':
            return Response({'error': '只有已入库状态才能结案'}, status=400)
        order.status = 'closed'
        order.save()
        return Response({'status': order.status, 'status_display': order.get_status_display()})

    @action(detail=False, methods=['post'])
    def batch_approve(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请选择订单'}, status=400)
        count = PurchaseOrder.objects.filter(
            id__in=ids, status='submitted'
        ).update(status='approved')
        return Response({'success': count, 'message': f'成功审核 {count} 个订单'})

    @action(detail=False, methods=['post'])
    def batch_review(self, request):
        ids = request.data.get('ids', [])
        count = PurchaseOrder.objects.filter(
            id__in=ids, status='approved'
        ).update(status='reviewed')
        return Response({'success': count})

    @action(detail=False, methods=['post'])
    def batch_final_approve(self, request):
        ids = request.data.get('ids', [])
        count = PurchaseOrder.objects.filter(
            id__in=ids, status='reviewed'
        ).update(status='final_approved')
        return Response({'success': count})

    @action(detail=False, methods=['post'])
    def batch_receive(self, request):
        ids = request.data.get('ids', [])
        count = PurchaseOrder.objects.filter(
            id__in=ids, status='final_approved'
        ).update(status='received')
        return Response({'success': count})

    @action(detail=False, methods=['post'])
    def batch_inspect(self, request):
        ids = request.data.get('ids', [])
        count = PurchaseOrder.objects.filter(
            id__in=ids, status='received'
        ).update(status='inspected')
        return Response({'success': count})

    @action(detail=False, methods=['post'])
    def batch_store(self, request):
        ids = request.data.get('ids', [])
        count = PurchaseOrder.objects.filter(
            id__in=ids, status='inspected'
        ).update(status='stored')
        return Response({'success': count})

    @action(detail=False, methods=['post'])
    def batch_close(self, request):
        ids = request.data.get('ids', [])
        count = PurchaseOrder.objects.filter(
            id__in=ids, status='stored'
        ).update(status='closed')
        return Response({'success': count})

    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        from rest_framework import status
        file = request.FILES.get('file')
        if not file:
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        file_name = file.name.lower()
        try:
            if file_name.endswith('.csv'):
                df = pd.read_csv(file, encoding='utf-8')
                df_orders = df
                df_items = pd.DataFrame()
            else:
                excel_data = pd.read_excel(
                    file, sheet_name=None, engine='openpyxl')
                if '订单列表' not in excel_data:
                    return Response({'error': '缺少【订单列表】sheet'}, status=status.HTTP_400_BAD_REQUEST)
                df_orders = excel_data['订单列表']
                df_items = excel_data.get('商品明细', pd.DataFrame())
        except Exception as e:
            return Response({'error': f'文件解析失败: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        # 修正后的 status_map
        status_map = {
            'draft': '草稿',
            'submitted': '已提交',
            'approved': '已审核',
            'reviewed': '已复核',
            'final_approved': '已审批',
            'received': '已收货',
            'completed': '已完成',
            'closed': '已结案',
            'cancelled': '已取消'
        }
        success_count = 0
        errors = []

        for idx, row in df_orders.iterrows():
            try:
                po_no = str(row.get('订单号', '')).strip()
                if not po_no:
                    errors.append(f'第{idx+2}行：订单号不能为空')
                    continue

                # 供应商匹配：兼容 '供应商编码', '供应商名称', '供应商'
                supplier_code = str(row.get('供应商编码', '')).strip()
                supplier_name = str(row.get('供应商名称', '')).strip()
                supplier_col = str(row.get('供应商', '')).strip()   # 新增：普通供应商列
                supplier = None

                # 优先用编码
                if supplier_code:
                    supplier = Supplier.objects.filter(
                        code=supplier_code).first()
                # 其次用供应商名称（从'供应商名称'列）
                if not supplier and supplier_name:
                    supplier = Supplier.objects.filter(
                        name=supplier_name).first()
                # 最后用普通'供应商'列（按名称匹配）
                if not supplier and supplier_col:
                    supplier = Supplier.objects.filter(
                        name=supplier_col).first()

                if not supplier:
                    errors.append(
                        f'第{idx+2}行：找不到供应商 (编码:{supplier_code} 名称:{supplier_name} 供应商列:{supplier_col})，请确保供应商已录入系统')
                    continue

                order_date = row.get('下单日期') if pd.notna(
                    row.get('下单日期')) else None
                expected_date = row.get('预计到货日期') if pd.notna(
                    row.get('预计到货日期')) else None
                actual_receive_date = row.get('实际到货日期') if pd.notna(
                    row.get('实际到货日期')) else None
                status_value = str(row.get('状态', '草稿')).strip()
                order_status = status_map.get(status_value, 'draft')
                total_amount = float(row.get('总金额', 0)) if pd.notna(
                    row.get('总金额')) else 0

                order, created = PurchaseOrder.objects.update_or_create(
                    po_no=po_no,
                    defaults={
                        'supplier': supplier,
                        'buyer': str(row.get('采购员', '')) if pd.notna(row.get('采购员')) else '',
                        'order_date': order_date,
                        'expected_date': expected_date,
                        'actual_receive_date': actual_receive_date,
                        'total_amount': total_amount,
                        'status': order_status,
                        'remark': str(row.get('备注', '')) if pd.notna(row.get('备注')) else '',
                        'company_id': 1,
                    }
                )

                if not df_items.empty:
                    order.items.all().delete()
                    order_items = df_items[df_items['订单号'].astype(
                        str) == po_no]
                    for _, item_row in order_items.iterrows():
                        material_code = str(item_row.get('物料编码', '')).strip()
                        material = Material.objects.filter(
                            code=material_code).first()
                        if not material:
                            errors.append(
                                f'订单 {po_no} 物料编码 {material_code} 不存在，跳过明细')
                            continue
                        quantity = float(item_row.get('数量', 0)) if pd.notna(
                            item_row.get('数量')) else 0
                        unit_price = float(item_row.get('单价', 0)) if pd.notna(
                            item_row.get('单价')) else 0
                        amount = float(item_row.get('金额', 0)) if pd.notna(
                            item_row.get('金额')) else quantity * unit_price
                        PurchaseOrderItem.objects.create(
                            po=order,
                            material=material,
                            specification=str(item_row.get('规格型号', ''))[:200],
                            quantity=quantity,
                            unit_price=unit_price,
                            amount=amount,
                            expected_date=item_row.get('期望到货日期') if pd.notna(
                                item_row.get('期望到货日期')) else None
                        )
                    order.total_amount = sum(
                        i.amount for i in order.items.all())
                    order.save()

                success_count += 1
            except Exception as e:
                errors.append(f'第{idx+2}行：{str(e)}')

        return Response({'success': success_count, 'errors': errors, 'total': len(df_orders)})
