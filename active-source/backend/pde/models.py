from decimal import Decimal
from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.expressions import RawSQL
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce, NullIf, Trim, Upper

from .operation_non_quantified_context import (
    EOR_REFERENCE_CHECK_SQL, TYPE_KEY as EOR_REFERENCE_TYPE_KEY,
    CONTEXT_KEY as EOR_PREPARATION_CONTEXT_KEY, reference_record_errors,
)


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


class ManufacturingApplicabilityScope(models.TextChoices):
    PRODUCT_DEFINITION = "PRODUCT_DEFINITION", "长期产品定义"
    PRODUCT_CATEGORY = "PRODUCT_CATEGORY", "产品分类/模板"
    ORDER_ENGINEERING = "ORDER_ENGINEERING", "订单工程实例"


class ManufacturingReleaseSubjectType(models.TextChoices):
    LONG_TERM_PRODUCT = "LONG_TERM_PRODUCT", "长期产品"
    ORDER_ENGINEERED_PRODUCT = "ORDER_ENGINEERED_PRODUCT", "订单工程产品"


def _routing_matches_order_engineering_instance(routing, instance):
    """Return whether one frozen routing header is applicable to one OEI."""
    if routing.company_id != instance.company_id:
        return False
    if routing.applicability_scope == ManufacturingApplicabilityScope.ORDER_ENGINEERING:
        return routing.order_engineering_instance_id == instance.pk
    if routing.applicability_scope == ManufacturingApplicabilityScope.PRODUCT_CATEGORY:
        return (
            routing.product_category_id == instance.product_category_id
            and routing.manufacturing_process_type_id == instance.selected_process_type_id
        )
    return bool(instance.product_id and routing.product_id == instance.product_id)


def _has_confirmable_release_baseline_item(baseline, instance):
    from .capacity_evidence_read_scope import evidence_cache
    from .operation_requirement_service import _read_once

    company_id, item_id, source_id = instance.company_id, instance.sales_order_item_id, instance.source_record_id
    return _read_once(evidence_cache(company_id),
        ('release_baseline_confirmable_row', company_id, baseline.pk, item_id, source_id),
        lambda: baseline.items.filter(design_item__sales_order_item_id=item_id,
            source_record_id=source_id, confirmable=True).exists())


def _order_engineering_release_identity_errors(instance, baseline, calculation):
    """Cross-row guards for the exact order-engineered release identity."""
    errors = {}
    if instance is None:
        errors["order_engineering_instance"] = "订单工程产品主体必须引用具体订单工程实例"
        return errors
    if instance.status == "inactive":
        errors["order_engineering_instance"] = "已失效订单工程实例不得形成制造发布主体"
    if not instance.product_category_id or not instance.selected_process_type_id:
        errors["order_engineering_instance"] = "订单工程产品必须保留产品分类与制造过程类型"
    elif not instance.product_category.is_active or not instance.selected_process_type.is_active:
        errors["order_engineering_instance"] = "已停用的产品分类或制造过程类型不得形成制造发布主体"
    if instance.source_record.status != "confirmed":
        errors["order_engineering_instance"] = "订单工程产品必须引用已确认且未被替代的工程来源"

    if baseline is None:
        errors["order_engineering_baseline"] = "订单工程产品主体必须冻结已确认工程基线"
    else:
        order = instance.sales_order_item.sales_order
        if baseline.company_id != instance.company_id or baseline.sales_order_id != order.pk:
            errors["order_engineering_baseline"] = "工程基线必须与订单工程实例属于同一公司和销售订单"
        elif baseline.status != "confirmed":
            errors["order_engineering_baseline"] = "订单工程产品只能冻结已确认工程基线"
        elif baseline.pk and not _has_confirmable_release_baseline_item(baseline, instance):
            errors["order_engineering_baseline"] = "工程基线必须包含当前订单行可确认的精确设计快照"

    if baseline is not None and baseline.pk and baseline.status == 'confirmed':
        from .baseline_usage_service import validate_baseline
        from .product_design_service import ProductDesignError
        try:validate_baseline(baseline)
        except ProductDesignError as exc:errors['order_engineering_baseline']=exc.message
    if calculation is None:
        errors["engineering_calculation"] = "订单工程产品主体必须冻结已完成工程核算修订"
    else:
        if calculation.company_id != instance.company_id:
            errors["engineering_calculation"] = "工程核算必须与订单工程实例属于同一公司"
        elif calculation.engineering_instance_id != instance.pk:
            errors["engineering_calculation"] = "工程核算必须属于当前订单工程实例"
        elif calculation.sales_order_item_id != instance.sales_order_item_id:
            errors["engineering_calculation"] = "工程核算必须对应当前销售订单行"
        elif calculation.source_record_id != instance.source_record_id:
            errors["engineering_calculation"] = "工程核算必须使用订单工程实例的精确来源版本"
        elif calculation.status != "completed":
            errors["engineering_calculation"] = "订单工程产品只能冻结已完成工程核算修订"
    return errors


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


class CapacityProductType(models.Model):
    """Governed product/semi-finished type for daily resource capacity facts."""

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="capacity_product_types", verbose_name="所属公司",
    )
    code = models.CharField("产能产品类型编码", max_length=64)
    name = models.CharField("产能产品类型名称", max_length=160)
    product_category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT,
        related_name="capacity_product_types", verbose_name="产品分类",
    )
    manufacturing_process_type = models.ForeignKey(
        ManufacturingProcessType, on_delete=models.PROTECT,
        related_name="capacity_product_types", verbose_name="工艺类型",
    )
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_capacity_product_type"
        ordering = ("company_id", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"), name="pde_capacity_product_type_company_code_unique",
            ),
        ]

    def clean(self):
        errors = {}
        if self.product_category_id and self.product_category.company_id != self.company_id:
            errors["product_category"] = "产能产品类型的产品分类必须属于同一公司"
        if self.manufacturing_process_type_id and self.manufacturing_process_type.company_id != self.company_id:
            errors["manufacturing_process_type"] = "产能产品类型的工艺类型必须属于同一公司"
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "失效日期不得早于生效日期"
        if errors:
            raise ValidationError(errors)


class EngineeringBreakdownOption(models.Model):
    """Governed engineering-entry choice that is not a manufacturing process type."""

    class OptionType(models.TextChoices):
        DOOR_OPENING_DIRECTION = "door_opening_direction", "门开方向"
        LINE_STYLE = "line_style", "线型"
        EDGE_METHOD = "edge_method", "封边方式"
        PACKAGING_METHOD = "packaging_method", "包装方式"

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="engineering_breakdown_options", verbose_name="所属公司",
    )
    option_type = models.CharField("选项类别", max_length=40, choices=OptionType.choices)
    code = models.CharField("选项编码", max_length=64)
    name = models.CharField("选项名称", max_length=160)
    description = models.CharField("说明", max_length=300, blank=True)
    source_reference = models.CharField("来源追溯", max_length=300, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_engineering_breakdown_option"
        ordering = ("company_id", "option_type", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "option_type", "code"),
                name="pde_eng_breakdown_option_company_type_code_unique",
            ),
            models.UniqueConstraint(
                fields=("company", "option_type", "name"),
                name="pde_eng_breakdown_option_company_type_name_unique",
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
        null=True, blank=True,
        related_name="production_work_centers", verbose_name="所属部门（可由车间推导）",
    )
    workshop = models.ForeignKey(
        "system.Workshop", on_delete=models.PROTECT, null=True, blank=True,
        related_name="production_work_centers", verbose_name="所属车间",
    )
    production_line = models.ForeignKey(
        "ProductionLine", on_delete=models.PROTECT, null=True, blank=True,
        related_name="work_centers", verbose_name="所属生产线（可选）",
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
        errors = {}
        if self.department_id and self.department.company_id != self.company_id:
            errors["department"] = "部门必须属于工作中心所在公司"
        if self.workshop_id:
            if self.workshop.company_id != self.company_id:
                errors["workshop"] = "车间必须属于工作中心所在公司"
            if self.department_id and self.workshop.department_id and self.workshop.department_id != self.department_id:
                errors["workshop"] = "车间与工作中心所属部门不一致"
        if self.production_line_id:
            if self.production_line.company_id != self.company_id:
                errors["production_line"] = "生产线必须属于工作中心所在公司"
            if self.workshop_id and self.production_line.workshop_id != self.workshop_id:
                errors["production_line"] = "生产线必须属于工作中心所在车间"
        policy = self.capacity_policy or {}
        calendar = policy.get("calendar") if isinstance(policy, dict) else None
        if calendar is not None:
            if not isinstance(calendar, dict):
                errors["capacity_policy"] = "制造日历必须是PCE-MFG-CALENDAR-V1.0对象"
            else:
                weekly = calendar.get("weeklyAvailableMinutes")
                exceptions = calendar.get("exceptions", [])
                if calendar.get("contractVersion") != "PCE-MFG-CALENDAR-V1.0":
                    errors["capacity_policy"] = "制造日历contractVersion必须为PCE-MFG-CALENDAR-V1.0"
                elif not str(calendar.get("timezone") or "").strip():
                    errors["capacity_policy"] = "制造日历必须明确timezone"
                elif not isinstance(weekly, dict) or set(weekly) != {
                    "MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN",
                }:
                    errors["capacity_policy"] = "制造日历必须明确周一至周日可用分钟"
                elif any(
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    or value < 0 or value > 1440
                    for value in weekly.values()
                ):
                    errors["capacity_policy"] = "制造日历每日可用分钟必须在0到1440之间"
                elif not isinstance(exceptions, list):
                    errors["capacity_policy"] = "制造日历exceptions必须是日期例外列表"
                else:
                    for item in exceptions:
                        try:
                            date.fromisoformat(str(item.get("date")))
                            minutes = item.get("availableMinutes")
                            valid_minutes = (
                                not isinstance(minutes, bool)
                                and isinstance(minutes, (int, float))
                                and 0 <= minutes <= 1440
                            )
                        except (AttributeError, TypeError, ValueError):
                            valid_minutes = False
                        if not valid_minutes:
                            errors["capacity_policy"] = "制造日历日期例外必须包含有效日期和0到1440可用分钟"
                            break
        if errors:
            raise ValidationError(errors)


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
    """Industry-neutral capacity fact; APS Phase 1 uses quantity per DAY only."""

    class MeasurementStatus(models.TextChoices):
        MEASURED = "measured", "已测定"
        NOT_DETERMINABLE = "not_determinable", "适用但无法确定"
        ZERO_CAPACITY = "zero_capacity", "来源零产能（不可排产）"

    class TimeUnit(models.TextChoices):
        DAY = "DAY", "天"

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
    product_type = models.ForeignKey(
        CapacityProductType, on_delete=models.PROTECT, null=True, blank=True,
        related_name="standard_capacities", verbose_name="产品/半成品类型",
        help_text="APS日产能引用正式产品类型；历史兼容记录允许为空但不作为APS日产能。",
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, null=True, blank=True,
        related_name="standard_capacities", verbose_name="设备",
    )
    measurement_status = models.CharField(
        "产能测量状态", max_length=24,
        choices=MeasurementStatus.choices, default=MeasurementStatus.MEASURED,
        help_text="已测定必须有正数量；来源零值按零产能保留并阻断排产；适用但无法确定时数量为空。无此工序不创建记录。",
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
        help_text="已停用的历史兼容字段；APS不得读取标准工时小时。未知时必须为空，不得用0表示未维护。",
    )
    preparation_days = models.DecimalField(
        "准备时间（天）", max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="仅保存业务确认的DAY事实；未维护保持为空，不从历史小时换算。",
    )
    transfer_days = models.DecimalField(
        "转运时间（天）", max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="仅保存业务确认的DAY事实；未维护保持为空，不从历史小时换算。",
    )
    time_unit = models.CharField(
        "准备/转运时间单位", max_length=3, choices=TimeUnit.choices, default=TimeUnit.DAY,
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
                    models.Q(measurement_status="measured", quantity__isnull=False, quantity__gt=0)
                    | models.Q(measurement_status="not_determinable", quantity__isnull=True)
                    | models.Q(measurement_status="zero_capacity", quantity__isnull=False, quantity=0)
                ),
                name="pde_standard_capacity_measurement_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(standard_hours__isnull=True) | models.Q(standard_hours__gt=0),
                name="pde_standard_capacity_hours_null_or_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(preparation_days__isnull=True) | models.Q(preparation_days__gte=0),
                name="pde_capacity_preparation_days_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(transfer_days__isnull=True) | models.Q(transfer_days__gte=0),
                name="pde_capacity_transfer_days_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(time_unit="DAY"), name="pde_capacity_time_unit_day",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(product_type__isnull=True)
                    | models.Q(
                        work_center__isnull=False, operation__isnull=False,
                        time_basis="day", time_basis_quantity__isnull=False,
                        time_basis_quantity=1,
                    )
                ),
                name="pde_capacity_typed_daily_valid",
            ),
        ]

    def clean(self):
        errors = {}
        if self.measurement_status == self.MeasurementStatus.MEASURED:
            if self.quantity is None or self.quantity <= 0:
                errors["quantity"] = "已测定产能必须填写大于0的数量"
        elif self.measurement_status == self.MeasurementStatus.ZERO_CAPACITY:
            if self.quantity is None or self.quantity != 0:
                errors["quantity"] = "来源零产能必须保留数量0，且不得用于APS排产"
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
        if self.product_type_id:
            if self.product_type.company_id != self.company_id:
                errors["product_type"] = "产能产品类型必须属于产能所在公司"
            if not self.work_center_id:
                errors["work_center"] = "产品类型日产能必须引用正式工作中心"
            if not self.operation_id:
                errors["operation"] = "产品类型日产能必须引用正式工序"
            if self.time_basis != self.TimeBasis.DAY:
                errors["time_basis"] = "产品类型日产能只能使用每日时间基准"
            if self.time_basis_quantity != 1:
                errors["time_basis_quantity"] = "产品类型日产能的时间基准数量必须为1天"
        if self.time_unit != self.TimeUnit.DAY:
            errors["time_unit"] = "准备时间和转运时间只允许使用DAY（天）"
        for field_name in ("preparation_days", "transfer_days"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                errors[field_name] = "准备时间和转运时间不得为负数"
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
    """Tenant-owned template-assisted input; never the final manufacturing structure."""

    DEFINITION_MODE_CHOICES = (
        ("template_assisted", "模板辅助配置"),
    )

    STATUS_CHOICES = (
        ("draft", "草稿"), ("validated", "已校验"),
        ("resolved", "已解析"), ("superseded", "已被替代"),
    )

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="product_configurations", verbose_name="所属公司",
    )
    template = models.ForeignKey(
        ProductTemplate, on_delete=models.PROTECT,
        related_name="configurations", verbose_name="产品模板",
        help_text="ProductConfiguration仅服务模板辅助配置，因此必须引用同公司模板。",
    )
    definition_mode = models.CharField(
        "定义模式", max_length=24, choices=DEFINITION_MODE_CHOICES,
        default="template_assisted",
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
        ordering = ("company_id", "configuration_no")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "configuration_no"),
                name="pde_product_configuration_no_unique",
            ),
            models.UniqueConstraint(
                fields=("company", "idempotency_key"),
                name="pde_product_configuration_idempotency_unique",
            ),
        ]

    def clean(self):
        errors = {}
        if self.definition_mode != "template_assisted":
            errors["definition_mode"] = "ProductConfiguration只允许模板辅助配置模式"
        if not self.company_id:
            errors["company"] = "产品配置必须明确所属公司"
        if not self.template_id:
            errors["template"] = "模板辅助配置必须引用正式产品模板"
        elif self.company_id and self.template.company_id != self.company_id:
            errors["template"] = "产品配置与产品模板必须属于同一公司"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Compatibility for pre-W26 callers: ownership is persisted, never inferred at read time.
        if not self.company_id and self.template_id:
            self.company_id = self.template.company_id
        super().save(*args, **kwargs)


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


class BomPurposeQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if set(kwargs) & {'usage_purpose','source_calculation','source_calculation_id','origin_version','origin_version_id','order_engineering_instance','order_engineering_instance_id','bom','bom_id'}:
            raise ValidationError('BOM用途及来源禁止批量改写。')
        if kwargs.get('status') not in (None,'draft') and self.filter(usage_purpose='TEST_BUSINESS').exists():
            raise ValidationError('测试BOM不得进入正式生命周期。')
        return super().update(**kwargs)
    def bulk_create(self, objs, **kwargs):
        from .bom_usage_contract import bind_usage
        for obj in objs:bind_usage(obj)
        return super().bulk_create(objs, **kwargs)
    def bulk_update(self, objs, fields, **kwargs):
        if set(fields)&{'usage_purpose','source_calculation','origin_version','bom','order_engineering_instance','status'}:
            raise ValidationError('BOM用途、状态及来源禁止批量改写。')
        return super().bulk_update(objs, fields, **kwargs)

class ProductBOM(models.Model):
    objects = models.Manager.from_queryset(BomPurposeQuerySet)()
    usage_purpose = models.CharField("用途", max_length=24, default="UNCLASSIFIED", choices=(("UNCLASSIFIED","历史用途待核定"),("PRODUCTION_USE","生产业务"),("TEST_BUSINESS","测试业务")))
    source_calculation = models.ForeignKey("pde.EngineeringCalculationRecord", on_delete=models.PROTECT, null=True, blank=True, related_name="purpose_bom_headers")
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
        choices=ManufacturingApplicabilityScope.choices,
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
            models.CheckConstraint(condition=(~models.Q(usage_purpose='TEST_BUSINESS') | models.Q(status='draft', source_calculation__isnull=False)), name='pde_productbom_test_draft_source'),
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
                name="pde_bom_exactly_one_applicability_target",
            ),
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
        from .bom_usage_contract import bind_usage
        bind_usage(self)
        targets = {
            ManufacturingApplicabilityScope.PRODUCT_DEFINITION: self.product_id,
            ManufacturingApplicabilityScope.PRODUCT_CATEGORY: self.product_category_id,
            ManufacturingApplicabilityScope.ORDER_ENGINEERING: self.order_engineering_instance_id,
        }
        if sum(value is not None for value in targets.values()) != 1 or not targets.get(self.applicability_scope):
            raise ValidationError({"applicability_scope": "BOM适用范围必须且只能引用与类型一致的一个主体"})
        target = (
            self.product if self.product_id else
            self.product_category if self.product_category_id else
            self.order_engineering_instance
        )
        if self.company_id and target.company_id != self.company_id:
            raise ValidationError({"company": "BOM与适用主体必须属于同一公司"})


    def save(self, *args, **kwargs):
        from .bom_usage_contract import bind_usage
        bind_usage(self)
        super().save(*args, **kwargs)


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
    release_subject_type = models.CharField(
        "制造发布主体类型", max_length=32,
        choices=ManufacturingReleaseSubjectType.choices,
        default=ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT,
    )
    product = models.ForeignKey(
        ProductDefinition,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="engineering_documents",
        verbose_name="长期产品定义",
    )
    order_engineering_instance = models.ForeignKey(
        "pde.OrderEngineeringInstance",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="engineering_documents",
        verbose_name="订单工程产品身份",
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
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        release_subject_type=ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT,
                        product__isnull=False,
                        order_engineering_instance__isnull=True,
                    )
                    | models.Q(
                        release_subject_type=ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
                        product__isnull=True,
                        order_engineering_instance__isnull=False,
                    )
                ),
                name="pde_doc_release_subject_xor",
            ),
        ]

    def clean(self):
        errors = {}
        if self.release_subject_type == ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT:
            if not self.product_id or self.order_engineering_instance_id:
                errors["release_subject_type"] = "长期产品资料必须且只能引用长期产品定义"
            elif self.product_bom_id:
                if (
                    self.product_bom.applicability_scope
                    != ManufacturingApplicabilityScope.PRODUCT_DEFINITION
                    or self.product_bom.product_id != self.product_id
                ):
                    errors["product_bom"] = "长期产品资料BOM主表必须属于当前长期产品"
            if self.routing_id and (
                self.routing.applicability_scope
                != ManufacturingApplicabilityScope.PRODUCT_DEFINITION
                or self.routing.product_id != self.product_id
            ):
                errors["routing"] = "长期产品资料工艺路线必须属于当前长期产品"
        else:
            if self.product_id or not self.order_engineering_instance_id:
                errors["release_subject_type"] = "订单工程资料必须且只能引用具体订单工程实例"
            else:
                instance = self.order_engineering_instance
                if instance.status == "inactive":
                    errors["order_engineering_instance"] = "已失效订单工程实例不得形成工程资料"
                if self.product_bom_id and (
                    self.product_bom.company_id != instance.company_id
                    or self.product_bom.applicability_scope
                    != ManufacturingApplicabilityScope.ORDER_ENGINEERING
                    or self.product_bom.order_engineering_instance_id != instance.pk
                ):
                    errors["product_bom"] = "订单工程资料BOM主表必须属于当前订单工程实例"
                if self.routing_id and not _routing_matches_order_engineering_instance(
                    self.routing, instance,
                ):
                    errors["routing"] = "订单工程资料工艺路线必须适用于当前订单工程实例"
        if errors:
            raise ValidationError(errors)


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

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.version_status == "released":
                immutable = (
                    "product_id", "version_no", "effective_date", "expire_date", "change_reason",
                )
                if any(getattr(original, field) != getattr(self, field) for field in immutable):
                    raise ValidationError({
                        "version_no": "已发布产品版本不可原地覆盖；请创建新版本。",
                    })
        super().save(*args, **kwargs)


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


class ProductDesignItem(models.Model):
    """One stable, source-backed product design item inside a sales order line."""

    DESIGN_DATA_NATURE_CHOICES = (
        ("EXISTING_DESIGN_IMPORTED", "已有设计资料带入"),
        ("FORMAL", "正式设计"),
        ("SIMULATED_FOR_TEST", "开发演练模拟"),
    )

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="product_design_items", verbose_name="所属公司",
    )
    sales_order_item = models.ForeignKey(
        "sales.SalesOrderItem", on_delete=models.PROTECT,
        related_name="product_design_items", verbose_name="销售订单设计分组",
    )
    source_record = models.ForeignKey(
        EngineeringSourceRecord, on_delete=models.PROTECT,
        related_name="product_design_items", verbose_name="工程来源版本",
    )
    source_attribute = models.OneToOneField(
        "sales.SalesOrderItemEngineeringAttribute", on_delete=models.PROTECT,
        related_name="product_design_item", verbose_name="稳定来源行",
    )
    item_no = models.CharField("设计项编号", max_length=120)
    item_name = models.CharField("设计项名称", max_length=200)
    space_snapshot = models.CharField("空间快照", max_length=240, blank=True, default="")
    installation_position_snapshot = models.CharField("安装位置快照", max_length=240, blank=True, default="")
    physical_quantity = models.DecimalField(
        "实物数量", max_digits=20, decimal_places=6, null=True, blank=True,
    )
    physical_uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_design_items", verbose_name="实物计量单位",
    )
    physical_uom_snapshot = models.CharField("实物单位快照", max_length=80, blank=True, default="")
    product_category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_design_items", verbose_name="正式产品分类",
    )
    product_definition = models.ForeignKey(
        ProductDefinition, on_delete=models.PROTECT, null=True, blank=True,
        related_name="order_design_items", verbose_name="正式产品定义",
    )
    original_requirement = models.JSONField("原始需求事实", default=dict)
    existing_design_data = models.JSONField("已有设计资料", default=dict)
    design_data_nature = models.CharField(
        "设计资料性质", max_length=32, choices=DESIGN_DATA_NATURE_CHOICES,
        default="EXISTING_DESIGN_IMPORTED",
    )
    source_version = models.CharField("来源版本快照", max_length=80)
    source_content_hash = models.CharField("来源内容哈希", max_length=64)
    match_results = models.JSONField("正式资料匹配结果", default=dict)
    version = models.PositiveIntegerField("并发版本", default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_product_design_item"
        ordering = ("sales_order_item_id", "source_attribute_id")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "item_no"), name="pde_design_item_company_no_unique",
            ),
        ]


