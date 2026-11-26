"""
PCE 用户模型（对应数据库 user 表）
"""

import threading
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
    Group,
)
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("用户名必须提供")
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("company_id", 1)
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField("登录账号", max_length=50, unique=True)
    real_name = models.CharField("真实姓名", max_length=50)
    email = models.EmailField("邮箱", blank=True, null=True)
    mobile = models.CharField("手机号", max_length=20, blank=True, null=True)
    company_id = models.BigIntegerField("所属公司ID")
    is_active = models.BooleanField("是否启用", default=True)
    is_staff = models.BooleanField("是否员工", default=False)
    last_login = models.DateTimeField("最后登录时间", blank=True, null=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["real_name"]

    objects = UserManager()

    class Meta:
        db_table = "user_system"
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self):
        return f"{self.username}({self.real_name})"


class Company(models.Model):
    name = models.CharField("公司名称", max_length=100, unique=True)
    code = models.CharField("公司编码", max_length=20, unique=True)
    address = models.CharField("地址", max_length=200, blank=True)
    contact = models.CharField("联系人", max_length=50, blank=True)
    phone = models.CharField("联系电话", max_length=20, blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "公司"
        verbose_name_plural = "公司"

    def __str__(self):
        return self.name


class OrganizationUnit(models.Model):
    """Canonical operating hierarchy layered over existing Company/Department facts."""

    class UnitType(models.TextChoices):
        COMPANY = "COMPANY", "公司"
        BUSINESS_UNIT = "BUSINESS_UNIT", "事业部"
        CENTER = "CENTER", "中心"
        DEPARTMENT = "DEPARTMENT", "部门"
        TEAM = "TEAM", "团队/班组"

    code = models.CharField("组织单元编码", max_length=50)
    name = models.CharField("组织单元名称", max_length=100)
    unit_type = models.CharField("组织类型", max_length=30, choices=UnitType.choices)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="children", verbose_name="父组织",
    )
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="organization_units", verbose_name="所属公司"
    )
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)

    class Meta:
        verbose_name = "组织单元"
        verbose_name_plural = "组织单元"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uniq_system_org_unit_company_code"
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Department(models.Model):
    class DepartmentType(models.TextChoices):
        FUNCTIONAL = "FUNCTIONAL", "职能部门"
        BUSINESS = "BUSINESS", "业务部门"
        PRODUCTION = "PRODUCTION", "生产部门"
        SUPPORT = "SUPPORT", "支持部门"
        TEAM = "TEAM", "团队/班组"

    name = models.CharField("部门名称", max_length=100)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="上级部门",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="departments",
        verbose_name="所属公司",
    )
    code = models.CharField("部门编码", max_length=20, blank=True)
    manager = models.CharField("负责人", max_length=50, blank=True)
    department_type = models.CharField(
        "部门类型", max_length=20, choices=DepartmentType.choices,
        default=DepartmentType.FUNCTIONAL,
    )
    organization_unit = models.ForeignKey(
        OrganizationUnit, on_delete=models.PROTECT, null=True, blank=True,
        related_name="departments", verbose_name="组织单元",
    )
    responsible_position = models.ForeignKey(
        "Position", on_delete=models.PROTECT, null=True, blank=True,
        related_name="responsible_departments", verbose_name="责任岗位",
    )
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "部门"
        verbose_name_plural = "部门"
        unique_together = [["name", "company"]]

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class Workshop(models.Model):
    name = models.CharField("车间名称", max_length=100)
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="workshops",
        verbose_name="所属部门",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="workshops",
        verbose_name="所属公司",
    )
    code = models.CharField("车间编码", max_length=20)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "车间"
        verbose_name_plural = "车间"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="system_workshop_company_code_unique",
            ),
        ]

    def __str__(self):
        return f"{self.department.name if self.department else self.company.name} - {self.name}"


