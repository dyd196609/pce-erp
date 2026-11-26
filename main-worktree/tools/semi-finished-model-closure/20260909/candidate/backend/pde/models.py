from django.core.exceptions import ValidationError
from django.db import models
from decimal import Decimal
from .material_configuration_models import (
    MaterialConfiguration, MaterialConfigurationAttribute,
    MaterialFamilyAllowedMaterial, MaterialConfigurationSourceBinding,
)


class ManufacturingApplicabilityScope(models.TextChoices):
    PRODUCT_DEFINITION = "PRODUCT_DEFINITION", "长期产品定义"
    PRODUCT_CATEGORY = "PRODUCT_CATEGORY", "产品分类/模板"
    ORDER_ENGINEERING = "ORDER_ENGINEERING", "订单工程实例"


class ProductCategory(models.Model):
    class IndustryType(models.TextChoices):
        PRINTING = "printing", "印刷"
        WHOLE_HOUSE_WOOD = "wholeHouseWood", "全屋定制/整木"
        GENERAL = "general", "通用制造"

    code = models.CharField("分类编码", max_length=50)
    name = models.CharField("分类名称", max_length=120)
    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="product_categories", verbose_name="所属公司",
    )
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="children", verbose_name="上级分类",
    )
    industry_type = models.CharField(
        "行业语义代码", max_length=64, default=IndustryType.GENERAL,
        help_text="受治理的配置代码；不得据此在通用Schema写入行业专属字段。",
    )
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_product_category"
        ordering = ("company_id", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"), name="pde_product_category_company_code_unique"
            )
        ]

    def clean(self):
        if self.parent_id and self.parent.company_id != self.company_id:
            raise ValidationError({"parent": "上级分类必须属于同一公司"})
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "失效日期不得早于生效日期"})


class ManufacturingProcessType(models.Model):
    """Company-maintained manufacturing/finishing process dimension."""

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="manufacturing_process_types", verbose_name="所属公司",
    )
    code = models.CharField("工艺类型编码", max_length=64)
    name = models.CharField("工艺类型名称", max_length=160)
    description = models.CharField("说明", max_length=300, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_manufacturing_process_type"
        ordering = ("company_id", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"),
                name="pde_process_type_company_code_unique",
            ),
            models.UniqueConstraint(
                fields=("company", "name"),
                name="pde_process_type_company_name_unique",
            ),
        ]

    def clean(self):
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "失效日期不得早于生效日期"})


class WorkCenter(models.Model):
    code = models.CharField("工作中心编码", max_length=50)
    name = models.CharField("工作中心名称", max_length=120)
    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="production_work_centers", verbose_name="所属公司",
    )
    department = models.ForeignKey(
        "system.Department", on_delete=models.PROTECT,
        related_name="production_work_centers", verbose_name="所属部门",
    )
    workshop = models.ForeignKey(
        "system.Workshop", on_delete=models.PROTECT, null=True, blank=True,
        related_name="production_work_centers", verbose_name="所属车间",
    )
    standard_labor_capacity = models.DecimalField(
        "标准人工产能", max_digits=18, decimal_places=4, default=0
    )
    machine_hours = models.DecimalField("机器工时", max_digits=18, decimal_places=4, default=0)
    unit_labor_cost = models.DecimalField("单位人工成本", max_digits=18, decimal_places=4, default=0)
    manufacturing_overhead = models.DecimalField("制造费用", max_digits=18, decimal_places=4, default=0)
    resource_capabilities = models.JSONField(
        "资源能力边界", default=dict, blank=True,
        help_text="设备、人员、工装和工艺能力的受治理描述；不把设备等同于工作中心。",
    )
    capacity_policy = models.JSONField(
        "产能策略边界", default=dict, blank=True,
        help_text="班次、日历、效率和队列等扩展边界；真实产能事实仍由StandardCapacity维护。",
    )
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_work_center"
        ordering = ("company_id", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"), name="pde_work_center_company_code_unique"
            ),
            models.CheckConstraint(condition=models.Q(standard_labor_capacity__gte=0), name="pde_wc_labor_capacity_nonnegative"),
            models.CheckConstraint(condition=models.Q(machine_hours__gte=0), name="pde_wc_machine_hours_nonnegative"),
            models.CheckConstraint(condition=models.Q(unit_labor_cost__gte=0), name="pde_wc_labor_cost_nonnegative"),
            models.CheckConstraint(condition=models.Q(manufacturing_overhead__gte=0), name="pde_wc_overhead_nonnegative"),
        ]

    def clean(self):
        if self.department_id and self.department.company_id != self.company_id:
            raise ValidationError({"department": "部门必须属于工作中心所在公司"})
        if self.workshop_id:
            if self.workshop.company_id != self.company_id:
                raise ValidationError({"workshop": "车间必须属于工作中心所在公司"})
            if self.workshop.department_id and self.workshop.department_id != self.department_id:
                raise ValidationError({"workshop": "车间与工作中心所属部门不一致"})


class Equipment(models.Model):
    code = models.CharField("设备编码", max_length=50)
    name = models.CharField("设备名称", max_length=120)
    equipment_type = models.CharField("设备类型", max_length=80, blank=True)
    work_center = models.ForeignKey(
        WorkCenter, on_delete=models.PROTECT,
        related_name="equipment", verbose_name="所属工作中心",
    )
    capacity_per_hour = models.DecimalField("小时产能", max_digits=18, decimal_places=4, default=0)
    interface_identity = models.CharField(
        "标准接口标识", max_length=120, blank=True,
        help_text="只登记标准接口边界；协议、PLC和数据点需真实设备资料另行确认。",
    )
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_equipment"
        ordering = ("work_center__company_id", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("work_center", "code"), name="pde_equipment_work_center_code_unique"
            ),
            models.CheckConstraint(condition=models.Q(capacity_per_hour__gte=0), name="pde_equipment_capacity_nonnegative"),
        ]


class StandardCapacity(models.Model):
    """Industry-neutral capacity fact. Capacity and standard hours are separate facts."""

    class MeasurementStatus(models.TextChoices):
        MEASURED = "measured", "已测定"
        NOT_DETERMINABLE = "not_determinable", "适用但无法确定"

    class ResourceScope(models.TextChoices):
        WORK_CENTER = "work_center", "工作中心"
        OPERATION = "operation", "工序"
        EQUIPMENT = "equipment", "设备"
        COMPOSITE = "composite", "组合资源"

    class TimeBasis(models.TextChoices):
        NOT_MAINTAINED = "not_maintained", "时间基准未维护"
        HOUR = "hour", "每小时"
        SHIFT = "shift", "每班次"
        DAY = "day", "每日"
        BATCH = "batch", "每批次"
        CUSTOM = "custom", "自定义时间基准"

    code = models.CharField("产能编码", max_length=64)
    name = models.CharField("产能名称", max_length=160)
    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="standard_capacities", verbose_name="所属公司",
    )
    resource_scope = models.CharField(
        "资源范围", max_length=24, choices=ResourceScope.choices,
    )
    work_center = models.ForeignKey(
        WorkCenter, on_delete=models.PROTECT, null=True, blank=True,
        related_name="standard_capacities", verbose_name="工作中心",
    )
    operation = models.ForeignKey(
        "system.Process", on_delete=models.PROTECT, null=True, blank=True,
        related_name="standard_capacities", verbose_name="工序",
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, null=True, blank=True,
        related_name="standard_capacities", verbose_name="设备",
    )
    measurement_status = models.CharField(
        "产能测量状态", max_length=24,
        choices=MeasurementStatus.choices, default=MeasurementStatus.MEASURED,
        help_text="已测定必须有正数量；适用但无法确定时数量为空。无此工序不创建记录。",
    )
    quantity = models.DecimalField(
        "标准产能数量", max_digits=18, decimal_places=6, null=True, blank=True,
    )
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT,
        related_name="standard_capacities", verbose_name="计量单位",
    )
    time_basis = models.CharField(
        "时间基准", max_length=24, choices=TimeBasis.choices,
        default=TimeBasis.NOT_MAINTAINED,
    )
    time_basis_quantity = models.DecimalField(
        "时间基准数量", max_digits=12, decimal_places=4, null=True, blank=True,
    )
    standard_hours = models.DecimalField(
        "标准工时（可选）", max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="未知时必须为空，不得用0表示未维护。",
    )
    conditions = models.JSONField("适用条件", default=dict, blank=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_standard_capacity"
        ordering = ("company_id", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"), name="pde_standard_capacity_company_code_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(measurement_status="measured", quantity__gt=0)
                    | models.Q(measurement_status="not_determinable", quantity__isnull=True)
                ),
                name="pde_standard_capacity_measurement_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(standard_hours__isnull=True) | models.Q(standard_hours__gt=0),
                name="pde_standard_capacity_hours_null_or_positive",
            ),
        ]

    def clean(self):
        errors = {}
        if self.measurement_status == self.MeasurementStatus.MEASURED:
            if self.quantity is None or self.quantity <= 0:
                errors["quantity"] = "已测定产能必须填写大于0的数量"
        elif self.quantity is not None:
            errors["quantity"] = "产能无法确定时数量必须为空，不得用0表示"
        scope_requirements = {
            self.ResourceScope.WORK_CENTER: self.work_center_id,
            self.ResourceScope.OPERATION: self.operation_id,
            self.ResourceScope.EQUIPMENT: self.equipment_id,
        }
        if self.resource_scope in scope_requirements and not scope_requirements[self.resource_scope]:
            errors["resource_scope"] = "资源范围必须引用对应的正式资源"
        if self.work_center_id and self.work_center.company_id != self.company_id:
            errors["work_center"] = "工作中心必须属于产能所在公司"
        if self.operation_id and self.operation.company_id != self.company_id:
            errors["operation"] = "工序必须属于产能所在公司"
        if self.equipment_id and self.equipment.work_center.company_id != self.company_id:
            errors["equipment"] = "设备必须属于产能所在公司"
        if self.uom_id and self.uom.company_id != self.company_id:
            errors["uom"] = "计量单位必须属于产能所在公司"
        if self.time_basis == self.TimeBasis.NOT_MAINTAINED and self.time_basis_quantity is not None:
            errors["time_basis_quantity"] = "时间基准未维护时不得填写时间基准数量"
        if self.time_basis != self.TimeBasis.NOT_MAINTAINED and not self.time_basis_quantity:
            errors["time_basis_quantity"] = "已维护时间基准必须填写大于0的基准数量"
        if self.time_basis_quantity is not None and self.time_basis_quantity <= 0:
            errors["time_basis_quantity"] = "时间基准数量必须大于0"
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "失效日期不得早于生效日期"
        if errors:
            raise ValidationError(errors)


class ProductRequirement(models.Model):
    STATUS_CHOICES = (
        ("draft", "草稿"),
        ("reviewing", "评审中"),
        ("confirmed", "已确认"),
    )

    requirement_no = models.CharField("需求编号", max_length=64, unique=True)
    customer = models.CharField("客户", max_length=160)
    product_name = models.CharField("产品名称", max_length=160)
    requirement_source = models.CharField("需求来源", max_length=80)
    requirement_date = models.DateField("需求日期")
    owner = models.CharField("负责人", max_length=80)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_product_requirement"
        ordering = ("requirement_no",)


class ProductDefinition(models.Model):
    MANUFACTURING_DEFINITION_MODE_CHOICES = (
        ("standard", "标准制造"),
        ("order_engineered", "按单工程制造"),
    )
    STATUS_CHOICES = (
        ("draft", "草稿"),
        ("designed", "已设计"),
        ("released", "已发布"),
    )

    product_code = models.CharField("产品编码", max_length=64)
    product_name = models.CharField("产品名称", max_length=160)
    specification = models.CharField("规格", max_length=160, blank=True)
    model = models.CharField("型号", max_length=120, blank=True)
    version = models.CharField(
        "兼容版本投影", max_length=40, blank=True, default="",
        help_text="只由正式ProductVersion发布动作同步，不是独立版本事实源。",
    )
    emd_material_code = models.CharField(
        "EMD产品物料编码",
        max_length=64,
        help_text="引用企业主数据中心的成品或半成品物料，不在PDE分配物料编码。",
    )
    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_definitions", verbose_name="所属公司",
    )
    category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT, null=True, blank=True,
        related_name="products", verbose_name="产品分类",
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_definitions", verbose_name="成品/半成品物料",
    )
    manufacturing_definition_mode = models.CharField(
        "制造定义形成模式", max_length=24,
        choices=MANUFACTURING_DEFINITION_MODE_CHOICES, default="standard",
        help_text="只决定制造定义的形成路径；两种模式均发布为ProductManufacturingOutput。",
    )
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_product_definition"
        ordering = ("product_code",)
        constraints = [
            models.UniqueConstraint(
                fields=("company", "product_code"),
                name="pde_product_company_code_unique",
            )
        ]

    def clean(self):
        errors = {}
        if self.category_id and self.company_id and self.category.company_id != self.company_id:
            errors["category"] = "产品分类必须属于产品所在公司"
        if self.material_id:
            if self.company_id and self.material.company_id != self.company_id:
                errors["material"] = "产品物料必须属于产品所在公司"
            if self.material.material_type not in {"semi", "finished"}:
                errors["material"] = "产品只能引用半成品或成品物料"
            if self.emd_material_code and self.emd_material_code != self.material.code:
                errors["emd_material_code"] = "兼容物料编码必须与正式物料引用一致"
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "失效日期不得早于生效日期"
        if errors:
            raise ValidationError(errors)


class ProductTemplate(models.Model):
    """Industry-neutral template for standard, configurable and custom products."""

    PRODUCT_MODE_CHOICES = (
        ("standard", "标准产品"),
        ("configurable", "可配置产品"),
        ("custom", "定制产品"),
    )
    STATUS_CHOICES = (
        ("draft", "草稿"), ("reviewed", "已评审"),
        ("released", "已发布"), ("obsolete", "已失效"),
    )

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="product_templates", verbose_name="所属公司",
    )
    category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT,
        related_name="product_templates", verbose_name="产品分类",
    )
    template_code = models.CharField("模板编码", max_length=80)
    name = models.CharField("模板名称", max_length=200)
    product_mode = models.CharField(
        "产品模式", max_length=24, choices=PRODUCT_MODE_CHOICES,
        default="configurable",
    )
    parameter_schema = models.JSONField(
        "参数定义", default=dict,
        help_text="参数名称、类型、单位、范围和必填性；行业公式由正式规则引用，不写死在核心。",
    )
    attribute_schema = models.JSONField(
        "属性定义", default=dict, blank=True,
        help_text="饰面、颜色、纹理和可见面等可选属性定义。",
    )
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_product_template"
        ordering = ("company_id", "template_code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "template_code"),
                name="pde_product_template_company_code_unique",
            )
        ]

    def clean(self):
        errors = {}
        if self.category_id and self.category.company_id != self.company_id:
            errors["category"] = "产品模板分类必须属于同一公司"
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "失效日期不得早于生效日期"
        if errors:
            raise ValidationError(errors)


class ProductConfiguration(models.Model):
    """Immutable-source configuration request, distinct from a permanent SKU."""

    STATUS_CHOICES = (
        ("draft", "草稿"), ("validated", "已校验"),
        ("resolved", "已解析"), ("superseded", "已被替代"),
    )

    template = models.ForeignKey(
        ProductTemplate, on_delete=models.PROTECT,
        related_name="configurations", verbose_name="产品模板",
    )
    configuration_no = models.CharField("配置编号", max_length=100)
    parameters = models.JSONField("配置参数", default=dict)
    design_specification = models.JSONField("设计规格", default=dict, blank=True)
    delivery_context = models.JSONField(
        "交付上下文", default=dict, blank=True,
        help_text="Customer Order、Project、Space和Installation Location的稳定引用边界。",
    )
    input_hash = models.CharField("规范输入哈希", max_length=64)
    idempotency_key = models.CharField("幂等键", max_length=160)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_product_configuration"
        ordering = ("template_id", "configuration_no")
        constraints = [
            models.UniqueConstraint(
                fields=("template", "configuration_no"),
                name="pde_product_configuration_no_unique",
            ),
            models.UniqueConstraint(
                fields=("template", "idempotency_key"),
                name="pde_product_configuration_idempotency_unique",
            ),
        ]


