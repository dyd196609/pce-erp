import pandas as pd
from io import BytesIO
from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import render
from rest_framework import viewsets, permissions
from .models import Employee, Shift, EmployeeCertificate
from .serializers import EmployeeSerializer, ShiftSerializer, EmployeeCertificateSerializer


class EmployeePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = EmployeePagination

    def get_queryset(self):
        """支持筛选的查询集（模糊查询 + 多选批量查询）"""
        queryset = super().get_queryset()
        
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
                queryset = queryset.filter(department_name__in=values)
        if position_in and position_in.strip():
            values = [v.strip() for v in position_in.split(',') if v.strip()]
            if values:
                queryset = queryset.filter(position__in=values)
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
            queryset = queryset.filter(department_name__icontains=department_name)
        position = self.request.query_params.get('position')
        if position:
            queryset = queryset.filter(position__icontains=position)
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
            
        return queryset

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
        file = request.FILES.get('file')
        if not file:
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)
        
        file_name = file.name.lower()
        try:
            if file_name.endswith('.csv'):
                # 处理 CSV 文件
                df = pd.read_csv(file, encoding='utf-8')
            else:
                # 处理 Excel 文件
                df = pd.read_excel(file, engine='openpyxl')
        except Exception as e:
            return Response({'error': f'文件解析失败: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        success_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                employee_no = str(row.get('工号', '')).strip() if pd.notna(row.get('工号')) else None
                if not employee_no:
                    errors.append(f'第{index+2}行：工号不能为空')
                    continue
                
                # 性别转换（导入时统一存储为 M/F）
                gender_value = row.get('性别', '') if pd.notna(row.get('性别')) else ''
                if gender_value == '男':
                    gender_code = 'M'
                elif gender_value == '女':
                    gender_code = 'F'
                else:
                    gender_code = ''
                
                # 状态转换（导入时统一存储为 active/inactive）
                status_value = row.get('状态', '') if pd.notna(row.get('状态')) else ''
                if status_value == '在职':
                    status_code = 'active'
                elif status_value == '离职':
                    status_code = 'inactive'
                else:
                    status_code = 'active'
                
                employee, created = Employee.objects.update_or_create(
                    employee_no=employee_no,
                    defaults={
                        'full_name': str(row.get('姓名', '')) if pd.notna(row.get('姓名')) else '',
                        'phone': str(row.get('手机号', '')) if pd.notna(row.get('手机号')) else '',
                        'status': status_code,
                        'department_name': str(row.get('部门', '')) if pd.notna(row.get('部门')) else '',
                        'position': str(row.get('职位', '')) if pd.notna(row.get('职位')) else '',
                        'gender': gender_code,
                        'birth_date': row.get('生日') if pd.notna(row.get('生日')) else None,
                        'hire_date': row.get('入职日期') if pd.notna(row.get('入职日期')) else None,
                        'resignation_date': row.get('离职日期') if pd.notna(row.get('离职日期')) else None,
                    }
                )
                success_count += 1
            except Exception as e:
                errors.append(f'第{index+2}行：{str(e)}')
        
        return Response({
            'success': success_count,
            'errors': errors,
            'total': len(df)
        })

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
                '部门': emp.department_name,
                '职位': emp.position,
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