class Team(models.Model):
    name = models.CharField("班组名称", max_length=100)
    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.CASCADE,
        related_name="teams",
        verbose_name="所属车间",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="所属部门",
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="teams", verbose_name="所属公司"
    )
    code = models.CharField("班组编码", max_length=20, blank=True)
    leader = models.CharField("班组长", max_length=50, blank=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "班组"
        verbose_name_plural = "班组"

    def __str__(self):
        return f"{self.workshop.name} - {self.name}"

    def clean(self):
        super().clean()
        errors = {}
        if self.workshop_id and self.company_id and self.workshop.company_id != self.company_id:
            errors["workshop"] = "班组与所属车间必须属于同一公司。"
        if self.department_id and self.company_id and self.department.company_id != self.company_id:
            errors["department"] = "班组与所属部门必须属于同一公司。"
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "失效日期不能早于生效日期。"
        if errors:
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)


class Process(models.Model):
    UNSPECIFIED_DISPLAY_ORDER = 2147483647

    class TransitionMode(models.TextChoices):
        GENERAL = "GENERAL", "一般工序"
        KITTING = "KITTING", "齐套工序"

    class OperationKind(models.TextChoices):
        ATOMIC = "atomic", "单工序"
        GROUP = "group", "工序组"

    class CalculationBasis(models.TextChoices):
        COUNT = "count", "数量"
        LENGTH = "length", "长度"
        AREA = "area", "面积"
        VOLUME = "volume", "体积"
        MASS = "mass", "质量"
        TIME = "time", "时间"
        OTHER = "other", "其他"
        UNDETERMINED = "undetermined", "待确认"

    name = models.CharField("工序名称", max_length=100)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="processes",
        verbose_name="旧版默认班组（兼容）",
        help_text="仅保留旧数据兼容；正式可承担班组由工序班组能力关系维护。",
    )
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, null=True, blank=True,
        related_name="production_operations", verbose_name="所属公司",
    )
    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="operations",
        verbose_name="所属车间/生产区域",
        help_text="真实资料只确认车间时可维护；工作中心可后续补齐。",
    )
    work_center = models.ForeignKey(
        "pde.WorkCenter", on_delete=models.PROTECT, null=True, blank=True,
        related_name="operations", verbose_name="默认工作中心",
    )
    code = models.CharField("工序编码", max_length=20, blank=True)
    display_order = models.PositiveIntegerField(
        "展示顺序", default=UNSPECIFIED_DISPLAY_ORDER,
        help_text="仅表示工序主数据默认展示顺序；不替代任何RoutingStep.sequence。",
    )
    operation_kind = models.CharField(
        "工序类型", max_length=20, choices=OperationKind.choices,
        default=OperationKind.ATOMIC,
    )
    calculation_basis = models.CharField(
        "核算维度", max_length=20, choices=CalculationBasis.choices,
        default=CalculationBasis.UNDETERMINED,
        help_text="描述作业量的计量维度；面积是维度，不等同于具体计量单位。",
    )
    calculation_uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="calculated_operations", verbose_name="核算计量单位",
        help_text="具体正式UOM；来源只给出维度而未给具体单位时保持为空。",
    )
    quantity_driver = models.CharField(
        "投产量驱动", max_length=120, blank=True,
        help_text="受治理的作业量来源标识；未知或无法核算时保持为空。",
    )
    workload_source_selection = models.JSONField(
        "正式作业量来源方案引用", null=True, blank=True, default=None,
        help_text="由原工序维护服务保存精确产品/路线范围的完整正式方案引用；为空沿用既有规则。",
    )
    default_transition_mode = models.CharField(
        "默认转序方式", max_length=16, choices=TransitionMode.choices,
        default=TransitionMode.GENERAL,
        help_text="工序默认值；具体路线步骤存在覆盖值时，以路线步骤为准。",
    )
    description = models.TextField("描述", blank=True)
    standard_hours = models.DecimalField(
        "标准工时", max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="资料未维护时为空；标准产能由pde.StandardCapacity独立表达。",
    )
    skill_required = models.CharField("技能要求", max_length=160, blank=True)
    quality_check_required = models.BooleanField("是否质量检查点", default=False)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "工序"
        verbose_name_plural = "工序"
        ordering = ["company_id", "display_order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uniq_system_process_company_code"
            ),
            models.CheckConstraint(
                condition=models.Q(standard_hours__isnull=True) | models.Q(standard_hours__gt=0),
                name="system_process_hours_null_or_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(display_order__gt=0),
                name="system_process_display_order_positive",
            ),
        ]

    def __str__(self):
        owner = self.team.name if self.team_id else (self.company.name if self.company_id else "未归属")
        return f"{owner} - {self.name}"

    @property
    def calculation_measurement_status(self):
        """Return governed readiness without making a concrete UOM mandatory."""
        if self.calculation_uom_id:
            return "UOM_READY"
        if self.calculation_basis != self.CalculationBasis.UNDETERMINED:
            return "BASIS_ONLY_READY"
        return "UNDETERMINED"

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.workshop_id and self.company_id and self.workshop.company_id != self.company_id:
            errors["workshop"] = "车间必须属于工序所在公司"
        if self.work_center_id:
            if self.company_id and self.work_center.company_id != self.company_id:
                errors["work_center"] = "工作中心必须属于工序所在公司"
            if self.workshop_id and self.work_center.workshop_id not in {None, self.workshop_id}:
                errors["work_center"] = "工作中心必须属于工序所在车间"
        if self.calculation_uom_id:
            if self.company_id and self.calculation_uom.company_id != self.company_id:
                errors["calculation_uom"] = "核算单位必须属于工序所在公司"
            compatible = {
                "count": "count", "length": "length", "area": "area",
                "volume": "volume", "mass": "mass", "time": "time",
            }
            expected = compatible.get(self.calculation_basis)
            if expected and self.calculation_uom.dimension != expected:
                errors["calculation_uom"] = "核算单位维度与工序核算维度不一致"
        if errors:
            raise ValidationError(errors)