class ConfiguredProduct(models.Model):
    """Order/project product instance resolved from a template configuration."""

    STATUS_CHOICES = (
        ("draft", "草稿"), ("resolved", "制造定义已解析"),
        ("released", "已发布"), ("inactive", "已失效"),
    )

    configuration = models.OneToOneField(
        ProductConfiguration, on_delete=models.PROTECT,
        related_name="configured_product", verbose_name="产品配置",
    )
    instance_no = models.CharField("配置产品实例编号", max_length=100)
    product_definition = models.ForeignKey(
        ProductDefinition, on_delete=models.PROTECT, null=True, blank=True,
        related_name="configured_instances", verbose_name="正式产品定义",
        help_text="按单产品无需因此创建永久SKU；需要正式产品身份时才引用。",
    )
    manufacturing_specification = models.JSONField(
        "制造规格", default=dict,
        help_text="由受治理规则从设计规格解析形成，不保存前端临时计算。",
    )
    resolution_hash = models.CharField("解析结果哈希", max_length=64)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_configured_product"
        ordering = ("configuration__template_id", "instance_no")
        constraints = [
            models.UniqueConstraint(
                fields=("configuration", "instance_no"),
                name="pde_configured_product_instance_unique",
            )
        ]


class ProductBOM(models.Model):
    """Canonical BOM header. BOM content belongs only to BOMVersion/BOMItem."""

    STATUS_CHOICES = (
        ("draft", "草稿"),
        ("released", "已发布"),
        ("obsolete", "已失效"),
    )
    BOM_TYPE_CHOICES = (
        ("manufacturing", "制造BOM"),
        ("packaging", "包装需求"),
        ("installation", "安装需求"),
    )

    applicability_scope = models.CharField(
        "适用主体类型", max_length=32,
        choices=ManufacturingApplicabilityScope.choices + [("MATERIAL", "物料"), ("MATERIAL_CONFIGURATION", "半成品物料配置")],
        default=ManufacturingApplicabilityScope.PRODUCT_DEFINITION,
    )
    product = models.ForeignKey(
        ProductDefinition, on_delete=models.PROTECT, null=True, blank=True,
        related_name="bom_lines", verbose_name="长期产品定义",
    )
    product_category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_boms", verbose_name="适用产品分类",
    )
    order_engineering_instance = models.ForeignKey(
        "pde.OrderEngineeringInstance", on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_boms", verbose_name="适用订单工程实例",
    )
    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_boms", verbose_name="所属公司",
    )
    bom_code = models.CharField("BOM编码", max_length=64, null=True, blank=True)
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, null=True, blank=True,
        related_name="applicable_manufacturing_boms", verbose_name="适用物料",
    )
    material_configuration = models.ForeignKey(
        "pde.MaterialConfiguration", on_delete=models.PROTECT, null=True, blank=True,
        related_name="boms", verbose_name="适用半成品物料配置",
    )
    name = models.CharField("BOM名称", max_length=160, blank=True)
    bom_type = models.CharField(
        "BOM类型", max_length=24, choices=BOM_TYPE_CHOICES,
        default="manufacturing",
    )
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_product_bom"
        ordering = ("company_id", "bom_code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "bom_code"),
                name="pde_bom_company_code_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        applicability_scope=ManufacturingApplicabilityScope.PRODUCT_DEFINITION,
                        product__isnull=False, product_category__isnull=True,
                        order_engineering_instance__isnull=True,
                        material__isnull=True, material_configuration__isnull=True,
                    )
                    | models.Q(
                        applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
                        product__isnull=True, product_category__isnull=False,
                        order_engineering_instance__isnull=True,
                        material__isnull=True, material_configuration__isnull=True,
                    )
                    | models.Q(
                        applicability_scope=ManufacturingApplicabilityScope.ORDER_ENGINEERING,
                        product__isnull=True, product_category__isnull=True,
                        order_engineering_instance__isnull=False,
                        material__isnull=True, material_configuration__isnull=True,
                    )
                    | models.Q(applicability_scope="MATERIAL", product__isnull=True,
                               product_category__isnull=True, order_engineering_instance__isnull=True,
                               material__isnull=False, material_configuration__isnull=True)
                    | models.Q(applicability_scope="MATERIAL_CONFIGURATION", product__isnull=True,
                               product_category__isnull=True, order_engineering_instance__isnull=True,
                               material__isnull=True, material_configuration__isnull=False)
                ),
                name="pde_bom_exactly_one_applicability_target",
            ),
            models.UniqueConstraint(fields=("company", "material_configuration", "bom_type"),
                condition=models.Q(applicability_scope="MATERIAL_CONFIGURATION", is_active=True),
                name="pde_active_mat_config_bom_unique"),
            models.UniqueConstraint(fields=("company", "material", "bom_type"),
                condition=models.Q(applicability_scope="MATERIAL", is_active=True),
                name="pde_active_material_bom_unique"),
            models.UniqueConstraint(
                fields=("company", "product_category", "bom_type"),
                condition=models.Q(
                    applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
                    is_active=True,
                ),
                name="pde_active_category_bom_unique",
            ),
            models.UniqueConstraint(
                fields=("company", "order_engineering_instance", "bom_type"),
                condition=models.Q(
                    applicability_scope=ManufacturingApplicabilityScope.ORDER_ENGINEERING,
                    is_active=True,
                ),
                name="pde_active_order_bom_unique",
            ),
        ]

    def clean(self):
        targets = {
            ManufacturingApplicabilityScope.PRODUCT_DEFINITION: self.product_id,
            ManufacturingApplicabilityScope.PRODUCT_CATEGORY: self.product_category_id,
            ManufacturingApplicabilityScope.ORDER_ENGINEERING: self.order_engineering_instance_id,
            "MATERIAL": self.material_id,
            "MATERIAL_CONFIGURATION": self.material_configuration_id,
        }
        if sum(value is not None for value in targets.values()) != 1 or not targets.get(self.applicability_scope):
            raise ValidationError({"applicability_scope": "BOM适用范围必须且只能引用与类型一致的一个主体"})
        if self.applicability_scope in {"MATERIAL", "MATERIAL_CONFIGURATION"} and not self.company_id:
            raise ValidationError({"company": "物料/配置BOM必须明确所属公司"})
        target = (
            self.product if self.product_id else
            self.product_category if self.product_category_id else
            self.order_engineering_instance if self.order_engineering_instance_id else
            self.material if self.material_id else self.material_configuration
        )
        if self.company_id and target.company_id != self.company_id:
            raise ValidationError({"company": "BOM与适用主体必须属于同一公司"})


class Routing(models.Model):
    """Canonical routing header. Steps belong only to RoutingVersion/RoutingStep."""

    STATUS_CHOICES = ProductBOM.STATUS_CHOICES

    applicability_scope = models.CharField(
        "适用主体类型", max_length=32,
        choices=ManufacturingApplicabilityScope.choices,
        default=ManufacturingApplicabilityScope.PRODUCT_DEFINITION,
    )
    product = models.ForeignKey(
        ProductDefinition, on_delete=models.PROTECT, null=True, blank=True,
        related_name="routings", verbose_name="长期产品定义",
    )
    product_category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT, null=True, blank=True,
        related_name="routings", verbose_name="适用产品分类",
    )
    order_engineering_instance = models.ForeignKey(
        "pde.OrderEngineeringInstance", on_delete=models.PROTECT, null=True, blank=True,
        related_name="routings", verbose_name="适用订单工程实例",
    )
    manufacturing_process_type = models.ForeignKey(
        ManufacturingProcessType, on_delete=models.PROTECT, null=True, blank=True,
        related_name="routings", verbose_name="工艺类型",
    )
    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_routings", verbose_name="所属公司",
    )
    routing_code = models.CharField("工艺路线编码", max_length=64, null=True, blank=True)
    name = models.CharField("工艺路线名称", max_length=160, blank=True)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_routing"
        ordering = ("company_id", "routing_code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "routing_code"),
                name="pde_routing_company_code_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        applicability_scope=ManufacturingApplicabilityScope.PRODUCT_DEFINITION,
                        product__isnull=False, product_category__isnull=True,
                        order_engineering_instance__isnull=True,
                    )
                    | models.Q(
                        applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
                        product__isnull=True, product_category__isnull=False,
                        order_engineering_instance__isnull=True,
                    )
                    | models.Q(
                        applicability_scope=ManufacturingApplicabilityScope.ORDER_ENGINEERING,
                        product__isnull=True, product_category__isnull=True,
                        order_engineering_instance__isnull=False,
                    )
                ),
                name="pde_routing_exactly_one_applicability_target",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY)
                    | models.Q(manufacturing_process_type__isnull=False)
                ),
                name="pde_category_routing_process_type_required",
            ),
            models.UniqueConstraint(
                fields=("company", "product_category", "manufacturing_process_type"),
                condition=models.Q(
                    applicability_scope=ManufacturingApplicabilityScope.PRODUCT_CATEGORY,
                    is_active=True,
                ),
                name="pde_active_category_process_route_unique",
            ),
            models.UniqueConstraint(
                fields=("company", "order_engineering_instance"),
                condition=models.Q(
                    applicability_scope=ManufacturingApplicabilityScope.ORDER_ENGINEERING,
                    is_active=True,
                ),
                name="pde_active_order_route_unique",
            ),
        ]

    def clean(self):
        targets = {
            ManufacturingApplicabilityScope.PRODUCT_DEFINITION: self.product_id,
            ManufacturingApplicabilityScope.PRODUCT_CATEGORY: self.product_category_id,
            ManufacturingApplicabilityScope.ORDER_ENGINEERING: self.order_engineering_instance_id,
        }
        errors = {}
        if sum(value is not None for value in targets.values()) != 1 or not targets.get(self.applicability_scope):
            errors["applicability_scope"] = "工艺路线适用范围必须且只能引用与类型一致的一个主体"
        else:
            target = (
                self.product if self.product_id else
                self.product_category if self.product_category_id else
                self.order_engineering_instance
            )
            if self.company_id and target.company_id != self.company_id:
                errors["company"] = "工艺路线与适用主体必须属于同一公司"
        if self.manufacturing_process_type_id:
            if self.manufacturing_process_type.company_id != self.company_id:
                errors["manufacturing_process_type"] = "工艺类型必须属于工艺路线所在公司"
        elif self.applicability_scope == ManufacturingApplicabilityScope.PRODUCT_CATEGORY:
            errors["manufacturing_process_type"] = "产品分类级工艺路线必须选择可维护的工艺类型"
        if errors:
            raise ValidationError(errors)


class EngineeringDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = (
        ("process", "工艺文件"),
        ("technical", "技术资料"),
        ("version_record", "版本记录"),
    )
    STATUS_CHOICES = (
        ("draft", "草稿"),
        ("released", "已发布"),
        ("obsolete", "已作废"),
    )

    document_no = models.CharField("资料编号", max_length=64, unique=True)
    document_name = models.CharField("资料名称", max_length=200)
    document_type = models.CharField("资料类型", max_length=32, choices=DOCUMENT_TYPE_CHOICES)
    version = models.CharField(
        "兼容版本投影", max_length=40, blank=True, default="",
        help_text="只由正式EngineeringDocumentVersion发布动作同步。",
    )
    product = models.ForeignKey(
        ProductDefinition,
        on_delete=models.PROTECT,
        related_name="engineering_documents",
    )
    product_bom = models.ForeignKey(
        ProductBOM,
        on_delete=models.PROTECT,
        related_name="engineering_documents",
    )
    routing = models.ForeignKey(
        Routing,
        on_delete=models.PROTECT,
        related_name="engineering_documents",
    )
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    effective_date = models.DateField("生效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_engineering_document"
        ordering = ("document_no",)


class ProductVersion(models.Model):
    STATUS_CHOICES = (
        ("draft", "草稿"),
        ("reviewed", "已评审"),
        ("released", "已发布"),
        ("obsolete", "已失效"),
    )

    product = models.ForeignKey(ProductDefinition, on_delete=models.PROTECT, related_name="product_versions")
    version_no = models.CharField("版本号", max_length=40)
    version_status = models.CharField("版本状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    effective_date = models.DateField("生效日期", null=True, blank=True)
    expire_date = models.DateField("失效日期", null=True, blank=True)
    change_reason = models.CharField("变更原因", max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_product_version"
        ordering = ("product__product_code", "version_no")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "version_no"),
                name="pde_product_version_unique",
            )
        ]


class EngineeringSourceRecord(models.Model):
    SOURCE_TYPE_CHOICES = (
        ("order_input", "订单工程输入"),
        ("design_package", "设计资料包"),
        ("controlled_import", "受控导入"),
        ("manual_confirmed", "人工确认资料"),
    )
    STATUS_CHOICES = (
        ("draft", "草稿"),
        ("confirmed", "已确认"),
        ("superseded", "已被替代"),
    )

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="engineering_source_records", verbose_name="所属公司",
    )
    source_no = models.CharField("工程来源编号", max_length=80)
    source_name = models.CharField("工程来源名称", max_length=200)
    source_type = models.CharField("来源类型", max_length=32, choices=SOURCE_TYPE_CHOICES)
    source_version = models.CharField("来源版本", max_length=40)
    source_payload = models.JSONField("原始来源快照", default=dict)
    content_hash = models.CharField("内容哈希", max_length=64)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    effective_date = models.DateField("生效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_engineering_source_record"
        ordering = ("company_id", "source_no", "source_version")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "source_no", "source_version"),
                name="pde_eng_source_company_no_version_unique",
            )
        ]


class EngineeringRuleDefinition(models.Model):
    RULE_KIND_CHOICES = (
        ("formula", "公式规则"),
        ("lookup", "查表规则"),
        ("decision", "判断规则"),
        ("mapping", "映射规则"),
    )
    STATUS_CHOICES = ProductVersion.STATUS_CHOICES

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="engineering_rule_definitions", verbose_name="所属公司",
    )
    rule_code = models.CharField("规则编码", max_length=80)
    rule_name = models.CharField("规则名称", max_length=200)
    version = models.CharField("规则版本", max_length=40)
    rule_kind = models.CharField("规则类型", max_length=24, choices=RULE_KIND_CHOICES)
    specification = models.JSONField("规则规格", default=dict)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_engineering_rule_definition"
        ordering = ("company_id", "rule_code", "version")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "rule_code", "version"),
                name="pde_eng_rule_company_code_version_unique",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.status == "released":
                immutable_fields = (
                    "company_id", "rule_code", "rule_name", "version", "rule_kind",
                    "specification", "effective_from", "effective_to",
                )
                changed = [
                    field for field in immutable_fields
                    if getattr(original, field) != getattr(self, field)
                ]
                if changed:
                    raise ValidationError({
                        "specification": (
                            "已发布规则核心定义不可修改；请创建新版本。"
                            f" 发生变化：{', '.join(changed)}"
                        )
                    })
        super().save(*args, **kwargs)