class ProductDesignPlanRevision(models.Model):
    PLAN_TYPE_CHOICES = (
        ("FORMAL", "正式计划"),
        ("HISTORICAL_EVIDENCE", "历史计划依据"),
        ("SIMULATED_FOR_TEST", "开发演练模拟计划"),
    )
    PLAN_NATURE_CHOICES = PLAN_TYPE_CHOICES

    design_item = models.ForeignKey(
        ProductDesignItem, on_delete=models.PROTECT, null=True, blank=True,
        related_name="plan_revisions", verbose_name="历史产品设计项关联",
    )
    order = models.ForeignKey(
        "sales.SalesOrder", on_delete=models.PROTECT,
        related_name="product_design_plan_revisions", verbose_name="销售订单",
    )
    design_group = models.CharField("设计分组", max_length=16)
    revision = models.PositiveIntegerField("计划修订")
    designer_employee = models.ForeignKey(
        "pfm.Employee", on_delete=models.PROTECT,
        related_name="product_design_plan_revisions", verbose_name="设计师",
    )
    planned_start_date = models.DateField("计划开始设计日期")
    planned_finish_date = models.DateField("计划完成设计日期")
    actual_start_date = models.DateField("实际开始设计日期", null=True, blank=True)
    plan_type = models.CharField("计划性质", max_length=32, choices=PLAN_TYPE_CHOICES)
    adjustment_reason = models.CharField("计划登记/调整原因", max_length=500)
    previous_revision = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="next_revisions", verbose_name="上一计划修订",
    )
    created_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="created_product_design_plan_revisions", verbose_name="登记人",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_product_design_plan_revision"
        ordering = ("order_id", "design_group", "revision")
        constraints = [
            models.UniqueConstraint(
                fields=("order", "design_group", "revision"),
                condition=models.Q(design_item__isnull=True),
                name="pde_design_plan_group_revision_unique",
            ),
        ]


class ProductDesignRevision(models.Model):
    DESIGN_NATURE_CHOICES = (
        ("FORMAL", "正式设计修订"),
        ("EXISTING_DESIGN_IMPORTED", "已有设计资料带入"),
        ("SIMULATED_FOR_TEST", "开发演练模拟设计"),
    )

    design_item = models.ForeignKey(
        ProductDesignItem, on_delete=models.PROTECT,
        related_name="design_revisions", verbose_name="产品设计项",
    )
    revision = models.PositiveIntegerField("设计修订")
    design_nature = models.CharField("设计性质", max_length=32, choices=DESIGN_NATURE_CHOICES)
    predecessor_revision = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="approved_successors")
    origin_nature = models.CharField(max_length=32, blank=True, default="")
    approval_scope = models.CharField(max_length=32, blank=True, default="")
    approval = models.OneToOneField("DesignRevisionApproval", on_delete=models.PROTECT, null=True, blank=True, related_name="successor_revision")
    design_length = models.DecimalField("设计长度", max_digits=20, decimal_places=6, null=True, blank=True)
    design_width = models.DecimalField("设计宽度", max_digits=20, decimal_places=6, null=True, blank=True)
    design_thickness = models.DecimalField("设计厚度", max_digits=20, decimal_places=6, null=True, blank=True)
    design_uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_design_revisions", verbose_name="设计尺寸单位",
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_design_revisions", verbose_name="正式材料/规格",
    )
    material_process_type = models.ForeignKey(
        ManufacturingProcessType, on_delete=models.PROTECT, null=True, blank=True,
        related_name="material_product_design_revisions", verbose_name="材料/工艺配置",
    )
    paint_process_type = models.ForeignKey(
        ManufacturingProcessType, on_delete=models.PROTECT, null=True, blank=True,
        related_name="paint_product_design_revisions", verbose_name="油漆工艺",
    )
    edge_method = models.ForeignKey(
        EngineeringBreakdownOption, on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_design_revisions", verbose_name="封边方式",
    )
    design_data = models.JSONField("结构化设计数据", default=dict)
    source_provenance = models.JSONField("设计值来源追溯", default=dict)
    master_match_results = models.JSONField("主数据匹配结果", default=dict)
    legacy_source_record = models.OneToOneField(
        EngineeringSourceRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_design_revision_compatibility", verbose_name="既有设计草稿兼容引用",
    )
    change_reason = models.CharField("设计修订原因", max_length=500)
    created_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="created_product_design_revisions", verbose_name="设计登记人",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_product_design_revision"
        ordering = ("design_item_id", "revision")
        constraints = [
            models.UniqueConstraint(
                fields=("design_item", "revision"), name="pde_design_revision_item_revision_unique",
            ),
        ]


class ProductDesignCompletionRecord(models.Model):
    COMPLETION_NATURE_CHOICES = (
        ("FORMAL", "正式完成登记"),
        ("HISTORICAL_EVIDENCE", "已有完成事实补录"),
        ("SIMULATED_FOR_TEST", "开发演练模拟完成"),
        ("REWORK", "返工/变更登记"),
    )

    design_item = models.ForeignKey(
        ProductDesignItem, on_delete=models.PROTECT,
        related_name="completion_records", verbose_name="产品设计项",
    )
    sequence = models.PositiveIntegerField("完成记录序号")
    completion_nature = models.CharField(
        "完成记录性质", max_length=32, choices=COMPLETION_NATURE_CHOICES,
    )
    actual_completion_date = models.DateField("实际完成设计日期", null=True, blank=True)
    completion_basis = models.CharField("完成依据/说明", max_length=500)
    plan_revision = models.ForeignKey(
        ProductDesignPlanRevision, on_delete=models.PROTECT, null=True, blank=True,
        related_name="completion_records", verbose_name="对应计划修订",
    )
    design_revision = models.ForeignKey(
        ProductDesignRevision, on_delete=models.PROTECT, null=True, blank=True,
        related_name="completion_records", verbose_name="对应设计修订",
    )
    completed_designer = models.ForeignKey(
        "pfm.Employee", on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_design_completion_records", verbose_name="完成设计师",
    )
    recorded_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="recorded_product_design_completions", verbose_name="登记人",
    )
    action_code = models.CharField("动作编码", max_length=120)
    recorded_at = models.DateTimeField("系统登记时间", auto_now_add=True)

    class Meta:
        db_table = "pde_product_design_completion_record"
        ordering = ("design_item_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("design_item", "sequence"), name="pde_design_completion_item_sequence_unique",
            ),
        ]