class ProcessTeamCapability(models.Model):
    """Time-bound many-to-many qualification between an operation and real teams."""

    operation = models.ForeignKey(
        Process, on_delete=models.PROTECT, related_name="team_capabilities", verbose_name="工序",
    )
    team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="operation_capabilities", verbose_name="班组",
    )
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    note = models.CharField("能力与安排说明", max_length=240, blank=True)

    class Meta:
        verbose_name = "工序班组能力关系"
        verbose_name_plural = "工序班组能力关系"
        constraints = [
            models.UniqueConstraint(
                fields=["operation", "team", "effective_from"],
                name="uniq_system_process_team_capability_period",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.operation_id and self.team_id:
            if self.operation.company_id != self.team.company_id:
                errors["team"] = "工序与班组必须属于同一公司。"
            if self.operation.workshop_id and self.team.workshop_id != self.operation.workshop_id:
                errors["team"] = "班组必须属于工序指定的车间/生产区域。"
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "失效日期不能早于生效日期。"
        if errors:
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.operation.name} - {self.team.name}"


class TeamMembership(models.Model):
    """Employee membership is independent from operation qualification and may vary by period."""

    team = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="memberships", verbose_name="班组",
    )
    employee = models.ForeignKey(
        "pfm.Employee", on_delete=models.PROTECT, related_name="team_memberships", verbose_name="员工",
    )
    role_label = models.CharField("班组内角色", max_length=80, blank=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "班组成员关系"
        verbose_name_plural = "班组成员关系"
        constraints = [
            models.UniqueConstraint(
                fields=["team", "employee", "effective_from"],
                name="uniq_system_team_membership_period",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        employee_company_id = (
            self.employee.department_ref.company_id
            if self.employee_id and self.employee.department_ref_id else None
        )
        if employee_company_id and self.team_id and employee_company_id != self.team.company_id:
            errors["employee"] = "班组成员必须属于班组所在公司。"
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "失效日期不能早于生效日期。"
        if errors:
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.team.name} - {self.employee.full_name}"


class JobFamily(models.Model):
    code = models.CharField("岗位族编码", max_length=50, unique=True)
    name = models.CharField("岗位族名称", max_length=100)
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="job_families", verbose_name="所属公司"
    )
    description = models.TextField("岗位族说明", blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "岗位族"
        verbose_name_plural = "岗位族"

    def __str__(self):
        return f"{self.code} - {self.name}"


class JobLevel(models.Model):
    code = models.CharField("岗位等级编码", max_length=50)
    name = models.CharField("岗位等级名称", max_length=100)
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="job_levels", verbose_name="所属公司"
    )
    rank = models.PositiveIntegerField("等级顺序", default=1)
    description = models.TextField("岗位等级说明", blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "岗位等级"
        verbose_name_plural = "岗位等级"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uniq_system_job_level_company_code"
            )
        ]
        ordering = ["company_id", "rank", "code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Position(models.Model):
    name = models.CharField("岗位名称", max_length=100, unique=True)
    code = models.CharField("岗位编码", max_length=20, unique=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="所属部门",
    )
    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="所属车间",
    )
    team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="所属班组"
    )
    process = models.ForeignKey(
        Process,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="所属工序",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="positions",
        verbose_name="所属公司",
    )
    group = models.OneToOneField(
        Group, on_delete=models.CASCADE, null=True, blank=True, verbose_name="权限组"
    )
    job_family = models.ForeignKey(
        JobFamily, on_delete=models.PROTECT, null=True, blank=True,
        related_name="positions", verbose_name="岗位族",
    )
    job_level = models.ForeignKey(
        JobLevel, on_delete=models.PROTECT, null=True, blank=True,
        related_name="positions", verbose_name="岗位等级",
    )
    parent_position = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="child_positions", verbose_name="上级岗位",
    )
    default_role = models.ForeignKey(
        "Role", on_delete=models.PROTECT, null=True, blank=True,
        related_name="default_positions", verbose_name="默认系统角色",
    )
    description = models.TextField("岗位说明", blank=True)
    responsibility_summary = models.TextField("岗位职责摘要", blank=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "岗位"
        verbose_name_plural = "岗位"

    def __str__(self):
        return f"{self.name} ({self.code})"


# ==============================
# 权限系统（新增）
# ==============================


class Role(models.Model):
    name = models.CharField("角色名称", max_length=50, unique=True)
    code = models.CharField("角色编码", max_length=50, unique=True)
    description = models.CharField("描述", max_length=200, blank=True)

    class Meta:
        verbose_name = "角色"
        verbose_name_plural = "角色"

    def __str__(self):
        return self.name


class Permission(models.Model):
    code = models.CharField("权限编码", max_length=100, unique=True)
    name = models.CharField("权限名称", max_length=100)
    module = models.CharField("所属模块", max_length=50)

    class Meta:
        verbose_name = "权限"
        verbose_name_plural = "权限"

    def __str__(self):
        return self.code


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, verbose_name="角色")
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, verbose_name="权限"
    )

    class Meta:
        verbose_name = "角色权限"
        verbose_name_plural = "角色权限"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="uniq_system_role_permission",
            )
        ]