class OrderEngineeringInstance(models.Model):
    STATUS_CHOICES = (
        ("draft", "草稿"),
        ("source_confirmed", "工程来源已确认"),
        ("calculated", "工程转换已完成"),
        ("released", "制造定义已发布"),
        ("inactive", "已失效"),
    )

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="order_engineering_instances", verbose_name="所属公司",
    )
    instance_no = models.CharField("订单工程实例编号", max_length=80)
    sales_order_item = models.OneToOneField(
        "sales.SalesOrderItem", on_delete=models.PROTECT,
        related_name="order_engineering_instance", verbose_name="销售订单明细",
    )
    product = models.ForeignKey(
        ProductDefinition, on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_engineering_instances", verbose_name="长期产品定义",
    )
    baseline_product_version = models.ForeignKey(
        ProductVersion, on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_engineering_instances", verbose_name="基线产品版本",
    )
    product_category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_engineering_instances", verbose_name="产品分类",
    )
    selected_process_type = models.ForeignKey(
        ManufacturingProcessType, on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_engineering_instances", verbose_name="选定工艺类型",
    )
    source_record = models.ForeignKey(
        EngineeringSourceRecord, on_delete=models.PROTECT,
        related_name="order_engineering_instances", verbose_name="工程来源记录",
    )
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_order_engineering_instance"
        ordering = ("company_id", "instance_no")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "instance_no"),
                name="pde_order_eng_company_instance_no_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        product__isnull=False,
                        baseline_product_version__isnull=False,
                    )
                    | models.Q(
                        product__isnull=True,
                        baseline_product_version__isnull=True,
                        product_category__isnull=False,
                        selected_process_type__isnull=False,
                    )
                ),
                name="pde_order_eng_product_or_category_identity",
            ),
        ]

    def clean(self):
        errors = {}
        if self.sales_order_item.sales_order.company_id != self.company_id:
            errors["sales_order_item"] = "销售订单明细必须属于工程实例所在公司"
        if self.product_id:
            if self.product.company_id != self.company_id:
                errors["product"] = "产品必须属于工程实例所在公司"
            if self.product.manufacturing_definition_mode != "order_engineered":
                errors["product"] = "订单工程实例只能用于按单工程制造产品"
            if not self.baseline_product_version_id:
                errors["baseline_product_version"] = "存在长期产品时必须引用基线产品版本"
            elif self.baseline_product_version.product_id != self.product_id:
                errors["baseline_product_version"] = "基线产品版本必须属于当前产品"
        else:
            if self.baseline_product_version_id:
                errors["baseline_product_version"] = "没有长期产品时不得伪造基线产品版本"
            if not self.product_category_id:
                errors["product_category"] = "按单工程实例必须选择正式产品分类"
            elif self.product_category.company_id != self.company_id:
                errors["product_category"] = "产品分类必须属于工程实例所在公司"
            if not self.selected_process_type_id:
                errors["selected_process_type"] = "按单工程实例必须选择正式工艺类型"
        if self.selected_process_type_id and self.selected_process_type.company_id != self.company_id:
            errors["selected_process_type"] = "工艺类型必须属于工程实例所在公司"
        if self.source_record.company_id != self.company_id:
            errors["source_record"] = "工程来源记录必须属于工程实例所在公司"
        if self.product_id and self.sales_order_item.material_id != self.product.material_id:
            errors["sales_order_item"] = "订单明细物料必须与产品正式物料一致"
        if errors:
            raise ValidationError(errors)


class EngineeringCalculationRecord(models.Model):
    SCOPE_CHOICES = (
        ("validation", "规则技术验证"),
        ("order_engineering", "正式订单工程核算"),
    )
    STATUS_CHOICES = (
        ("draft", "草稿"),
        ("prepared", "已准备"),
        ("running", "执行中"),
        ("completed", "计算完成"),
        ("failed", "计算失败"),
        ("superseded", "已被新修订替代"),
        ("obsolete", "已失效"),
    )
    ERROR_CLASSIFICATION_CHOICES = (
        ("none", "无错误"),
        ("input_incomplete", "输入不完整"),
        ("rule_recoverable", "规则可恢复"),
        ("external_link_missing", "外部链接缺失"),
        ("irrecoverable", "不可恢复"),
    )

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_calculations", verbose_name="所属公司",
    )
    scope = models.CharField(
        "计算范围", max_length=24, choices=SCOPE_CHOICES,
        default="order_engineering",
    )
    source_record = models.ForeignKey(
        EngineeringSourceRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="calculation_records", verbose_name="工程来源记录",
    )
    sales_order_item = models.ForeignKey(
        "sales.SalesOrderItem", on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_calculations", verbose_name="销售订单明细",
    )
    engineering_instance = models.ForeignKey(
        OrderEngineeringInstance, on_delete=models.PROTECT,
        null=True, blank=True, related_name="calculation_records", verbose_name="订单工程实例",
    )
    calculation_no = models.CharField("计算记录编号", max_length=80)
    rule_set_version = models.CharField("规则集版本", max_length=80)
    revision = models.PositiveIntegerField("修订号", default=1)
    supersedes = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="revisions", verbose_name="替代的历史计算",
    )
    idempotency_key = models.CharField("幂等键", max_length=64, blank=True, default="")
    input_hash = models.CharField("规范输入哈希", max_length=64, blank=True, default="")
    rule_graph_hash = models.CharField("规则图哈希", max_length=64, blank=True, default="")
    result_hash = models.CharField("结果哈希", max_length=64, blank=True, default="")
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    error_classification = models.CharField(
        "错误分类", max_length=32, choices=ERROR_CLASSIFICATION_CHOICES, default="none",
    )
    error_code = models.CharField("错误编码", max_length=80, blank=True, default="")
    error_message = models.TextField("错误信息", blank=True, default="")
    trace = models.JSONField("计算追踪", default=dict, blank=True)
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_engineering_calculation_record"
        ordering = ("engineering_instance_id", "calculation_no")
        constraints = [
            models.UniqueConstraint(
                fields=("engineering_instance", "calculation_no"),
                name="pde_eng_calc_instance_no_unique",
            ),
            models.UniqueConstraint(
                fields=("company", "calculation_no"),
                condition=models.Q(company__isnull=False),
                name="pde_eng_calc_company_no_unique",
            ),
            models.UniqueConstraint(
                fields=("company", "idempotency_key"),
                condition=~models.Q(idempotency_key=""),
                name="pde_eng_calc_company_idempotency_unique",
            ),
        ]

    def clean(self):
        errors = {}
        if self.company_id and self.source_record_id and self.source_record.company_id != self.company_id:
            errors["source_record"] = "工程来源记录必须属于计算所在公司"
        if self.sales_order_item_id and self.company_id:
            if self.sales_order_item.sales_order.company_id != self.company_id:
                errors["sales_order_item"] = "销售订单明细必须属于计算所在公司"
        if self.engineering_instance_id:
            if self.company_id and self.engineering_instance.company_id != self.company_id:
                errors["engineering_instance"] = "订单工程实例必须属于计算所在公司"
            if self.sales_order_item_id and self.engineering_instance.sales_order_item_id != self.sales_order_item_id:
                errors["engineering_instance"] = "订单工程实例必须对应当前销售订单明细"
            if self.source_record_id and self.engineering_instance.source_record_id != self.source_record_id:
                errors["engineering_instance"] = "订单工程实例必须引用当前工程来源记录"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.status in {"completed", "failed", "superseded", "obsolete"}:
                immutable_fields = (
                    "company_id", "scope", "source_record_id", "sales_order_item_id",
                    "engineering_instance_id", "calculation_no", "rule_set_version",
                    "revision", "supersedes_id", "idempotency_key", "input_hash",
                    "rule_graph_hash", "result_hash", "trace", "started_at", "finished_at",
                    "error_classification", "error_code", "error_message",
                )
                changed = [
                    field for field in immutable_fields
                    if getattr(original, field) != getattr(self, field)
                ]
                if changed:
                    raise ValidationError({
                        "trace": "终态计算证据不可覆盖；输入或规则变化必须创建新修订。"
                    })
        super().save(*args, **kwargs)


class EngineeringCalculationDetail(models.Model):
    STATUS_CHOICES = (
        ("running", "执行中"),
        ("succeeded", "成功"),
        ("failed", "失败"),
    )

    calculation = models.ForeignKey(
        EngineeringCalculationRecord, on_delete=models.PROTECT,
        related_name="details", verbose_name="计算记录",
    )
    sequence = models.PositiveIntegerField("执行顺序")
    rule = models.ForeignKey(
        EngineeringRuleDefinition, on_delete=models.PROTECT,
        related_name="calculation_details", verbose_name="规则定义",
    )
    rule_code = models.CharField("规则编码快照", max_length=80)
    rule_version = models.CharField("规则版本快照", max_length=40)
    expression_snapshot = models.TextField("表达式快照")
    input_snapshot = models.JSONField("输入快照", default=dict)
    dependency_snapshot = models.JSONField("依赖快照", default=list)
    output_name = models.CharField("输出规范名", max_length=160)
    output_value = models.JSONField("输出值", null=True, blank=True)
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_calculation_details", verbose_name="计量单位",
    )
    precision = models.PositiveSmallIntegerField("计算精度")
    rounding = models.CharField("舍入策略", max_length=32)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="running")
    error_code = models.CharField("错误编码", max_length=80, blank=True, default="")
    error_message = models.TextField("错误信息", blank=True, default="")
    started_at = models.DateTimeField("开始时间")
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)

    class Meta:
        db_table = "pde_engineering_calculation_detail"
        ordering = ("calculation_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("calculation", "sequence"),
                name="pde_eng_calc_detail_sequence_unique",
            )
        ]


class EngineeringBreakdownItem(models.Model):
    ITEM_TYPE_CHOICES = (
        ("component", "构件/部件"),
        ("operation", "工序需求"),
        ("capacity", "产能需求"),
        ("other", "其它派生项"),
    )

    calculation = models.ForeignKey(
        EngineeringCalculationRecord, on_delete=models.PROTECT,
        related_name="breakdown_items", verbose_name="计算记录",
    )
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="children", verbose_name="上级拆分项",
    )
    line_no = models.PositiveIntegerField("行号")
    item_type = models.CharField("拆分项类型", max_length=24, choices=ITEM_TYPE_CHOICES)
    item_code = models.CharField("拆分项编码", max_length=120)
    item_name = models.CharField("拆分项名称", max_length=200)
    attributes = models.JSONField("通用属性", default=dict, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_engineering_breakdown_item"
        ordering = ("calculation_id", "line_no")
        constraints = [
            models.UniqueConstraint(
                fields=("calculation", "line_no"), name="pde_eng_breakdown_calc_line_unique",
            )
        ]

    def clean(self):
        if self.parent_id and self.parent.calculation_id != self.calculation_id:
            raise ValidationError({"parent": "上级拆分项必须属于同一计算记录"})


class EngineeringDerivedFact(models.Model):
    calculation = models.ForeignKey(
        EngineeringCalculationRecord, on_delete=models.PROTECT,
        related_name="derived_facts", verbose_name="计算记录",
    )
    breakdown_item = models.ForeignKey(
        EngineeringBreakdownItem, on_delete=models.PROTECT, null=True, blank=True,
        related_name="derived_facts", verbose_name="拆分项",
    )
    rule = models.ForeignKey(
        EngineeringRuleDefinition, on_delete=models.PROTECT, null=True, blank=True,
        related_name="derived_facts", verbose_name="来源规则",
    )
    source_detail = models.ForeignKey(
        EngineeringCalculationDetail, on_delete=models.PROTECT, null=True, blank=True,
        related_name="derived_facts", verbose_name="来源计算明细",
    )
    fact_code = models.CharField("派生事实编码", max_length=120)
    canonical_field = models.CharField("规范字段", max_length=160, blank=True, default="")
    sequence = models.PositiveIntegerField("序号", default=1)
    value = models.JSONField("派生值")
    value_type = models.CharField("值类型", max_length=20, default="decimal")
    source_type = models.CharField(
        "来源类型", max_length=32, default="ENGINEERING_DERIVED",
    )
    status = models.CharField("状态", max_length=24, default="active")
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_derived_facts", verbose_name="计量单位",
    )
    source_path = models.CharField("来源路径", max_length=500)
    trace = models.JSONField("派生追踪", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_engineering_derived_fact"
        ordering = ("calculation_id", "fact_code", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("calculation", "fact_code", "sequence"),
                name="pde_eng_fact_calc_code_sequence_unique",
            )
        ]

    def clean(self):
        errors = {}
        if self.breakdown_item_id and self.breakdown_item.calculation_id != self.calculation_id:
            errors["breakdown_item"] = "派生事实与拆分项必须属于同一计算记录"
        if self.source_detail_id and self.source_detail.calculation_id != self.calculation_id:
            errors["source_detail"] = "派生事实与计算明细必须属于同一计算记录"
        if self.source_type != "ENGINEERING_DERIVED":
            errors["source_type"] = "工程派生事实来源类型必须为ENGINEERING_DERIVED"
        if errors:
            raise ValidationError(errors)


class BOMVersion(models.Model):
    STATUS_CHOICES = ProductVersion.STATUS_CHOICES
    SCOPE_CHOICES = (
        ("standard", "标准BOM"),
        ("order_specific", "按单BOM"),
    )

    product = models.ForeignKey(
        ProductDefinition, on_delete=models.PROTECT, null=True, blank=True,
        related_name="bom_versions",
    )
    product_version = models.ForeignKey(
        ProductVersion, on_delete=models.PROTECT, null=True, blank=True,
        related_name="bom_versions",
    )
    bom = models.ForeignKey(
        ProductBOM, on_delete=models.PROTECT, null=True, blank=True,
        related_name="versions", verbose_name="BOM主表",
    )
    bom_version = models.CharField("BOM版本", max_length=40)
    revision = models.PositiveIntegerField("修订号", default=1)
    bom_scope = models.CharField(
        "BOM作用域", max_length=24, choices=SCOPE_CHOICES, default="standard",
    )
    order_engineering_instance = models.ForeignKey(
        OrderEngineeringInstance, on_delete=models.PROTECT, null=True, blank=True,
        related_name="bom_versions", verbose_name="订单工程实例",
    )
    effective_date = models.DateField("生效日期", null=True, blank=True)
    expire_date = models.DateField("失效日期", null=True, blank=True)
    approval_state = models.CharField(
        "审批状态", max_length=40, default="not_submitted",
        help_text="对象生命周期投影；审批事实由正式BPM/Workflow Runtime持有。",
    )
    applicability = models.JSONField(
        "适用条件", default=dict, blank=True,
        help_text="并行版本存在时必须提供可确定的适用条件。",
    )
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_bom_version"
        ordering = ("bom_id", "bom_version")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "bom_version"),
                name="pde_bom_version_unique",
            ),
            models.UniqueConstraint(
                fields=("bom", "bom_version"),
                condition=models.Q(bom__isnull=False),
                name="pde_bom_header_version_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(product__isnull=True, product_version__isnull=True)
                    | models.Q(product__isnull=False, product_version__isnull=False)
                ),
                name="pde_bom_version_product_pair_consistent",
            ),
        ]

    def clean(self):
        errors = {}
        if self.product_version_id and self.product_version.product_id != self.product_id:
            errors["product_version"] = "产品版本必须属于当前产品"
        if self.bom_id:
            if self.bom.applicability_scope == ManufacturingApplicabilityScope.PRODUCT_DEFINITION:
                if self.bom.product_id != self.product_id:
                    errors["bom"] = "BOM版本产品必须与BOM主表适用产品一致"
                if not self.product_version_id:
                    errors["product_version"] = "产品级BOM版本必须引用正式产品版本"
            elif self.product_id or self.product_version_id:
                errors["product"] = "分类级或订单工程级BOM版本必须继承Header，不得重复绑定产品"
            if self.bom.applicability_scope in {"MATERIAL", "MATERIAL_CONFIGURATION"} and self.order_engineering_instance_id:
                errors["order_engineering_instance"] = "物料/配置BOM版本只能继承Header，不能混挂订单实例"
            if (
                self.bom.applicability_scope == ManufacturingApplicabilityScope.ORDER_ENGINEERING
                and self.bom.order_engineering_instance_id != self.order_engineering_instance_id
            ):
                errors["order_engineering_instance"] = "按单BOM版本必须继承Header订单工程实例"
        elif not self.product_id or not self.product_version_id:
            errors["bom"] = "兼容的无Header BOM版本必须提供产品及产品版本"
        if self.bom_scope == "standard" and self.order_engineering_instance_id:
            errors["order_engineering_instance"] = "标准BOM不得绑定订单工程实例"
        if self.bom_scope == "order_specific" and not self.order_engineering_instance_id:
            errors["order_engineering_instance"] = "按单BOM必须绑定订单工程实例"
        if self.order_engineering_instance_id:
            if self.product_id and self.order_engineering_instance.product_id != self.product_id:
                errors["order_engineering_instance"] = "订单工程实例必须属于当前产品"
            if self.product_version_id and self.order_engineering_instance.baseline_product_version_id != self.product_version_id:
                errors["product_version"] = "按单BOM必须引用订单工程实例的基线产品版本"
        if self.effective_date and self.expire_date and self.expire_date < self.effective_date:
            errors["expire_date"] = "失效日期不得早于生效日期"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.status == "released":
                immutable = (
                    "product_id", "product_version_id", "bom_id", "bom_version",
                    "revision", "bom_scope", "order_engineering_instance_id",
                    "effective_date", "expire_date", "applicability",
                )
                if any(getattr(original, field) != getattr(self, field) for field in immutable):
                    raise ValidationError({"bom_version": "已发布BOM版本不可原地覆盖；请创建新版本。"})
        super().save(*args, **kwargs)