class OrderEngineeringBaseline(models.Model):
    """Immutable order-wide snapshot of the engineering facts used at save time."""

    STATUS_CHOICES = (("draft", "草稿"), ("confirmed", "已确认"))

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="order_engineering_baselines", verbose_name="所属公司",
    )
    sales_order = models.ForeignKey(
        "sales.SalesOrder", on_delete=models.PROTECT,
        related_name="engineering_baselines", verbose_name="销售订单",
    )
    approval_scope = models.CharField(max_length=32, blank=True, default="")
    baseline_no = models.CharField("工程基线编号", max_length=120)
    sequence = models.PositiveIntegerField("订单内基线序号")
    status = models.CharField("状态", max_length=16, choices=STATUS_CHOICES, default="draft")
    reason = models.CharField("保存原因", max_length=500)
    candidate_hash = models.CharField("候选范围哈希", max_length=64)
    snapshot_hash = models.CharField("基线内容哈希", max_length=64)
    scope_item_count = models.PositiveIntegerField("工程范围项数")
    confirmable_item_count = models.PositiveIntegerField("可确认项数")
    blocker_count = models.PositiveIntegerField("确认阻断项数")
    blocker_summary = models.JSONField("确认阻断汇总", default=dict)
    version = models.PositiveIntegerField("乐观并发版本", default=1)
    created_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="created_order_engineering_baselines", verbose_name="保存人",
    )
    confirmed_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT, null=True, blank=True,
        related_name="confirmed_order_engineering_baselines", verbose_name="确认人",
    )
    confirmed_at = models.DateTimeField("确认时间", null=True, blank=True)
    created_at = models.DateTimeField("保存时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "pde_order_engineering_baseline"
        ordering = ("sales_order_id", "-sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "baseline_no"),
                name="pde_order_eng_baseline_company_no_unique",
            ),
            models.UniqueConstraint(
                fields=("sales_order", "sequence"),
                name="pde_order_eng_baseline_order_sequence_unique",
            ),
        ]
        indexes = [
            models.Index(fields=("company", "sales_order", "status"), name="pde_oeb_scope_status_idx"),
            models.Index(fields=("sales_order", "created_at"), name="pde_oeb_order_created_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and any(getattr(original,key)!=getattr(self,key) for key in ('approval_scope','company_id','sales_order_id','candidate_hash','snapshot_hash','scope_item_count','blocker_count','blocker_summary')):
                raise ValidationError("已保存基线冻结内容与用途不可修改。")
            if original and original.status == "confirmed" and not getattr(
                self, "_baseline_confirmation_metadata_authorized", False,
            ):
                raise ValidationError("已确认工程基线不可修改；请保存新的后续基线。")
            if original and original.status != self.status and not getattr(
                self, "_business_state_transition_authorized", False,
            ):
                raise ValidationError("工程基线状态必须通过统一状态转换服务修改。")
        elif not getattr(self, "_business_state_initialization_authorized", False):
            raise ValidationError("工程基线必须通过正式服务初始化。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == "confirmed":
            raise ValidationError("已确认工程基线不可删除。")
        return super().delete(*args, **kwargs)


class OrderEngineeringBaselineItem(models.Model):
    SOURCE_TYPE_CHOICES = (
        ("DESIGN_REVISION", "设计修订"),
        ("PERSISTED_DESIGN_CONTENT", "已持久保存的工程内容"),
        ("SOURCE_CONTENT", "稳定来源内容"),
        ("MISSING", "缺少必要工程内容"),
    )

    baseline = models.ForeignKey(
        OrderEngineeringBaseline, on_delete=models.PROTECT,
        related_name="items", verbose_name="订单工程基线",
    )
    design_item = models.ForeignKey(
        ProductDesignItem, on_delete=models.PROTECT,
        related_name="engineering_baseline_items", verbose_name="产品设计项",
    )
    design_revision = models.ForeignKey(
        ProductDesignRevision, on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_baseline_items", verbose_name="精确设计修订",
    )
    source_record = models.ForeignKey(
        EngineeringSourceRecord, on_delete=models.PROTECT,
        related_name="engineering_baseline_items", verbose_name="来源记录",
    )
    source_attribute = models.ForeignKey(
        "sales.SalesOrderItemEngineeringAttribute", on_delete=models.PROTECT,
        related_name="engineering_baseline_items", verbose_name="稳定来源行",
    )
    source_type = models.CharField("快照来源类型", max_length=40, choices=SOURCE_TYPE_CHOICES)
    item_no_snapshot = models.CharField("设计项编号快照", max_length=120)
    item_name_snapshot = models.CharField("设计项名称快照", max_length=200)
    design_item_version = models.PositiveIntegerField("设计项并发版本")
    design_revision_no = models.PositiveIntegerField("设计修订号", null=True, blank=True)
    design_nature_snapshot = models.CharField("设计性质快照", max_length=32, blank=True, default="")
    source_version_snapshot = models.CharField("来源版本快照", max_length=80)
    source_content_hash_snapshot = models.CharField("来源内容哈希快照", max_length=64)
    content_snapshot = models.JSONField("工程内容快照", default=dict)
    content_hash = models.CharField("工程内容哈希", max_length=64)
    confirmable = models.BooleanField("可用于基线确认", default=False)
    blocker_code = models.CharField("确认阻断编码", max_length=80, blank=True, default="")
    blocker_label = models.CharField("确认阻断说明", max_length=240, blank=True, default="")
    created_at = models.DateTimeField("快照时间", auto_now_add=True)

    class Meta:
        db_table = "pde_order_engineering_baseline_item"
        ordering = ("baseline_id", "design_item_id")
        constraints = [
            models.UniqueConstraint(
                fields=("baseline", "design_item"),
                name="pde_order_eng_baseline_item_unique",
            ),
        ]
        indexes = [
            models.Index(fields=("design_item", "created_at"), name="pde_oebi_item_created_idx"),
            models.Index(fields=("baseline", "confirmable"), name="pde_oebi_confirmable_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.baseline_id and self.baseline.status == "confirmed":
            raise ValidationError("已确认工程基线的明细不可修改。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.baseline.status == "confirmed":
            raise ValidationError("已确认工程基线的明细不可删除。")
        return super().delete(*args, **kwargs)


class OrderCrossFunctionalReview(models.Model):
    """Immutable, independently versioned CRM/PDE review conclusion."""

    REVIEW_TYPES = (
        ("CRM_ORDER_REVIEW", "订单评审"),
        ("PDE_PRODUCTION_FEASIBILITY", "生产可行性评审"),
    )
    CONCLUSIONS = (
        ("CONDITIONAL", "有条件通过"),
        ("ACCEPT", "通过"),
        ("RETURN_FOR_COMPLETION", "退回补充"),
        ("REJECT", "不通过"),
    )
    RECORD_STATUSES = (("DRAFT", "草稿"), ("SUBMITTED", "已提交"))

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="order_cross_functional_reviews", verbose_name="所属公司",
    )
    source_record = models.ForeignKey(
        EngineeringSourceRecord, on_delete=models.PROTECT,
        related_name="cross_functional_reviews", verbose_name="工程来源",
    )
    review_type = models.CharField("评审类型", max_length=40, choices=REVIEW_TYPES)
    source_order_no = models.CharField("来源订单标识", max_length=80)
    source_version = models.CharField("评审依据版本", max_length=80)
    source_content_hash = models.CharField("评审依据哈希", max_length=64)
    review_version = models.PositiveIntegerField("评审记录版本")
    conclusion = models.CharField("评审结论", max_length=32, choices=CONCLUSIONS, blank=True, default="")
    review_opinion = models.TextField("评审意见", blank=True, default="")
    evidence = models.JSONField("评审依据", default=dict)
    missing_conditions = models.JSONField("待补条件", default=list)
    responsibility_feedback = models.JSONField("处理责任及反馈", default=dict)
    reviewer = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="order_cross_functional_reviews", verbose_name="执行人",
    )
    idempotency_key = models.CharField("幂等键", max_length=120)
    audit_hash = models.CharField("审计哈希", max_length=64, unique=True)
    record_status = models.CharField("记录状态", max_length=16, choices=RECORD_STATUSES, default="SUBMITTED")
    template_version = models.CharField("评审模板版本", max_length=40, blank=True, default="")
    item_summary = models.JSONField("逐项汇总", default=dict, blank=True)
    submitted_at = models.DateTimeField("提交时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_order_cross_functional_review"
        ordering = ("company_id", "source_order_no", "review_type", "-review_version")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "review_type", "source_order_no", "review_version"),
                name="pde_order_review_type_version_unique",
            ),
            models.UniqueConstraint(
                fields=("company", "review_type", "idempotency_key"),
                name="pde_order_review_idempotency_unique",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, record_status="SUBMITTED").exists():
            raise ValidationError("评审历史为不可变审计记录，不允许覆盖修改。")
        return super().save(*args, **kwargs)


class OrderReviewSalesOrderRelation(models.Model):
    """Append-only formal relation from one CRM review version to one order."""

    SCOPE_MODES = (
        ("WHOLE_ORDER", "全订单"),
        ("SELECTED_ITEMS", "明确选择订单行"),
        ("UNRESOLVED", "历史范围未解析"),
    )
    RESOLUTION_BASES = (
        ("RUNTIME_GATE", "在线准入Gate"),
        ("APPROVED_HISTORICAL_MANIFEST", "已批准历史登记清单"),
    )

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="order_review_sales_order_relations", verbose_name="所属公司",
    )
    review = models.OneToOneField(
        OrderCrossFunctionalReview, on_delete=models.PROTECT,
        related_name="sales_order_relation", verbose_name="订单评审版本",
    )
    sales_order = models.ForeignKey(
        "sales.SalesOrder", on_delete=models.PROTECT,
        related_name="order_review_relations", verbose_name="正式销售订单",
    )
    scope_mode = models.CharField("评审范围模式", max_length=24, choices=SCOPE_MODES)
    order_version_snapshot = models.PositiveIntegerField("订单版本快照")
    source_content_hash_snapshot = models.CharField("来源内容哈希快照", max_length=64)
    resolution_basis = models.CharField("关系解析依据", max_length=40, choices=RESOLUTION_BASES)
    scope_reason = models.TextField("范围说明", blank=True, default="")
    created_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="created_order_review_sales_order_relations", verbose_name="创建人",
    )
    audit_hash = models.CharField("关系审计哈希", max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_order_review_sales_order_relation"
        ordering = ("company_id", "sales_order_id", "review_id")
        indexes = [
            models.Index(
                fields=("company", "sales_order"),
                name="pde_orr_company_order_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(scope_mode__in=("WHOLE_ORDER", "SELECTED_ITEMS", "UNRESOLVED")),
                name="pde_orr_scope_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    resolution_basis__in=("RUNTIME_GATE", "APPROVED_HISTORICAL_MANIFEST"),
                ),
                name="pde_orr_basis_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(order_version_snapshot__gt=0),
                name="pde_orr_order_version_positive",
            ),
        ]

    def clean(self):
        errors = {}
        if self.review_id:
            if self.review.review_type != "CRM_ORDER_REVIEW":
                errors["review"] = "正式销售订单关系只允许关联CRM订单评审"
            if self.review.record_status != "SUBMITTED":
                errors["review"] = "正式销售订单关系只允许关联已提交评审"
            if self.company_id and self.review.company_id != self.company_id:
                errors["company"] = "关系公司必须与评审公司一致"
            if self.source_content_hash_snapshot != self.review.source_content_hash:
                errors["source_content_hash_snapshot"] = "来源内容哈希快照必须与评审依据一致"
        if self.sales_order_id:
            if self.company_id and self.sales_order.company_id != self.company_id:
                errors["sales_order"] = "销售订单必须与关系属于同一公司"
            if self.order_version_snapshot != self.sales_order.version:
                errors["order_version_snapshot"] = "订单版本快照必须与当前正式订单版本一致"
        if self.resolution_basis == "RUNTIME_GATE" and self.scope_mode == "UNRESOLVED":
            errors["scope_mode"] = "新在线流程禁止使用UNRESOLVED范围"
        if self.scope_mode == "UNRESOLVED" and self.resolution_basis != "APPROVED_HISTORICAL_MANIFEST":
            errors["resolution_basis"] = "UNRESOLVED仅允许用于已批准历史登记"
        if self.scope_mode == "SELECTED_ITEMS" and not self.scope_reason.strip():
            errors["scope_reason"] = "部分订单行范围必须保存明确原因"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("订单评审正式关系为只追加记录，不允许修改。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("订单评审正式关系为只追加记录，不允许删除。")


class OrderReviewScopeItem(models.Model):
    """Immutable SalesOrderItem membership snapshot for one formal review relation."""

    relation = models.ForeignKey(
        OrderReviewSalesOrderRelation, on_delete=models.PROTECT,
        related_name="scope_items", verbose_name="订单评审正式关系",
    )
    sales_order_item = models.ForeignKey(
        "sales.SalesOrderItem", on_delete=models.PROTECT,
        related_name="order_review_scope_items", verbose_name="评审范围订单行",
    )
    line_no_snapshot = models.PositiveIntegerField("订单行号快照")
    external_line_no_snapshot = models.CharField("外部行号快照", max_length=80, blank=True, default="")
    item_identity_hash = models.CharField("订单行身份哈希", max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_order_review_scope_item"
        ordering = ("relation_id", "line_no_snapshot", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("relation", "sales_order_item"),
                name="pde_orsi_relation_item_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(line_no_snapshot__gt=0),
                name="pde_orsi_line_positive",
            ),
        ]

    def clean(self):
        errors = {}
        if self.relation_id and self.sales_order_item_id:
            if self.sales_order_item.sales_order_id != self.relation.sales_order_id:
                errors["sales_order_item"] = "评审范围订单行必须属于关系对应的销售订单"
            if self.line_no_snapshot != self.sales_order_item.line_no:
                errors["line_no_snapshot"] = "订单行号快照必须与正式订单行一致"
            if self.external_line_no_snapshot != self.sales_order_item.external_line_no:
                errors["external_line_no_snapshot"] = "外部行号快照必须与正式订单行一致"
        if len(self.item_identity_hash or "") != 64:
            errors["item_identity_hash"] = "订单行身份哈希必须是64位SHA256"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("订单评审范围为只追加快照，不允许修改。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("订单评审范围为只追加快照，不允许删除。")


class PDEReviewPredecessorRelation(models.Model):
    """Immutable predecessor from one PDE review version to the CRM 0032 relation."""

    RESOLUTION_BASES = (("RUNTIME_GATE", "在线CRM准入Gate"),)

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="pde_review_predecessor_relations", verbose_name="所属公司",
    )
    pde_review = models.OneToOneField(
        OrderCrossFunctionalReview, on_delete=models.PROTECT,
        related_name="pde_predecessor_relation", verbose_name="PDE生产可行性评审版本",
    )
    crm_order_relation = models.ForeignKey(
        OrderReviewSalesOrderRelation, on_delete=models.PROTECT,
        related_name="pde_review_predecessors", verbose_name="CRM订单评审正式关系",
    )
    crm_review_version_snapshot = models.PositiveIntegerField("CRM评审版本快照")
    pde_review_version_snapshot = models.PositiveIntegerField("PDE评审版本快照")
    order_version_snapshot = models.PositiveIntegerField("订单版本快照")
    source_content_hash_snapshot = models.CharField("来源内容哈希快照", max_length=64)
    scope_identity_hash_snapshot = models.CharField("订单行范围身份哈希", max_length=64)
    resolution_basis = models.CharField("关系解析依据", max_length=40, choices=RESOLUTION_BASES)
    created_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="created_pde_review_predecessor_relations", verbose_name="创建人",
    )
    audit_hash = models.CharField("关系审计哈希", max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_review_predecessor_relation"
        ordering = ("company_id", "pde_review_id")
        indexes = [
            models.Index(
                fields=("company", "crm_order_relation"),
                name="pde_rpr_company_crm_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(resolution_basis="RUNTIME_GATE"),
                name="pde_rpr_basis_runtime_gate",
            ),
            models.CheckConstraint(
                condition=models.Q(crm_review_version_snapshot__gt=0),
                name="pde_rpr_crm_version_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(pde_review_version_snapshot__gt=0),
                name="pde_rpr_pde_version_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(order_version_snapshot__gt=0),
                name="pde_rpr_order_version_positive",
            ),
        ]

    def clean(self):
        errors = {}
        if self.pde_review_id:
            if self.pde_review.review_type != "PDE_PRODUCTION_FEASIBILITY":
                errors["pde_review"] = "正式前置关系只允许关联PDE生产可行性评审"
            if self.company_id and self.pde_review.company_id != self.company_id:
                errors["company"] = "关系公司必须与PDE评审公司一致"
            if self.pde_review_version_snapshot != self.pde_review.review_version:
                errors["pde_review_version_snapshot"] = "PDE评审版本快照不一致"
            if self.source_content_hash_snapshot != self.pde_review.source_content_hash:
                errors["source_content_hash_snapshot"] = "来源内容哈希快照与PDE评审不一致"
        if self.crm_order_relation_id:
            relation = self.crm_order_relation
            crm_review = relation.review
            if crm_review.review_type != "CRM_ORDER_REVIEW":
                errors["crm_order_relation"] = "前置关系必须引用CRM订单评审正式关系"
            if self.company_id and relation.company_id != self.company_id:
                errors["company"] = "关系公司必须与CRM订单关系公司一致"
            if self.crm_review_version_snapshot != crm_review.review_version:
                errors["crm_review_version_snapshot"] = "CRM评审版本快照不一致"
            if self.order_version_snapshot != relation.order_version_snapshot:
                errors["order_version_snapshot"] = "订单版本快照必须继承0032正式关系"
            if relation.scope_mode == "UNRESOLVED":
                errors["crm_order_relation"] = "UNRESOLVED订单范围不能形成PDE正式前置"
            if self.pde_review_id:
                if crm_review.source_record_id != self.pde_review.source_record_id:
                    errors["pde_review"] = "CRM与PDE评审的来源记录不一致"
                if crm_review.source_version != self.pde_review.source_version:
                    errors["pde_review"] = "CRM与PDE评审的来源版本不一致"
                if crm_review.source_content_hash != self.pde_review.source_content_hash:
                    errors["pde_review"] = "CRM与PDE评审的来源内容哈希不一致"
        if len(self.scope_identity_hash_snapshot or "") != 64:
            errors["scope_identity_hash_snapshot"] = "范围身份哈希必须是64位SHA256"
        if len(self.audit_hash or "") != 64:
            errors["audit_hash"] = "审计哈希必须是64位SHA256"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PDE评审正式前置关系为只追加记录，不允许修改。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PDE评审正式前置关系为只追加记录，不允许删除。")


class PDEEngineeringPreparationAuthorization(models.Model):
    """Immutable approval fact authorizing PDE engineering preparation writes."""

    AUTHORIZATION_BASES = (("FINAL_APPROVAL", "PDE最终审批"),)

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="pde_engineering_preparation_authorizations", verbose_name="所属公司",
    )
    predecessor_relation = models.OneToOneField(
        PDEReviewPredecessorRelation, on_delete=models.PROTECT,
        related_name="engineering_preparation_authorization", verbose_name="PDE评审正式前置关系",
    )
    workflow_instance = models.OneToOneField(
        "workflow_runtime.WorkflowInstance", on_delete=models.PROTECT,
        related_name="pde_engineering_preparation_authorization", verbose_name="最终审批流程",
    )
    approval_decision = models.OneToOneField(
        "workflow_runtime.ApprovalDecision", on_delete=models.PROTECT,
        related_name="pde_engineering_preparation_authorization", verbose_name="最终批准决定",
    )
    pde_review_version_snapshot = models.PositiveIntegerField("PDE评审版本快照")
    pde_review_content_hash_snapshot = models.CharField("PDE评审内容哈希快照", max_length=64)
    order_version_snapshot = models.PositiveIntegerField("订单版本快照")
    scope_identity_hash_snapshot = models.CharField("订单行范围身份哈希", max_length=64)
    authorization_basis = models.CharField("授权形成依据", max_length=40, choices=AUTHORIZATION_BASES)
    created_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="created_pde_engineering_preparation_authorizations", verbose_name="创建人",
    )
    audit_hash = models.CharField("授权审计哈希", max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_engineering_preparation_authorization"
        ordering = ("company_id", "predecessor_relation_id")
        indexes = [
            models.Index(
                fields=("company", "created_at"),
                name="pde_epa_company_created_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(authorization_basis="FINAL_APPROVAL"),
                name="pde_epa_basis_final_approval",
            ),
            models.CheckConstraint(
                condition=models.Q(pde_review_version_snapshot__gt=0),
                name="pde_epa_pde_version_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(order_version_snapshot__gt=0),
                name="pde_epa_order_version_positive",
            ),
        ]

    def clean(self):
        errors = {}
        if self.predecessor_relation_id:
            predecessor = self.predecessor_relation
            review = predecessor.pde_review
            if self.company_id and predecessor.company_id != self.company_id:
                errors["company"] = "授权公司必须与正式前置关系公司一致"
            if self.pde_review_version_snapshot != review.review_version:
                errors["pde_review_version_snapshot"] = "PDE评审版本快照不一致"
            if self.pde_review_content_hash_snapshot != review.source_content_hash:
                errors["pde_review_content_hash_snapshot"] = "PDE评审内容哈希快照不一致"
            if self.order_version_snapshot != predecessor.order_version_snapshot:
                errors["order_version_snapshot"] = "授权订单版本必须继承正式前置关系"
            if self.scope_identity_hash_snapshot != predecessor.scope_identity_hash_snapshot:
                errors["scope_identity_hash_snapshot"] = "授权范围哈希必须继承正式前置关系"
            if self.workflow_instance_id:
                if self.workflow_instance.document_type != "PDEProductionFeasibilityReview":
                    errors["workflow_instance"] = "授权流程类型不是PDE生产可行性评审"
                if self.workflow_instance.document_id != review.pk:
                    errors["workflow_instance"] = "授权流程未精确指向PDE评审"
                if self.workflow_instance.status != "approved":
                    errors["workflow_instance"] = "PDE评审流程尚未最终批准"
            if self.approval_decision_id:
                decision = self.approval_decision
                if decision.task.workflow_instance_id != self.workflow_instance_id:
                    errors["approval_decision"] = "最终决定不属于授权流程"
                if decision.decision != "approved":
                    errors["approval_decision"] = "最终决定不是approved"
        if len(self.scope_identity_hash_snapshot or "") != 64:
            errors["scope_identity_hash_snapshot"] = "范围身份哈希必须是64位SHA256"
        if len(self.audit_hash or "") != 64:
            errors["audit_hash"] = "审计哈希必须是64位SHA256"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PDE工程准备授权为只追加记录，不允许修改。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PDE工程准备授权为只追加记录，不允许删除。")


class OrderReviewTemplate(models.Model):
    """Versioned server authority for the fixed review checklist."""

    review_type = models.CharField("评审类型", max_length=40, choices=OrderCrossFunctionalReview.REVIEW_TYPES)
    version = models.CharField("模板版本", max_length=40)
    title = models.CharField("模板名称", max_length=120)
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_order_review_template"
        constraints = [models.UniqueConstraint(fields=("review_type", "version"), name="pde_order_review_template_version_unique")]


class OrderReviewTemplateItem(models.Model):
    template = models.ForeignKey(OrderReviewTemplate, on_delete=models.PROTECT, related_name="items")
    item_code = models.CharField("项目编码", max_length=20)
    item_text = models.CharField("评审项目", max_length=300)
    display_order = models.PositiveIntegerField("显示顺序")
    is_applicable = models.BooleanField("是否适用", default=True)
    disagreement_reasons = models.JSONField("标准不同意原因", default=list)

    class Meta:
        db_table = "pde_order_review_template_item"
        ordering = ("display_order", "id")
        constraints = [models.UniqueConstraint(fields=("template", "item_code"), name="pde_order_review_template_item_code_unique")]


class OrderCrossFunctionalReviewItem(models.Model):
    ITEM_KINDS = (("FIXED", "固定项目"), ("OTHER", "其它评审事项"))
    DECISIONS = (("AGREE", "同意"), ("DISAGREE", "不同意"))
    SIGNATURE_STATUSES = (("UNSIGNED", "未签认"), ("SIGNED", "已签认"))

    review = models.ForeignKey(OrderCrossFunctionalReview, on_delete=models.PROTECT, related_name="items")
    stable_key = models.CharField("稳定条目身份", max_length=64)
    item_kind = models.CharField("项目类型", max_length=12, choices=ITEM_KINDS)
    template_item = models.ForeignKey(OrderReviewTemplateItem, on_delete=models.PROTECT, null=True, blank=True)
    item_code = models.CharField("项目编码快照", max_length=20)
    item_text = models.CharField("评审项目快照", max_length=300)
    evidence_note = models.TextField("依据说明", blank=True, default="")
    decision = models.CharField("判定", max_length=12, choices=DECISIONS, blank=True, default="")
    disagreement_reason_code = models.CharField("不同意原因编码", max_length=40, blank=True, default="")
    disagreement_reason_text = models.TextField("不同意具体说明", blank=True, default="")
    responsible_employee = models.ForeignKey("pfm.Employee", on_delete=models.PROTECT, null=True, blank=True, related_name="responsible_order_review_items")
    signature_status = models.CharField("签认状态", max_length=12, choices=SIGNATURE_STATUSES, default="UNSIGNED")
    signed_by_user = models.ForeignKey("system.User", on_delete=models.PROTECT, null=True, blank=True, related_name="signed_order_review_items")
    signed_employee_id_snapshot = models.BigIntegerField(null=True, blank=True)
    signed_employee_no_snapshot = models.CharField(max_length=50, blank=True, default="")
    signed_employee_name_snapshot = models.CharField(max_length=50, blank=True, default="")
    signed_at = models.DateTimeField(null=True, blank=True)
    signature_content_hash = models.CharField(max_length=64, blank=True, default="")
    content_revision = models.PositiveIntegerField(default=1)
    display_order = models.PositiveIntegerField(default=0)
    is_removed = models.BooleanField(default=False)
    removed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_order_cross_functional_review_item"
        ordering = ("display_order", "id")
        constraints = [models.UniqueConstraint(fields=("review", "stable_key"), name="pde_order_review_item_stable_unique")]


class OrderReviewItemAudit(models.Model):
    review = models.ForeignKey(OrderCrossFunctionalReview, on_delete=models.PROTECT, related_name="item_audits")
    item = models.ForeignKey(OrderCrossFunctionalReviewItem, on_delete=models.PROTECT, null=True, blank=True, related_name="audits")
    action = models.CharField("动作", max_length=32)
    actor = models.ForeignKey("system.User", on_delete=models.PROTECT, related_name="order_review_item_audits")
    before_snapshot = models.JSONField(default=dict)
    after_snapshot = models.JSONField(default=dict)
    audit_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_order_review_item_audit"
        ordering = ("created_at", "id")


class OrderReviewParticipantGrant(models.Model):
    """Review-object authorization for one real employee and linked login account.

    This grant deliberately does not confer ``sales.order.update`` or any other
    order-wide permission.  Runtime checks still require the current employee,
    assigned review item, company, review version and source version to match.
    """

    review = models.ForeignKey(
        OrderCrossFunctionalReview, on_delete=models.PROTECT,
        related_name="participant_grants", verbose_name="授权评审",
    )
    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="order_review_participant_grants", verbose_name="所属公司",
    )
    employee = models.ForeignKey(
        "pfm.Employee", on_delete=models.PROTECT,
        related_name="order_review_participant_grants", verbose_name="责任人员工",
    )
    user = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="order_review_participant_grants", verbose_name="办理账号",
    )
    review_version_snapshot = models.PositiveIntegerField("评审版本")
    source_version_snapshot = models.CharField("来源版本", max_length=80)
    can_view = models.BooleanField("可查看本评审", default=True)
    can_maintain_own_opinion = models.BooleanField("可维护本人负责项", default=True)
    can_sign_own_items = models.BooleanField("可签认本人负责项", default=True)
    active = models.BooleanField("是否有效", default=True)
    reason = models.CharField("授权依据", max_length=300)
    created_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="created_order_review_participant_grants", verbose_name="配置人",
    )
    audit_hash = models.CharField("审计哈希", max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_order_review_participant_grant"
        ordering = ("review_id", "employee_id")
        constraints = [
            models.UniqueConstraint(
                fields=("review", "employee", "user"),
                name="pde_order_review_participant_unique",
            ),
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
    engineering_preparation_authorization = models.ForeignKey(
        PDEEngineeringPreparationAuthorization, on_delete=models.PROTECT,
        null=True, blank=True, related_name="order_engineering_instances",
        verbose_name="PDE工程准备授权",
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
        if self.engineering_preparation_authorization_id:
            authorization = self.engineering_preparation_authorization
            predecessor = authorization.predecessor_relation
            crm_relation = predecessor.crm_order_relation
            if authorization.company_id != self.company_id:
                errors["engineering_preparation_authorization"] = "工程准备授权必须属于工程实例所在公司"
            if self.sales_order_item.sales_order_id != crm_relation.sales_order_id:
                errors["engineering_preparation_authorization"] = "工程准备授权不属于当前销售订单"
            if not crm_relation.scope_items.filter(sales_order_item_id=self.sales_order_item_id).exists():
                errors["sales_order_item"] = "销售订单行不在工程准备授权继承的0032范围内"
            if self.source_record_id != predecessor.pde_review.source_record_id:
                errors["source_record"] = "工程实例来源必须与工程准备授权的PDE评审一致"
        if self.product_id:
            if self.product.company_id != self.company_id:
                errors["product"] = "产品必须属于工程实例所在公司"
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


class PDEAdmissionChainRevocation(models.Model):
    """Immutable fact revoking one complete PDE admission chain.

    The referenced historical relation, reviews, approval facts and OEI remain
    untouched.  Current-fact readers exclude a chain when this fact exists.
    """

    REASON_CODES = (
        ("BUSINESS_IDENTITY_CONFLICT", "业务身份冲突"),
    )

    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="pde_admission_chain_revocations", verbose_name="所属公司",
    )
    revocation_no = models.CharField("撤销编号", max_length=120)
    idempotency_key = models.CharField("幂等键", max_length=120)
    crm_order_relation = models.OneToOneField(
        OrderReviewSalesOrderRelation, on_delete=models.PROTECT,
        related_name="admission_chain_revocation", verbose_name="0032正式关系",
    )
    pde_review = models.OneToOneField(
        OrderCrossFunctionalReview, on_delete=models.PROTECT,
        related_name="admission_chain_revocation", verbose_name="PDE评审",
    )
    predecessor_relation = models.OneToOneField(
        PDEReviewPredecessorRelation, on_delete=models.PROTECT,
        related_name="admission_chain_revocation", verbose_name="PDE正式前置关系",
    )
    authorization = models.OneToOneField(
        PDEEngineeringPreparationAuthorization, on_delete=models.PROTECT,
        related_name="admission_chain_revocation", verbose_name="PDE工程准备授权",
    )
    engineering_instance = models.OneToOneField(
        OrderEngineeringInstance, on_delete=models.PROTECT,
        related_name="admission_chain_revocation", verbose_name="订单工程实例",
    )
    reason_code = models.CharField(
        "撤销原因编码", max_length=40, choices=REASON_CODES,
        default="BUSINESS_IDENTITY_CONFLICT",
    )
    reason = models.CharField("撤销原因", max_length=300)
    identity_snapshot = models.JSONField("链级身份快照", default=dict)
    authorized_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="authorized_pde_admission_chain_revocations", verbose_name="授权确认人",
    )
    created_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="created_pde_admission_chain_revocations", verbose_name="执行人",
    )
    audit_record = models.OneToOneField(
        "system.OrganizationOperatingAuditRecord", on_delete=models.PROTECT,
        related_name="pde_admission_chain_revocation", verbose_name="组织审计记录",
    )
    audit_hash = models.CharField("撤销事实哈希", max_length=64, unique=True)
    effective_at = models.DateTimeField("生效时间")
    created_at = models.DateTimeField("记录时间", auto_now_add=True)

    class Meta:
        db_table = "pde_admission_chain_revocation"
        ordering = ("company_id", "effective_at", "pk")
        indexes = [
            models.Index(
                fields=("company", "effective_at"),
                name="pde_acr_company_effective_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("company", "revocation_no"),
                name="pde_acr_company_no_unique",
            ),
            models.UniqueConstraint(
                fields=("company", "idempotency_key"),
                name="pde_acr_company_idem_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(reason_code="BUSINESS_IDENTITY_CONFLICT"),
                name="pde_acr_reason_identity_conflict",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""),
                name="pde_acr_reason_required",
            ),
        ]

    def clean(self):
        errors = {}
        if self.predecessor_relation_id:
            predecessor = self.predecessor_relation
            if predecessor.crm_order_relation_id != self.crm_order_relation_id:
                errors["predecessor_relation"] = "PDE前置关系必须属于被撤销的0032关系"
            if predecessor.pde_review_id != self.pde_review_id:
                errors["pde_review"] = "PDE评审必须与被撤销的前置关系一致"
        if self.authorization_id:
            authorization = self.authorization
            if authorization.predecessor_relation_id != self.predecessor_relation_id:
                errors["authorization"] = "工程准备授权必须属于被撤销的PDE前置关系"
        if self.engineering_instance_id:
            instance = self.engineering_instance
            if instance.engineering_preparation_authorization_id != self.authorization_id:
                errors["engineering_instance"] = "OEI必须属于被撤销的工程准备授权"
            if self.crm_order_relation_id and (
                instance.sales_order_item.sales_order_id
                != self.crm_order_relation.sales_order_id
            ):
                errors["engineering_instance"] = "OEI订单必须与被撤销的0032关系一致"
        company_ids = {
            value for value in (
                getattr(self.crm_order_relation, "company_id", None)
                if self.crm_order_relation_id else None,
                getattr(self.pde_review, "company_id", None)
                if self.pde_review_id else None,
                getattr(self.predecessor_relation, "company_id", None)
                if self.predecessor_relation_id else None,
                getattr(self.authorization, "company_id", None)
                if self.authorization_id else None,
                getattr(self.engineering_instance, "company_id", None)
                if self.engineering_instance_id else None,
            ) if value is not None
        }
        if self.company_id and company_ids != {self.company_id}:
            errors["company"] = "撤销事实与完整准入链必须属于同一公司"
        if self.audit_record_id:
            if self.audit_record.organization_id != self.company_id:
                errors["audit_record"] = "组织审计记录必须属于撤销事实公司"
            if self.audit_record.actor_id != self.created_by_id:
                errors["audit_record"] = "组织审计记录操作人必须与纠正执行人一致"
        if not str(self.reason or "").strip():
            errors["reason"] = "撤销原因不能为空"
        if len(self.audit_hash or "") != 64:
            errors["audit_hash"] = "撤销事实哈希必须是64位SHA256"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("PDE准入链撤销事实为不可变记录，不允许修改。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PDE准入链撤销事实为不可变记录，不允许删除。")


