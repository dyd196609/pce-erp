from django.db import models

# Create your models here.
from django.db import models

class Employee(models.Model):
    """员工档案表"""
    user = models.OneToOneField(
        'system.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employee_profile', verbose_name='关联用户',
    )
    employee_no = models.CharField(max_length=50, unique=True, verbose_name='工号')
    full_name = models.CharField(max_length=50, verbose_name='姓名')
    gender = models.CharField(max_length=1, choices=[('M','男'),('F','女')], blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    id_card = models.CharField(max_length=18, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact = models.CharField(max_length=50, blank=True, null=True)
    emergency_phone = models.CharField(max_length=20, blank=True, null=True)
    hire_date = models.DateField(blank=True, null=True)
    leave_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=[
        ('active','在职'),('inactive','停用'),('leave','休假'),('quit','离职')
    ], default='active')
    department_id = models.BigIntegerField(blank=True, null=True)
    department_name = models.CharField(max_length=100, blank=True, null=True)
    position = models.CharField(max_length=50, blank=True, null=True)
    department_ref = models.ForeignKey(
        'system.Department', on_delete=models.PROTECT, null=True, blank=True,
        related_name='employee_profiles', verbose_name='正式部门',
    )
    position_ref = models.ForeignKey(
        'system.Position', on_delete=models.PROTECT, null=True, blank=True,
        related_name='employee_profiles', verbose_name='正式岗位',
    )
    work_shift_id = models.BigIntegerField(blank=True, null=True, verbose_name='班次ID')
    skills = models.TextField(blank=True, null=True, help_text='JSON数组，如["焊工","叉车"]')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resignation_date = models.DateField(blank=True, null=True, verbose_name='离职日期')

    class Meta:
        db_table = 'employee'
        managed = True
        verbose_name = '员工'
        verbose_name_plural = '员工'

    def __str__(self):
        return f"{self.employee_no}-{self.full_name}"


class Shift(models.Model):
    """班次表（二班倒/三班倒）"""
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_start = models.TimeField(blank=True, null=True)
    break_end = models.TimeField(blank=True, null=True)
    company_id = models.BigIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'shift'
        managed = True
        verbose_name = '班次'
        verbose_name_plural = '班次'

    def __str__(self):
        return self.name


class EmployeeCertificate(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='employee_id', related_name='certificates')
    certificate_name = models.CharField(max_length=100)
    certificate_no = models.CharField(max_length=100, blank=True, null=True)
    issue_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    issuing_authority = models.CharField(max_length=100, blank=True, null=True)
    attachment_url = models.CharField(max_length=255, blank=True, null=True)
    remind_before_days = models.IntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'employee_certificate'
        managed = True
        verbose_name = '员工证书'
        verbose_name_plural = '员工证书'

    def __str__(self):
        return f"{self.employee.full_name} - {self.certificate_name}"


class EmployeeReportingRelation(models.Model):
    """Formal employee reporting line; separate from Department and Position."""

    class RelationType(models.TextChoices):
        DIRECT = 'DIRECT', '直属主管'
        FUNCTIONAL = 'FUNCTIONAL', '职能汇报'

    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name='reporting_relations',
        verbose_name='员工',
    )
    manager = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name='managed_relations',
        verbose_name='主管',
    )
    relation_type = models.CharField(
        max_length=20, choices=RelationType.choices, default=RelationType.DIRECT,
        verbose_name='汇报类型',
    )
    is_primary = models.BooleanField(default=True, verbose_name='是否主汇报关系')
    active = models.BooleanField(default=True, verbose_name='是否启用')
    effective_from = models.DateField(null=True, blank=True, verbose_name='生效日期')
    effective_to = models.DateField(null=True, blank=True, verbose_name='失效日期')

    class Meta:
        db_table = 'employee_reporting_relation'
        verbose_name = '员工汇报关系'
        verbose_name_plural = '员工汇报关系'
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'relation_type'],
                condition=models.Q(active=True, is_primary=True),
                name='uniq_pfm_active_primary_reporting_relation',
            ),
            models.CheckConstraint(
                condition=~models.Q(employee=models.F('manager')),
                name='pfm_employee_manager_must_differ',
            ),
        ]


class OrganizationLeadershipAssignment(models.Model):
    """Employee leadership for an OrganizationUnit or Department without text guessing."""

    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name='organization_leaderships',
        verbose_name='负责人',
    )
    organization_unit = models.ForeignKey(
        'system.OrganizationUnit', on_delete=models.PROTECT, null=True, blank=True,
        related_name='leadership_assignments', verbose_name='组织单元',
    )
    department = models.ForeignKey(
        'system.Department', on_delete=models.PROTECT, null=True, blank=True,
        related_name='leadership_assignments', verbose_name='部门',
    )
    active = models.BooleanField(default=True, verbose_name='是否启用')
    effective_from = models.DateField(null=True, blank=True, verbose_name='生效日期')
    effective_to = models.DateField(null=True, blank=True, verbose_name='失效日期')

    class Meta:
        db_table = 'organization_leadership_assignment'
        verbose_name = '组织负责人关系'
        verbose_name_plural = '组织负责人关系'
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(organization_unit__isnull=False, department__isnull=True)
                    | models.Q(organization_unit__isnull=True, department__isnull=False)
                ),
                name='pfm_leadership_exactly_one_target',
            )
        ]