class RoutingVersion(models.Model):
    STATUS_CHOICES = ProductVersion.STATUS_CHOICES

    product = models.ForeignKey(
        ProductDefinition, on_delete=models.PROTECT, null=True, blank=True,
        related_name="routing_versions",
    )
    product_version = models.ForeignKey(
        ProductVersion, on_delete=models.PROTECT, null=True, blank=True,
        related_name="routing_versions",
    )
    routing = models.ForeignKey(
        Routing, on_delete=models.PROTECT, null=True, blank=True,
        related_name="versions", verbose_name="工艺路线主表",
    )
    routing_version = models.CharField("工艺版本", max_length=40)
    revision = models.PositiveIntegerField("修订号", default=1)
    effective_date = models.DateField("生效日期", null=True, blank=True)
    expire_date = models.DateField("失效日期", null=True, blank=True)
    approval_state = models.CharField(
        "审批状态", max_length=40, default="not_submitted",
        help_text="对象生命周期投影；审批事实由正式BPM/Workflow Runtime持有。",
    )
    applicability = models.JSONField(
        "适用条件", default=dict, blank=True,
        help_text="资源、产品、部件和配置适用条件；不得只按最大版本号选择。",
    )
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_routing_version"
        ordering = ("routing_id", "routing_version")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "routing_version"),
                name="pde_routing_version_unique",
            ),
            models.UniqueConstraint(
                fields=("routing", "routing_version"),
                condition=models.Q(routing__isnull=False),
                name="pde_routing_header_version_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(product__isnull=True, product_version__isnull=True)
                    | models.Q(product__isnull=False, product_version__isnull=False)
                ),
                name="pde_routing_version_product_pair_consistent",
            ),
        ]

    def clean(self):
        errors = {}
        if self.product_version_id and self.product_version.product_id != self.product_id:
            errors["product_version"] = "产品版本必须属于当前产品"
        if self.routing_id:
            if self.routing.applicability_scope == ManufacturingApplicabilityScope.PRODUCT_DEFINITION:
                if self.routing.product_id != self.product_id:
                    errors["routing"] = "工艺版本产品必须与Routing主表适用产品一致"
                if not self.product_version_id:
                    errors["product_version"] = "产品级工艺版本必须引用正式产品版本"
            elif self.product_id or self.product_version_id:
                errors["product"] = "分类级或订单工程级工艺版本必须继承Header，不得重复绑定产品"
        elif not self.product_id or not self.product_version_id:
            errors["routing"] = "兼容的无Header工艺版本必须提供产品及产品版本"
        if self.effective_date and self.expire_date and self.expire_date < self.effective_date:
            errors["expire_date"] = "失效日期不得早于生效日期"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.status == "released":
                immutable = (
                    "product_id", "product_version_id", "routing_id", "routing_version",
                    "revision", "effective_date", "expire_date", "applicability",
                )
                if any(getattr(original, field) != getattr(self, field) for field in immutable):
                    raise ValidationError({"routing_version": "已发布工艺版本不可原地覆盖；请创建新版本。"})
        super().save(*args, **kwargs)


class BOMItem(models.Model):
    ITEM_ROLE_CHOICES = (
        ("assembly", "总成/模块"), ("component", "组件"),
        ("part", "制造零件"), ("material", "材料"),
    )
    REQUIREMENT_TYPE_CHOICES = (
        ("manufacturing", "制造构成"), ("packaging", "包装需求"),
        ("installation", "安装需求"), ("process_consumable", "工艺耗材"),
        ("indirect", "间接材料"),
    )
    SUPPLY_TYPE_CHOICES = (
        ("MAKE", "自制"), ("BUY", "外购"),
        ("SUBCONTRACT", "委外"), ("MAKE_OR_BUY", "自制或外购"),
    )
    class ScrapRateStatus(models.TextChoices):
        MAINTAINED = "maintained", "已维护"
        NOT_MAINTAINED = "not_maintained", "待维护"

    class SubstituteStatus(models.TextChoices):
        NOT_MAINTAINED = "not_maintained", "待维护"
        CONFIRMED_NONE = "confirmed_none", "已确认无替代料"
        MAINTAINED = "maintained", "已维护替代料"

    bom_version = models.ForeignKey(
        BOMVersion, on_delete=models.PROTECT,
        related_name="items", verbose_name="BOM版本",
    )
    parent_item = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="children", verbose_name="上级BOM项",
    )
    line_no = models.PositiveIntegerField("行号")
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT,
        related_name="bom_items", verbose_name="物料",
    )
    quantity = models.DecimalField("数量", max_digits=18, decimal_places=6, null=True, blank=True)
    quantity_mode = models.CharField("数量方式", max_length=24, default="FIXED",
        choices=(("FIXED", "固定数量"), ("CALCULATED", "规则计算"), ("MANUAL", "工程人工指定")))
    engineering_rule = models.ForeignKey("pde.EngineeringRuleDefinition", on_delete=models.PROTECT,
        null=True, blank=True, related_name="bom_quantity_bindings", verbose_name="版本化数量规则")
    item_role = models.CharField(
        "结构角色", max_length=24, choices=ITEM_ROLE_CHOICES, default="material",
    )
    requirement_type = models.CharField(
        "需求类型", max_length=32, choices=REQUIREMENT_TYPE_CHOICES,
        default="manufacturing",
    )
    supply_type = models.CharField(
        "供给方式", max_length=24, choices=SUPPLY_TYPE_CHOICES,
        default="BUY",
    )
    order_specification = models.JSONField(
        "按单规格", default=dict, blank=True,
        help_text="玻璃等按单尺寸规格；不要求为每个尺寸创建永久SKU。",
    )
    manufacturing_attributes = models.JSONField(
        "制造属性", default=dict, blank=True,
        help_text="饰面、纹理、封边、孔槽和可见面等Part级属性。",
    )
    quantity_rule = models.JSONField(
        "参数数量规则", default=dict, blank=True,
        help_text="引用受治理参数/公式；核心不硬编码门数、铰链等行业公式。",
    )
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT,
        related_name="bom_items", verbose_name="单位",
    )
    scrap_rate_status = models.CharField(
        "损耗率维护状态", max_length=24,
        choices=ScrapRateStatus.choices, default=ScrapRateStatus.NOT_MAINTAINED,
    )
    scrap_rate = models.DecimalField(
        "损耗率", max_digits=8, decimal_places=6, null=True, blank=True, default=None,
        help_text="未知时必须为空；明确0只表示已确认零损耗。",
    )
    substitute_status = models.CharField(
        "替代料维护状态", max_length=24,
        choices=SubstituteStatus.choices, default=SubstituteStatus.NOT_MAINTAINED,
        help_text="无替代记录不等于已确认无替代料。",
    )
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_bom_item"
        ordering = ("bom_version_id", "line_no")
        constraints = [
            models.UniqueConstraint(fields=("bom_version", "line_no"), name="pde_bom_item_version_line_unique"),
            models.UniqueConstraint(
                fields=("bom_version", "parent_item", "material"),
                condition=models.Q(parent_item__isnull=False),
                name="pde_bom_item_parent_material_unique",
            ),
            models.UniqueConstraint(
                fields=("bom_version", "material"),
                condition=models.Q(parent_item__isnull=True),
                name="pde_bom_item_root_material_unique",
            ),
            models.CheckConstraint(condition=(
                models.Q(quantity_mode="FIXED", quantity__isnull=False, quantity__gt=0, engineering_rule__isnull=True)
                | models.Q(quantity_mode="CALCULATED", quantity__isnull=True)
                | (models.Q(quantity_mode="MANUAL", engineering_rule__isnull=True) & (models.Q(quantity__isnull=True) | models.Q(quantity__gt=0)))
            ), name="pde_bom_item_quantity_mode_valid"),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        scrap_rate_status="maintained",
                        scrap_rate__gte=0,
                        scrap_rate__lt=1,
                    )
                    | models.Q(
                        scrap_rate_status="not_maintained",
                        scrap_rate__isnull=True,
                    )
                ),
                name="pde_bom_item_scrap_rate_semantic_valid",
            ),
        ]

    def clean(self):
        errors = {}
        bom_company_id = (
            self.bom_version.bom.company_id
            if self.bom_version.bom_id else self.bom_version.product.company_id
        )
        if bom_company_id and self.material.company_id != bom_company_id:
            errors["material"] = "BOM物料必须属于BOM所在公司"
        if self.quantity_mode == "FIXED" and (self.quantity is None or self.quantity <= 0):
            errors["quantity"] = "固定数量必须明确且大于0"
        if self.quantity_mode == "CALCULATED" and self.quantity is not None:
            errors["quantity"] = "计算型数量由运行结果持有，BOM不得预填0、1或已计算结果"
        if self.quantity_mode != "CALCULATED" and self.engineering_rule_id:
            errors["engineering_rule"] = "只有计算型数量可绑定工程规则"
        if self.quantity_mode == "MANUAL" and self.quantity is not None and self.quantity <= 0:
            errors["quantity"] = "人工数量未知时为空；填写时必须大于0"
        if self.engineering_rule_id and self.engineering_rule.company_id != bom_company_id:
            errors["engineering_rule"] = "BOM数量规则必须同公司"
        if self.quantity_mode == "CALCULATED" and self.quantity_rule:
            errors["quantity_rule"] = "计算型数量只引用EngineeringRuleDefinition，不内嵌第二份公式"
        if self.uom.company_id != self.material.company_id:
            errors["uom"] = "BOM单位必须属于物料所在公司"
        if self.scrap_rate_status == self.ScrapRateStatus.MAINTAINED:
            if self.scrap_rate is None or self.scrap_rate < 0 or self.scrap_rate >= 1:
                errors["scrap_rate"] = "损耗率已维护时必须填写0（含）到1（不含）的值"
        elif self.scrap_rate is not None:
            errors["scrap_rate"] = "损耗率待维护时必须为空，不得用0表示未知"
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "失效日期不得早于生效日期"
        if self.parent_item_id and self.parent_item.bom_version_id != self.bom_version_id:
            errors["parent_item"] = "上级BOM项必须属于同一BOM版本"
        if self.parent_item_id and self.parent_item_id == self.pk:
            errors["parent_item"] = "BOM项不得以自身为上级"
        if errors:
            raise ValidationError(errors)