class LegacyInFlightOrderAdoption(models.Model):
    """Immutable adoption of one pre-admission-model in-flight order.

    This is deliberately independent from CRM Review, 0032, 0033 and PDE
    engineering-preparation authorization.  It records a closed historical
    scope; it is not a mechanism for manufacturing those missing objects.
    """

    REASON_CODES = (
        ("PRE_ADMISSION_MODEL_IN_FLIGHT", "新准入模型上线前历史在制订单"),
    )

    adoption_no = models.CharField("承接编号", max_length=120)
    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="legacy_inflight_order_adoptions", verbose_name="所属公司",
    )
    sales_order = models.OneToOneField(
        "sales.SalesOrder", on_delete=models.PROTECT,
        related_name="legacy_inflight_adoption", verbose_name="历史在制销售订单",
    )
    source_record = models.ForeignKey(
        EngineeringSourceRecord, on_delete=models.PROTECT,
        related_name="legacy_inflight_order_adoptions", verbose_name="正式工程来源",
    )
    source_identity = models.ForeignKey(
        "masterdata.ExternalIdentity", on_delete=models.PROTECT,
        related_name="legacy_inflight_order_adoptions", verbose_name="正式来源身份",
    )
    engineering_baseline = models.ForeignKey(
        OrderEngineeringBaseline, on_delete=models.PROTECT,
        related_name="legacy_inflight_order_adoptions", verbose_name="确认工程基线",
    )
    reason_code = models.CharField(
        "承接原因编码", max_length=48, choices=REASON_CODES,
        default="PRE_ADMISSION_MODEL_IN_FLIGHT",
    )
    business_reason = models.CharField("业务授权依据", max_length=500)
    evidence_snapshot = models.JSONField("不可变承接证据快照", default=dict)
    evidence_hash = models.CharField("承接证据哈希", max_length=64, unique=True)
    cutoff_evidence = models.JSONField("Admission模型上线时间证据", default=dict)
    idempotency_key = models.CharField("幂等键", max_length=160)
    created_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="created_legacy_inflight_order_adoptions", verbose_name="执行人",
    )
    audit_record = models.OneToOneField(
        "system.OrganizationOperatingAuditRecord", on_delete=models.PROTECT,
        related_name="legacy_inflight_order_adoption", verbose_name="组织审计记录",
    )
    action_request = models.OneToOneField(
        "masterdata.MasterDataWriteRequest", on_delete=models.PROTECT,
        related_name="legacy_inflight_order_adoption", verbose_name="幂等动作请求",
    )
    created_at = models.DateTimeField("承接时间", auto_now_add=True)

    class Meta:
        db_table = "pde_legacy_inflight_order_adoption"
        ordering = ("company_id", "sales_order_id", "pk")
        indexes = [
            models.Index(
                fields=("company", "created_at"),
                name="pde_lioa_company_created_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("company", "adoption_no"),
                name="pde_lioa_company_no_unique",
            ),
            models.UniqueConstraint(
                fields=("company", "idempotency_key"),
                name="pde_lioa_company_idem_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(reason_code="PRE_ADMISSION_MODEL_IN_FLIGHT"),
                name="pde_lioa_reason_pre_model",
            ),
            models.CheckConstraint(
                condition=~models.Q(business_reason=""),
                name="pde_lioa_business_reason_required",
            ),
        ]

    def clean(self):
        errors = {}
        if self.sales_order_id and self.sales_order.company_id != self.company_id:
            errors["sales_order"] = "历史在制订单必须属于承接事实公司"
        if self.source_record_id and self.source_record.company_id != self.company_id:
            errors["source_record"] = "工程来源必须属于承接事实公司"
        if self.source_identity_id:
            if self.source_identity.organization_id != self.company_id:
                errors["source_identity"] = "来源身份必须属于承接事实公司"
            if self.sales_order_id and self.source_identity.target_entity_id != str(self.sales_order_id):
                errors["source_identity"] = "来源身份必须精确指向被承接销售订单"
        if self.engineering_baseline_id:
            if self.engineering_baseline.company_id != self.company_id:
                errors["engineering_baseline"] = "工程基线必须属于承接事实公司"
            if self.sales_order_id and self.engineering_baseline.sales_order_id != self.sales_order_id:
                errors["engineering_baseline"] = "工程基线必须属于被承接销售订单"
        if self.audit_record_id:
            if self.audit_record.organization_id != self.company_id:
                errors["audit_record"] = "组织审计记录必须属于承接事实公司"
            if self.audit_record.actor_id != self.created_by_id:
                errors["audit_record"] = "组织审计操作人必须与承接执行人一致"
        if self.action_request_id:
            if self.action_request.organization_id != self.company_id:
                errors["action_request"] = "幂等动作请求必须属于承接事实公司"
            if self.action_request.source_identity_id != self.source_identity_id:
                errors["action_request"] = "幂等动作请求必须引用同一正式来源身份"
        if len(self.evidence_hash or "") != 64:
            errors["evidence_hash"] = "承接证据哈希必须是64位SHA256"
        if not isinstance(self.evidence_snapshot, dict) or not self.evidence_snapshot:
            errors["evidence_snapshot"] = "承接证据快照不能为空"
        if not isinstance(self.cutoff_evidence, dict) or not self.cutoff_evidence:
            errors["cutoff_evidence"] = "Admission模型上线时间证据不能为空"
        if not str(self.business_reason or "").strip():
            errors["business_reason"] = "业务授权依据不能为空"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("历史在制订单承接事实为不可变记录，不允许修改。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("历史在制订单承接事实为不可变记录，不允许删除。")


class LegacyInFlightOrderAdoptionRevocation(models.Model):
    """Append-only revocation of one immutable legacy adoption."""

    REASON_CODES = (
        ("BUSINESS_IDENTITY_CONFLICT", "业务身份冲突"),
        ("EVIDENCE_INVALIDATED", "承接证据失效"),
    )

    revocation_no = models.CharField("撤销编号", max_length=120)
    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT,
        related_name="legacy_inflight_order_adoption_revocations", verbose_name="所属公司",
    )
    adoption = models.OneToOneField(
        LegacyInFlightOrderAdoption, on_delete=models.PROTECT,
        related_name="revocation", verbose_name="被撤销承接事实",
    )
    reason_code = models.CharField("撤销原因编码", max_length=40, choices=REASON_CODES)
    reason = models.CharField("撤销原因", max_length=500)
    evidence_snapshot = models.JSONField("撤销证据快照", default=dict)
    evidence_hash = models.CharField("撤销证据哈希", max_length=64, unique=True)
    idempotency_key = models.CharField("幂等键", max_length=160)
    created_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT,
        related_name="created_legacy_inflight_order_adoption_revocations", verbose_name="执行人",
    )
    audit_record = models.OneToOneField(
        "system.OrganizationOperatingAuditRecord", on_delete=models.PROTECT,
        related_name="legacy_inflight_order_adoption_revocation", verbose_name="组织审计记录",
    )
    action_request = models.OneToOneField(
        "masterdata.MasterDataWriteRequest", on_delete=models.PROTECT,
        related_name="legacy_inflight_order_adoption_revocation", verbose_name="幂等动作请求",
    )
    effective_at = models.DateTimeField("撤销生效时间")
    created_at = models.DateTimeField("记录时间", auto_now_add=True)

    class Meta:
        db_table = "pde_legacy_inflight_order_adoption_revocation"
        ordering = ("company_id", "effective_at", "pk")
        indexes = [
            models.Index(
                fields=("company", "effective_at"),
                name="pde_lioar_company_eff_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("company", "revocation_no"),
                name="pde_lioar_company_no_unique",
            ),
            models.UniqueConstraint(
                fields=("company", "idempotency_key"),
                name="pde_lioar_company_idem_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    reason_code__in=("BUSINESS_IDENTITY_CONFLICT", "EVIDENCE_INVALIDATED"),
                ),
                name="pde_lioar_reason_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""),
                name="pde_lioar_reason_required",
            ),
        ]

    def clean(self):
        errors = {}
        if self.adoption_id and self.adoption.company_id != self.company_id:
            errors["adoption"] = "撤销事实必须与承接事实属于同一公司"
        if self.audit_record_id:
            if self.audit_record.organization_id != self.company_id:
                errors["audit_record"] = "组织审计记录必须属于撤销事实公司"
            if self.audit_record.actor_id != self.created_by_id:
                errors["audit_record"] = "组织审计操作人必须与撤销执行人一致"
        if self.action_request_id:
            if self.action_request.organization_id != self.company_id:
                errors["action_request"] = "幂等动作请求必须属于撤销事实公司"
            if self.adoption_id and self.action_request.source_identity_id != self.adoption.source_identity_id:
                errors["action_request"] = "撤销请求必须引用原承接的正式来源身份"
        if len(self.evidence_hash or "") != 64:
            errors["evidence_hash"] = "撤销证据哈希必须是64位SHA256"
        if not isinstance(self.evidence_snapshot, dict) or not self.evidence_snapshot:
            errors["evidence_snapshot"] = "撤销证据快照不能为空"
        if not str(self.reason or "").strip():
            errors["reason"] = "撤销原因不能为空"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("历史在制订单承接撤销事实为不可变记录，不允许修改。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("历史在制订单承接撤销事实为不可变记录，不允许删除。")


class TestSafeCalculationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.filter(scope='test_business').exists():
            raise ValidationError('测试核算只能通过受控保存与状态服务变更。')
        return super().update(**kwargs)
    def delete(self):
        if self.filter(scope='test_business').exists():
            raise ValidationError('测试核算历史不可删除。')
        return super().delete()
    def bulk_create(self, objs, **kwargs):
        if any(x.scope=='test_business' for x in objs): raise ValidationError('测试核算不可批量绕过保存服务。')
        return super().bulk_create(objs,**kwargs)

class ProductionCalculationManager(models.Manager.from_queryset(TestSafeCalculationQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(usage_purpose="PRODUCTION_USE")

class EngineeringCalculationRecord(models.Model):
    usage_purpose = models.CharField(max_length=24, default="UNCLASSIFIED", choices=(("UNCLASSIFIED","未分类"),("PRODUCTION_USE","正式生产用途"),("TEST_BUSINESS","测试业务")))
    # Existing production consumers cannot acquire the new test records.
    objects=ProductionCalculationManager()
    all_records=models.Manager.from_queryset(TestSafeCalculationQuerySet)()
    approval_scope = models.CharField(max_length=32, blank=True, default='')
    baseline = models.ForeignKey('OrderEngineeringBaseline', on_delete=models.PROTECT, null=True, blank=True)
    design_revision = models.ForeignKey('ProductDesignRevision', on_delete=models.PROTECT, null=True, blank=True)
    design_approval = models.ForeignKey('DesignRevisionApproval', on_delete=models.PROTECT, null=True, blank=True)
    SCOPE_CHOICES = (
        ("validation", "规则技术验证"),
        ("test_business", "测试业务核算"),
        ("order_engineering", "正式订单工程核算"),
        ("fact_extension", "固定工程事实增量承接"),
        ("operation_requirement", "工程工序需求承接"),
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
    origin_calculation = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="fact_extensions", verbose_name="固定原订单工程核算",
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
            models.CheckConstraint(
                condition=(
                    models.Q(scope="fact_extension", origin_calculation__isnull=False, supersedes__isnull=True)
                    | (~models.Q(scope="fact_extension") & models.Q(origin_calculation__isnull=True))
                ),
                name="pde_eng_calc_extension_origin_valid",
            ),
            models.CheckConstraint(condition=(~models.Q(scope='test_business') | models.Q(
                approval_scope='TEST_BUSINESS', company__isnull=False, sales_order_item__isnull=False,
                engineering_instance__isnull=False,source_record__isnull=False,baseline__isnull=False,
                design_revision__isnull=False,design_approval__isnull=False,supersedes__isnull=True,
                origin_calculation__isnull=True)),name='pde_test_calc_exact_required'),
        ]

    def clean(self):
        errors = {}
        if self.scope=='test_business':
            from .test_calculation_persistence import validate_record_binding
            validate_record_binding(self)
        if self.scope == "fact_extension":
            if not self.origin_calculation_id:
                errors["origin_calculation"] = "工程事实增量必须固定引用原已完成订单工程核算"
            else:
                origin = self.origin_calculation
                context_fields = ("company_id", "source_record_id", "sales_order_item_id", "engineering_instance_id")
                if (origin.pk == self.pk or origin.scope not in {"order_engineering", "test_business"} or origin.status != "completed"
                        or any(getattr(origin, field) is None or getattr(origin, field) != getattr(self, field)
                               for field in context_fields)):
                    errors["origin_calculation"] = "增量必须继承固定原核算的公司、来源、订单行和工程实例正式FK"
            if self.supersedes_id:
                errors["supersedes"] = "工程事实增量不得替代或改写原核算"
        elif self.origin_calculation_id:
            errors["origin_calculation"] = "只有独立工程事实增量运行允许引用固定原核算"
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
        from .workload_usage_contract import calculation_purpose
        derived = calculation_purpose(self)
        if self.usage_purpose not in ('UNCLASSIFIED', derived):
            raise ValidationError('用途必须由可信来源派生。')
        self.usage_purpose = derived
        if self.pk:
            original = type(self).all_records.filter(pk=self.pk).first()
            if original and original.scope=='test_business' and (self.scope!=original.scope or self.status!=original.status) and not getattr(self,'_business_state_transition_authorized',False):
                raise ValidationError('测试核算状态须经统一状态服务。')
            if original and original.status in {"completed", "failed", "superseded", "obsolete"}:
                immutable_fields = (
                    "usage_purpose", "approval_scope", "baseline_id", "design_revision_id", "design_approval_id",
                    "company_id", "scope", "source_record_id", "sales_order_item_id",
                    "engineering_instance_id", "calculation_no", "rule_set_version",
                    "revision", "supersedes_id", "origin_calculation_id", "idempotency_key", "input_hash",
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
        if self.scope=='test_business':
            if not self.pk and not getattr(self,'_business_state_initialization_authorized',False): raise ValidationError('测试核算须受控初始化。')
            self.clean()
        super().save(*args, **kwargs)

    def delete(self,*args,**kwargs):
        if self.scope=='test_business': raise ValidationError('测试核算历史不可删除。')
        return super().delete(*args,**kwargs)


class EngineeringCalculationContinuationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('主核算版本接续只能通过正式原子服务变更。')

    def delete(self):
        raise ValidationError('正式主核算版本接续历史不可删除。')

    def bulk_create(self, objs, **kwargs):
        raise ValidationError('正式主核算版本接续不得批量绕过原生服务。')


class EngineeringCalculationContinuation(models.Model):
    """Append-only version authority beside the immutable legacy adoption."""
    objects = EngineeringCalculationContinuationQuerySet.as_manager()
    company = models.ForeignKey('system.Company', on_delete=models.PROTECT)
    adoption = models.ForeignKey(LegacyInFlightOrderAdoption, on_delete=models.PROTECT,
        related_name='calculation_continuations')
    sales_order_item = models.ForeignKey('sales.SalesOrderItem', on_delete=models.PROTECT)
    engineering_instance = models.ForeignKey(OrderEngineeringInstance, on_delete=models.PROTECT)
    previous_calculation = models.OneToOneField(EngineeringCalculationRecord, on_delete=models.PROTECT,
        related_name='formal_version_successor')
    new_calculation = models.OneToOneField(EngineeringCalculationRecord, on_delete=models.PROTECT,
        related_name='formal_version_admission', null=True, blank=True)
    baseline = models.ForeignKey(OrderEngineeringBaseline, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default='draft', choices=(('draft','办理中'),('committed','已正式接续')))
    version = models.PositiveIntegerField(default=0)
    context_hash = models.CharField(max_length=64)
    basis_hash = models.CharField(max_length=64)
    source_snapshot = models.JSONField(default=dict)
    result_snapshot = models.JSONField(default=dict, blank=True)
    write_request = models.OneToOneField('masterdata.MasterDataWriteRequest', on_delete=models.PROTECT)
    audit_record = models.ForeignKey('system.OrganizationOperatingAuditRecord', on_delete=models.PROTECT,
        null=True, blank=True)
    created_by = models.ForeignKey('system.User', on_delete=models.PROTECT)
    reason = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pde_engineering_calculation_continuation'
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=('draft','committed')), name='pde_calc_cont_status_valid'),
            models.CheckConstraint(condition=(models.Q(status='draft') | models.Q(
                audit_record__isnull=False,new_calculation__isnull=False)), name='pde_calc_cont_commit_proven'),
        ]

    def clean(self):
        from .engineering_calculation_continuation_service import validate_continuation_model
        validate_continuation_model(self)

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.get(pk=self.pk)
            allowed = {'status','version','updated_at'}
            if previous.status == 'draft' and getattr(self, '_continuation_write_authorized', False):
                allowed |= {'new_calculation_id','result_snapshot','audit_record_id'}
            if any(getattr(previous,f.attname) != getattr(self,f.attname)
                   for f in self._meta.concrete_fields if f.attname not in allowed):
                raise ValidationError('主核算接续身份及冻结证据不可改写。')
            if (previous.status != self.status or previous.version != self.version) and not getattr(
                self,'_business_state_transition_authorized',False):
                raise ValidationError('主核算接续状态必须经过共享状态服务。')
        elif not getattr(self,'_business_state_initialization_authorized',False):
            raise ValidationError('主核算接续必须通过正式初始化服务。')
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('正式主核算版本接续历史不可删除。')


class TestSafeDetailQuerySet(models.QuerySet):
    def update(self,**kwargs):
        if self.filter(calculation__scope='test_business').exists(): raise ValidationError('测试核算明细不可覆盖。')
        return super().update(**kwargs)
    def delete(self):
        if self.filter(calculation__scope='test_business').exists(): raise ValidationError('测试核算明细不可删除。')
        return super().delete()
    def bulk_create(self,objs,**kwargs):
        if any(x.calculation.scope=='test_business' for x in objs): raise ValidationError('测试明细不得批量绕过保存。')
        return super().bulk_create(objs,**kwargs)

class ProductionDetailManager(models.Manager.from_queryset(TestSafeDetailQuerySet)):
    def get_queryset(self):return super().get_queryset().exclude(calculation__scope='test_business')

class EngineeringCalculationDetail(models.Model):
    objects=ProductionDetailManager()
    all_records=models.Manager.from_queryset(TestSafeDetailQuerySet)()
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


    def save(self,*args,**kwargs):
        if self.calculation.scope=='test_business' and self.calculation.status in ('completed','failed','obsolete','superseded'):
            raise ValidationError('终态测试核算明细不可覆盖或补写。')
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):
        if self.calculation.scope=='test_business':raise ValidationError('测试核算明细不可删除。')
        return super().delete(*args,**kwargs)

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


class ImmutableEngineeringFactInputQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("工程事实输入来源为不可变证据，不允许编辑。")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("工程事实输入来源为不可变证据，不允许批量编辑。")

    def delete(self):
        raise ValidationError("工程事实输入来源为不可变证据，不允许删除。")

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("工程事实输入来源必须逐项校验正式FK和证据，不允许批量绕过。")


class EngineeringFactInput(models.Model):
    source_kind = models.CharField(max_length=24, default="DERIVED_FACT")
    source_detail = models.ForeignKey("EngineeringCalculationDetail", on_delete=models.PROTECT, null=True, blank=True)
    source_baseline_item = models.ForeignKey("OrderEngineeringBaselineItem", on_delete=models.PROTECT, null=True, blank=True)
    component_key = models.CharField(max_length=80, default="", blank=True)
    """Formal input provenance for an incremental fact, without duplicating sources."""

    objects = ImmutableEngineeringFactInputQuerySet.as_manager()

    fact = models.ForeignKey(
        EngineeringDerivedFact, on_delete=models.PROTECT,
        related_name="inputs", verbose_name="目标工程事实",
    )
    source_fact = models.ForeignKey(
        EngineeringDerivedFact, on_delete=models.PROTECT,
        related_name="input_consumptions", verbose_name="固定来源工程事实", null=True, blank=True,
    )
    input_name = models.CharField("规范输入名", max_length=160)
    sequence = models.PositiveIntegerField("来源顺序", default=1)
    source_hash = models.CharField("来源输入证据哈希", max_length=64)
    input_snapshot = models.JSONField("固定输入快照", default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_engineering_fact_input"
        ordering = ("fact_id", "input_name", "sequence")
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=("fact", "input_name", "sequence"), name="pde_eng_fact_input_identity_unique",
            ),
            models.CheckConstraint(condition=models.Q(sequence__gt=0), name="pde_eng_fact_input_sequence_positive"),
            models.CheckConstraint(condition=~models.Q(fact=models.F("source_fact")), name="pde_eng_fact_input_no_self"),
        ]

    def clean(self):
        from hashlib import sha256
        import json
        from .engineering_rule_foundation import canonical_json

        errors = {}
        if not self.input_name.strip() or self.input_name != self.input_name.strip():
            errors["input_name"] = "工程事实输入必须保存精确且非空的规范名"
        if not isinstance(self.input_snapshot, dict) or not self.input_snapshot:
            errors["input_snapshot"] = "工程事实输入必须保存完整来源证据快照"
        else:
            try:
                json.dumps(self.input_snapshot, allow_nan=False)
                expected_hash = sha256(canonical_json(self.input_snapshot).encode("utf-8")).hexdigest()
                if self.source_hash != expected_hash:
                    errors["source_hash"] = "来源哈希必须等于固定输入快照的SHA256"
            except (TypeError, ValueError):
                errors["input_snapshot"] = "来源快照必须是有限且可持久保存的JSON证据"
        if self.fact_id and self.source_fact_id:
            target, source = self.fact, self.source_fact
            target_calc, source_calc = target.calculation, source.calculation
            context_fields = ("company_id", "source_record_id", "sales_order_item_id", "engineering_instance_id")
            if target_calc.scope != "fact_extension" or not target_calc.origin_calculation_id:
                errors["fact"] = "通用输入关联只能属于固定原核算的独立工程事实增量"
            if (target.pk == source.pk or any(getattr(target_calc, field) is None
                    or getattr(target_calc, field) != getattr(source_calc, field) for field in context_fields)):
                errors["source_fact"] = "来源与目标必须继承相同公司、来源记录、订单行及工程实例，且不得自引用"
            original_source = (source_calc.pk == target_calc.origin_calculation_id
                               and source_calc.scope == "order_engineering" and source_calc.status == "completed")
            local_source = (source_calc.pk == target_calc.pk and source.sequence < target.sequence)
            if not original_source and not local_source:
                errors["source_fact"] = "只能引用固定原核算事实或同一增量运行中更早的正式输出"
            if (source.status != "active" or source.source_type != "ENGINEERING_DERIVED"
                    or not source.source_detail_id or source.source_detail.status != "succeeded"
                    or source.source_detail.calculation_id != source_calc.pk):
                errors["source_fact"] = "输入必须引用有效工程事实及同核算真实成功明细"
        if self.source_kind == 'FROZEN_TEST_DETAIL':
            from .frozen_workload_persistence import validate_input
            validate_input(self)
        elif self.source_kind != 'DERIVED_FACT' or not self.source_fact_id or self.source_detail_id or self.source_baseline_item_id or self.component_key:
            errors['source_kind'] = '原生来源分支不完整或混用'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("工程事实输入来源为不可变证据，不允许编辑。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("工程事实输入来源为不可变证据，不允许删除。")


class EngineeringMaterialRequirement(models.Model):
    """Traceable material demand produced by one formal calculation output."""

    QUANTITY_BASIS_CHOICES = (
        ("PER_SALES_ITEM_UNIT", "每订单行单位"),
        ("ORDER_TOTAL", "订单行总量"),
    )

    calculation = models.ForeignKey(
        EngineeringCalculationRecord, on_delete=models.PROTECT,
        related_name="material_requirements", verbose_name="计算记录",
    )
    source_detail = models.OneToOneField(
        EngineeringCalculationDetail, on_delete=models.PROTECT,
        related_name="material_requirement", verbose_name="来源计算明细",
    )
    sequence = models.PositiveIntegerField("序号")
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT,
        related_name="engineering_material_requirements", verbose_name="正式物料",
    )
    quantity_basis = models.CharField(
        "数量口径", max_length=32, choices=QUANTITY_BASIS_CHOICES,
    )
    calculated_quantity = models.DecimalField("规则计算量", max_digits=18, decimal_places=6)
    order_quantity = models.DecimalField("订单行数量", max_digits=18, decimal_places=6)
    net_quantity = models.DecimalField("净需求量", max_digits=18, decimal_places=6)
    gross_quantity = models.DecimalField(
        "含损耗需求量", max_digits=18, decimal_places=6, null=True, blank=True,
    )
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT,
        related_name="engineering_material_requirements", verbose_name="正式单位",
    )
    item_role = models.CharField("结构角色", max_length=24, default="material")
    requirement_type = models.CharField("需求类型", max_length=32, default="manufacturing")
    supply_type = models.CharField("供给方式", max_length=24, default="BUY")
    order_specification = models.JSONField("按单规格", default=dict, blank=True)
    scrap_rate_status = models.CharField(
        "损耗率维护状态", max_length=24, default="not_maintained",
    )
    scrap_rate = models.DecimalField(
        "损耗率", max_digits=8, decimal_places=6, null=True, blank=True,
    )
    source_path = models.CharField("来源路径", max_length=500)
    trace = models.JSONField("需求追踪", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_engineering_material_requirement"
        ordering = ("calculation_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("calculation", "sequence"),
                name="pde_eng_mat_req_calc_sequence_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(calculated_quantity__gt=0),
                name="pde_eng_mat_req_calculated_qty_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(order_quantity__gt=0),
                name="pde_eng_mat_req_order_qty_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(net_quantity__gt=0),
                name="pde_eng_mat_req_net_qty_positive",
            ),
        ]

    def clean(self):
        errors = {}
        if self.source_detail.calculation_id != self.calculation_id:
            errors["source_detail"] = "物料需求与来源明细必须属于同一计算记录"
        if self.calculation.company_id != self.material.company_id:
            errors["material"] = "物料需求与正式物料必须属于同一公司"
        if self.material.company_id != self.uom.company_id:
            errors["uom"] = "物料需求单位必须与物料属于同一公司"
        # Saved instances are also checked by frozen-source read paths.
        # Current supply qualification belongs to new facts and release gates.
        if self._state.adding:
            from .material_supply_authority import material_supply_fact
            supply = material_supply_fact(self.material, self.supply_type)
            if not supply["allowed"]:
                errors["supply_type"] = supply["message"]
        if self.material.base_uom_id and self.material.base_uom_id != self.uom_id:
            errors["uom"] = "物料需求单位必须等于物料正式基本单位；不得隐式换算"
        if self.scrap_rate_status == "maintained":
            if self.scrap_rate is None or self.scrap_rate < 0 or self.scrap_rate >= 1:
                errors["scrap_rate"] = "已维护损耗率必须在0（含）到1（不含）之间"
            elif self.gross_quantity is None:
                errors["gross_quantity"] = "已维护损耗率时必须保存含损耗需求量"
        elif self.scrap_rate is not None or self.gross_quantity is not None:
            errors["scrap_rate"] = "损耗未知时必须保留为空，不得按0处理"
        if errors:
            raise ValidationError(errors)


class ManufacturingModeQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "status" in kwargs:
            raise ValidationError("制造模式状态禁止批量写入；必须使用统一状态转换服务。")
        if self.filter(status__in=("released", "obsolete")).exists():
            raise ValidationError("已发布制造模式不可批量修改；请建立新版本。")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(status__in=("released", "obsolete")).exists():
            raise ValidationError("已发布制造模式不可删除。")
        return super().delete()

    def bulk_update(self, objs, fields, batch_size=None):
        if "status" in fields:
            raise ValidationError("制造模式状态禁止批量写入。")
        if self.model.objects.filter(pk__in=[obj.pk for obj in objs], status__in=("released", "obsolete")).exists():
            raise ValidationError("已发布制造模式不可批量修改。")
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("制造模式禁止批量直接创建；必须使用正式配置服务。")


