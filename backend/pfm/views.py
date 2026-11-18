import importlib


class _LazyPandas:
    def __getattr__(self, name):
        return getattr(importlib.import_module("pandas"), name)


pd = _LazyPandas()
from io import BytesIO
from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import render
from rest_framework import viewsets, permissions
from .formal_employee import employee_archive_queryset, formal_employee_queryset
from .models import Employee, Shift, EmployeeCertificate
from .serializers import EmployeeSerializer, ShiftSerializer, EmployeeCertificateSerializer
from system.authorization import scope_employee_queryset


class EmployeePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = EmployeePagination

    def _history_write_block(self):
        view_mode = str(self.request.query_params.get('view') or 'current').strip().lower()
        if view_mode in {'history', 'all', 'archive'}:
            return Response(
                {
                    'code': 'EMPLOYEE_HISTORY_READ_ONLY',
                    'error': '历史员工视图只读；正式员工变更必须通过当前员工正式组织关系入口。',
                },
                status=status.HTTP_409_CONFLICT,
            )
        return None

    def update(self, request, *args, **kwargs):
        blocked = self._history_write_block()
        return blocked if blocked is not None else super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        blocked = self._history_write_block()
        return blocked if blocked is not None else super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        blocked = self._history_write_block()
        return blocked if blocked is not None else super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        """支持筛选的查询集（模糊查询 + 多选批量查询）"""
        queryset = scope_employee_queryset(super().get_queryset(), self.request.user)
        view_mode = str(self.request.query_params.get('view') or 'current').strip().lower()
        if view_mode == 'history':
            queryset = queryset.exclude(
                pk__in=formal_employee_queryset(queryset).values_list('pk', flat=True)
            )
        elif view_mode in {'all', 'archive'}:
            queryset = employee_archive_queryset(queryset)
        elif view_mode != 'all':
            queryset = formal_employee_queryset(queryset)
        department_filter_field = (
            'department_ref__name' if view_mode == 'current' else 'department_name'
        )
        position_filter_field = 'position_ref__name' if view_mode == 'current' else 'position'
        
        # ========== 多选批量筛选（__in 精确匹配） ==========
        employee_no_in = self.request.query_params.get('employee_no__in')
        full_name_in = self.request.query_params.get('full_name__in')
        phone_in = self.request.query_params.get('phone__in')
        status_in = self.request.query_params.get('status__in')
        department_name_in = self.request.query_params.get('department_name__in')
        position_in = self.request.query_params.get('position__in')
        gender_in = self.request.query_params.get('gender__in')
        birth_date_in = self.request.query_params.get('birth_date__in')
        hire_date_in = self.request.query_params.get('hire_date__in')
        resignation_date_in = self.request.query_params.get('resignation_date__in')
        
        if employee_no_in and employee_no_in.strip():
            values = [v.strip() for v in employee_no_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(employee_no__in=values)
        if full_name_in and full_name_in.strip():
            values = [v.strip() for v in full_name_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(full_name__in=values)
        if phone_in and phone_in.strip():
            values = [v.strip() for v in phone_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(phone__in=values)
        if status_in and status_in.strip():
            values = [v.strip() for v in status_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(status__in=values)
        if department_name_in and department_name_in.strip():
            values = [v.strip() for v in department_name_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(**{f'{department_filter_field}__in': values})
        if position_in and position_in.strip():
            values = [v.strip() for v in position_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(**{f'{position_filter_field}__in': values})
        if gender_in and gender_in.strip():
            values = [v.strip() for v in gender_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(gender__in=values)
        if birth_date_in and birth_date_in.strip():
            values = [v.strip() for v in birth_date_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(birth_date__in=values)
        if hire_date_in and hire_date_in.strip():
            values = [v.strip() for v in hire_date_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(hire_date__in=values)
        if resignation_date_in and resignation_date_in.strip():
            values = [v.strip() for v in resignation_date_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(resignation_date__in=values)

        # ========== 输入框筛选（模糊匹配） ==========
        employee_no = self.request.query_params.get('employee_no')
        if employee_no:
            queryset = queryset.filter(employee_no__icontains=employee_no)
        full_name = self.request.query_params.get('full_name')
        if full_name:
            queryset = queryset.filter(full_name__icontains=full_name)
        phone = self.request.query_params.get('phone')
        if phone:
            queryset = queryset.filter(phone__icontains=phone)
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        department_name = self.request.query_params.get('department_name')
        if department_name:
            queryset = queryset.filter(**{f'{department_filter_field}__icontains': department_name})
        position = self.request.query_params.get('position')
        if position:
            queryset = queryset.filter(**{f'{position_filter_field}__icontains': position})
        gender = self.request.query_params.get('gender')
        if gender:
            queryset = queryset.filter(gender=gender)
        birth_date = self.request.query_params.get('birth_date')
        if birth_date:
            queryset = queryset.filter(birth_date=birth_date)
        hire_date = self.request.query_params.get('hire_date')
        if hire_date:
            queryset = queryset.filter(hire_date=hire_date)
        resignation_date = self.request.query_params.get('resignation_date')
        if resignation_date:
            queryset = queryset.filter(resignation_date=resignation_date)
                # ========== 日期范围筛选 ==========
        birth_date_start = self.request.query_params.get('birth_date_start')
        birth_date_end = self.request.query_params.get('birth_date_end')
        if birth_date_start and birth_date_end:
            queryset = queryset.filter(birth_date__range=[birth_date_start, birth_date_end])
        elif birth_date_start:
            queryset = queryset.filter(birth_date__gte=birth_date_start)
        elif birth_date_end:
            queryset = queryset.filter(birth_date__lte=birth_date_end)
        
        hire_date_start = self.request.query_params.get('hire_date_start')
        hire_date_end = self.request.query_params.get('hire_date_end')
        if hire_date_start and hire_date_end:
            queryset = queryset.filter(hire_date__range=[hire_date_start, hire_date_end])
        elif hire_date_start:
            queryset = queryset.filter(hire_date__gte=hire_date_start)
        elif hire_date_end:
            queryset = queryset.filter(hire_date__lte=hire_date_end)
        
        resignation_date_start = self.request.query_params.get('resignation_date_start')
        resignation_date_end = self.request.query_params.get('resignation_date_end')
        if resignation_date_start and resignation_date_end:
            queryset = queryset.filter(resignation_date__range=[resignation_date_start, resignation_date_end])
        elif resignation_date_start:
            queryset = queryset.filter(resignation_date__gte=resignation_date_start)
        elif resignation_date_end:
            queryset = queryset.filter(resignation_date__lte=resignation_date_end)
            
        return queryset.order_by('employee_no', 'pk')

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def export_template(self, request):
        """下载导入模板（Excel）"""
        df = pd.DataFrame({
            '序号': [1],
            '工号': ['C001'],
            '姓名': ['张三'],
            '手机号': ['13800138001'],
            '状态': ['在职'],
            '部门': ['技术部'],
            '职位': ['工程师'],
            '性别': ['男'],
            '生日': ['1990-01-01'],
            '入职日期': ['2020-01-01'],
            '离职日期': [''],
            '工龄': [0]
        })
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='员工模板', index=False)
        
        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="employee_template.xlsx"'
        return response

    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        """导入 Excel 或 CSV 文件"""
        return Response(
            {
                'code': 'LEGACY_EMPLOYEE_IMPORT_DISABLED',
                'error': '旧员工导入只包含历史文本字段，已停止作为正式员工写入入口；请通过正式组织员工维护入口关联公司、部门和岗位。',
            },
            status=status.HTTP_409_CONFLICT,
        )

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出员工列表"""
        queryset = self.get_queryset()
        
        data = []
        for index, emp in enumerate(queryset, start=1):
            # 性别转换
            gender_display = ''
            if emp.gender == 'M':
                gender_display = '男'
            elif emp.gender == 'F':
                gender_display = '女'
            else:
                gender_display = emp.gender or ''
            
            # 状态转换
            status_display = ''
            if emp.status == 'active':
                status_display = '在职'
            elif emp.status == 'inactive':
                status_display = '离职'
            else:
                status_display = emp.status or ''
            
            data.append({
                '序号': index,
                '工号': emp.employee_no,
                '姓名': emp.full_name,
                '手机号': emp.phone,
                '状态': status_display,
                '部门': emp.department_ref.name if emp.department_ref else '',
                '职位': emp.position_ref.name if emp.position_ref else '',
                '性别': gender_display,
                '生日': emp.birth_date,
                '入职日期': emp.hire_date,
                '离职日期': emp.resignation_date,
                '工龄': emp.seniority if hasattr(emp, 'seniority') else '',
            })
        
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='员工列表', index=False)
        
        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="employees.xlsx"'
        return response


class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer
    permission_classes = [permissions.IsAuthenticated]


class EmployeeCertificateViewSet(viewsets.ModelViewSet):
    queryset = EmployeeCertificate.objects.all()
    serializer_class = EmployeeCertificateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        employee_id = self.request.query_params.get('employee_id')
        qs = super().get_queryset()
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        return qs