class BOMItemSubstitute(models.Model):
    bom_item = models.ForeignKey(
        BOMItem, on_delete=models.PROTECT,
        related_name="substitutes", verbose_name="BOM明细",
    )
    substitute_material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT,
        related_name="bom_substitute_usages", verbose_name="替代物料",
    )
    priority = models.PositiveIntegerField("优先级", default=1)
    conversion_rate = models.DecimalField("替代换算率", max_digits=18, decimal_places=6, default=1)
    approval_state = models.CharField("审批状态", max_length=40, default="not_submitted")
    applicability = models.JSONField("适用范围", default=dict, blank=True)
    cost_impact = models.JSONField("成本影响", default=dict, blank=True)
    quality_impact = models.JSONField("质量影响", default=dict, blank=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_bom_item_substitute"
        ordering = ("bom_item_id", "priority", "id")
        constraints = [
            models.UniqueConstraint(fields=("bom_item", "substitute_material"), name="pde_bom_substitute_material_unique"),
            models.CheckConstraint(condition=models.Q(conversion_rate__gt=0), name="pde_bom_substitute_rate_positive"),
        ]

    def clean(self):
        if self.bom_item.material_id == self.substitute_material_id:
            raise ValidationError({"substitute_material": "替代物料不得与原物料相同"})


class RoutingStep(models.Model):
    routing_version = models.ForeignKey(
        RoutingVersion, on_delete=models.PROTECT,
        related_name="steps", verbose_name="路线版本",
    )
    sequence = models.PositiveIntegerField("步骤顺序")
    operation = models.ForeignKey(
        "system.Process", on_delete=models.PROTECT,
        related_name="routing_steps", verbose_name="正式工序",
    )
    workshop = models.ForeignKey(
        "system.Workshop", on_delete=models.PROTECT, null=True, blank=True,
        related_name="routing_steps", verbose_name="正式车间",
        help_text="仅确认车间时允许不指定工作中心。",
    )
    work_center = models.ForeignKey(
        WorkCenter, on_delete=models.PROTECT, null=True, blank=True,
        related_name="routing_steps", verbose_name="正式工作中心",
        help_text="真实资料只确认Workshop时允许待维护，不得虚构工作中心。",
    )
    applies_to_item = models.ForeignKey(
        BOMItem, on_delete=models.PROTECT, null=True, blank=True,
        related_name="routing_steps", verbose_name="适用BOM项",
        help_text="用于部件/零件级路线；为空表示产品级路线步骤。",
    )
    standard_hours = models.DecimalField(
        "标准工时", max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="资料未维护时为空；标准产能由StandardCapacity独立表达。",
    )
    setup_hours = models.DecimalField("准备工时", max_digits=12, decimal_places=4, default=0)
    transfer_hours = models.DecimalField("转移工时", max_digits=12, decimal_places=4, default=0)
    quality_checkpoint = models.BooleanField("质量检查点", default=False)
    instruction = models.TextField("操作说明", blank=True)
    operation_parameters = models.JSONField("工序参数", default=dict, blank=True)
    predecessor_sequences = models.JSONField(
        "前置步骤顺序", default=list, blank=True,
        help_text="显式依赖序号，不以页面行顺序替代正式依赖。",
    )
    effective_transition_mode = models.CharField(
        "有效转序方式", max_length=16, choices=(
            ("GENERAL", "一般工序"), ("KITTING", "齐套工序"),
        ), null=True, blank=True,
        help_text="路线步骤覆盖值；为空时继承正式工序默认转序方式。",
    )
    resource_selection_rule = models.JSONField(
        "资源选择规则", default=dict, blank=True,
        help_text="允许按产品、材料和设备能力解析资源；不得把Operation永久写死到WorkCenter。",
    )
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_routing_step"
        ordering = ("routing_version_id", "sequence")
        constraints = [
            models.UniqueConstraint(fields=("routing_version", "sequence"), name="pde_routing_step_version_sequence_unique"),
            models.CheckConstraint(
                condition=models.Q(standard_hours__isnull=True) | models.Q(standard_hours__gt=0),
                name="pde_routing_step_hours_null_or_positive",
            ),
            models.CheckConstraint(condition=models.Q(setup_hours__gte=0), name="pde_routing_step_setup_hours_nonnegative"),
            models.CheckConstraint(condition=models.Q(transfer_hours__gte=0), name="pde_routing_step_transfer_hours_nonnegative"),
        ]

    def clean(self):
        errors = {}
        routing_company_id = (
            self.routing_version.routing.company_id
            if self.routing_version.routing_id else self.routing_version.product.company_id
        )
        if self.operation.company_id and routing_company_id and self.operation.company_id != routing_company_id:
            errors["operation"] = "路线步骤工序必须属于路线所在公司"
        if self.work_center_id and routing_company_id and self.work_center.company_id != routing_company_id:
            errors["work_center"] = "路线步骤工作中心必须属于路线所在公司"
        if self.workshop_id and routing_company_id and self.workshop.company_id != routing_company_id:
            errors["workshop"] = "路线步骤车间必须属于路线所在公司"
        if self.work_center_id and self.workshop_id and self.work_center.workshop_id:
            if self.work_center.workshop_id != self.workshop_id:
                errors["work_center"] = "路线步骤工作中心必须属于所选车间"
        if self.applies_to_item_id:
            bom_company_id = (
                self.applies_to_item.bom_version.bom.company_id
                if self.applies_to_item.bom_version.bom_id
                else self.applies_to_item.bom_version.product.company_id
            )
            if bom_company_id != routing_company_id:
                errors["applies_to_item"] = "路线步骤适用BOM项必须属于同一公司"
        predecessors = self.predecessor_sequences or []
        if any(not isinstance(value, int) or value <= 0 or value >= self.sequence for value in predecessors):
            errors["predecessor_sequences"] = "前置步骤必须是小于当前顺序的正整数"
        linked_work_center_id = getattr(self.operation, "work_center_id", None)
        if linked_work_center_id and self.work_center_id and linked_work_center_id != self.work_center_id:
            errors["operation"] = "工序默认工作中心与路线步骤工作中心不一致"
        if errors:
            raise ValidationError(errors)


class BOMItemRoutingAssignment(models.Model):
    """Decouples component routing selection from BOM version identity."""

    bom_item = models.ForeignKey(
        BOMItem, on_delete=models.PROTECT,
        related_name="routing_assignments", verbose_name="BOM项",
    )
    routing_version = models.ForeignKey(
        RoutingVersion, on_delete=models.PROTECT,
        related_name="component_assignments", verbose_name="工艺路线版本",
    )
    priority = models.PositiveIntegerField("优先级", default=1)
    selection_rule = models.JSONField("选择规则", default=dict, blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        db_table = "pde_bom_item_routing_assignment"
        ordering = ("bom_item_id", "priority")
        constraints = [
            models.UniqueConstraint(
                fields=("bom_item", "routing_version"),
                name="pde_bom_item_routing_unique",
            )
        ]

    def clean(self):
        bom_header = self.bom_item.bom_version.bom
        routing_header = self.routing_version.routing
        same_target = (
            bom_header.company_id == routing_header.company_id
            and bom_header.applicability_scope == routing_header.applicability_scope
            and bom_header.product_id == routing_header.product_id
            and bom_header.product_category_id == routing_header.product_category_id
            and bom_header.order_engineering_instance_id
            == routing_header.order_engineering_instance_id
        )
        if not same_target:
            raise ValidationError({"routing_version": "组件路线必须与BOM使用同一适用范围和目标"})
        if self.bom_item.supply_type == "BUY":
            raise ValidationError({"bom_item": "外购组件不得分配内部工艺路线"})


class BOMCompletenessRule(models.Model):
    """Product-family/template driven completeness rule; no industry formula in core."""

    SEVERITY_CHOICES = (("warning", "警告"), ("block", "阻断"))

    template = models.ForeignKey(
        ProductTemplate, on_delete=models.PROTECT,
        related_name="completeness_rules", verbose_name="产品模板",
    )
    rule_code = models.CharField("规则编码", max_length=100)
    severity = models.CharField("严重度", max_length=16, choices=SEVERITY_CHOICES)
    predicate = models.JSONField("适用条件", default=dict)
    requirement = models.JSONField("完整性要求", default=dict)
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)

    class Meta:
        db_table = "pde_bom_completeness_rule"
        ordering = ("template_id", "rule_code")
        constraints = [
            models.UniqueConstraint(
                fields=("template", "rule_code"),
                name="pde_bom_completeness_rule_unique",
            )
        ]


class EngineeringDocumentVersion(models.Model):
    STATUS_CHOICES = ProductVersion.STATUS_CHOICES

    document = models.ForeignKey(EngineeringDocument, on_delete=models.PROTECT, related_name="document_versions")
    document_name = models.CharField("资料名称", max_length=200)
    document_version = models.CharField("资料版本", max_length=40)
    product_version = models.ForeignKey(
        ProductVersion,
        on_delete=models.PROTECT,
        related_name="engineering_document_versions",
    )
    related_product = models.ForeignKey(
        ProductDefinition,
        on_delete=models.PROTECT,
        related_name="engineering_document_versions",
    )
    related_bom = models.ForeignKey(BOMVersion, on_delete=models.PROTECT, related_name="document_versions")
    related_routing = models.ForeignKey(RoutingVersion, on_delete=models.PROTECT, related_name="document_versions")
    effective_date = models.DateField("生效日期", null=True, blank=True)
    expire_date = models.DateField("失效日期", null=True, blank=True)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_engineering_document_version"
        ordering = ("document__document_no", "document_version")
        constraints = [
            models.UniqueConstraint(
                fields=("document", "document_version"),
                name="pde_engineering_document_version_unique",
            )
        ]

    def clean(self):
        errors = {}
        if self.product_version.product_id != self.related_product_id:
            errors["product_version"] = "工程资料产品版本必须属于关联产品"
        if self.related_bom.product_id != self.related_product_id:
            errors["related_bom"] = "工程资料BOM版本必须属于关联产品"
        if self.related_routing.product_id != self.related_product_id:
            errors["related_routing"] = "工程资料工艺版本必须属于关联产品"
        if self.related_bom.product_version_id != self.product_version_id:
            errors["related_bom"] = "工程资料BOM必须对应关联产品版本"
        if self.related_routing.product_version_id != self.product_version_id:
            errors["related_routing"] = "工程资料工艺必须对应关联产品版本"
        if self.document.product_id != self.related_product_id:
            errors["document"] = "工程资料版本必须属于资料主表产品"
        if self.document.product_bom_id != self.related_bom.bom_id:
            errors["document"] = "工程资料版本必须对应资料主表BOM"
        if self.document.routing_id != self.related_routing.routing_id:
            errors["document"] = "工程资料版本必须对应资料主表工艺路线"
        if errors:
            raise ValidationError(errors)


class EffectiveDateControl(models.Model):
    order_date = models.DateField("订单日期")
    product_version = models.ForeignKey(ProductVersion, on_delete=models.PROTECT, related_name="effective_controls")
    bom_version = models.ForeignKey(BOMVersion, on_delete=models.PROTECT, related_name="effective_controls")
    routing_version = models.ForeignKey(RoutingVersion, on_delete=models.PROTECT, related_name="effective_controls")
    is_effective = models.BooleanField("是否有效", default=False)
    rejection_reason = models.CharField("拒绝原因", max_length=500, blank=True)
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_effective_date_control"
        ordering = ("-evaluated_at",)

    def clean(self):
        errors = []
        versions = (
            ("产品版本", self.product_version, "version_status"),
            ("BOM版本", self.bom_version, "status"),
            ("工艺版本", self.routing_version, "status"),
        )
        for label, version, status_field in versions:
            if getattr(version, status_field) != "released":
                errors.append(f"{label}未发布或已失效")
            if version.effective_date and self.order_date < version.effective_date:
                errors.append(f"{label}尚未生效")
            if version.expire_date and self.order_date > version.expire_date:
                errors.append(f"{label}已经失效")
        if errors:
            raise ValidationError({"order_date": errors})


class EngineeringChangeNotice(models.Model):
    CHANGE_TYPE_CHOICES = (
        ("design", "设计变更"),
        ("material", "材料变更"),
        ("routing", "工艺变更"),
        ("document", "资料变更"),
    )
    STATUS_CHOICES = (
        ("draft", "草稿"),
        ("reviewing", "评审中"),
        ("approved", "已批准"),
        ("effective", "已生效"),
    )

    change_no = models.CharField("变更编号", max_length=64, unique=True)
    change_type = models.CharField("变更类型", max_length=24, choices=CHANGE_TYPE_CHOICES)
    reason = models.CharField("变更原因", max_length=500)
    before_version = models.ForeignKey(ProductVersion, on_delete=models.PROTECT, related_name="ecn_before")
    after_version = models.ForeignKey(ProductVersion, on_delete=models.PROTECT, related_name="ecn_after")
    effective_date = models.DateField("生效日期", null=True, blank=True)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_engineering_change_notice"
        ordering = ("change_no",)


class ProductManufacturingOutput(models.Model):
    DEFINITION_MODE_CHOICES = (
        ("standard", "标准制造定义"),
        ("order_specific", "按单制造定义"),
    )
    ENGINEERING_STATUS_CHOICES = (
        ("incomplete", "工程资料不完整"),
        ("ready", "工程资料已齐套"),
    )
    RELEASE_STATUS_CHOICES = (
        ("draft", "草稿"),
        ("engineering_review", "工程评审中"),
        ("released_to_manufacturing", "已发布至制造"),
        ("inactive", "已失效"),
    )

    product = models.ForeignKey(
        ProductDefinition,
        on_delete=models.PROTECT,
        related_name="manufacturing_outputs",
    )
    product_version = models.ForeignKey(
        ProductVersion,
        on_delete=models.PROTECT,
        related_name="manufacturing_outputs",
    )
    bom_version = models.ForeignKey(
        BOMVersion,
        on_delete=models.PROTECT,
        related_name="manufacturing_outputs",
    )
    routing_version = models.ForeignKey(
        RoutingVersion,
        on_delete=models.PROTECT,
        related_name="manufacturing_outputs",
    )
    engineering_document_version = models.ForeignKey(
        EngineeringDocumentVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="manufacturing_outputs",
        verbose_name="工程资料版本",
    )
    definition_mode = models.CharField(
        "制造定义模式", max_length=24,
        choices=DEFINITION_MODE_CHOICES, default="standard",
    )
    order_engineering_instance = models.ForeignKey(
        OrderEngineeringInstance, on_delete=models.PROTECT, null=True, blank=True,
        related_name="manufacturing_outputs", verbose_name="订单工程实例",
    )
    engineering_status = models.CharField(
        "工程状态",
        max_length=24,
        choices=ENGINEERING_STATUS_CHOICES,
        default="incomplete",
    )
    effective_date = models.DateField("生效日期", null=True, blank=True)
    release_status = models.CharField(
        "发布状态",
        max_length=32,
        choices=RELEASE_STATUS_CHOICES,
        default="draft",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_product_manufacturing_output"
        ordering = ("product__product_code", "product_version__version_no")
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "product", "product_version", "bom_version", "routing_version",
                    "engineering_document_version",
                ),
                name="pde_mfg_output_version_set_unique",
            ),
            models.UniqueConstraint(
                fields=("order_engineering_instance",),
                condition=models.Q(order_engineering_instance__isnull=False),
                name="pde_mfg_output_order_instance_unique",
            ),
        ]

    def clean(self):
        errors = {}
        if self.product_version.product_id != self.product_id:
            errors["product_version"] = "产品版本必须属于当前产品"
        if self.bom_version.product_id != self.product_id:
            errors["bom_version"] = "BOM版本必须属于当前产品"
        if self.routing_version.product_id != self.product_id:
            errors["routing_version"] = "工艺版本必须属于当前产品"
        if self.engineering_document_version_id:
            document_version = self.engineering_document_version
            if document_version.related_product_id != self.product_id:
                errors["engineering_document_version"] = "工程资料版本必须属于当前产品"
            if document_version.product_version_id != self.product_version_id:
                errors["engineering_document_version"] = "工程资料版本必须引用当前产品版本"
            if document_version.related_bom_id != self.bom_version_id:
                errors["engineering_document_version"] = "工程资料版本必须引用当前BOM版本"
            if document_version.related_routing_id != self.routing_version_id:
                errors["engineering_document_version"] = "工程资料版本必须引用当前工艺版本"
        if self.definition_mode == "standard" and self.order_engineering_instance_id:
            errors["order_engineering_instance"] = "标准制造定义不得绑定订单工程实例"
        if self.definition_mode == "standard" and self.bom_version.bom_scope != "standard":
            errors["bom_version"] = "标准制造定义必须引用标准BOM版本"
        if self.definition_mode == "order_specific" and not self.order_engineering_instance_id:
            errors["order_engineering_instance"] = "按单制造定义必须绑定订单工程实例"
        expected_mode = (
            "order_specific"
            if self.product.manufacturing_definition_mode == "order_engineered"
            else "standard"
        )
        if self.definition_mode != expected_mode:
            errors["definition_mode"] = "制造定义模式必须与产品定义形成模式一致"
        if self.order_engineering_instance_id:
            instance = self.order_engineering_instance
            if instance.product_id != self.product_id:
                errors["order_engineering_instance"] = "订单工程实例必须属于当前产品"
            if instance.baseline_product_version_id != self.product_version_id:
                errors["product_version"] = "按单制造定义必须使用订单工程实例的基线产品版本"
            if self.bom_version.bom_scope != "order_specific":
                errors["bom_version"] = "按单制造定义必须引用按单BOM版本"
            elif self.bom_version.order_engineering_instance_id != instance.pk:
                errors["bom_version"] = "按单BOM必须属于同一订单工程实例"
        if self.release_status == "released_to_manufacturing":
            if not self.engineering_document_version_id:
                errors["engineering_document_version"] = "发布至制造必须引用正式工程资料版本"
            version_statuses = (
                self.product_version.version_status,
                self.bom_version.status,
                self.routing_version.status,
                self.engineering_document_version.status if self.engineering_document_version_id else None,
            )
            if any(status != "released" for status in version_statuses):
                errors["release_status"] = "失效或未发布版本禁止输出至制造"
            if self.engineering_status != "ready":
                errors["engineering_status"] = "工程资料未齐套时禁止输出至制造"
        if errors:
            raise ValidationError(errors)