class ManufacturingMode(models.Model):
    """Versioned quantity/UOM mode, without product or industry branches."""

    company = models.ForeignKey("system.Company", on_delete=models.PROTECT,
                                related_name="manufacturing_modes")
    code = models.CharField("制造模式编码", max_length=80)
    name = models.CharField("制造模式名称", max_length=160)
    version = models.CharField("制造模式版本", max_length=40)
    uom = models.ForeignKey("masterdata.UnitOfMeasure", on_delete=models.PROTECT,
                           related_name="manufacturing_modes")
    status = models.CharField("状态", max_length=24,
                              choices=EngineeringRuleDefinition.STATUS_CHOICES, default="draft")
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = ManufacturingModeQuerySet.as_manager()

    class Meta:
        db_table = "pde_manufacturing_mode"
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=("company", "code", "version"),
                       name="pde_mfg_mode_company_code_version_unique")]

    def clean(self):
        if self.uom_id and (self.uom.company_id != self.company_id or not self.uom.is_active):
            raise ValidationError({"uom": "制造模式必须引用同公司有效正式单位。"})
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "失效日期不得早于生效日期。"})

    def save(self, *args, **kwargs):
        original = None
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.status in ("released", "obsolete"):
                fields = ("company_id", "code", "name", "version", "uom_id", "effective_from", "effective_to")
                if any(getattr(original, field) != getattr(self, field) for field in fields):
                    raise ValidationError("已发布制造模式核心不可修改；请建立新版本。")
            if original and original.status != self.status and not getattr(self, "_business_state_transition_authorized", False):
                raise ValidationError("制造模式状态必须由统一状态转换服务办理。")
        if original is None and not getattr(self, "_business_state_initialization_authorized", False):
            raise ValidationError("制造模式必须由统一状态初始化服务创建。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in ("released", "obsolete"):
            raise ValidationError("已发布制造模式不可删除。")
        return super().delete(*args, **kwargs)


class EngineeringOperationRequirementQuerySet(models.QuerySet):
    def _assert_legacy_only(self):
        if self.exclude(quantity_basis="UNKNOWN").exists() or self.filter(
            generation_key__isnull=False,
        ).exclude(generation_key="").exists():
            raise ValidationError("已生成的正式工序需求不可修改或删除；请创建新的承接运行。")

    def update(self, **kwargs):
        self._assert_legacy_only()
        return super().update(**kwargs)

    def delete(self):
        self._assert_legacy_only()
        return super().delete()

    def bulk_create(self, objs, **kwargs):
        for obj in objs:
            if obj.quantity_basis != "UNKNOWN" or obj.generation_key:
                obj.full_clean()
        return super().bulk_create(objs, **kwargs)


class EngineeringOperationRequirement(models.Model):
    usage_purpose = models.CharField(max_length=24, default="UNCLASSIFIED")
    execution_arrangement = models.ForeignKey("OrderRoutingExecutionArrangement", on_delete=models.PROTECT, null=True, blank=True)
    arrangement_revision = models.PositiveIntegerField(null=True, blank=True)
    arrangement_edit_version = models.PositiveIntegerField(null=True, blank=True)
    arrangement_snapshot_hash = models.CharField(max_length=64, default="", blank=True)
    routing_step = models.ForeignKey("RoutingStep", on_delete=models.PROTECT, null=True, blank=True)
    baseline_item = models.ForeignKey("OrderEngineeringBaselineItem", on_delete=models.PROTECT, null=True, blank=True)
    component_key = models.CharField(max_length=80, default="", blank=True)
    """Traceable operation workload; it does not create routing or planning facts."""

    class QuantityBasis(models.TextChoices):
        UNKNOWN = "UNKNOWN", "数量口径未确认"
        PER_BASIS_QUANTITY = "PER_BASIS_QUANTITY", "每基准数量作业量"
        SOURCE_SCOPE_TOTAL = "SOURCE_SCOPE_TOTAL", "固定来源范围总作业量"

    objects = EngineeringOperationRequirementQuerySet.as_manager()

    calculation = models.ForeignKey(
        EngineeringCalculationRecord, on_delete=models.PROTECT,
        related_name="operation_requirements", verbose_name="计算记录",
    )
    source_detail = models.OneToOneField(
        EngineeringCalculationDetail, on_delete=models.PROTECT,
        related_name="operation_requirement", verbose_name="来源计算明细",
    )
    sequence = models.PositiveIntegerField("序号")
    operation = models.ForeignKey(
        "system.Process", on_delete=models.PROTECT,
        related_name="engineering_operation_requirements", verbose_name="正式工序",
    )
    workload_quantity = models.DecimalField("作业量", max_digits=18, decimal_places=6)
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT,
        related_name="engineering_operation_requirements", verbose_name="正式单位",
    )
    source_path = models.CharField("来源路径", max_length=500)
    trace = models.JSONField("需求追踪", default=dict, blank=True)
    quantity_basis = models.CharField(
        "数量口径", max_length=32, choices=QuantityBasis.choices, default=QuantityBasis.UNKNOWN,
    )
    basis_quantity = models.DecimalField("基准数量", max_digits=18, decimal_places=6, null=True, blank=True)
    basis_uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_operation_basis_requirements", verbose_name="基准数量单位",
    )
    source_calculation = models.ForeignKey(
        EngineeringCalculationRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="derived_operation_requirements", verbose_name="固定来源工程核算",
    )
    source_fact = models.ForeignKey(
        EngineeringDerivedFact, on_delete=models.PROTECT, null=True, blank=True,
        related_name="operation_requirements", verbose_name="固定来源派生事实",
    )
    generation_key = models.CharField("承接生成幂等键", max_length=160, null=True, blank=True, unique=True)
    created_by = models.ForeignKey(
        "system.User", on_delete=models.PROTECT, null=True, blank=True,
        related_name="created_engineering_operation_requirements", verbose_name="承接办理人",
    )
    audit_record = models.ForeignKey(
        "system.OrganizationOperatingAuditRecord", on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_operation_requirements", verbose_name="承接审计",
    )
    source_hash = models.CharField("来源事实哈希", max_length=64, blank=True, default="")
    input_hash = models.CharField("承接输入哈希", max_length=64, blank=True, default="")
    manufacturing_mode = models.ForeignKey(
        ManufacturingMode, on_delete=models.PROTECT, null=True, blank=True,
        related_name="operation_requirements", verbose_name="固定制造模式版本",
    )
    work_center = models.ForeignKey(
        WorkCenter, on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_operation_requirements", verbose_name="固定工作中心",
    )
    standard_capacity = models.ForeignKey(
        StandardCapacity, on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_operation_requirements", verbose_name="固定标准产能",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_engineering_operation_requirement"
        ordering = ("calculation_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("calculation", "sequence"),
                name="pde_eng_op_req_calc_sequence_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(workload_quantity__gt=0),
                name="pde_eng_op_req_workload_positive",
            ),
            models.CheckConstraint(
                condition=(models.Q(basis_quantity__isnull=True, basis_uom__isnull=True)
                           | models.Q(basis_quantity__isnull=False, basis_quantity__gt=0, basis_uom__isnull=False)),
                name="pde_eor_basis_pair_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(quantity_basis="UNKNOWN")
                    | (models.Q(quantity_basis__in=("PER_BASIS_QUANTITY", "SOURCE_SCOPE_TOTAL"),
                                basis_quantity__isnull=False, basis_quantity__gt=0, basis_uom__isnull=False,
                                source_calculation__isnull=False, source_fact__isnull=False,
                                created_by__isnull=False, audit_record__isnull=False, generation_key__isnull=False)
                       & ~models.Q(generation_key="") & ~models.Q(source_hash="") & ~models.Q(input_hash=""))
                ),
                name="pde_eor_known_basis_metadata",
            ),
            models.CheckConstraint(
                condition=RawSQL(EOR_REFERENCE_CHECK_SQL, (), output_field=models.BooleanField()),
                name="pde_eor_manufacturing_refs_complete",
            ),
        ]

    def clean(self):
        errors = {}
        if self.source_detail.calculation_id != self.calculation_id:
            errors["source_detail"] = "工序需求与来源明细必须属于同一计算记录"
        if self.operation.company_id != self.calculation.company_id:
            errors["operation"] = "工序需求与正式工序必须属于同一公司"
        if self.uom.company_id != self.calculation.company_id:
            errors["uom"] = "工序需求单位必须属于计算所在公司"
        if self.operation.calculation_uom_id and self.operation.calculation_uom_id != self.uom_id:
            errors["uom"] = "工序需求单位必须等于工序正式核算单位；不得隐式换算"
        references = (self.manufacturing_mode_id, self.work_center_id, self.standard_capacity_id)
        reference_trace = self.trace if isinstance(self.trace, dict) else {}
        if EOR_REFERENCE_TYPE_KEY in reference_trace or EOR_PREPARATION_CONTEXT_KEY in reference_trace:
            errors.update(reference_record_errors(self))
        elif any(references):
            if not all(references):
                errors["manufacturing_mode"] = "制造模式、工作中心和产能必须完整引用。"
            elif (self.manufacturing_mode.company_id != self.calculation.company_id
                  or self.manufacturing_mode.uom_id != self.uom_id
                  or self.work_center.company_id != self.calculation.company_id
                  or self.standard_capacity.company_id != self.calculation.company_id
                  or self.standard_capacity.work_center_id != self.work_center_id
                  or self.standard_capacity.operation_id != self.operation_id
                  or self.standard_capacity.uom_id != self.uom_id):
                errors["standard_capacity"] = "制造引用的公司、工序、工作中心及单位必须一致。"
        if (self.basis_quantity is None) != (self.basis_uom_id is None):
            errors["basis_quantity"] = "基准数量与单位必须成对维护"
        if self.basis_quantity is not None and (not self.basis_quantity.is_finite() or self.basis_quantity <= 0):
            errors["basis_quantity"] = "基准数量必须大于0"
        known = self.quantity_basis != self.QuantityBasis.UNKNOWN
        if known:
            if self.quantity_basis not in {self.QuantityBasis.PER_BASIS_QUANTITY, self.QuantityBasis.SOURCE_SCOPE_TOTAL}:
                errors["quantity_basis"] = "数量口径不受支持"
            for field in ("basis_quantity", "basis_uom_id", "source_calculation_id", "source_fact_id",
                          "created_by_id", "audit_record_id", "generation_key"):
                if getattr(self, field) in (None, ""):
                    errors[field.removesuffix("_id")] = "已确认数量口径必须保存完整正式来源及审计"
            for field in ("source_hash", "input_hash"):
                value = getattr(self, field)
                if len(value or "") != 64 or any(c not in "0123456789abcdefABCDEF" for c in value or ""):
                    errors[field] = "事实哈希必须是64位SHA256"
            if self.basis_uom_id and (not self.basis_uom.is_active or self.basis_uom.company_id != self.calculation.company_id):
                errors["basis_uom"] = "基准单位必须启用且属于同一公司"
            if self.source_calculation_id:
                origin = self.source_calculation
                if (origin.pk == self.calculation_id or origin.scope not in {"order_engineering", "fact_extension"}
                        or origin.status != "completed"):
                    errors["source_calculation"] = "必须引用独立的已完成正式来源核算，不得覆盖旧核算"
                elif origin.scope == "fact_extension" and self.source_fact_id and self.usage_purpose != "TEST_BUSINESS":
                    from .engineering_fact_extension_service import validate_extension_fact
                    from .operation_requirement_service import OperationRequirementError
                    try:
                        validate_extension_fact(origin, self.source_fact)
                    except OperationRequirementError as exc:
                        errors["source_calculation"] = exc.message
                if self.calculation.scope != "operation_requirement" or any(
                    getattr(origin, field) != getattr(self.calculation, field)
                    for field in ("company_id", "sales_order_item_id", "engineering_instance_id", "source_record_id")
                ) or any(getattr(origin, field) is None for field in ("company_id", "sales_order_item_id", "engineering_instance_id", "source_record_id")):
                    errors["source_calculation"] = "新承接运行必须继承同公司、订单行、工程实例和EngineeringSourceRecord正式FK"
                if origin.sales_order_item_id:
                    item = origin.sales_order_item
                    if self.basis_uom_id != item.uom_id:
                        errors["basis_uom"] = "当前来源范围仅支持正式订单行，基准单位必须等于订单行单位"
                    if self.quantity_basis == self.QuantityBasis.SOURCE_SCOPE_TOTAL and self.basis_quantity != item.quantity:
                        errors["basis_quantity"] = "来源范围总量的基准数量必须等于正式订单行总数量"
            if self.source_fact_id:
                fact = self.source_fact
                if fact.calculation_id != self.source_calculation_id or fact.status != "active" or not fact.source_detail_id:
                    errors["source_fact"] = "来源派生事实必须属于固定来源核算且有真实成功明细"
                elif fact.source_detail.calculation_id != fact.calculation_id or fact.source_detail.status != "succeeded":
                    errors["source_fact"] = "来源事实与成功来源明细的核算血缘不一致"
            if self.source_detail.status != "succeeded" or self.source_detail.rule_version != self.source_detail.rule.version:
                errors["source_detail"] = "承接来源必须是新运行成功明细及其精确规则版本"
            if self.source_detail.rule.company_id != self.calculation.company_id:
                errors["source_detail"] = "承接规则必须属于同一公司"
            if self.source_detail.uom_id != self.uom_id or self.source_detail.rule_code != self.source_detail.rule.rule_code:
                errors["source_detail"] = "新成功明细的规则编码和单位必须与工序需求一致"
            output = self.source_detail.output_value
            try:
                result_quantity = Decimal(str(output.get("decimal"))) if isinstance(output, dict) else None
            except Exception:
                result_quantity = None
            if result_quantity is None or not result_quantity.is_finite() or result_quantity != self.workload_quantity:
                errors["workload_quantity"] = "工序作业量必须等于新成功明细保存的十进制结果"
            if self.created_by_id and self.created_by.company_id != self.calculation.company_id:
                errors["created_by"] = "办理人必须属于核算公司"
            if self.audit_record_id and (self.audit_record.organization_id != self.calculation.company_id
                                          or self.audit_record.actor_id != self.created_by_id):
                errors["audit_record"] = "承接审计必须属于同一公司及实际办理人"
        if self.usage_purpose == 'TEST_BUSINESS':
            from .frozen_workload_persistence import validate_requirement
            validate_requirement(self, current=False)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and (original.quantity_basis != self.QuantityBasis.UNKNOWN or original.generation_key):
                raise ValidationError("已生成工序需求为不可变事实，不允许编辑。")
        if not self.pk and self.source_calculation_id:
            derived = self.source_calculation.usage_purpose
            if self.usage_purpose not in ('UNCLASSIFIED', derived):
                raise ValidationError('需求用途必须继承真实来源。')
            self.usage_purpose = derived
        if self.quantity_basis != self.QuantityBasis.UNKNOWN or self.generation_key:
            self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.quantity_basis != self.QuantityBasis.UNKNOWN or self.generation_key:
            raise ValidationError("已生成工序需求为不可变事实，不允许删除。")
        return super().delete(*args, **kwargs)


class ImmutableOperationAllocationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("生产计划工序分配为不可变事实，不允许编辑。")

    def delete(self):
        raise ValidationError("生产计划工序分配为不可变事实，不允许删除。")

    def bulk_create(self, objs, **kwargs):
        for obj in objs:
            obj.full_clean()
        return super().bulk_create(objs, **kwargs)


class ProductionPlanOperationRequirementAllocation(models.Model):
    """Confirmed workload allocation; it never creates or modifies a schedule."""

    objects = ImmutableOperationAllocationQuerySet.as_manager()
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT, related_name="operation_requirement_allocations")
    production_plan = models.ForeignKey("planning.ProductionPlan", on_delete=models.PROTECT, related_name="operation_requirement_allocations")
    operation_requirement = models.ForeignKey(EngineeringOperationRequirement, on_delete=models.PROTECT, related_name="plan_allocations")
    routing_step = models.ForeignKey("RoutingStep", on_delete=models.PROTECT, related_name="operation_requirement_allocations")
    operation = models.ForeignKey("system.Process", on_delete=models.PROTECT, related_name="operation_requirement_allocations")
    product_type = models.ForeignKey(CapacityProductType, on_delete=models.PROTECT, related_name="operation_requirement_allocations")
    quantity_basis = models.CharField(
        "数量口径快照", max_length=32,
        choices=[choice for choice in EngineeringOperationRequirement.QuantityBasis.choices if choice[0] != "UNKNOWN"],
    )
    source_quantity = models.DecimalField("计划分配基准数量", max_digits=18, decimal_places=6)
    source_uom = models.ForeignKey("masterdata.UnitOfMeasure", on_delete=models.PROTECT, related_name="operation_allocation_source_quantities")
    allocated_quantity = models.DecimalField("已分配工序作业量", max_digits=18, decimal_places=6)
    uom = models.ForeignKey("masterdata.UnitOfMeasure", on_delete=models.PROTECT, related_name="operation_allocated_quantities")
    rule = models.ForeignKey(EngineeringRuleDefinition, on_delete=models.PROTECT, related_name="operation_requirement_allocations")
    rule_version = models.CharField("规则版本快照", max_length=40)
    created_by = models.ForeignKey("system.User", on_delete=models.PROTECT, related_name="created_operation_requirement_allocations")
    audit_record = models.ForeignKey("system.OrganizationOperatingAuditRecord", on_delete=models.PROTECT, related_name="operation_requirement_allocations")
    source_hash = models.CharField("来源事实哈希", max_length=64)
    input_hash = models.CharField("分配输入哈希", max_length=64)
    idempotency_key = models.CharField("分配幂等键", max_length=160)
    source_snapshot = models.JSONField("不可变来源快照", default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_production_plan_operation_requirement_allocation"
        default_permissions = ()
        ordering = ("production_plan_id", "routing_step_id", "pk")
        constraints = [
            models.UniqueConstraint(fields=("company", "idempotency_key"), name="pde_op_alloc_company_idem_unique"),
            models.UniqueConstraint(fields=("production_plan", "operation_requirement", "routing_step"), name="pde_op_alloc_plan_req_step_unique"),
            models.CheckConstraint(condition=models.Q(source_quantity__gt=0), name="pde_op_alloc_source_positive"),
            models.CheckConstraint(condition=models.Q(allocated_quantity__gt=0), name="pde_op_alloc_workload_positive"),
            models.CheckConstraint(condition=~models.Q(idempotency_key=""), name="pde_op_alloc_idem_required"),
            models.CheckConstraint(condition=models.Q(quantity_basis__in=("PER_BASIS_QUANTITY", "SOURCE_SCOPE_TOTAL")), name="pde_op_alloc_known_basis"),
        ]

    def clean(self):
        errors = {}
        for field in ("company", "production_plan", "operation_requirement", "routing_step", "operation",
                      "product_type", "source_uom", "uom", "rule", "created_by", "audit_record"):
            if getattr(self, field + "_id") is None:
                errors[field] = "计划分配必须引用完整正式对象"
        if errors:
            raise ValidationError(errors)
        req = self.operation_requirement
        if req.quantity_basis == req.QuantityBasis.UNKNOWN or not req.basis_uom_id or req.basis_quantity is None:
            errors["operation_requirement"] = "未确认数量口径的工序需求不得分配"
        if req.calculation.status != "completed" or req.source_detail.status != "succeeded":
            errors["operation_requirement"] = "只有已完成承接运行的成功工序需求允许计划分配"
        if self.quantity_basis != req.quantity_basis or self.quantity_basis not in {req.QuantityBasis.PER_BASIS_QUANTITY, req.QuantityBasis.SOURCE_SCOPE_TOTAL}:
            errors["quantity_basis"] = "分配数量口径快照必须与已确认工序需求一致"
        if self.operation_id != req.operation_id or self.routing_step.operation_id != self.operation_id:
            errors["operation"] = "计划步骤、工序需求与分配工序必须一致"
        demand = self.production_plan.planning_requirement.demand
        from .plan_step_context_service import resolve_step_context, bind_plan_context, PlanStepContextError
        try:
            version_context = resolve_step_context(self.production_plan, self.routing_step_id,
                historical=bool(self.pk), frozen_proof=self.source_snapshot.get('planStepVersionBinding') if self.pk else None)
            self.production_plan = bind_plan_context(self.production_plan, version_context)
            item, output = demand.sales_order_item, version_context['output']
        except PlanStepContextError as error:
            raise ValidationError({'production_plan':error.message}) from error
        if not item or item.sales_order.company_id != self.company_id or not output:
            errors["production_plan"] = "计划必须有同公司固定订单行与制造输出"
        elif (self.routing_step.routing_version_id != output.routing_version_id
              or item.pk != req.calculation.sales_order_item_id):
            errors["production_plan"] = "分配必须绑定计划固定核算、订单行及同一工艺版本步骤"
        else:
            # The service and immutable model use one formal direct/extension
            # source contract. This changes Python validation only, not schema.
            from .operation_requirement_service import _plan_source_consistency, OperationRequirementError
            try:
                from .operation_non_quantified_context import reference_type, REFERENCE_TYPE
                if reference_type(req) == REFERENCE_TYPE:
                    envelope = getattr(self, '_native_requirement_context', None)
                    native = envelope.get('context') if isinstance(envelope, dict) else None
                    if (not isinstance(native, dict) or envelope.get('operationRequirementId') != req.pk
                            or getattr(native.get('origin'), 'pk', None) != req.source_calculation_id
                            or getattr(native.get('fact'), 'pk', None) != req.source_fact_id
                            or getattr(native.get('rule'), 'pk', None) != req.source_detail.rule_id
                            or native.get('source_hash') != req.source_hash
                            or native.get('input_hash') != req.input_hash
                            or native.get('generation_key') != req.generation_key):
                        raise OperationRequirementError('NON_QUANTIFIED_CONTEXT_REQUIRED',
                            '不可定量分配必须复用本次真实办理人对同一需求、来源及Hash的正式验证')
                    _plan_source_consistency(self.company_id, self.production_plan, req,
                        routing_step=self.routing_step, native_context=native)
                else:
                    _plan_source_consistency(self.company_id, self.production_plan, req, routing_step=self.routing_step)
            except OperationRequirementError as exc:
                errors["production_plan"] = f"{exc.message}（{exc.code}）"
            route = output.routing_version.routing
            kind = self.product_type
            specification = self.rule.specification if isinstance(self.rule.specification, dict) else {}
            outputs = specification.get("outputs")
            declared_type_id = outputs[0].get("productTypeId") if (
                isinstance(outputs, list) and len(outputs) == 1 and isinstance(outputs[0], dict)
            ) else None
            from .routing_capacity_identity import routing_capacity_identity
            route_category_id, route_process_id = routing_capacity_identity(route, self.company_id)
            if (not route or kind.company_id != self.company_id or not kind.is_active
                or self.rule.status != "released" or type(declared_type_id) is not int
                or declared_type_id != self.product_type_id or kind.product_category_id != route_category_id
                or kind.manufacturing_process_type_id != route_process_id):
                errors["product_type"] = "分配产品类型必须由已发布规则正式引用，并与固定工艺路线分类和工艺类型一致"
        if item and (self.source_uom_id != item.uom_id or self.source_quantity != self.production_plan.planned_qty
                     or self.source_quantity > item.quantity):
            errors["source_quantity"] = "分配基准数量必须等于计划正式数量，单位一致且不得超过订单行总预算"
        if req.calculation.company_id != self.company_id or self.operation.company_id != self.company_id:
            errors["company"] = "核算、工序和计划分配必须属于同一公司"
        if self.source_uom_id != req.basis_uom_id or self.uom_id != req.uom_id:
            errors["uom"] = "分配基准和作业量单位必须与已确认工序需求一致，不做隐式换算"
        for unit in (self.source_uom, self.uom):
            if unit.company_id != self.company_id or not unit.is_active:
                errors["uom"] = "分配单位必须启用且属于同一公司"
        if self.rule_id != req.source_detail.rule_id or self.rule_version != req.source_detail.rule_version or self.rule_version != self.rule.version:
            errors["rule_version"] = "分配规则及版本必须与新承接成功明细一致"
        if self.created_by.company_id != self.company_id or self.audit_record.organization_id != self.company_id or self.audit_record.actor_id != self.created_by_id:
            errors["audit_record"] = "分配审计必须属于同一公司与实际办理人"
        if (self.source_quantity is None or not self.source_quantity.is_finite() or self.source_quantity <= 0
            or self.allocated_quantity is None or not self.allocated_quantity.is_finite() or self.allocated_quantity <= 0):
            errors["allocated_quantity"] = "分配基准数量和工序作业量必须大于0"
        elif req.basis_quantity is not None and req.basis_quantity > 0:
            if req.quantity_basis == req.QuantityBasis.PER_BASIS_QUANTITY:
                from fractions import Fraction
                exact = Fraction(req.workload_quantity) * Fraction(self.source_quantity) / Fraction(req.basis_quantity)
                scaled, remainder = divmod(exact.numerator * 1_000_000, exact.denominator)
                if remainder:
                    errors["allocated_quantity"] = "分配结果不能精确表示为六位小数，缺少正式舍入规则"
                elif self.allocated_quantity != Decimal(scaled).scaleb(-6):
                    errors["allocated_quantity"] = "分配作业量与每基准数量的正式计算不一致"
            elif req.quantity_basis == req.QuantityBasis.SOURCE_SCOPE_TOTAL:
                if self.source_quantity != req.basis_quantity or self.allocated_quantity != req.workload_quantity:
                    errors["allocated_quantity"] = "来源范围总量只能完整承接，部分分摊须有另外获批的正式规则"
        if not isinstance(self.source_snapshot, dict) or not self.source_snapshot:
            errors["source_snapshot"] = "分配必须保存不可变来源快照"
        for field in ("source_hash", "input_hash"):
            value = getattr(self, field)
            if len(value or "") != 64 or any(c not in "0123456789abcdefABCDEF" for c in value or ""):
                errors[field] = "事实哈希必须是64位SHA256"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("生产计划工序分配为不可变事实，不允许编辑。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("生产计划工序分配为不可变事实，不允许删除。")


class BOMVersion(models.Model):
    objects = models.Manager.from_queryset(BomPurposeQuerySet)()
    usage_purpose = models.CharField("用途", max_length=24, default="UNCLASSIFIED", choices=(("UNCLASSIFIED","历史用途待核定"),("PRODUCTION_USE","生产业务"),("TEST_BUSINESS","测试业务")))
    origin_version = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="derived_versions")
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
    source_calculation = models.ForeignKey(
        EngineeringCalculationRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="generated_bom_versions", verbose_name="来源工程核算",
    )
    preview_hash = models.CharField("生成预览哈希", max_length=64, blank=True, default="")
    generation_key = models.CharField("生成幂等键", max_length=64, blank=True, default="")
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
            models.CheckConstraint(condition=(~models.Q(usage_purpose='TEST_BUSINESS') | (models.Q(status='draft') & (models.Q(source_calculation__isnull=False) | models.Q(origin_version__isnull=False)))), name='pde_bomversion_test_draft_source'),
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
            models.UniqueConstraint(
                fields=("source_calculation",),
                condition=models.Q(source_calculation__isnull=False),
                name="pde_bom_version_source_calc_unique",
            ),
            models.UniqueConstraint(
                fields=("generation_key",),
                condition=~models.Q(generation_key=""),
                name="pde_bom_version_generation_key_unique",
            ),
        ]

    def clean(self):
        from .bom_usage_contract import bind_usage
        bind_usage(self)
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
        if self.source_calculation_id:
            if self.bom_scope != "order_specific":
                errors["source_calculation"] = "核算生成的BOM版本必须为按单BOM"
            elif self.source_calculation.status != "completed":
                errors["source_calculation"] = "只能引用已完成的正式工程核算"
            elif self.source_calculation.engineering_instance_id != self.order_engineering_instance_id:
                errors["source_calculation"] = "核算记录与BOM版本必须属于同一订单工程实例"
        if self.effective_date and self.expire_date and self.expire_date < self.effective_date:
            errors["expire_date"] = "失效日期不得早于生效日期"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        from .bom_usage_contract import bind_usage
        bind_usage(self)
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
    usage_purpose = models.CharField("用途", max_length=24, default="UNCLASSIFIED", editable=False,
        choices=(("UNCLASSIFIED", "历史用途待核定"), ("SHARED_DEFINITION", "通用路线定义"), ("TEST_BUSINESS", "测试业务")))
    origin_version = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors", editable=False)
    test_origin_bom = models.ForeignKey("BOMVersion", on_delete=models.PROTECT, null=True, blank=True, editable=False)


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
            models.CheckConstraint(condition=(~models.Q(usage_purpose='TEST_BUSINESS') | (models.Q(status='draft', origin_version__isnull=False, test_origin_bom__isnull=False))), name='pde_route_test_draft_origin'),
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
        if self.usage_purpose == 'TEST_BUSINESS':
            if self.status != 'draft' or not self.origin_version_id or not self.test_origin_bom_id:
                errors['usage_purpose'] = '测试路线只允许带完整来源的草稿，禁止正式评审或发布。'
            elif self.test_origin_bom.usage_purpose != 'TEST_BUSINESS' or self.origin_version.routing_id != self.routing_id:
                errors['test_origin_bom'] = '测试路线来源用途或所属路线不一致。'
        if self.origin_version_id and self.origin_version.usage_purpose == 'TEST_BUSINESS' and self.usage_purpose != 'TEST_BUSINESS':
            errors['usage_purpose'] = '测试路线派生不能改为通用或生产用途。'

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
            if original and any(getattr(original, key) != getattr(self, key) for key in ('usage_purpose','origin_version_id','test_origin_bom_id')):
                raise ValidationError('路线持久用途及来源不可改写。')
            if self.usage_purpose == 'TEST_BUSINESS' and self.status != 'draft':
                raise ValidationError('测试路线禁止正式评审或发布。')
            if original and original.status in {"reviewed", "released", "obsolete"}:
                immutable = (
                    "product_id", "product_version_id", "routing_id", "routing_version",
                    "revision", "effective_date", "expire_date", "applicability",
                )
                if any(getattr(original, field) != getattr(self, field) for field in immutable):
                    raise ValidationError({"routing_version": "终态工艺版本不可原地覆盖；请创建后续版本。"})
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
    quantity = models.DecimalField("数量", max_digits=18, decimal_places=6)
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
                models.F("bom_version"), models.F("parent_item"), models.F("material"),
                Upper(Trim(Coalesce(NullIf(KeyTextTransform("structureRole", "order_specification"), models.Value("null")),
                                    models.Value(""), output_field=models.CharField()))),
                condition=models.Q(parent_item__isnull=False),
                name="pde_bom_item_parent_material_role_unique",
            ),
            models.UniqueConstraint(
                models.F("bom_version"), models.F("material"),
                Upper(Trim(Coalesce(NullIf(KeyTextTransform("structureRole", "order_specification"), models.Value("null")),
                                    models.Value(""), output_field=models.CharField()))),
                condition=models.Q(parent_item__isnull=True),
                name="pde_bom_item_root_material_role_unique",
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="pde_bom_item_quantity_positive"),
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
        if self.uom.company_id != self.material.company_id:
            errors["uom"] = "BOM单位必须属于物料所在公司"
        # Saved instances are also checked by frozen-source read paths.
        # Current supply qualification belongs to new facts and release gates.
        if self._state.adding:
            from .material_supply_authority import material_supply_fact
            supply = material_supply_fact(self.material, self.supply_type)
            if not supply["allowed"]:
                errors["supply_type"] = supply["message"]
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