class Responsibility(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "草稿"
        ACTIVE = "ACTIVE", "生效"
        SUSPENDED = "SUSPENDED", "暂停"
        EXPIRED = "EXPIRED", "失效"

    code = models.CharField("职责编码", max_length=80, unique=True)
    name = models.CharField("职责名称", max_length=120)
    description = models.TextField("职责说明", blank=True)
    category = models.CharField("职责类别", max_length=50, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    status = models.CharField(
        "状态", max_length=12, choices=Status.choices, default=Status.DRAFT,
    )
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)

    class Meta:
        verbose_name = "岗位职责"
        verbose_name_plural = "岗位职责"

    def __str__(self):
        return f"{self.code} - {self.name}"


class PositionResponsibility(models.Model):
    position = models.ForeignKey(
        Position, on_delete=models.PROTECT, related_name="responsibility_mappings",
        verbose_name="岗位",
    )
    responsibility = models.ForeignKey(
        Responsibility, on_delete=models.PROTECT, related_name="position_mappings",
        verbose_name="职责",
    )
    is_primary = models.BooleanField("是否主要职责", default=False)
    active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "岗位职责映射"
        verbose_name_plural = "岗位职责映射"
        constraints = [
            models.UniqueConstraint(
                fields=["position", "responsibility"],
                name="uniq_system_position_responsibility",
            )
        ]


class PositionWorkflowResponsibility(models.Model):
    class OwnershipType(models.TextChoices):
        OWNER = "OWNER", "负责"
        APPROVER = "APPROVER", "审批"
        REVIEWER = "REVIEWER", "审核/复核"
        EXECUTOR = "EXECUTOR", "执行"

    position = models.ForeignKey(
        Position, on_delete=models.PROTECT, related_name="workflow_responsibilities",
        verbose_name="责任岗位",
    )
    responsibility = models.ForeignKey(
        Responsibility, on_delete=models.PROTECT, null=True, blank=True,
        related_name="workflow_mappings", verbose_name="关联职责",
    )
    workflow_node = models.ForeignKey(
        "workflow_runtime.WorkflowNodeDefinition",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="position_responsibilities",
        verbose_name="正式流程节点",
    )
    workflow_code = models.CharField("流程编码", max_length=100)
    node_code = models.CharField("流程节点编码", max_length=100)
    ownership_type = models.CharField(
        "责任类型", max_length=20, choices=OwnershipType.choices,
        default=OwnershipType.OWNER,
    )
    active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)

    class Meta:
        verbose_name = "岗位流程责任"
        verbose_name_plural = "岗位流程责任"
        constraints = [
            models.UniqueConstraint(
                fields=["position", "workflow_code", "node_code", "ownership_type"],
                name="uniq_system_position_workflow_responsibility",
            )
        ]