class ManufacturingInputReference(models.Model):
    TARGET_MODULE_CHOICES = (
        ("MRP", "物料需求计划"),
        ("SCM", "供应链管理中心"),
    )
    REFERENCE_STATUS_CHOICES = (
        ("draft", "草稿"),
        ("active", "有效引用"),
        ("inactive", "已停用"),
    )

    source_module = models.CharField("来源模块", max_length=16, default="PDE", editable=False)
    target_module = models.CharField("目标模块", max_length=16, choices=TARGET_MODULE_CHOICES)
    source_object = models.CharField("来源对象", max_length=80)
    target_object = models.CharField("目标对象", max_length=80)
    source_manufacturing_output = models.ForeignKey(
        ProductManufacturingOutput,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stable_input_references",
        verbose_name="稳定工程发布来源",
    )
    target_demand = models.ForeignKey(
        "planning.Demand",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="engineering_input_references",
        verbose_name="稳定计划需求目标",
    )
    reference_status = models.CharField(
        "引用状态",
        max_length=24,
        choices=REFERENCE_STATUS_CHOICES,
        default="draft",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_manufacturing_input_reference"
        ordering = ("target_module", "source_object", "target_object")
        constraints = [
            models.UniqueConstraint(
                fields=("source_module", "target_module", "source_object", "target_object"),
                name="pde_mfg_input_reference_unique",
            )
        ]

    def clean(self):
        errors = {}
        if self.source_module != "PDE":
            errors["source_module"] = "制造输入引用来源必须为PDE"
        if self.reference_status == "active" and not self.source_manufacturing_output_id:
            errors["source_manufacturing_output"] = "有效核心交接必须引用正式工程发布组合"
        if self.source_manufacturing_output_id and self.source_manufacturing_output.release_status != "released_to_manufacturing":
            errors["source_manufacturing_output"] = "未发布工程组合不得作为制造输入来源"
        if errors:
            raise ValidationError(errors)


class ProductEngineeringReadiness(models.Model):
    STATUS_CHOICES = (
        ("not_started", "未开始"),
        ("engineering_preparing", "工程准备中"),
        ("bom_completed", "BOM已完成"),
        ("routing_completed", "工艺路线已完成"),
        ("document_completed", "工程资料已完成"),
        ("manufacturing_ready", "制造准备完成"),
        ("mrp_ready", "MRP输入已准备"),
        ("completed", "已完成"),
    )
    DELIVERY_RISK_CHOICES = (
        ("on_track", "交期正常"),
        ("attention", "需要关注"),
        ("delayed", "存在延期风险"),
        ("blocked", "工程阻断"),
    )

    order_no = models.CharField(
        "兼容CRM订单号", max_length=64, blank=True, default="",
        help_text="历史只读兼容投影；新数据必须使用SalesOrder/SalesOrderItem正式引用。",
    )
    sales_order = models.ForeignKey(
        "sales.SalesOrder",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="engineering_readiness_records",
        verbose_name="正式销售订单",
    )
    sales_order_item = models.OneToOneField(
        "sales.SalesOrderItem",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="engineering_readiness",
        verbose_name="正式销售订单明细",
    )
    product = models.ForeignKey(
        ProductDefinition,
        on_delete=models.PROTECT,
        related_name="engineering_readiness_records",
    )
    delivery_date = models.DateField("客户交期")
    engineering_status = models.CharField("工程状态", max_length=32, choices=STATUS_CHOICES, default="not_started")
    bom_status = models.CharField("BOM状态", max_length=32, choices=STATUS_CHOICES, default="not_started")
    routing_status = models.CharField("工艺状态", max_length=32, choices=STATUS_CHOICES, default="not_started")
    document_status = models.CharField("资料状态", max_length=32, choices=STATUS_CHOICES, default="not_started")
    manufacturing_output_status = models.CharField(
        "制造输出状态",
        max_length=32,
        choices=STATUS_CHOICES,
        default="not_started",
    )
    mrp_ready_status = models.CharField("MRP状态", max_length=32, choices=STATUS_CHOICES, default="not_started")
    delivery_risk = models.CharField(
        "交期风险",
        max_length=24,
        choices=DELIVERY_RISK_CHOICES,
        default="on_track",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_product_engineering_readiness"
        ordering = ("delivery_date", "order_no")

    @property
    def production_input_ready(self):
        ready_states = {"manufacturing_ready", "mrp_ready", "completed"}
        return (
            self.manufacturing_output_status in ready_states
            and self.mrp_ready_status in {"mrp_ready", "completed"}
        )

    def clean(self):
        errors = {}
        if self.sales_order_item_id:
            if self.sales_order_id and self.sales_order_item.sales_order_id != self.sales_order_id:
                errors["sales_order_item"] = "订单明细必须属于当前销售订单"
            if self.sales_order_item.product_definition_id and self.sales_order_item.product_definition_id != self.product_id:
                errors["product"] = "工程准备产品必须与销售订单明细产品一致"
        if self.mrp_ready_status in {"mrp_ready", "completed"} and self.manufacturing_output_status not in {
            "manufacturing_ready",
            "mrp_ready",
            "completed",
        }:
            errors["mrp_ready_status"] = "制造输出未准备完成时不得标记MRP输入已准备"
        if errors:
            raise ValidationError(errors)


# Restored canonical contracts from wave26/27, isolated candidate only.
def _engineering_rule_is_test_only(rule):
    specification = rule.specification if isinstance(rule.specification, dict) else {}
    markers = (
        rule.rule_code,
        rule.rule_name,
        rule.version,
        specification.get("scope", ""),
        specification.get("ruleNature", ""),
        specification.get("rule_nature", ""),
    )
    return any(
        "TEST_ONLY" in str(value).upper() or "TEST ONLY" in str(value).upper()
        for value in markers
    )


class StructureRole(models.Model):
    """Tenant-maintained structural role vocabulary; never a coded product taxonomy."""

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="structure_roles", verbose_name="所属公司",
    )
    role_code = models.CharField("结构角色编码", max_length=80)
    role_name = models.CharField("结构角色名称", max_length=160)
    description = models.TextField("业务说明", blank=True, default="")
    applicability = models.JSONField(
        "适用范围", default=dict, blank=True,
        help_text="由企业维护适用品类、场景和约束；不得以Django choices固化角色。",
    )
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_structure_role"
        ordering = ("company_id", "role_code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "role_code"),
                name="pde_structure_role_company_code_unique",
            )
        ]


class EngineeringRuleCategory(models.Model):
    """Data-driven rule classification for material, operation, time and capacity."""

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="engineering_rule_categories", verbose_name="所属公司",
    )
    category_code = models.CharField("规则类别编码", max_length=100)
    category_name = models.CharField("规则类别名称", max_length=200)
    calculation_domain = models.CharField(
        "核算域", max_length=60,
        help_text="数据值，例如material、operation、standard_time、capacity。",
    )
    description = models.TextField("业务说明", blank=True, default="")
    input_contract = models.JSONField("输入契约", default=dict, blank=True)
    output_contract = models.JSONField("输出契约", default=dict, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_engineering_rule_category"
        ordering = ("company_id", "calculation_domain", "category_code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "category_code"),
                name="pde_eng_rule_category_company_code_unique",
            )
        ]


class ProductTemplateStructureNode(models.Model):
    """Industry-neutral structural slot; concrete manufacturing facts live on orders."""

    COMPONENT_TYPE_CHOICES = (
        ("assembly", "总成/模块"), ("component", "构件/组件"), ("part", "零件"),
    )
    SLOT_REQUIREMENT_CHOICES = (
        ("required", "必需"), ("optional", "可选"), ("conditional", "条件可选"),
    )

    template = models.ForeignKey(
        ProductTemplate, on_delete=models.PROTECT,
        related_name="structure_nodes", verbose_name="结构模板",
    )
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="children", verbose_name="上级结构槽位",
    )
    structure_role = models.ForeignKey(
        StructureRole, on_delete=models.PROTECT, null=True, blank=True,
        related_name="template_nodes", verbose_name="结构角色",
        help_text="Wave 2.7候选期允许为空；正式发布前应完成企业结构角色绑定。",
    )
    node_code = models.CharField("槽位编码", max_length=120)
    node_name = models.CharField("槽位名称", max_length=240)
    component_type = models.CharField(
        "建议构件类型", max_length=24, choices=COMPONENT_TYPE_CHOICES,
    )
    slot_requirement = models.CharField(
        "槽位要求", max_length=24, choices=SLOT_REQUIREMENT_CHOICES,
        default="required",
    )
    parameter_schema = models.JSONField(
        "订单参数定义", default=dict, blank=True,
        help_text="只定义参数名称、类型、范围和必填性，不保存订单实际尺寸。",
    )
    condition_schema = models.JSONField(
        "启用条件定义", default=dict, blank=True,
    )
    material_category_requirement = models.JSONField(
        "材料类别需求定义", default=dict, blank=True,
        help_text="只描述类别/能力需求，不得保存具体Material、品牌或型号。",
    )
    hardware_category_requirement = models.JSONField(
        "五金类别需求定义", default=dict, blank=True,
        help_text="只描述五金类别需求，不得保存具体Material、品牌或型号。",
    )
    routing_candidates = models.JSONField(
        "工艺候选定义", default=list, blank=True,
        help_text="仅提供候选或规则引用；订单最终工艺必须写入订单构件。",
    )
    default_rules = models.JSONField(
        "默认结构规则", default=dict, blank=True,
    )
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_product_template_structure_node"
        ordering = ("template_id", "node_code")
        constraints = [
            models.UniqueConstraint(
                fields=("template", "node_code"),
                name="pde_template_structure_node_code_unique",
            )
        ]

    def clean(self):
        errors = {}
        if self.structure_role_id and self.structure_role.company_id != self.template.company_id:
            errors["structure_role"] = "结构角色必须与产品模板属于同一公司"
        if self.parent_id:
            if self.parent.template_id != self.template_id:
                errors["parent"] = "上级结构槽位必须属于同一产品模板"
            else:
                ancestor = self.parent
                seen = set()
                while ancestor is not None:
                    marker = ancestor.pk if ancestor.pk is not None else id(ancestor)
                    if marker in seen or ancestor is self or (
                        self.pk is not None and ancestor.pk == self.pk
                    ):
                        errors["parent"] = "模板结构槽位不得形成循环"
                        break
                    seen.add(marker)
                    ancestor = ancestor.parent
        if self.slot_requirement == "conditional" and not self.condition_schema:
            errors["condition_schema"] = "条件可选槽位必须明确受治理的启用条件"
        if errors:
            raise ValidationError(errors)


class TemplateNodeCalculationRuleBinding(models.Model):
    """A template slot references a governed, versioned rule; it never embeds a formula."""

    STATUS_CHOICES = (
        ("draft", "草稿"), ("reviewed", "已评审"),
        ("released", "已发布"), ("obsolete", "已失效"),
    )

    template_node = models.ForeignKey(
        ProductTemplateStructureNode, on_delete=models.PROTECT,
        related_name="calculation_rule_bindings", verbose_name="模板结构槽位",
    )
    rule_category = models.ForeignKey(
        EngineeringRuleCategory, on_delete=models.PROTECT,
        related_name="template_node_bindings", verbose_name="核算规则类别",
    )
    rule = models.ForeignKey(
        "EngineeringRuleDefinition", on_delete=models.PROTECT,
        related_name="template_node_bindings", verbose_name="版本化工程规则",
    )
    application_condition = models.JSONField("适用条件", default=dict, blank=True)
    input_mapping = models.JSONField(
        "输入映射", default=dict, blank=True,
        help_text="只映射构件尺寸、数量、结构角色、边面事实、配置参数和工程来源事实。",
    )
    output_mapping = models.JSONField("输出映射", default=dict, blank=True)
    is_primary = models.BooleanField("是否主规则", default=True)
    status = models.CharField(
        "状态", max_length=24, choices=STATUS_CHOICES, default="draft",
    )
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_template_node_calculation_rule_binding"
        ordering = ("template_node_id", "rule_category_id", "rule_id")
        constraints = [
            models.UniqueConstraint(
                fields=("template_node", "rule_category", "rule"),
                name="pde_template_node_rule_binding_unique",
            )
        ]

    def clean(self):
        errors = {}
        company_id = self.template_node.template.company_id
        if self.rule_category.company_id != company_id:
            errors["rule_category"] = "规则类别必须与模板槽位属于同一公司"
        if self.rule.company_id != company_id:
            errors["rule"] = "工程规则必须与模板槽位属于同一公司"
        if self.status == "released" and self.rule.status != "released":
            errors["rule"] = "已发布模板规则绑定只能引用已发布工程规则"
        if self.status == "released" and _engineering_rule_is_test_only(self.rule):
            errors["rule"] = "TEST_ONLY工程规则不得形成已发布模板规则绑定"
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "失效日期不得早于生效日期"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class TemplateMaterialRequirementSlot(models.Model):
    """Reusable material need: category and selection contract, never a concrete SKU."""

    template_node = models.ForeignKey(
        ProductTemplateStructureNode, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="material_requirement_slots", verbose_name="模板结构槽位",
    )
    material_configuration = models.ForeignKey("pde.MaterialConfiguration", on_delete=models.PROTECT,
        null=True, blank=True, related_name="composition_slots", verbose_name="半成品配置")
    configuration_attribute = models.ForeignKey("pde.MaterialConfigurationAttribute", on_delete=models.PROTECT,
        null=True, blank=True, related_name="composition_slots", verbose_name="来源配置属性")
    fixed_material = models.ForeignKey("masterdata.Material", on_delete=models.PROTECT,
        null=True, blank=True, related_name="fixed_composition_slots", verbose_name="固定组成物料身份")
    quantity_mode = models.CharField("数量方式", max_length=24, default="UNKNOWN", choices=(
        ("FIXED", "固定数量"), ("CALCULATED", "规则计算"), ("MANUAL", "工程人工指定"), ("UNKNOWN", "待确定")))
    fixed_quantity = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    engineering_rule = models.ForeignKey("pde.EngineeringRuleDefinition", on_delete=models.PROTECT,
        null=True, blank=True, related_name="material_configuration_slots", verbose_name="版本化数量规则")
    composition_channel = models.CharField(max_length=32, default="FIXED_COMPOSITION", choices=(
        ("FIXED_COMPOSITION", "固定组成身份"), ("CALCULATED_COMPOSITION", "计算用量"),
        ("MANUAL_ENGINEERING", "工程人工指定"), ("AD_HOC", "临时追加"), ("CUSTOMER_SPECIFIC", "客户特殊要求")))
    slot_code = models.CharField("需求槽位编码", max_length=120)
    slot_name = models.CharField("需求槽位名称", max_length=240)
    material_category = models.ForeignKey(
        "masterdata.MaterialCategory", on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="template_requirement_slots", verbose_name="所需物料分类",
        help_text="复用企业物料分类；不得以Django choices固化合页、把手、灯带等类别。",
    )
    quantity_rule_binding = models.ForeignKey(
        TemplateNodeCalculationRuleBinding, on_delete=models.PROTECT,
        null=True, blank=True, related_name="material_requirement_slots",
        verbose_name="数量核算规则绑定",
        help_text="只回答需要多少；候选筛选和正式物料解析由选料链路负责。",
    )
    expected_uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT,
        null=True, blank=True, related_name="template_material_requirement_slots",
        verbose_name="预期计量单位",
    )
    applicability_condition = models.JSONField("适用条件", default=dict, blank=True)
    selection_constraints = models.JSONField(
        "选料约束", default=dict, blank=True,
        help_text="按类别、品牌、型号、规格、属性、供应商和已批准货源等数据约束候选；不得写死品牌。",
    )
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_template_material_requirement_slot"
        ordering = ("template_node_id", "slot_code")
        constraints = [
            models.UniqueConstraint(
                fields=("template_node", "slot_code"),
                name="pde_template_material_req_slot_unique",
            ),
            models.UniqueConstraint(fields=("material_configuration", "slot_code"),
                condition=models.Q(material_configuration__isnull=False), name="pde_mat_config_role_slot_unique"),
            models.CheckConstraint(condition=(
                models.Q(template_node__isnull=False, material_configuration__isnull=True)
                | models.Q(template_node__isnull=True, material_configuration__isnull=False)
            ), name="pde_material_slot_one_owner"),
            models.CheckConstraint(condition=(
                models.Q(quantity_mode="FIXED", fixed_quantity__isnull=False, fixed_quantity__gt=0, engineering_rule__isnull=True)
                | models.Q(quantity_mode="CALCULATED", fixed_quantity__isnull=True)
                | (models.Q(quantity_mode="MANUAL", engineering_rule__isnull=True) & (models.Q(fixed_quantity__isnull=True) | models.Q(fixed_quantity__gt=0)))
                | models.Q(quantity_mode="UNKNOWN", fixed_quantity__isnull=True, engineering_rule__isnull=True)
            ), name="pde_mat_config_slot_quantity_valid"),
        ]

    def clean(self):
        errors = {}
        if bool(self.template_node_id) == bool(self.material_configuration_id):
            raise ValidationError("需求槽位必须且只属于模板结构或半成品配置之一")
        company_id = self.template_node.template.company_id if self.template_node_id else self.material_configuration.company_id
        if self.material_category_id and self.material_category.company_id != company_id:
            errors["material_category"] = "物料分类必须与模板槽位属于同一公司"
        if self.quantity_rule_binding_id and self.quantity_rule_binding.template_node_id != self.template_node_id:
            errors["quantity_rule_binding"] = "数量规则只能引用同一模板结构槽位"
        if self.expected_uom_id and self.expected_uom.company_id != company_id:
            errors["expected_uom"] = "预期计量单位必须与模板槽位属于同一公司"
        if self.configuration_attribute_id:
            if self.configuration_attribute.configuration_id != self.material_configuration_id:
                errors["configuration_attribute"] = "组成角色必须引用同一配置属性"
            if self.configuration_attribute.attribute_kind in {"color", "paintProcess", "splice", "skinFeel", "uom"}:
                errors["configuration_attribute"] = "配置约束不能自动变成耗用物料"
        if self.fixed_material_id and self.fixed_material.company_id != company_id:
            errors["fixed_material"] = "组成物料必须与配置同公司"
        if self.engineering_rule_id and self.engineering_rule.company_id != company_id:
            errors["engineering_rule"] = "数量规则必须与配置同公司"
        if self.quantity_rule_binding_id and self.engineering_rule_id:
            errors["engineering_rule"] = "同一槽位不得重复绑定两个公式入口"
        if errors:
            raise ValidationError(errors)


