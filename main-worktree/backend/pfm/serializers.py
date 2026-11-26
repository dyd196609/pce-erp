from rest_framework import serializers
from .models import Employee, Shift, EmployeeCertificate

class EmployeeSerializer(serializers.ModelSerializer):
    seniority = serializers.SerializerMethodField(read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    department_code = serializers.CharField(source='department_ref.code', read_only=True)
    formal_department_name = serializers.CharField(source='department_ref.name', read_only=True)
    position_code = serializers.CharField(source='position_ref.code', read_only=True)
    formal_position_name = serializers.CharField(source='position_ref.name', read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'seniority',
            'department_id', 'department_name', 'position',
        )

    def validate(self, attrs):
        department = attrs.get('department_ref', getattr(self.instance, 'department_ref', None))
        position = attrs.get('position_ref', getattr(self.instance, 'position_ref', None))
        employee_status = attrs.get('status', getattr(self.instance, 'status', 'active'))
        errors = {}
        if position and department and position.department_id != department.pk:
            errors['position_ref'] = '岗位不属于所选部门。'
        if position and department and position.company_id != department.company_id:
            errors['position_ref'] = '岗位与部门不属于同一公司。'
        if employee_status == 'active':
            if not department:
                errors['department_ref'] = '在职员工必须关联正式部门。'
            elif not department.is_active or not department.company.is_active:
                errors['department_ref'] = '在职员工必须关联启用公司下的启用部门。'
            if not position:
                errors['position_ref'] = '在职员工必须关联正式岗位。'
            elif not position.is_active:
                errors['position_ref'] = '在职员工必须关联启用岗位。'
        if errors:
            raise serializers.ValidationError(errors)
        if department:
            attrs['department_id'] = department.pk
            attrs['department_name'] = department.name
        if position:
            attrs['position'] = position.name
        return attrs

    def get_seniority(self, obj):
        if obj.hire_date:
            from datetime import date
            today = date.today()
            delta = today - obj.hire_date
            return delta.days // 365
        return None

class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = '__all__'

class EmployeeCertificateSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = EmployeeCertificate
        fields = ['id', 'employee', 'employee_name', 'certificate_name', 'certificate_no', 
                  'issue_date', 'expiry_date', 'issuing_authority', 'attachment_url', 
                  'remind_before_days', 'created_at']
        read_only_fields = ('id', 'created_at', 'employee_name')
