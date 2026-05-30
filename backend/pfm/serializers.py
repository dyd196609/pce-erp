from rest_framework import serializers
from .models import Employee, Shift, EmployeeCertificate

class EmployeeSerializer(serializers.ModelSerializer):
    seniority = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'seniority')

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