class OrderConfiguredProduct(models.Model):
    """One engineering root per SalesOrder; never an installation-area alias or SKU."""

    DEFINITION_MODE_CHOICES = (
        ("standard", "标准定义派生"),
        ("template_assisted", "模板辅助配置"),
        ("order_engineered", "按单工程"),
    )
    STATUS_CHOICES = (
        ("draft", "草稿"), ("engineering", "工程定义中"),
        ("frozen", "工程冻结"), ("inactive", "已失效"),
    )

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="order_configured_products", verbose_name="所属公司",
    )
    sales_order = models.OneToOneField(
        "sales.SalesOrder", on_delete=models.PROTECT,
        related_name="order_configured_product", verbose_name="销售订单",
    )
    root_no = models.CharField("订单工程根编码", max_length=100)
    name = models.CharField("订单工程产品名称", max_length=200)
    definition_mode = models.CharField(
        "定义模式", max_length=24, choices=DEFINITION_MODE_CHOICES,
        default="order_engineered",
    )
    template = models.ForeignKey(
        ProductTemplate, on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_configured_products", verbose_name="可选产品模板",
    )
    configuration = models.OneToOneField(
        ProductConfiguration, on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_product", verbose_name="可选配置请求",
    )
    source_identity = models.ForeignKey(
        "masterdata.ExternalIdentity", on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_configured_products", verbose_name="来源身份",
    )
    source_lineage = models.JSONField("来源血缘", default=dict, blank=True)
    engineering_version = models.PositiveIntegerField("工程版本", default=1)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_order_configured_product"
        ordering = ("company_id", "root_no")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "root_no"), name="pde_order_product_company_root_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(engineering_version__gt=0),
                name="pde_order_product_version_positive",
            ),
        ]

    def clean(self):
        errors = {}
        if self.sales_order_id and self.sales_order.company_id != self.company_id:
            errors["sales_order"] = "订单工程产品必须与销售订单属于同一公司"
        if self.definition_mode == "template_assisted" and not self.template_id:
            errors["template"] = "模板辅助配置模式必须引用正式产品模板"
        if self.definition_mode == "template_assisted" and not self.configuration_id:
            errors["configuration"] = "模板辅助配置模式必须引用同公司配置快照"
        if self.definition_mode == "order_engineered" and self.configuration_id:
            errors["configuration"] = "纯按单工程不得创建或依赖ProductConfiguration"
        if self.template_id and self.template.company_id != self.company_id:
            errors["template"] = "产品模板必须与订单工程产品属于同一公司"
        if self.configuration_id:
            if self.configuration.company_id != self.company_id:
                errors["configuration"] = "配置请求必须与订单工程产品属于同一公司"
            if self.configuration.definition_mode != self.definition_mode:
                errors["configuration"] = "配置请求与订单工程产品的定义模式必须一致"
            if self.configuration.template_id and self.template_id != self.configuration.template_id:
                errors["configuration"] = "配置请求模板必须与订单工程产品模板一致"
        if self.source_identity_id and self.source_identity.organization_id != self.company_id:
            errors["source_identity"] = "来源身份必须属于订单工程产品所在公司"
        if self.status == "frozen" and self.pk:
            unresolved = self.components.filter(is_active=True).filter(
                models.Q(supply_strategy="UNKNOWN")
                | models.Q(quantity_basis="UNKNOWN")
                | models.Q(uom_status="not_confirmed")
                | models.Q(uom__isnull=True)
            )
            if unresolved.exists():
                errors["status"] = "订单工程结构仍有供应策略或计量单位待确认，不得冻结"
            if ComponentMaterialRequirement.objects.filter(
                component__order_product=self, component__is_active=True, is_active=True,
            ).filter(
                models.Q(supply_strategy="UNKNOWN")
                | models.Q(quantity_basis="UNKNOWN")
                | models.Q(uom_status="not_confirmed")
                | models.Q(uom__isnull=True)
                | models.Q(identity_status="unresolved")
                | models.Q(material__isnull=True)
            ).exists():
                errors["status"] = "订单工程物料需求仍有供应策略或计量单位待确认，不得冻结"
        if errors:
            raise ValidationError(errors)


class InstallationContext(models.Model):
    """Delivery/installation context below an order product; explicitly not Product."""

    order_product = models.ForeignKey(
        OrderConfiguredProduct, on_delete=models.PROTECT,
        related_name="installation_contexts", verbose_name="订单工程产品",
    )
    context_code = models.CharField("上下文编码", max_length=100)
    raw_source_value = models.CharField("来源原值", max_length=240)
    normalized_display_value = models.CharField("规范显示值", max_length=240)
    drawing_group = models.CharField("图纸/来源组", max_length=120, blank=True, default="")
    source_column = models.CharField("来源列", max_length=160, blank=True, default="")
    source_lineage = models.JSONField("来源血缘", default=dict, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_installation_context"
        ordering = ("order_product_id", "context_code")
        constraints = [
            models.UniqueConstraint(
                fields=("order_product", "context_code"),
                name="pde_install_context_product_code_unique",
            )
        ]


class OrderProductComponent(models.Model):
    """Order-specific assembly/component/part identity; Material is intentionally absent."""

    COMPONENT_TYPE_CHOICES = (
        ("assembly", "总成/模块"), ("component", "构件/组件"), ("part", "零件"),
    )
    SUPPLY_STRATEGY_CHOICES = (
        ("UNKNOWN", "待确认"),
        ("MAKE", "自制"), ("BUY", "外购"),
        ("SUBCONTRACT", "委外"), ("MAKE_OR_BUY", "自制或外购"),
    )
    QUANTITY_BASIS_CHOICES = (
        ("UNKNOWN", "待确认"),
        ("PER_PARENT_UNIT", "每上级单位"),
        ("ORDER_TOTAL", "订单总量"),
    )
    UOM_STATUS_CHOICES = (
        ("confirmed", "已确认"),
        ("not_confirmed", "待确认"),
    )
    STATUS_CHOICES = (
        ("draft", "草稿"), ("confirmed", "已确认"),
        ("frozen", "工程冻结"), ("inactive", "已失效"),
    )

    order_product = models.ForeignKey(
        OrderConfiguredProduct, on_delete=models.PROTECT,
        related_name="components", verbose_name="订单工程产品",
    )
    installation_context = models.ForeignKey(
        InstallationContext, on_delete=models.PROTECT, null=True, blank=True,
        related_name="components", verbose_name="安装/交付上下文",
    )
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="children", verbose_name="上级总成/构件",
    )
    template_node = models.ForeignKey(
        ProductTemplateStructureNode, on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_components", verbose_name="实例化来源模板槽位",
    )
    component_code = models.CharField("构件编码", max_length=120)
    component_name = models.CharField("构件名称", max_length=240)
    component_type = models.CharField(
        "构件类型", max_length=24, choices=COMPONENT_TYPE_CHOICES,
    )
    dimensions = models.JSONField("尺寸事实", default=dict, blank=True)
    quantity = models.DecimalField("结构数量", max_digits=18, decimal_places=6)
    quantity_basis = models.CharField(
        "结构数量口径", max_length=32, choices=QUANTITY_BASIS_CHOICES,
        default="UNKNOWN",
    )
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_product_components", verbose_name="结构计量单位",
    )
    uom_status = models.CharField(
        "结构单位状态", max_length=20, choices=UOM_STATUS_CHOICES,
        default="not_confirmed",
    )
    supply_strategy = models.CharField(
        "供应策略", max_length=24, choices=SUPPLY_STRATEGY_CHOICES,
        default="UNKNOWN",
    )
    process_attributes = models.JSONField("工艺属性", default=dict, blank=True)
    finish_attributes = models.JSONField("表面/饰面属性", default=dict, blank=True)
    source_identity = models.ForeignKey(
        "masterdata.ExternalIdentity", on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_product_components", verbose_name="来源身份",
    )
    source_lineage = models.JSONField("来源血缘", default=dict, blank=True)
    engineering_version = models.PositiveIntegerField("工程版本", default=1)
    status = models.CharField("状态", max_length=24, choices=STATUS_CHOICES, default="draft")
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_order_product_component"
        ordering = ("order_product_id", "component_code")
        constraints = [
            models.UniqueConstraint(
                fields=("order_product", "component_code"),
                name="pde_order_component_product_code_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="pde_order_component_qty_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(engineering_version__gt=0),
                name="pde_order_component_version_positive",
            ),
        ]

    def clean(self):
        errors = {}
        company_id = self.order_product.company_id
        if self.parent_id:
            if self.parent.order_product_id != self.order_product_id:
                errors["parent"] = "上级构件必须属于同一订单工程产品"
            else:
                ancestor = self.parent
                seen = set()
                while ancestor is not None:
                    marker = ancestor.pk if ancestor.pk is not None else id(ancestor)
                    if marker in seen:
                        errors["parent"] = "构件上级链存在循环"
                        break
                    seen.add(marker)
                    if ancestor is self or (self.pk is not None and ancestor.pk == self.pk):
                        errors["parent"] = "构件不得形成自身、两级或多级循环"
                        break
                    ancestor = ancestor.parent
        if self.installation_context_id and self.installation_context.order_product_id != self.order_product_id:
            errors["installation_context"] = "安装上下文必须属于同一订单工程产品"
        if self.template_node_id:
            if self.order_product.definition_mode != "template_assisted":
                errors["template_node"] = "只有模板辅助订单实例可以记录模板槽位血缘"
            elif self.order_product.template_id != self.template_node.template_id:
                errors["template_node"] = "订单构件的模板槽位必须来自订单所选模板"
        if self.uom_id and self.uom.company_id != company_id:
            errors["uom"] = "构件计量单位必须属于订单工程产品所在公司"
        if self.uom_status == "confirmed" and not self.uom_id:
            errors["uom"] = "结构单位状态为已确认时必须选择正式计量单位"
        if self.uom_status == "not_confirmed" and self.uom_id:
            errors["uom_status"] = "结构单位待确认时不得预填或猜测计量单位"
        if self.status == "frozen":
            if self.quantity_basis == "UNKNOWN":
                errors["quantity_basis"] = "工程结构冻结前必须确认结构数量口径"
            if self.supply_strategy == "UNKNOWN":
                errors["supply_strategy"] = "工程结构冻结前必须确认供应策略"
            if self.uom_status != "confirmed" or not self.uom_id:
                errors["uom_status"] = "工程结构冻结前必须确认计量单位"
            if self.pk and self.material_requirements.filter(is_active=True).filter(
                models.Q(supply_strategy="UNKNOWN")
                | models.Q(quantity_basis="UNKNOWN")
                | models.Q(uom_status="not_confirmed")
                | models.Q(uom__isnull=True)
                | models.Q(identity_status="unresolved")
                | models.Q(material__isnull=True)
            ).exists():
                errors["status"] = "构件仍有未确认物料需求，不得冻结"
        if self.source_identity_id and self.source_identity.organization_id != company_id:
            errors["source_identity"] = "来源身份必须属于订单工程产品所在公司"
        if errors:
            raise ValidationError(errors)