class BOMItemSourceRequirement(models.Model):
    """Many-to-one provenance retained when exact-compatible requirements aggregate."""

    bom_item = models.ForeignKey(
        BOMItem, on_delete=models.PROTECT,
        related_name="source_requirements", verbose_name="BOM明细",
    )
    material_requirement = models.OneToOneField(
        EngineeringMaterialRequirement, on_delete=models.PROTECT,
        related_name="generated_bom_item_link", verbose_name="来源物料需求",
    )
    contributed_quantity = models.DecimalField("贡献数量", max_digits=18, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pde_bom_item_source_requirement"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(contributed_quantity__gt=0),
                name="pde_bom_source_req_qty_positive",
            ),
        ]

    def clean(self):
        version = self.bom_item.bom_version
        source_id = version.source_calculation_id
        if version.usage_purpose == 'TEST_BUSINESS' and version.origin_version_id:
            from .bom_usage_contract import bind_usage
            bind_usage(version)
            source_id = version.bom.source_calculation_id
        if source_id != self.material_requirement.calculation_id:
            raise ValidationError({
                "material_requirement": "BOM明细来源需求必须属于该BOM版本的来源核算"
            })


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


ROUTING_STEP_IMMUTABLE_PARENT_STATUSES = {"reviewed", "released", "obsolete"}


def _raise_if_routing_steps_are_frozen(version_ids):
    frozen = list(RoutingVersion.objects.filter(
        pk__in={value for value in version_ids if value},
        status__in=ROUTING_STEP_IMMUTABLE_PARENT_STATUSES,
    ).values_list("pk", "status"))
    if frozen:
        raise ValidationError({
            "routing_version": (
                "已评审、已发布或已失效工艺路线版本的步骤不可修改；"
                "请通过正式入口创建后续草稿版本。"
            ),
        })


class RoutingStepQuerySet(models.QuerySet):
    def _assert_writable(self):
        _raise_if_routing_steps_are_frozen(
            self.values_list("routing_version_id", flat=True).distinct(),
        )

    def update(self, **kwargs):
        self._assert_writable()
        if {'predecessor_step', 'predecessor_step_id'} & kwargs.keys():
            raise ValidationError('正式步骤前驱身份建立后不得批量改写。')
        if "routing_version" in kwargs:
            _raise_if_routing_steps_are_frozen([getattr(kwargs["routing_version"], "pk", None)])
        if "routing_version_id" in kwargs:
            _raise_if_routing_steps_are_frozen([kwargs["routing_version_id"]])
        return super().update(**kwargs)

    def delete(self):
        self._assert_writable()
        return super().delete()

    def bulk_create(self, objs, **kwargs):
        _raise_if_routing_steps_are_frozen([obj.routing_version_id for obj in objs])
        for obj in objs:
            from .plan_step_context_service import validate_step_predecessor
            validate_step_predecessor(obj)
            from .routing_step_applicability_service import validate_operation_parameters_applicability
            validate_operation_parameters_applicability(obj.operation_parameters)
        return super().bulk_create(objs, **kwargs)

    def bulk_update(self, objs, fields, **kwargs):
        if {'predecessor_step', 'predecessor_step_id'} & set(fields):
            raise ValidationError('正式步骤前驱身份建立后不得批量改写。')
        object_ids = [obj.pk for obj in objs if obj.pk]
        existing_version_ids = self.model._base_manager.filter(
            pk__in=object_ids,
        ).values_list("routing_version_id", flat=True)
        _raise_if_routing_steps_are_frozen(existing_version_ids)
        _raise_if_routing_steps_are_frozen([obj.routing_version_id for obj in objs])
        for obj in objs:
            from .routing_step_applicability_service import validate_operation_parameters_applicability
            validate_operation_parameters_applicability(obj.operation_parameters)
        return super().bulk_update(objs, fields, **kwargs)


class RoutingStep(models.Model):
    objects = RoutingStepQuerySet.as_manager()

    predecessor_step = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="successor_steps", verbose_name="正式继任前驱步骤",
    )

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
        help_text="已停用的历史兼容字段；APS不得读取标准工时小时。标准产能由StandardCapacity独立表达。",
    )
    setup_hours = models.DecimalField(
        "准备工时", max_digits=12, decimal_places=4, default=0,
        help_text="已停用的历史兼容字段；APS不得读取，也不得回写已发布步骤。",
    )
    transfer_hours = models.DecimalField(
        "转移工时", max_digits=12, decimal_places=4, default=0,
        help_text="已停用的历史兼容字段；APS不得读取，也不得回写已发布步骤。",
    )
    preparation_days = models.DecimalField(
        "准备时间（天）", max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="未来草稿步骤的DAY事实；未维护保持为空，不从历史小时换算。",
    )
    transfer_days = models.DecimalField(
        "转运时间（天）", max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="未来草稿步骤的DAY事实；未维护保持为空，不从历史小时换算。",
    )
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
            models.UniqueConstraint(fields=("routing_version", "predecessor_step"),
                condition=models.Q(predecessor_step__isnull=False), name="pde_step_predecessor_unique"),
            models.CheckConstraint(condition=~models.Q(id=models.F("predecessor_step_id")),
                name="pde_step_predecessor_not_self"),
            models.CheckConstraint(
                condition=models.Q(standard_hours__isnull=True) | models.Q(standard_hours__gt=0),
                name="pde_routing_step_hours_null_or_positive",
            ),
            models.CheckConstraint(condition=models.Q(setup_hours__gte=0), name="pde_routing_step_setup_hours_nonnegative"),
            models.CheckConstraint(condition=models.Q(transfer_hours__gte=0), name="pde_routing_step_transfer_hours_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(preparation_days__isnull=True) | models.Q(preparation_days__gte=0),
                name="pde_routing_step_preparation_days_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(transfer_days__isnull=True) | models.Q(transfer_days__gte=0),
                name="pde_routing_step_transfer_days_nonnegative",
            ),
        ]

    def clean(self):
        errors = {}
        if self.predecessor_step_id:
            from .plan_step_context_service import validate_step_predecessor
            try:
                validate_step_predecessor(self)
            except ValidationError as error:
                errors["predecessor_step"] = error.messages
        routing_company_id = (
            self.routing_version.routing.company_id
            if self.routing_version.routing_id else self.routing_version.product.company_id
        )
        for field_name in ("preparation_days", "transfer_days"):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                errors[field_name] = "准备时间和转运时间不得为负数"
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
        parameters = self.operation_parameters or {}
        if not isinstance(parameters, dict):
            errors["operation_parameters"] = "工序参数必须是对象"
        else:
            if "executionMode" in parameters and parameters["executionMode"] not in {
                "internal", "subcontract",
            }:
                errors["operation_parameters"] = "executionMode只允许internal或subcontract"
            if "yieldRate" in parameters:
                try:
                    yield_rate = Decimal(str(parameters["yieldRate"]))
                except Exception:
                    yield_rate = None
                if yield_rate is None or yield_rate <= 0 or yield_rate > 1:
                    errors["operation_parameters"] = "yieldRate必须大于0且不大于1"
            try:
                from .routing_step_applicability_service import validate_operation_parameters_applicability
                validate_operation_parameters_applicability(parameters)
            except ValidationError as exc:
                errors["operation_parameters"] = exc.messages
        linked_work_center_id = getattr(self.operation, "work_center_id", None)
        if linked_work_center_id and self.work_center_id and linked_work_center_id != self.work_center_id:
            errors["operation"] = "工序默认工作中心与路线步骤工作中心不一致"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.predecessor_step_id:
            from .plan_step_context_service import validate_step_predecessor
            validate_step_predecessor(self)
        version_ids = [self.routing_version_id]
        if self.pk:
            original_predecessor = type(self).objects.filter(pk=self.pk).values_list("predecessor_step_id", flat=True).first()
            if original_predecessor != self.predecessor_step_id:
                raise ValidationError("正式步骤前驱创建后不可修改。")
            original_version_id = type(self).objects.filter(pk=self.pk).values_list(
                "routing_version_id", flat=True,
            ).first()
            version_ids.append(original_version_id)
        _raise_if_routing_steps_are_frozen(version_ids)
        from .routing_step_applicability_service import validate_operation_parameters_applicability
        validate_operation_parameters_applicability(self.operation_parameters)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        _raise_if_routing_steps_are_frozen([self.routing_version_id])
        return super().delete(*args, **kwargs)


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
    release_subject_type = models.CharField(
        "制造发布主体类型", max_length=32,
        choices=ManufacturingReleaseSubjectType.choices,
        default=ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT,
    )
    product_version = models.ForeignKey(
        ProductVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="engineering_document_versions",
    )
    related_product = models.ForeignKey(
        ProductDefinition,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="engineering_document_versions",
    )
    order_engineering_instance = models.ForeignKey(
        OrderEngineeringInstance, on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_document_versions", verbose_name="订单工程产品身份",
    )
    order_engineering_baseline = models.ForeignKey(
        OrderEngineeringBaseline, on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_document_versions", verbose_name="冻结工程基线",
    )
    engineering_calculation = models.ForeignKey(
        EngineeringCalculationRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="engineering_document_versions", verbose_name="冻结工程核算修订",
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
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        release_subject_type=ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT,
                        related_product__isnull=False,
                        product_version__isnull=False,
                        order_engineering_instance__isnull=True,
                        order_engineering_baseline__isnull=True,
                        engineering_calculation__isnull=True,
                    )
                    | models.Q(
                        release_subject_type=ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
                        related_product__isnull=True,
                        product_version__isnull=True,
                        order_engineering_instance__isnull=False,
                        order_engineering_baseline__isnull=False,
                        engineering_calculation__isnull=False,
                    )
                ),
                name="pde_docver_release_subject_xor",
            ),
        ]

    def clean(self):
        errors = {}
        if self.document.release_subject_type != self.release_subject_type:
            errors["document"] = "工程资料版本主体类型必须与资料主表一致"
        if self.document.product_bom_id != self.related_bom.bom_id:
            errors["document"] = "工程资料版本必须对应资料主表BOM"
        if self.document.routing_id != self.related_routing.routing_id:
            errors["document"] = "工程资料版本必须对应资料主表工艺路线"
        if self.release_subject_type == ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT:
            if (
                not self.related_product_id or not self.product_version_id
                or self.order_engineering_instance_id
                or self.order_engineering_baseline_id
                or self.engineering_calculation_id
            ):
                errors["release_subject_type"] = "长期产品资料版本必须且只能冻结长期产品及其版本"
            else:
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
        else:
            if self.related_product_id or self.product_version_id:
                errors["release_subject_type"] = "订单工程资料版本不得伪造长期产品或产品版本"
            errors.update(_order_engineering_release_identity_errors(
                self.order_engineering_instance if self.order_engineering_instance_id else None,
                self.order_engineering_baseline if self.order_engineering_baseline_id else None,
                self.engineering_calculation if self.engineering_calculation_id else None,
            ))
            if self.order_engineering_instance_id:
                instance = self.order_engineering_instance
                if self.document.order_engineering_instance_id != instance.pk:
                    errors["document"] = "工程资料版本必须属于资料主表订单工程产品"
                if (
                    self.related_bom.order_engineering_instance_id != instance.pk
                    or self.related_bom.bom_scope != "order_specific"
                ):
                    errors["related_bom"] = "订单工程资料必须冻结同一订单工程实例的按单BOM版本"
                elif self.related_bom.source_calculation_id != self.engineering_calculation_id:
                    errors["related_bom"] = "订单工程资料BOM必须由所冻结的工程核算生成"
                if not self.related_routing.routing_id or not _routing_matches_order_engineering_instance(
                    self.related_routing.routing, instance,
                ):
                    errors["related_routing"] = "订单工程资料必须冻结适用于同一订单工程实例的工艺版本"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.status == "released":
                immutable = (
                    "document_id", "document_name", "document_version", "product_version_id",
                    "related_product_id", "release_subject_type",
                    "order_engineering_instance_id", "order_engineering_baseline_id",
                    "engineering_calculation_id", "related_bom_id", "related_routing_id",
                    "effective_date", "expire_date",
                )
                if any(getattr(original, field) != getattr(self, field) for field in immutable):
                    raise ValidationError({
                        "document_version": "已发布工程资料版本不可原地覆盖；请创建新版本。",
                    })
        super().save(*args, **kwargs)


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
    order_routing_arrangement = models.ForeignKey('pde.OrderRoutingExecutionArrangement',on_delete=models.PROTECT,null=True,blank=True,editable=False,related_name='manufacturing_outputs')
    revision = models.PositiveIntegerField("制造发布修订", default=1)
    predecessor = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="successor_outputs", verbose_name="制造发布前驱")
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

    release_subject_type = models.CharField(
        "制造发布主体类型", max_length=32,
        choices=ManufacturingReleaseSubjectType.choices,
        default=ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT,
    )
    product = models.ForeignKey(
        ProductDefinition,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="manufacturing_outputs",
    )
    product_version = models.ForeignKey(
        ProductVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
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
    order_engineering_baseline = models.ForeignKey(
        OrderEngineeringBaseline, on_delete=models.PROTECT, null=True, blank=True,
        related_name="manufacturing_outputs", verbose_name="冻结工程基线",
    )
    engineering_calculation = models.ForeignKey(
        EngineeringCalculationRecord, on_delete=models.PROTECT, null=True, blank=True,
        related_name="manufacturing_outputs", verbose_name="冻结工程核算修订",
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
                condition=(models.Q(order_engineering_instance__isnull=False)
                    & ~models.Q(release_subject_type="ORDER_ENGINEERED_PRODUCT")),
                name="pde_mfg_output_order_instance_unique",
            ),
            models.UniqueConstraint(fields=("order_engineering_instance", "revision"),
                condition=models.Q(release_subject_type="ORDER_ENGINEERED_PRODUCT"), name="pde_oe_output_revision_unique"),
            models.UniqueConstraint(fields=("order_engineering_instance",),
                condition=models.Q(release_subject_type="ORDER_ENGINEERED_PRODUCT", predecessor__isnull=True),
                name="pde_oe_output_root_unique"),
            models.UniqueConstraint(fields=("predecessor",),
                condition=models.Q(release_subject_type="ORDER_ENGINEERED_PRODUCT", predecessor__isnull=False),
                name="pde_oe_output_successor_unique"),
            models.UniqueConstraint(fields=("order_engineering_instance", "order_engineering_baseline",
                "engineering_calculation", "bom_version", "routing_version", "engineering_document_version"),
                condition=models.Q(release_subject_type="ORDER_ENGINEERED_PRODUCT"), name="pde_oe_output_source_unique"),
            models.CheckConstraint(condition=models.Q(revision__gt=0), name="pde_output_revision_positive"),
            models.CheckConstraint(condition=~models.Q(id=models.F("predecessor_id")), name="pde_output_predecessor_not_self"),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        release_subject_type=ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT,
                        product__isnull=False,
                        product_version__isnull=False,
                        order_engineering_baseline__isnull=True,
                        engineering_calculation__isnull=True,
                    )
                    | models.Q(
                        release_subject_type=ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
                        product__isnull=True,
                        product_version__isnull=True,
                        order_engineering_instance__isnull=False,
                        order_engineering_baseline__isnull=False,
                        engineering_calculation__isnull=False,
                    )
                ),
                name="pde_mfg_release_subject_xor",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        release_subject_type=ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT,
                        order_engineering_instance__isnull=True,
                        definition_mode="standard",
                    )
                    | models.Q(
                        release_subject_type=ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT,
                        order_engineering_instance__isnull=False,
                        definition_mode="order_specific",
                    )
                    | models.Q(
                        release_subject_type=ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
                        definition_mode="order_specific",
                    )
                ),
                name="pde_mfg_subject_mode_consistent",
            ),
        ]

    def clean(self):
        if self.order_routing_arrangement_id:
            from .order_routing_execution_service import validate_manufacturing_reference
            validate_manufacturing_reference(self)

        errors = {}
        if self.release_subject_type == ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT:
            if self.predecessor_id:
                previous = self.predecessor
                if (previous.pk == self.pk or previous.release_subject_type != self.release_subject_type
                    or previous.order_engineering_instance_id != self.order_engineering_instance_id
                    or self.revision != previous.revision + 1
                    or previous.release_status != "released_to_manufacturing"):
                    errors["predecessor"] = "继任制造输出必须承接同实例的已发布前驱及下一修订。"
            elif self.revision != 1:
                errors["revision"] = "首制造输出修订必须为1。"
        elif self.predecessor_id or self.revision != 1:
            errors["predecessor"] = "长期产品输出不开放订单工程继任合同。"
        if self.release_subject_type == ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT:
            if not self.product_id or not self.product_version_id:
                errors["release_subject_type"] = "长期产品发布必须冻结产品定义和产品版本"
            elif self.product_version.product_id != self.product_id:
                errors["product_version"] = "产品版本必须属于当前长期产品"
            if self.order_engineering_baseline_id or self.engineering_calculation_id:
                errors["release_subject_type"] = "长期产品主体不得同时绑定订单工程基线或核算主体"
            if self.product_id and self.bom_version.product_id != self.product_id:
                errors["bom_version"] = "BOM版本必须属于当前长期产品"
            if self.product_id and self.routing_version.product_id != self.product_id:
                errors["routing_version"] = "工艺版本必须属于当前长期产品"
            if self.order_engineering_instance_id:
                instance = self.order_engineering_instance
                if instance.product_id != self.product_id:
                    errors["order_engineering_instance"] = "长期产品发布的订单来源必须引用同一长期产品"
                if instance.baseline_product_version_id != self.product_version_id:
                    errors["product_version"] = "长期产品发布的订单来源必须使用同一基线产品版本"
            expected_mode = "order_specific" if self.order_engineering_instance_id else "standard"
            if self.definition_mode != expected_mode:
                errors["definition_mode"] = "制造定义模式必须与长期产品发布范围一致"
            if self.definition_mode == "standard" and self.bom_version.bom_scope != "standard":
                errors["bom_version"] = "标准制造定义必须引用标准BOM版本"
            if self.definition_mode == "order_specific":
                if self.bom_version.bom_scope != "order_specific":
                    errors["bom_version"] = "按单形成的长期产品制造定义必须引用按单BOM版本"
                elif self.bom_version.order_engineering_instance_id != self.order_engineering_instance_id:
                    errors["bom_version"] = "按单BOM必须属于同一订单工程实例"
        else:
            if self.product_id or self.product_version_id:
                errors["release_subject_type"] = "订单工程产品主体不得伪造长期产品或产品版本"
            if self.definition_mode != "order_specific":
                errors["definition_mode"] = "订单工程产品发布必须使用按单制造定义模式"
            errors.update(_order_engineering_release_identity_errors(
                self.order_engineering_instance if self.order_engineering_instance_id else None,
                self.order_engineering_baseline if self.order_engineering_baseline_id else None,
                self.engineering_calculation if self.engineering_calculation_id else None,
            ))
            if self.order_engineering_instance_id:
                instance = self.order_engineering_instance
                if (
                    self.bom_version.bom_scope != "order_specific"
                    or self.bom_version.order_engineering_instance_id != instance.pk
                ):
                    errors["bom_version"] = "订单工程产品必须冻结同一订单工程实例的按单BOM版本"
                elif self.bom_version.source_calculation_id != self.engineering_calculation_id:
                    errors["bom_version"] = "订单工程BOM必须由所冻结的工程核算生成"
                if not self.routing_version.routing_id or not _routing_matches_order_engineering_instance(
                    self.routing_version.routing, instance,
                ):
                    errors["routing_version"] = "订单工程产品必须冻结适用于同一实例的工艺版本"

        if self.engineering_document_version_id:
            document_version = self.engineering_document_version
            if document_version.release_subject_type != self.release_subject_type:
                errors["engineering_document_version"] = "工程资料版本主体类型必须与制造发布主体一致"
            if document_version.related_bom_id != self.bom_version_id:
                errors["engineering_document_version"] = "工程资料版本必须引用当前BOM版本"
            if document_version.related_routing_id != self.routing_version_id:
                errors["engineering_document_version"] = "工程资料版本必须引用当前工艺版本"
            if self.release_subject_type == ManufacturingReleaseSubjectType.LONG_TERM_PRODUCT:
                if document_version.related_product_id != self.product_id:
                    errors["engineering_document_version"] = "工程资料版本必须属于当前长期产品"
                if document_version.product_version_id != self.product_version_id:
                    errors["engineering_document_version"] = "工程资料版本必须引用当前产品版本"
            else:
                if document_version.order_engineering_instance_id != self.order_engineering_instance_id:
                    errors["engineering_document_version"] = "工程资料版本必须属于当前订单工程产品"
                if document_version.order_engineering_baseline_id != self.order_engineering_baseline_id:
                    errors["engineering_document_version"] = "工程资料版本必须冻结同一工程基线"
                if document_version.engineering_calculation_id != self.engineering_calculation_id:
                    errors["engineering_document_version"] = "工程资料版本必须冻结同一工程核算修订"
        if self.release_status == "released_to_manufacturing":
            if not self.engineering_document_version_id:
                errors["engineering_document_version"] = "发布至制造必须引用正式工程资料版本"
            version_statuses = [
                self.bom_version.status,
                self.routing_version.status,
                self.engineering_document_version.status if self.engineering_document_version_id else None,
            ]
            if self.product_version_id:
                version_statuses.append(self.product_version.version_status)
            if any(status != "released" for status in version_statuses):
                errors["release_status"] = "失效或未发布版本禁止输出至制造"
            if self.engineering_status != "ready":
                errors["engineering_status"] = "工程资料未齐套时禁止输出至制造"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.release_status in {"released_to_manufacturing", "inactive"}:
                immutable = (
                    "product_id", "product_version_id", "bom_version_id", "routing_version_id",
                    "engineering_document_version_id", "release_subject_type", "definition_mode",
                    "order_engineering_instance_id", "order_engineering_baseline_id",
                    "engineering_calculation_id", "engineering_status", "effective_date",
                    "revision", "predecessor_id", "order_routing_arrangement_id",
                )
                if any(getattr(original, field) != getattr(self, field) for field in immutable):
                    raise ValidationError({
                        "release_status": "已发布制造定义不可原地覆盖；请形成新的发布记录。",
                    })
        super().save(*args, **kwargs)


class PlanStepVersionBindingQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("步骤版本绑定只能通过正式状态服务变更。")

    def delete(self):
        raise ValidationError("步骤版本承接历史不可删除。")

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("步骤版本承接必须逐项经过原生事务服务。")


class PlanStepVersionBinding(models.Model):
    """Audited activation over one stable plan step; no demand/output rewrite."""
    objects = PlanStepVersionBindingQuerySet.as_manager()
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT)
    production_plan = models.ForeignKey("planning.ProductionPlan", on_delete=models.PROTECT,
        related_name="engineering_step_bindings")
    root_step = models.ForeignKey(RoutingStep, on_delete=models.PROTECT, related_name="root_version_bindings")
    target_step = models.ForeignKey(RoutingStep, on_delete=models.PROTECT, related_name="target_version_bindings")
    manufacturing_output = models.ForeignKey(ProductManufacturingOutput, on_delete=models.PROTECT,
        related_name="plan_step_bindings")
    predecessor = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="successor_bindings")
    revision = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, default="draft", choices=(
        ("draft", "待生效"), ("active", "已生效"), ("superseded", "已被承接"), ("revoked", "已撤销")))
    version = models.PositiveIntegerField(default=0)
    context_hash = models.CharField(max_length=64)
    impact_hash = models.CharField(max_length=64)
    source_snapshot = models.JSONField(default=dict)
    impact_snapshot = models.JSONField(default=dict)
    write_request = models.OneToOneField("masterdata.MasterDataWriteRequest", on_delete=models.PROTECT)
    audit_record = models.ForeignKey("system.OrganizationOperatingAuditRecord", on_delete=models.PROTECT,
        null=True, blank=True)
    created_by = models.ForeignKey("system.User", on_delete=models.PROTECT)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_plan_step_version_binding"
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("company", "production_plan", "root_step", "revision"), name="pde_step_bind_revision_unique"),
            models.UniqueConstraint(fields=("company", "production_plan", "root_step"),
                condition=models.Q(predecessor__isnull=True), name="pde_step_bind_root_unique"),
            models.UniqueConstraint(fields=("predecessor",), condition=models.Q(predecessor__isnull=False), name="pde_step_bind_successor_unique"),
            models.UniqueConstraint(fields=("company", "production_plan", "root_step"),
                condition=models.Q(status="active"), name="pde_step_bind_active_unique"),
            models.CheckConstraint(condition=models.Q(revision__gt=0), name="pde_step_bind_revision_positive"),
            models.CheckConstraint(condition=~models.Q(id=models.F("predecessor_id")), name="pde_step_bind_not_self"),
            models.CheckConstraint(condition=models.Q(status__in=("draft", "active", "superseded", "revoked")), name="pde_step_bind_status_valid"),
            models.CheckConstraint(condition=(models.Q(status="draft") | models.Q(audit_record__isnull=False)), name="pde_step_bind_active_audited"),
        ]

    def clean(self):
        from .plan_step_context_service import validate_binding_model
        validate_binding_model(self)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            permitted = {"status", "version", "updated_at"}
            if original.status == "draft" and getattr(self, "_binding_write_authorized", False):
                permitted.add("audit_record_id")
            if any(getattr(original, f.attname) != getattr(self, f.attname)
                for f in self._meta.concrete_fields if f.attname not in permitted):
                raise ValidationError("步骤版本绑定的身份及冻结载荷不可改写。")
            if (original.status != self.status or original.version != self.version) and not getattr(
                self, "_business_state_transition_authorized", False):
                raise ValidationError("步骤版本绑定状态必须经过共享状态服务。")
        elif not getattr(self, "_business_state_initialization_authorized", False):
            raise ValidationError("步骤版本绑定必须经过正式初始化服务。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("步骤版本承接历史不可删除。")


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


# Historical applied-model branch retained for migration/code baseline convergence.

class ProductionLine(models.Model):
    """Optional production-line layer; enterprises without lines may omit it."""
    code = models.CharField("生产线编码", max_length=50)
    name = models.CharField("生产线名称", max_length=120)
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT, related_name="production_lines", verbose_name="所属公司")
    workshop = models.ForeignKey("system.Workshop", on_delete=models.PROTECT, related_name="production_lines", verbose_name="所属车间")
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_production_line"
        ordering = ("company_id", "code")
        constraints = [models.UniqueConstraint(fields=("company", "code"), name="pde_production_line_company_code_unique")]

    def clean(self):
        errors = {}
        if self.workshop_id and self.workshop.company_id != self.company_id:
            errors["workshop"] = "生产线车间必须属于同一公司"
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "失效日期不得早于生效日期"
        if errors:
            raise ValidationError(errors)


class Station(models.Model):
    """Optional station identity beneath a line and/or WorkCenter."""
    code = models.CharField("工位编码", max_length=50)
    name = models.CharField("工位名称", max_length=120)
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT, related_name="production_stations", verbose_name="所属公司")
    workshop = models.ForeignKey("system.Workshop", on_delete=models.PROTECT, related_name="production_stations", verbose_name="所属车间")
    production_line = models.ForeignKey(ProductionLine, on_delete=models.PROTECT, null=True, blank=True, related_name="stations", verbose_name="所属生产线（可选）")
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, null=True, blank=True, related_name="stations", verbose_name="所属工作中心（可选）")
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_station"
        ordering = ("company_id", "code")
        constraints = [models.UniqueConstraint(fields=("company", "code"), name="pde_station_company_code_unique")]

    def clean(self):
        errors = {}
        if self.workshop_id and self.workshop.company_id != self.company_id:
            errors["workshop"] = "工位车间必须属于同一公司"
        if self.production_line_id:
            if self.production_line.company_id != self.company_id:
                errors["production_line"] = "工位生产线必须属于同一公司"
            elif self.production_line.workshop_id != self.workshop_id:
                errors["production_line"] = "工位生产线必须属于同一车间"
        if self.work_center_id:
            if self.work_center.company_id != self.company_id:
                errors["work_center"] = "工位工作中心必须属于同一公司"
            elif self.work_center.workshop_id not in {None, self.workshop_id}:
                errors["work_center"] = "工位工作中心必须属于同一车间"
        if errors:
            raise ValidationError(errors)


class WorkCenterOperationCapability(models.Model):
    """Governed many-to-many capability with explicit primary/alternative role."""
    class AssignmentRole(models.TextChoices):
        PRIMARY = "primary", "主工作中心"
        ALTERNATIVE = "alternative", "备选工作中心"

    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, related_name="operation_capabilities", verbose_name="工作中心")
    operation = models.ForeignKey("system.Process", on_delete=models.PROTECT, related_name="work_center_capabilities", verbose_name="工序")
    assignment_role = models.CharField("资源角色", max_length=16, choices=AssignmentRole.choices, default=AssignmentRole.ALTERNATIVE)
    capability_code = models.CharField("能力编码", max_length=80, blank=True)
    capability_parameters = models.JSONField("能力参数", default=dict, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    effective_from = models.DateField("生效日期", null=True, blank=True)
    effective_to = models.DateField("失效日期", null=True, blank=True)

    class Meta:
        db_table = "pde_work_center_operation_capability"
        ordering = ("operation_id", "assignment_role", "work_center_id")
        constraints = [
            models.UniqueConstraint(fields=("work_center", "operation"), name="pde_wc_operation_capability_unique"),
            models.CheckConstraint(condition=models.Q(assignment_role__in=("primary", "alternative")), name="pde_wc_operation_role_valid"),
        ]

    def clean(self):
        errors = {}
        if self.operation.company_id and self.operation.company_id != self.work_center.company_id:
            errors["operation"] = "工序与工作中心必须属于同一公司"
        if self.operation.workshop_id and self.work_center.workshop_id not in {None, self.operation.workshop_id}:
            errors["work_center"] = "工作中心与工序必须属于同一车间"
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "失效日期不得早于生效日期"
        if errors:
            raise ValidationError(errors)


class WorkCenterTeamAssignment(models.Model):
    """Optional governed assignment of an existing enterprise Team to a WorkCenter."""
    work_center = models.ForeignKey(WorkCenter, on_delete=models.PROTECT, related_name="team_assignments", verbose_name="工作中心")
    team = models.ForeignKey("system.Team", on_delete=models.PROTECT, related_name="work_center_assignments", verbose_name="班组")
    is_primary = models.BooleanField("是否主班组", default=False)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        db_table = "pde_work_center_team_assignment"
        ordering = ("work_center_id", "team_id")
        constraints = [models.UniqueConstraint(fields=("work_center", "team"), name="pde_wc_team_assignment_unique")]

    def clean(self):
        errors = {}
        if self.team.company_id != self.work_center.company_id:
            errors["team"] = "班组与工作中心必须属于同一公司"
        if self.work_center.workshop_id and self.team.workshop_id != self.work_center.workshop_id:
            errors["team"] = "班组与工作中心必须属于同一车间"
        if errors:
            raise ValidationError(errors)


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
        related_name="material_requirement_slots", verbose_name="模板结构槽位",
    )
    slot_code = models.CharField("需求槽位编码", max_length=120)
    slot_name = models.CharField("需求槽位名称", max_length=240)
    material_category = models.ForeignKey(
        "masterdata.MaterialCategory", on_delete=models.PROTECT,
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
            )
        ]

    def clean(self):
        errors = {}
        company_id = self.template_node.template.company_id
        if self.material_category.company_id != company_id:
            errors["material_category"] = "物料分类必须与模板槽位属于同一公司"
        if self.quantity_rule_binding_id and self.quantity_rule_binding.template_node_id != self.template_node_id:
            errors["quantity_rule_binding"] = "数量规则只能引用同一模板结构槽位"
        if self.expected_uom_id and self.expected_uom.company_id != company_id:
            errors["expected_uom"] = "预期计量单位必须与模板槽位属于同一公司"
        if errors:
            raise ValidationError(errors)


class TemplateNodeEdgeDefinition(models.Model):
    """Industry-neutral edge fact definition; edge names and treatments remain data."""

    template_node = models.ForeignKey(
        ProductTemplateStructureNode, on_delete=models.PROTECT,
        related_name="edge_definitions", verbose_name="模板结构槽位",
    )
    edge_code = models.CharField("边编码", max_length=80)
    edge_name = models.CharField("边名称", max_length=160)
    treatment_required = models.BooleanField("是否需要处理", null=True, blank=True)
    treatment_requirement = models.JSONField("处理需求", default=dict, blank=True)
    calculation_rule_binding = models.ForeignKey(
        TemplateNodeCalculationRuleBinding, on_delete=models.PROTECT,
        null=True, blank=True, related_name="edge_definitions", verbose_name="核算规则绑定",
    )
    material_requirement_slot = models.ForeignKey(
        TemplateMaterialRequirementSlot, on_delete=models.PROTECT,
        null=True, blank=True, related_name="edge_definitions", verbose_name="封边材料需求槽位",
        help_text="边处理事实与封边材料选择分离；此处只建立需求血缘。",
    )
    sort_order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        db_table = "pde_template_node_edge_definition"
        ordering = ("template_node_id", "sort_order", "edge_code")
        constraints = [
            models.UniqueConstraint(
                fields=("template_node", "edge_code"),
                name="pde_template_node_edge_code_unique",
            )
        ]

    def clean(self):
        errors = {}
        if self.calculation_rule_binding_id and self.calculation_rule_binding.template_node_id != self.template_node_id:
            errors["calculation_rule_binding"] = "边定义只能引用同一模板槽位的规则绑定"
        if self.material_requirement_slot_id and self.material_requirement_slot.template_node_id != self.template_node_id:
            errors["material_requirement_slot"] = "边定义只能引用同一模板槽位的材料需求"
        if errors:
            raise ValidationError(errors)


class TemplateNodeSurfaceDefinition(models.Model):
    """Industry-neutral surface fact definition; enterprise terminology remains governed data."""

    template_node = models.ForeignKey(
        ProductTemplateStructureNode, on_delete=models.PROTECT,
        related_name="surface_definitions", verbose_name="模板结构槽位",
    )
    surface_code = models.CharField("面编码", max_length=80)
    surface_name = models.CharField("面名称", max_length=160)
    exposure_classification = models.CharField(
        "可见/饰面分类", max_length=120, blank=True, default="",
        help_text="企业维护术语；不得在Schema中固化木业专属字段。",
    )
    treatment_required = models.BooleanField("是否需要处理", null=True, blank=True)
    treatment_requirement = models.JSONField("处理需求", default=dict, blank=True)
    calculation_rule_binding = models.ForeignKey(
        TemplateNodeCalculationRuleBinding, on_delete=models.PROTECT,
        null=True, blank=True, related_name="surface_definitions", verbose_name="核算规则绑定",
    )
    material_requirement_slot = models.ForeignKey(
        TemplateMaterialRequirementSlot, on_delete=models.PROTECT,
        null=True, blank=True, related_name="surface_definitions", verbose_name="饰面材料需求槽位",
        help_text="面处理事实与饰面材料选择分离；此处只建立需求血缘。",
    )
    sort_order = models.PositiveIntegerField("排序", default=0)

    class Meta:
        db_table = "pde_template_node_surface_definition"
        ordering = ("template_node_id", "sort_order", "surface_code")
        constraints = [
            models.UniqueConstraint(
                fields=("template_node", "surface_code"),
                name="pde_template_node_surface_code_unique",
            )
        ]

    def clean(self):
        errors = {}
        if self.calculation_rule_binding_id and self.calculation_rule_binding.template_node_id != self.template_node_id:
            errors["calculation_rule_binding"] = "面定义只能引用同一模板槽位的规则绑定"
        if self.material_requirement_slot_id and self.material_requirement_slot.template_node_id != self.template_node_id:
            errors["material_requirement_slot"] = "面定义只能引用同一模板槽位的材料需求"
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


class ComponentRoutingStep(models.Model):
    """Routing step bound to a custom component without requiring Material."""

    component = models.ForeignKey(
        OrderProductComponent, on_delete=models.PROTECT,
        related_name="routing_steps", verbose_name="适用构件",
    )
    sequence = models.PositiveIntegerField("步骤顺序")
    operation = models.ForeignKey(
        "system.Process", on_delete=models.PROTECT,
        related_name="component_routing_steps", verbose_name="正式工序",
    )
    workshop = models.ForeignKey(
        "system.Workshop", on_delete=models.PROTECT, null=True, blank=True,
        related_name="component_routing_steps", verbose_name="正式车间",
    )
    work_center = models.ForeignKey(
        WorkCenter, on_delete=models.PROTECT, null=True, blank=True,
        related_name="component_routing_steps", verbose_name="正式工作中心",
    )
    standard_hours = models.DecimalField(
        "标准工时", max_digits=12, decimal_places=4, null=True, blank=True,
    )
    setup_hours = models.DecimalField("准备工时", max_digits=12, decimal_places=4, default=0)
    instruction = models.TextField("操作说明", blank=True)
    operation_parameters = models.JSONField("工序参数", default=dict, blank=True)
    predecessor_sequences = models.JSONField("前置步骤顺序", default=list, blank=True)
    resource_selection_rule = models.JSONField("资源选择规则", default=dict, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_component_routing_step"
        ordering = ("component_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("component", "sequence"),
                name="pde_component_routing_sequence_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(standard_hours__isnull=True) | models.Q(standard_hours__gt=0),
                name="pde_component_routing_hours_null_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(setup_hours__gte=0),
                name="pde_component_routing_setup_nonnegative",
            ),
        ]

    def clean(self):
        errors = {}
        company_id = self.component.order_product.company_id
        if self.operation_id and self.operation.company_id and self.operation.company_id != company_id:
            errors["operation"] = "工序必须属于构件所在公司"
        if self.workshop_id and self.workshop.company_id != company_id:
            errors["workshop"] = "车间必须属于构件所在公司"
        if self.work_center_id and self.work_center.company_id != company_id:
            errors["work_center"] = "工作中心必须属于构件所在公司"
        if self.work_center_id and self.workshop_id and self.work_center.workshop_id:
            if self.work_center.workshop_id != self.workshop_id:
                errors["work_center"] = "工作中心必须属于所选车间"
        predecessors = self.predecessor_sequences or []
        if any(not isinstance(value, int) or value <= 0 or value >= self.sequence for value in predecessors):
            errors["predecessor_sequences"] = "前置步骤必须是小于当前顺序的正整数"
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


class ImmutableRoutingObjectApplicabilityQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("已提交对象适用性证据不可覆盖。")

    def delete(self):
        raise ValidationError("已提交对象适用性证据不可删除。")

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("对象适用性必须通过正式成组服务逐项校验。")

    def bulk_update(self, objs, fields, **kwargs):
        raise ValidationError("已提交对象适用性证据不可批量覆盖。")