class OrganizationOperatingAuditRecord(models.Model):
    """Domain audit fact for explicit organization operating-model writes."""

    action_code = models.CharField("业务动作编码", max_length=120)
    actor = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="organization_operating_audits",
        verbose_name="操作人",
    )
    organization = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="organization_operating_audits",
        verbose_name="所属公司",
    )
    target_type = models.CharField("修改对象类型", max_length=80)
    target_id = models.BigIntegerField("修改对象ID")
    target_label = models.CharField("修改对象", max_length=200)
    reason = models.CharField("修改原因", max_length=300)
    before_snapshot = models.JSONField("修改前", default=dict)
    after_snapshot = models.JSONField("修改后", default=dict)
    created_at = models.DateTimeField("修改时间", auto_now_add=True)

    class Meta:
        db_table = "system_organization_operating_audits"
        indexes = [models.Index(fields=['organization', 'target_type', 'target_id', 'action_code'],
            name='sys_audit_object_action_idx')]
        verbose_name = "组织运作修改审计"
        verbose_name_plural = "组织运作修改审计"
        ordering = ["-created_at", "-pk"]


class UserRoleScopeAssignment(models.Model):
    """PCE V1 formal user-role grant with a typed data scope."""

    class ScopeCode(models.TextChoices):
        SELF = "SELF", "本人"
        DEPARTMENT = "DEPARTMENT", "本部门"
        ORGANIZATION = "ORGANIZATION", "本组织"
        ALL = "ALL", "全部"
        CUSTOM = "CUSTOM", "自定义（预留）"

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="role_scope_assignments",
        verbose_name="登录账户",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="user_scope_assignments",
        verbose_name="系统角色",
    )
    organization = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="user_role_scope_assignments",
        verbose_name="授权组织",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="user_role_scope_assignments",
        verbose_name="授权部门",
    )
    scope_code = models.CharField(
        "数据范围",
        max_length=20,
        choices=ScopeCode.choices,
        default=ScopeCode.ORGANIZATION,
    )
    active = models.BooleanField("是否启用", default=True)
    version = models.PositiveIntegerField("版本", default=1)
    business_hash = models.CharField("业务哈希", max_length=64)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "system_user_role_scope_assignments"
        verbose_name = "用户角色数据范围"
        verbose_name_plural = "用户角色数据范围"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "organization"],
                name="uniq_system_user_role_organization_scope",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(scope_code="DEPARTMENT", department__isnull=False)
                    | ~models.Q(scope_code="DEPARTMENT")
                ),
                name="system_department_scope_requires_department",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.workshop_id and self.company_id and self.workshop.company_id != self.company_id:
            errors["workshop"] = "工序车间必须属于工序所在公司"
        if self.work_center_id:
            if self.company_id and self.work_center.company_id != self.company_id:
                errors["work_center"] = "默认工作中心必须属于工序所在公司"
            if (
                self.workshop_id
                and self.work_center.workshop_id
                and self.work_center.workshop_id != self.workshop_id
            ):
                errors["work_center"] = "默认工作中心与工序所属车间不一致"
        if self.team_id and self.workshop_id and self.team.workshop_id != self.workshop_id:
            errors["team"] = "班组与工序所属车间不一致"
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.user.username}/{self.role.code}/"
            f"{self.organization.code}/{self.scope_code}"
        )