class ComponentMaterialRequirement(models.Model):
    """Component-owned usage fact from requirement through quantity and resolution."""

    REQUIREMENT_KIND_CHOICES = (
        ("semi_finished", "半成品"), ("raw", "原材料"),
        ("hardware", "五金"), ("glass", "玻璃"), ("other", "其他"),
    )
    QUANTITY_BASIS_CHOICES = (
        ("UNKNOWN", "待确认"),
        ("PER_COMPONENT_UNIT", "每构件单位"),
        ("ORDER_TOTAL", "订单总量"),
    )
    UOM_STATUS_CHOICES = OrderProductComponent.UOM_STATUS_CHOICES
    QUANTITY_STATUS_CHOICES = (
        ("pending_calculation", "待核算"), ("calculated", "已核算"),
        ("confirmed", "已确认"),
    )
    SELECTION_STATUS_CHOICES = (
        ("resolved", "已解析"), ("pending_selection", "待选择"),
        ("no_candidate", "无候选"), ("multiple_candidates", "多候选待裁决"),
        ("insufficient_information", "信息不足"),
    )

    component = models.ForeignKey(
        OrderProductComponent, on_delete=models.PROTECT,
        related_name="material_requirements", verbose_name="实际使用构件",
    )
    line_no = models.PositiveIntegerField("行号")
    IDENTITY_STATUS_CHOICES = (
        ("unresolved", "物料身份待解析"),
        ("resolved", "物料身份已解析"),
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, null=True, blank=True,
        related_name="component_requirements", verbose_name="正式物料",
    )
    template_requirement_slot = models.ForeignKey(
        TemplateMaterialRequirementSlot, on_delete=models.PROTECT,
        null=True, blank=True, related_name="component_requirements",
        verbose_name="来源模板物料需求槽位",
    )
    requirement_category = models.ForeignKey(
        "masterdata.MaterialCategory", on_delete=models.PROTECT,
        null=True, blank=True, related_name="component_material_requirements",
        verbose_name="所需物料分类",
    )
    requirement_kind = models.CharField(
        "需求类型", max_length=24, choices=REQUIREMENT_KIND_CHOICES,
    )
    quantity = models.DecimalField(
        "物料用量", max_digits=18, decimal_places=6, null=True, blank=True,
        help_text="需求已识别但规则尚未核算时保持为空，不得用0或示例值占位。",
    )
    quantity_status = models.CharField(
        "数量状态", max_length=24, choices=QUANTITY_STATUS_CHOICES,
        default="pending_calculation",
    )
    quantity_basis = models.CharField(
        "数量口径", max_length=32, choices=QUANTITY_BASIS_CHOICES,
        default="UNKNOWN",
    )
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="component_material_requirements", verbose_name="物料计量单位",
    )
    uom_status = models.CharField(
        "物料需求单位状态", max_length=20, choices=UOM_STATUS_CHOICES,
        default="not_confirmed",
    )
    source_uom_text = models.CharField(
        "来源单位原值", max_length=80, blank=True, default="",
    )
    normalized_quantity = models.DecimalField(
        "折算后基本单位用量", max_digits=18, decimal_places=6,
        null=True, blank=True,
    )
    conversion_lineage = models.JSONField(
        "单位换算血缘", default=dict, blank=True,
        help_text="消费单位不同于物料基本单位时，必须记录正式换算因子、规则来源和目标基本单位。",
    )
    supply_strategy = models.CharField(
        "供应策略", max_length=24,
        choices=OrderProductComponent.SUPPLY_STRATEGY_CHOICES, default="UNKNOWN",
    )
    calculation_rule = models.JSONField("用量计算规则", default=dict, blank=True)
    order_specification = models.JSONField("订单级规格", default=dict, blank=True)
    source_lineage = models.JSONField("来源血缘", default=dict, blank=True)
    identity_status = models.CharField(
        "物料身份状态", max_length=20, choices=IDENTITY_STATUS_CHOICES,
        default="resolved",
    )
    selection_status = models.CharField(
        "选料状态", max_length=40, choices=SELECTION_STATUS_CHOICES,
        default="insufficient_information",
    )
    selection_constraints_snapshot = models.JSONField(
        "选料约束快照", default=dict, blank=True,
        help_text="记录类别、品牌、型号、规格、属性、供应商及批准货源约束；不得自动取第一候选。",
    )
    unresolved_requirement = models.JSONField(
        "未决物料类别需求", default=dict, blank=True,
        help_text="保存五金/玻璃等类别、性能和来源事实，禁止创建占位Material。",
    )
    identity_resolution_decision = models.JSONField(
        "身份解析决策", default=dict, blank=True,
    )
    resolved_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT, null=True, blank=True,
        related_name="resolved_component_material_requirements", verbose_name="解析人",
    )
    resolved_at = models.DateTimeField("解析时间", null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_component_material_requirement"
        ordering = ("component_id", "line_no")
        constraints = [
            models.UniqueConstraint(
                fields=("component", "line_no"),
                name="pde_component_material_line_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(quantity_status="pending_calculation", quantity__isnull=True)
                    | models.Q(
                        quantity_status__in=("calculated", "confirmed"),
                        quantity__isnull=False,
                        quantity__gt=0,
                    )
                ),
                name="pde_component_material_qty_state_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(normalized_quantity__isnull=True) | models.Q(normalized_quantity__gt=0),
                name="pde_component_material_normalized_qty_null_positive",
            ),
        ]

    def clean(self):
        errors = {}
        company_id = self.component.order_product.company_id
        if self.material_id and self.material.company_id != company_id:
            errors["material"] = "物料必须属于构件所在公司"
        if self.material_id and self.requirement_category_id and self.material.category_id != self.requirement_category_id:
            errors["material"] = "已解析物料必须属于该部件需求指定的物料分类"
        if self.requirement_category_id and self.requirement_category.company_id != company_id:
            errors["requirement_category"] = "物料需求分类必须属于构件所在公司"
        if self.template_requirement_slot_id:
            if not self.component.template_node_id:
                errors["template_requirement_slot"] = "记录模板需求槽位血缘时，构件必须先关联模板槽位"
            elif self.template_requirement_slot.template_node_id != self.component.template_node_id:
                errors["template_requirement_slot"] = "物料需求槽位必须与构件模板槽位一致"
            if self.requirement_category_id and self.template_requirement_slot.material_category_id != self.requirement_category_id:
                errors["requirement_category"] = "物料需求分类必须与模板需求槽位一致"
        if self.quantity_status == "pending_calculation" and self.quantity is not None:
            errors["quantity"] = "待核算需求不得预填数量"
        if self.quantity_status in {"calculated", "confirmed"} and (
            self.quantity is None or self.quantity <= 0
        ):
            errors["quantity"] = "已核算或已确认需求必须保存大于0的数量"
        if self.identity_status == "unresolved":
            if self.material_id:
                errors["material"] = "物料身份待解析时不得关联占位或泛称Material"
            if not self.unresolved_requirement:
                errors["unresolved_requirement"] = "未决物料必须保存类别/性能需求事实"
            if self.resolved_by_id or self.resolved_at or self.identity_resolution_decision:
                errors["identity_status"] = "未解析需求不得伪造解析审计事实"
        else:
            if not self.material_id:
                errors["material"] = "物料身份已解析时必须关联正式Material"
            if self.pk and self.unresolved_requirement and (
                not self.resolved_by_id or not self.resolved_at or not self.identity_resolution_decision
            ):
                errors["identity_resolution_decision"] = "从未决需求解析时必须保留解析人、时间和决策审计"
        if self.selection_status == "resolved" and (
            self.identity_status != "resolved" or not self.material_id
        ):
            errors["selection_status"] = "选料已解析时必须关联已解析的正式物料"
        if self.uom_id and self.uom.company_id != company_id:
            errors["uom"] = "物料需求计量单位必须属于构件所在公司"
        if self.uom_status == "confirmed" and not self.uom_id:
            errors["uom"] = "物料需求单位状态为已确认时必须选择正式计量单位"
        if self.uom_status == "not_confirmed":
            if self.uom_id:
                errors["uom_status"] = "物料需求单位待确认时不得预填或猜测计量单位"
            if self.normalized_quantity is not None:
                errors["normalized_quantity"] = "单位待确认时不得生成折算后用量"
        if self.uom_status == "confirmed" and self.material_id and self.uom_id:
            if self.quantity is None:
                errors["quantity"] = "正式单位与物料已解析时必须先完成数量核算"
            if not self.material.base_uom_id:
                errors["material"] = "物料基本单位尚未确认，不能形成规范化物料需求"
            elif self.uom_id != self.material.base_uom_id:
                if self.uom.dimension != self.material.base_uom.dimension:
                    errors["uom"] = "消费单位与物料基本单位计量维度不一致"
                elif self.uom.conversion_base_id != self.material.base_uom_id:
                    errors["uom"] = "消费单位缺少指向物料基本单位的正式换算规则"
                if self.normalized_quantity is None:
                    errors["normalized_quantity"] = "消费单位不同于物料基本单位时必须提供折算后用量"
                required_lineage = {"factor", "ruleSource", "targetUomId"}
                if not required_lineage.issubset(self.conversion_lineage or {}):
                    errors["conversion_lineage"] = "单位换算必须记录因子、规则来源和目标基本单位"
                elif self.conversion_lineage.get("targetUomId") != self.material.base_uom_id:
                    errors["conversion_lineage"] = "换算目标必须是物料正式基本单位"
                else:
                    try:
                        lineage_factor = Decimal(str(self.conversion_lineage.get("factor")))
                    except Exception:
                        errors["conversion_lineage"] = "换算因子必须是有效Decimal数值"
                    else:
                        if lineage_factor != self.uom.conversion_factor:
                            errors["conversion_lineage"] = "换算因子必须与正式UOM规则完全一致"
                        if self.conversion_lineage.get("ruleSource") != "UnitOfMeasure.conversion_factor":
                            errors["conversion_lineage"] = "换算规则来源必须指向正式UOM换算规则"
                        expected = self.quantity * self.uom.conversion_factor if self.quantity is not None else None
                        if self.normalized_quantity is not None and self.normalized_quantity != expected:
                            errors["normalized_quantity"] = "折算后用量必须等于来源用量乘正式UOM换算因子"
            elif self.normalized_quantity not in (None, self.quantity):
                errors["normalized_quantity"] = "消费单位即基本单位时折算后用量必须与来源用量一致"
        if errors:
            raise ValidationError(errors)

    @property
    def normalized_base_quantity(self):
        if (
            self.identity_status != "resolved" or not self.material_id
            or self.quantity is None
            or self.quantity_basis == "UNKNOWN"
            or self.uom_status != "confirmed" or not self.uom_id
        ):
            return None
        if self.material.base_uom_id == self.uom_id:
            return self.quantity
        return self.normalized_quantity


class MaterialSelectionCandidate(models.Model):
    """Candidate of one component-owned requirement; never an independent selection fact."""

    EVALUATION_STATUS_CHOICES = (
        ("eligible", "满足约束"), ("rejected", "不满足约束"),
        ("selected", "经裁决选中"),
    )
    requirement = models.ForeignKey(
        ComponentMaterialRequirement, on_delete=models.PROTECT,
        related_name="selection_candidates", verbose_name="物料需求",
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT,
        related_name="selection_candidate_evaluations", verbose_name="候选正式物料",
    )
    evaluation_status = models.CharField(
        "候选评价状态", max_length=24, choices=EVALUATION_STATUS_CHOICES,
        default="eligible",
    )
    constraint_evidence = models.JSONField("约束匹配证据", default=dict)
    sourcing_evidence = models.JSONField(
        "货源与供应商证据", default=dict, blank=True,
        help_text="引用已批准货源、供应商或采购治理事实，不在此模型复制主数据。",
    )
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_material_selection_candidate"
        ordering = ("requirement_id", "material_id")
        constraints = [
            models.UniqueConstraint(
                fields=("requirement", "material"),
                name="pde_material_selection_candidate_unique",
            )
        ]

    def clean(self):
        errors = {}
        company_id = self.requirement.component.order_product.company_id
        if self.material.company_id != company_id:
            errors["material"] = "候选物料必须与需求属于同一公司"
        if self.requirement.requirement_category_id and self.material.category_id != self.requirement.requirement_category_id:
            errors["material"] = "候选物料必须属于需求指定的物料分类"
        if self.evaluation_status == "selected":
            if self.requirement.selection_status != "resolved":
                errors["evaluation_status"] = "候选选中前，需求选料状态必须经裁决更新为已解析"
            if self.requirement.material_id != self.material_id:
                errors["material"] = "经裁决选中的候选必须与需求正式物料一致"
        if errors:
            raise ValidationError(errors)


class EngineeringMaterialCalculationResult(models.Model):
    """Auditable material quantity result projected from a governed calculation rule."""

    calculation = models.ForeignKey(
        EngineeringCalculationRecord, on_delete=models.PROTECT,
        related_name="material_calculation_results", verbose_name="核算批次",
    )
    source_component = models.ForeignKey(
        OrderProductComponent, on_delete=models.PROTECT,
        related_name="material_calculation_results", verbose_name="来源订单构件",
    )
    material_requirement = models.ForeignKey(
        ComponentMaterialRequirement, on_delete=models.PROTECT,
        related_name="calculation_results", verbose_name="物料需求行",
        help_text="物料身份未解析时继续引用unresolved ComponentMaterialRequirement。",
    )
    requirement_slot = models.ForeignKey(
        TemplateMaterialRequirementSlot, on_delete=models.PROTECT,
        null=True, blank=True, related_name="calculation_results",
        verbose_name="来源模板物料需求槽位",
    )
    required_material_category = models.ForeignKey(
        "masterdata.MaterialCategory", on_delete=models.PROTECT,
        null=True, blank=True, related_name="engineering_material_calculation_results",
        verbose_name="所需物料分类",
    )
    rule_category = models.ForeignKey(
        EngineeringRuleCategory, on_delete=models.PROTECT,
        related_name="material_calculation_results", verbose_name="物料核算规则类别",
    )
    rule = models.ForeignKey(
        EngineeringRuleDefinition, on_delete=models.PROTECT,
        related_name="material_calculation_results", verbose_name="来源规则",
    )
    rule_version = models.CharField("规则版本快照", max_length=40)
    sequence = models.PositiveIntegerField("序号", default=1)
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_material_calculation_results", verbose_name="正式物料",
    )
    material_category_code = models.CharField("物料类别编码", max_length=100)
    quantity = models.DecimalField("工程派生数量", max_digits=18, decimal_places=6)
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT,
        related_name="engineering_material_calculation_results", verbose_name="工程派生数量单位",
    )
    quantity_basis = models.CharField("数量口径", max_length=80)
    input_snapshot = models.JSONField("输入快照", default=dict)
    selection_constraints_snapshot = models.JSONField(
        "选料约束快照", default=dict, blank=True,
        help_text="核算结果保留选料入口，但数量规则不得代替候选裁决。",
    )
    lineage = models.JSONField("结果血缘", default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_engineering_material_calculation_result"
        ordering = ("calculation_id", "source_component_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("calculation", "source_component", "rule_category", "sequence"),
                name="pde_material_calc_result_line_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="pde_material_calc_result_qty_positive",
            ),
        ]

    def clean(self):
        errors = {}
        company_id = self.calculation.company_id
        if not company_id:
            errors["calculation"] = "物料核算结果必须属于明确公司的订单工程核算批次"
        if self.source_component.order_product.company_id != company_id:
            errors["source_component"] = "来源构件必须与核算批次属于同一公司"
        requirement = self.material_requirement if self.material_requirement_id else None
        if requirement is None:
            errors["material_requirement"] = "任何持久化物料核算结果都必须引用来源构件的物料需求行"
        else:
            requirement_company_id = requirement.component.order_product.company_id
            if requirement.component_id != self.source_component_id:
                errors["material_requirement"] = "物料需求行必须属于来源构件"
            if requirement_company_id != company_id:
                errors["material_requirement"] = "物料需求行必须与核算批次属于同一公司"
            if self.required_material_category_id and (
                requirement.requirement_category_id != self.required_material_category_id
            ):
                errors["required_material_category"] = "核算结果物料分类必须与来源需求分类一致"
            authoritative_category = (
                requirement.requirement_category
                if requirement.requirement_category_id
                else self.required_material_category
                if self.required_material_category_id
                else None
            )
            if authoritative_category is None:
                errors["required_material_category"] = "物料类别编码快照必须锚定来源需求的正式物料分类"
            elif self.material_category_code != authoritative_category.code:
                errors["material_category_code"] = "物料类别编码快照必须与来源需求的正式分类编码一致"
            if self.material_id != requirement.material_id:
                errors["material"] = "核算结果具体物料必须与原部件需求行的解析结论一致"
            if requirement.quantity_status not in {"calculated", "confirmed"}:
                errors["material_requirement"] = "形成核算结果前，来源需求必须处于已核算或已确认状态"
            elif requirement.quantity != self.quantity:
                errors["quantity"] = "核算结果数量必须与来源需求行数量一致"
            if requirement.uom_id != self.uom_id:
                errors["uom"] = "核算结果计量单位必须与来源需求行一致"
        if self.requirement_slot_id:
            if self.source_component.template_node_id != self.requirement_slot.template_node_id:
                errors["requirement_slot"] = "需求槽位必须与来源构件的模板槽位一致"
            if self.required_material_category_id and self.requirement_slot.material_category_id != self.required_material_category_id:
                errors["required_material_category"] = "核算结果物料分类必须与需求槽位一致"
        if self.required_material_category_id and self.required_material_category.company_id != company_id:
            errors["required_material_category"] = "所需物料分类必须与核算批次属于同一公司"
        if self.rule_category.company_id != company_id:
            errors["rule_category"] = "规则类别必须与核算批次属于同一公司"
        if self.rule.company_id != company_id:
            errors["rule"] = "来源规则必须与核算批次属于同一公司"
        if self.rule_version != self.rule.version:
            errors["rule_version"] = "规则版本快照必须与来源规则版本一致"
        if self.material_id and self.material.company_id != company_id:
            errors["material"] = "正式物料必须与核算批次属于同一公司"
        if self.uom.company_id != company_id:
            errors["uom"] = "工程派生数量单位必须与核算批次属于同一公司"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