class RoutingStepObjectApplicability(models.Model):
    """Immutable plan/object evidence; the released route remains untouched."""

    objects = ImmutableRoutingObjectApplicabilityQuerySet.as_manager()
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT, related_name="routing_object_applicabilities")
    production_plan = models.ForeignKey("planning.ProductionPlan", on_delete=models.PROTECT, related_name="routing_object_applicabilities")
    manufacturing_output = models.ForeignKey("ProductManufacturingOutput", on_delete=models.PROTECT, related_name="routing_object_applicabilities")
    main_calculation = models.ForeignKey("EngineeringCalculationRecord", on_delete=models.PROTECT, related_name="routing_object_applicabilities")
    engineering_baseline = models.ForeignKey("OrderEngineeringBaseline", on_delete=models.PROTECT, related_name="routing_object_applicabilities")
    routing_version = models.ForeignKey("RoutingVersion", on_delete=models.PROTECT, related_name="object_applicabilities")
    routing_step = models.ForeignKey("RoutingStep", on_delete=models.PROTECT, related_name="object_applicabilities")
    baseline_item = models.ForeignKey("OrderEngineeringBaselineItem", on_delete=models.PROTECT, related_name="routing_object_applicabilities")
    design_item = models.ForeignKey("ProductDesignItem", on_delete=models.PROTECT, related_name="routing_object_applicabilities")
    source_record = models.ForeignKey("EngineeringSourceRecord", on_delete=models.PROTECT, related_name="routing_object_applicabilities")
    source_version = models.CharField(max_length=80)
    source_content_hash = models.CharField(max_length=64)
    baseline_snapshot_hash = models.CharField(max_length=64)
    object_content_hash = models.CharField(max_length=64)
    calculation_input_hash = models.CharField(max_length=64)
    calculation_rule_graph_hash = models.CharField(max_length=64)
    calculation_result_hash = models.CharField(max_length=64)
    context_hash = models.CharField(max_length=64)
    decision = models.CharField(max_length=16, choices=(
        ("REQUIRED", "必须执行"), ("NOT_APPLICABLE", "不适用"), ("PENDING", "待确认"),
    ))
    basis = models.JSONField(default=dict)
    reason = models.TextField()
    created_by = models.ForeignKey("system.User", on_delete=models.PROTECT, related_name="routing_object_applicabilities")
    created_at = models.DateTimeField(auto_now_add=True)
    write_request = models.ForeignKey("masterdata.MasterDataWriteRequest", on_delete=models.PROTECT, related_name="routing_object_applicabilities")

    class Meta:
        db_table = "pde_routing_step_object_applicability"
        default_permissions = ()
        ordering = ("production_plan_id", "routing_step_id", "baseline_item_id", "pk")
        constraints = [
            models.UniqueConstraint(fields=("company", "production_plan", "manufacturing_output", "routing_step", "baseline_item", "context_hash"), name="pde_obj_app_scope_unique"),
            models.CheckConstraint(condition=models.Q(decision__in=("REQUIRED", "NOT_APPLICABLE", "PENDING")), name="pde_obj_app_decision_valid"),
            models.CheckConstraint(condition=~models.Q(context_hash=""), name="pde_obj_app_context_required"),
        ]
        indexes = [models.Index(fields=("company", "production_plan", "manufacturing_output", "routing_step", "engineering_baseline"), name="pde_obj_app_scope_idx")]

    def clean(self):
        from .routing_object_applicability_service import validate_record_context
        from .routing_version_successor_service import RoutingVersionChangeError
        try:
            validate_record_context(self)
        except RoutingVersionChangeError as exc:
            raise ValidationError(exc.message) from exc

    def save(self, *args, **kwargs):
        if self.pk or not getattr(self, "_object_applicability_creation_authorized", False):
            raise ValidationError("对象适用性只能由正式服务新建，提交后不可改写。")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("已提交对象适用性证据不可删除。")


class ImmutableRoutingObjectCorrectionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('已提交适用性纠正不可覆盖。')

    def delete(self):
        raise ValidationError('已提交适用性纠正不可删除。')

    def bulk_create(self, objs, **kwargs):
        raise ValidationError('纠正必须通过正式成组服务。')

    def bulk_update(self, objs, fields, **kwargs):
        raise ValidationError('已提交适用性纠正不可批量覆盖。')


class RoutingStepObjectApplicabilityCorrection(models.Model):
    """Immutable decision event over a protected V1 root; no current flag."""
    objects = ImmutableRoutingObjectCorrectionQuerySet.as_manager()
    company = models.ForeignKey('system.Company', on_delete=models.PROTECT,
        related_name='routing_object_corrections')
    root_record = models.ForeignKey('RoutingStepObjectApplicability', on_delete=models.PROTECT,
        related_name='corrections')
    predecessor = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='successor')
    context_hash = models.CharField(max_length=64)
    root_record_hash = models.CharField(max_length=64)
    predecessor_hash = models.CharField(max_length=64)
    decision = models.CharField(max_length=16, choices=(
        ('REQUIRED', '必须执行'), ('NOT_APPLICABLE', '不适用'), ('PENDING', '待确认')))
    basis = models.JSONField(default=dict)
    reason = models.TextField()
    created_by = models.ForeignKey('system.User', on_delete=models.PROTECT,
        related_name='routing_object_corrections')
    created_at = models.DateTimeField(auto_now_add=True)
    write_request = models.OneToOneField('masterdata.MasterDataWriteRequest', on_delete=models.PROTECT,
        related_name='routing_object_correction')

    class Meta:
        db_table = 'pde_routing_object_applicability_correction'
        default_permissions = ()
        ordering = ('root_record_id', 'pk')  # Display only; never current selection.
        constraints = [
            models.UniqueConstraint(fields=('root_record',), condition=models.Q(predecessor__isnull=True),
                name='pde_obj_corr_first_unique'),
            models.CheckConstraint(condition=models.Q(decision__in=('REQUIRED', 'NOT_APPLICABLE', 'PENDING')),
                name='pde_obj_corr_decision_valid'),
            models.CheckConstraint(condition=(~models.Q(context_hash='') & ~models.Q(root_record_hash='')
                & ~models.Q(predecessor_hash='')), name='pde_obj_corr_hash_required'),
            models.CheckConstraint(condition=~models.Q(id=models.F('predecessor_id')),
                name='pde_obj_corr_no_self'),
        ]

    def clean(self):
        from .routing_object_applicability_correction_service import validate_record_context
        from .routing_version_successor_service import RoutingVersionChangeError
        try:
            validate_record_context(self)
        except RoutingVersionChangeError as error:
            raise ValidationError(error.message) from error

    def save(self, *args, **kwargs):
        if self.pk or not getattr(self, '_object_applicability_correction_creation_authorized', False):
            raise ValidationError('纠正只能由原生服务新建，提交后不可修改。')
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('纠正历史不可删除。')


class OperationInputPreparationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('工序投入准备只能由专用原生服务维护。')

    def delete(self):
        raise ValidationError('工序投入准备记录不可删除。')

    def bulk_create(self, objs, **kwargs):
        raise ValidationError('工序投入准备必须逐项执行完整原生保存合同。')

    def bulk_update(self, objs, fields, **kwargs):
        raise ValidationError('工序投入准备不得批量绕过并发及审计合同。')


class OperationInputPreparationDraft(models.Model):
    """Plan-bound preparation evidence; never a rule, capacity or requirement."""

    objects = OperationInputPreparationQuerySet.as_manager()
    company = models.ForeignKey('system.Company', on_delete=models.PROTECT, related_name='operation_input_preparations')
    operation = models.ForeignKey('system.Process', on_delete=models.PROTECT, related_name='input_preparations')
    product_type = models.ForeignKey('CapacityProductType', on_delete=models.PROTECT, related_name='input_preparations')
    production_plan = models.ForeignKey('planning.ProductionPlan', on_delete=models.PROTECT, related_name='operation_input_preparations')
    manufacturing_output = models.ForeignKey('ProductManufacturingOutput', on_delete=models.PROTECT, related_name='input_preparations')
    main_calculation = models.ForeignKey('EngineeringCalculationRecord', on_delete=models.PROTECT, related_name='input_preparations')
    engineering_baseline = models.ForeignKey('OrderEngineeringBaseline', on_delete=models.PROTECT, related_name='operation_input_preparations')
    routing_version = models.ForeignKey('RoutingVersion', on_delete=models.PROTECT, related_name='input_preparations')
    routing_step = models.ForeignKey('RoutingStep', on_delete=models.PROTECT, related_name='input_preparations')
    object_coverage = models.JSONField()
    objects_hash = models.CharField(max_length=64)
    context_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=12, choices=(('draft', '准备草稿'),))
    input_standard_status = models.CharField(max_length=24, choices=(('PENDING_CONFIRMATION', '待确认'),))
    capacity_measurement_status = models.CharField(max_length=16, choices=(('UNMEASURED', '尚未测定'),))
    producer_rule = models.ForeignKey('EngineeringRuleDefinition', null=True, blank=True, on_delete=models.PROTECT, related_name='input_preparations')
    manufacturing_mode = models.ForeignKey('ManufacturingMode', null=True, blank=True, on_delete=models.PROTECT, related_name='input_preparations')
    work_center = models.ForeignKey('WorkCenter', null=True, blank=True, on_delete=models.PROTECT, related_name='input_preparations')
    standard_capacity = models.ForeignKey('StandardCapacity', null=True, blank=True, on_delete=models.PROTECT, related_name='input_preparations')
    draft_selection = models.JSONField(null=True, blank=True)
    business_basis = models.JSONField()
    revision = models.PositiveIntegerField(default=1)
    content_hash = models.CharField(max_length=64)
    creation_write_request = models.OneToOneField('masterdata.MasterDataWriteRequest', on_delete=models.PROTECT, related_name='operation_input_preparation')
    created_by = models.ForeignKey('system.User', on_delete=models.PROTECT, related_name='created_operation_input_preparations')
    updated_by = models.ForeignKey('system.User', on_delete=models.PROTECT, related_name='updated_operation_input_preparations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pde_operation_input_preparation_draft'
        default_permissions = ()
        ordering = ('production_plan_id', 'routing_step_id', 'pk')
        constraints = [
            models.UniqueConstraint(fields=('company', 'operation', 'product_type', 'production_plan',
                'manufacturing_output', 'main_calculation', 'engineering_baseline', 'routing_version',
                'routing_step'), name='pde_opprep_real_scope_uniq'),
            models.CheckConstraint(condition=models.Q(status='draft', input_standard_status='PENDING_CONFIRMATION',
                capacity_measurement_status='UNMEASURED'), name='pde_opprep_states_valid'),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name='pde_opprep_revision_positive'),
            models.CheckConstraint(condition=(~models.Q(context_hash='') & ~models.Q(objects_hash='')
                & ~models.Q(content_hash='')), name='pde_opprep_hashes_required'),
        ]
        indexes = [models.Index(fields=('company', 'production_plan', 'routing_step'), name='pde_opprep_plan_step_idx')]

    def save(self, *args, **kwargs):
        from .operation_input_preparation_service import _write_guard, validate_model_record
        if not _write_guard.get():
            raise ValidationError('工序投入准备只能通过专用原生服务保存。')
        if self._state.adding and not getattr(self, '_business_state_initialization_authorized', False):
            raise ValidationError('准备草稿初始状态必须由统一初始化服务创建。')
        validate_model_record(self)
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('工序投入准备记录不可删除。')

class CRMOrderVersionCarryForward(models.Model):
    """Append-only evidence carrying an original CRM relation to an approved order version."""

    company = models.ForeignKey("system.Company", on_delete=models.PROTECT)
    relation = models.ForeignKey(OrderReviewSalesOrderRelation, on_delete=models.PROTECT)
    sales_order = models.ForeignKey("sales.SalesOrder", on_delete=models.PROTECT)
    original_version = models.PositiveIntegerField()
    target_version = models.PositiveIntegerField()
    content_snapshot = models.JSONField()
    content_hash = models.CharField(max_length=64)
    source_fingerprint = models.CharField(max_length=64)
    scope_fingerprint = models.CharField(max_length=64)
    version_differences = models.JSONField()
    validation_results = models.JSONField()
    approval_evidence = models.JSONField()
    created_by = models.ForeignKey("system.User", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("relation", "target_version", "content_hash"),
                name="pde_crm_carry_version_hash_unique",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("关系版本承接证明为只追加记录。")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("关系版本承接证明不允许删除。")


class DesignRevisionApproval(models.Model):
    """Exact revision approval; source nature is independent of business approval."""
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT)
    sales_order_item = models.ForeignKey("sales.SalesOrderItem", on_delete=models.PROTECT)
    engineering_instance = models.ForeignKey(OrderEngineeringInstance, on_delete=models.PROTECT)
    source_revision = models.ForeignKey(ProductDesignRevision, on_delete=models.PROTECT, related_name="approval_requests")
    source_record = models.ForeignKey(EngineeringSourceRecord, on_delete=models.PROTECT)
    source_version = models.CharField(max_length=120)
    source_hash = models.CharField(max_length=64)
    content_snapshot = models.JSONField()
    content_hash = models.CharField(max_length=64)
    origin_nature = models.CharField(max_length=32)
    approval_scope = models.CharField(max_length=32)
    applicant = models.ForeignKey("system.User", on_delete=models.PROTECT, related_name="design_approval_applications")
    process_definition = models.ForeignKey("workflow_runtime.ProcessDefinition", on_delete=models.PROTECT)
    process_version = models.PositiveIntegerField()
    process_hash = models.CharField(max_length=64)
    workflow_instance = models.OneToOneField("workflow_runtime.WorkflowInstance", on_delete=models.PROTECT, null=True, blank=True)
    final_decision = models.OneToOneField("workflow_runtime.ApprovalDecision", on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=24)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pde_design_revision_approval"

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.get(pk=self.pk)
            immutable = ("company_id", "sales_order_item_id", "engineering_instance_id", "source_revision_id", "source_record_id", "source_version", "source_hash", "content_snapshot", "content_hash", "origin_nature", "approval_scope", "applicant_id", "process_definition_id", "process_version", "process_hash")
            if any(getattr(old, key) != getattr(self, key) for key in immutable):
                raise ValidationError("批准申请冻结事实不可修改。")
            if old.final_decision_id and old.final_decision_id != self.final_decision_id:
                raise ValidationError("最终决定引用不可替换。")
            if old.workflow_instance_id and old.workflow_instance_id != self.workflow_instance_id:
                raise ValidationError("流程实例引用不可替换。")
            if old.status != self.status and not getattr(self, "_business_state_transition_authorized", False):
                raise ValidationError("批准状态必须通过统一转换服务。")
        elif not getattr(self, "_business_state_initialization_authorized", False):
            raise ValidationError("批准申请必须通过统一初始化服务。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("批准申请及决定历史不得删除。")


class TestEngineeringRoutingBinding(models.Model):
    """Immutable test-engineering reference, never a manufacturing release."""
    company = models.ForeignKey('system.Company', on_delete=models.PROTECT)
    bom_version = models.OneToOneField(BOMVersion, on_delete=models.PROTECT, related_name='test_routing_binding')
    source_calculation = models.ForeignKey(EngineeringCalculationRecord, on_delete=models.PROTECT)
    routing_version = models.ForeignKey(RoutingVersion, on_delete=models.PROTECT)
    usage_purpose = models.CharField(max_length=24, editable=False)
    preview_hash = models.CharField(max_length=64)
    source_proof = models.JSONField()
    step_plan = models.JSONField()
    created_by = models.ForeignKey('system.User', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pde_test_engineering_routing_binding'
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=models.Q(usage_purpose='TEST_BUSINESS'), name='pde_test_route_purpose_required')]

    def clean(self):
        if (self.usage_purpose != 'TEST_BUSINESS' or self.bom_version.usage_purpose != 'TEST_BUSINESS'
                or self.bom_version.status != 'draft' or self.source_calculation.scope != 'test_business'
                or self.company_id != self.source_calculation.company_id
                or self.bom_version.bom.company_id != self.company_id
                or self.bom_version.bom.source_calculation_id != self.source_calculation_id):
            raise ValidationError('测试路线绑定须保持同公司、完整测试来源及草稿用途。')

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('固定路线引用不可覆盖，请保留历史并使用新BOM版本。')
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('固定路线来源历史不得删除。')


from .order_routing_models import OrderRoutingExecutionArrangement, OrderRoutingExecutionDecision

from .work_center_responsibility_models import WorkCenterResponsibilityScope


class ManufacturingTimePolicyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('制造时间版本必须通过原生维护服务保存。')

    def delete(self):
        raise ValidationError('制造时间版本和历史不得删除。')

    def bulk_create(self, *args, **kwargs):
        raise ValidationError('制造时间版本不得绕过原生初始化服务。')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('制造时间版本不得批量改写。')

class ManufacturingTimePolicyNameOptionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('参考名称只能通过原工作制度维护服务逐项保存。')

    def bulk_create(self, *args, **kwargs):
        raise ValidationError('参考名称不得绕过原生维护证明批量写入。')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('参考名称不得绕过原生维护证明批量改写。')

    def delete(self):
        raise ValidationError('参考名称不得物理删除，请停用。')

# Restored mappings to existing native policy tables; no schema write.
class ManufacturingTimePolicyNameOption(models.Model):
    """Company reference text only; no calendar, capacity or approval meaning."""
    company = models.ForeignKey('system.Company', on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = ManufacturingTimePolicyNameOptionQuerySet.as_manager()

    class Meta:
        db_table = 'pde_manufacturing_time_policy_name_option'
        default_permissions = ()
        ordering = ('company_id', 'sort_order', 'pk')
        constraints = [
            models.UniqueConstraint(fields=('company', 'name'), name='pde_timepolicy_name_company_unique'),
            models.CheckConstraint(condition=models.Q(version__gte=1), name='pde_timepolicy_name_version_valid'),
            models.CheckConstraint(condition=models.Q(sort_order__gte=0), name='pde_timepolicy_name_sort_valid'),
            models.CheckConstraint(condition=~models.Q(name=''), name='pde_timepolicy_name_required'),
        ]

    def save(self, *args, **kwargs):
        from .manufacturing_time_policy_service import _name_write_guard
        if not _name_write_guard.get():
            raise ValidationError('参考名称只能通过原工作制度维护服务保存。')
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('参考名称不得物理删除，请停用。')

class ManufacturingTimePolicyRevision(models.Model):
    """One append-only production-time authority, separate from legacy facts."""
    class Kind(models.TextChoices):
        SHARED_ARRANGEMENT = 'SHARED_ARRANGEMENT', '共用工作安排'
        WC_APPLICATION = 'WC_APPLICATION', '工作中心适用'
        OPERATION_RESTRICTION = 'OPERATION_RESTRICTION', '工序时间限制'
        CAPACITY_TIME_BASIS = 'CAPACITY_TIME_BASIS', '产能时间依据'

    company = models.ForeignKey('system.Company', on_delete=models.PROTECT)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=160)
    revision = models.PositiveIntegerField(default=1)
    version = models.PositiveIntegerField(default=1)
    scope_key = models.CharField(max_length=64)
    predecessor = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='successors')
    shared_version = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='policy_applications')
    work_center = models.ForeignKey('WorkCenter', null=True, blank=True, on_delete=models.PROTECT,
        related_name='time_policy_revisions')
    operation = models.ForeignKey('system.Process', null=True, blank=True, on_delete=models.PROTECT,
        related_name='time_policy_revisions')
    standard_capacity = models.ForeignKey('StandardCapacity', null=True, blank=True, on_delete=models.PROTECT,
        related_name='time_policy_revisions')
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=(('draft', '待完善'), ('confirmed', '已确认')),
        default='draft')
    schema_version = models.CharField(max_length=64, default='PCE-MANUFACTURING-TIME-POLICY-V1')
    payload = models.JSONField(default=dict, blank=True)
    reference_snapshot = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64)
    confirmation_basis = models.CharField(max_length=1000, blank=True, default='')
    creation_write_request = models.OneToOneField('masterdata.MasterDataWriteRequest',
        on_delete=models.PROTECT, related_name='created_time_policy_revision')
    confirmation_write_request = models.OneToOneField('masterdata.MasterDataWriteRequest',
        null=True, blank=True, on_delete=models.PROTECT, related_name='confirmed_time_policy_revision')
    confirmation_audit = models.ForeignKey('system.OrganizationOperatingAuditRecord',
        null=True, blank=True, on_delete=models.PROTECT, related_name='confirmed_time_policies')
    created_by = models.ForeignKey('system.User', on_delete=models.PROTECT,
        related_name='created_time_policies')
    updated_by = models.ForeignKey('system.User', on_delete=models.PROTECT,
        related_name='updated_time_policies')
    confirmed_by = models.ForeignKey('system.User', null=True, blank=True, on_delete=models.PROTECT,
        related_name='confirmed_time_policies')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = ManufacturingTimePolicyQuerySet.as_manager()

    class Meta:
        db_table = 'pde_manufacturing_time_policy_revision'
        default_permissions = ()
        ordering = ('company_id', 'kind', 'scope_key', 'revision')
        constraints = [
            models.CheckConstraint(condition=models.Q(kind__in=(
                'SHARED_ARRANGEMENT', 'WC_APPLICATION', 'OPERATION_RESTRICTION', 'CAPACITY_TIME_BASIS')),
                name='pde_timepolicy_kind_valid'),
            models.CheckConstraint(condition=(
                models.Q(kind='SHARED_ARRANGEMENT', work_center__isnull=True, operation__isnull=True,
                    standard_capacity__isnull=True, shared_version__isnull=True)
                | models.Q(kind='WC_APPLICATION', work_center__isnull=False, operation__isnull=True,
                    standard_capacity__isnull=True, shared_version__isnull=False)
                | models.Q(kind='OPERATION_RESTRICTION', operation__isnull=False,
                    standard_capacity__isnull=True, shared_version__isnull=True)
                | models.Q(kind='CAPACITY_TIME_BASIS', work_center__isnull=True, operation__isnull=True,
                    standard_capacity__isnull=False)), name='pde_timepolicy_scope_valid'),
            models.CheckConstraint(condition=models.Q(status__in=('draft', 'confirmed')),
                name='pde_timepolicy_state_valid'),
            models.CheckConstraint(condition=models.Q(revision__gte=1, version__gte=1),
                name='pde_timepolicy_versions_valid'),
            models.CheckConstraint(condition=(models.Q(effective_from__isnull=True)
                | models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F('effective_from'))),
                name='pde_timepolicy_period_valid'),
            models.CheckConstraint(condition=(models.Q(status='draft') | models.Q(
                effective_from__isnull=False, confirmed_by__isnull=False, confirmed_at__isnull=False,
                confirmation_audit__isnull=False, confirmation_write_request__isnull=False)),
                name='pde_timepolicy_confirm_proven'),
            models.CheckConstraint(condition=(~models.Q(content_hash='') & ~models.Q(scope_key='')),
                name='pde_timepolicy_hash_required'),
            models.UniqueConstraint(fields=('company', 'kind', 'scope_key', 'revision'),
                name='pde_timepolicy_scope_revision'),
            models.UniqueConstraint(fields=('predecessor',), condition=models.Q(predecessor__isnull=False),
                name='pde_timepolicy_single_successor'),
        ]
        indexes = [models.Index(fields=('company', 'kind', 'status', 'scope_key'), name='pde_timepolicy_scope_idx')]

    def clean(self):
        from .manufacturing_time_policy_service import validate_model_record
        validate_model_record(self)

    def save(self, *args, **kwargs):
        from .manufacturing_time_policy_service import _write_guard
        if not _write_guard.get():
            raise ValidationError('制造时间版本只能由专用原生服务保存。')
        if self._state.adding and not getattr(self, '_business_state_initialization_authorized', False):
            raise ValidationError('制造时间版本初始状态必须由统一初始化服务创建。')
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and old.status == 'confirmed':
                raise ValidationError('已确认制造时间版本不可覆盖，只能追加修订。')
            if old and old.status != self.status and not getattr(self, '_business_state_transition_authorized', False):
                raise ValidationError('确认状态必须通过统一状态转换服务。')
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('制造时间版本和历史不得删除。')