# ==============================
# 菜单系统（新增）
# ==============================


class Menu(models.Model):
    name = models.CharField("菜单名称", max_length=50)
    code = models.CharField("菜单编码", max_length=100, unique=True)
    path = models.CharField("前端路由", max_length=200, blank=True)
    component = models.CharField("前端组件", max_length=200, blank=True)
    icon = models.CharField("菜单图标", max_length=50, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="上级菜单",
    )
    sort_order = models.IntegerField("排序号", default=0)
    permission_code = models.CharField("权限编码", max_length=100, blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "菜单"
        verbose_name_plural = "菜单"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class RoleMenu(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, verbose_name="角色")
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, verbose_name="菜单")

    class Meta:
        verbose_name = "角色菜单"
        verbose_name_plural = "角色菜单"
        unique_together = [["role", "menu"]]

    def __str__(self):
        return f"{self.role.name} - {self.menu.name}"


# @receiver(pre_save, sender=Position)
# def handle_position_group(sender, instance, **kwargs):
#     """在保存 Position 之前，自动关联或创建 Group"""
#     if instance.is_active:
#         group_name = f"pos_{instance.code}"
#         group, _ = Group.objects.get_or_create(name=group_name)
#         if instance.group_id != group.id:
#             instance.group = group
#     else:
#         # 如果停用，断开与 Group 的关联（Group 保留，不自动删除）
#         if instance.group_id:
#             instance.group = None


# @receiver(post_delete, sender=Position)
# def delete_orphan_group(sender, instance, **kwargs):
#     """删除 Position 时，如果关联的 Group 没有其他 Position 使用，则删除（可选）"""
#     if instance.group and not Position.objects.filter(group=instance.group).exclude(pk=instance.pk).exists():
#         instance.group.delete()


class ImmutableAuditSourceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError('Audit source evidence is append-only')

    def delete(self):
        raise ValueError('Audit source evidence cannot be deleted')


class AuditSourceEvent(models.Model):
    """Original audit evidence under a stable source namespace, not a replayed action."""
    organization = models.ForeignKey(Company, on_delete=models.PROTECT)
    source_namespace = models.CharField(max_length=100)
    source_audit_id = models.BigIntegerField()
    source_sha256 = models.CharField(max_length=64)
    content_hash = models.CharField(max_length=64)
    original_payload = models.JSONField()
    active_audit = models.ForeignKey(OrganizationOperatingAuditRecord, null=True, on_delete=models.PROTECT)
    registered_by = models.ForeignKey(User, on_delete=models.PROTECT)
    registered_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableAuditSourceQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('Audit source evidence is immutable')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Audit source evidence cannot be deleted')

    class Meta:
        db_table = 'system_audit_source_event'
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['organization','source_namespace','source_audit_id'],name='audit_source_identity_once')]
