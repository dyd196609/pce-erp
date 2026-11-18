from django.conf import settings
from django.db import models


class SchedulingCompanyMutex(models.Model):
    """Separate writer-lock row; never revises a historical engineering object."""
    company = models.OneToOneField("system.Company", on_delete=models.PROTECT)
    revision = models.PositiveBigIntegerField(default=0)

    class Meta:
        db_table = "planning_scheduling_company_mutex"


class FormalProductionSchedule(models.Model):
    STATUS_CHOICES = (("draft", "保存准备"), ("saved", "已保存正式排程"), ("cancelled", "已撤销并释放占用"))
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT)
    production_plan = models.ForeignKey("planning.ProductionPlan", on_delete=models.PROTECT, related_name="formal_schedules", null=True, blank=True)
    usage_purpose = models.CharField(max_length=20, default="UNCLASSIFIED")
    execution_arrangement = models.ForeignKey("pde.OrderRoutingExecutionArrangement", on_delete=models.PROTECT, null=True, blank=True)
    revision = models.PositiveIntegerField()
    version = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    saved_start_date = models.DateField()
    timezone = models.CharField(max_length=80)
    snapshot = models.JSONField()
    snapshot_hash = models.CharField(max_length=64)
    admission_token = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    request_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    cancel_idempotency_key = models.CharField(max_length=120, blank=True, default="")
    cancel_request_hash = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "planning_formal_production_schedule"
        constraints = [
            models.UniqueConstraint(fields=("company", "idempotency_key"), name="formal_schedule_company_idem"),
            models.UniqueConstraint(fields=("production_plan", "revision"), name="formal_schedule_plan_revision"),
            models.UniqueConstraint(fields=("production_plan",), condition=models.Q(status="saved"), name="formal_schedule_one_saved_plan"),
            models.CheckConstraint(condition=models.Q(end_at__gte=models.F("start_at")), name="formal_schedule_valid_window"),
            models.CheckConstraint(condition=(models.Q(usage_purpose="PRODUCTION_USE",production_plan__isnull=False,execution_arrangement__isnull=True) | models.Q(usage_purpose="TEST_BUSINESS",production_plan__isnull=True,execution_arrangement__isnull=False) | models.Q(usage_purpose="UNCLASSIFIED",execution_arrangement__isnull=True)),name="schedule_purpose_source_branch"),
            models.UniqueConstraint(fields=("execution_arrangement","revision"),name="test_schedule_arr_revision"),
            models.UniqueConstraint(fields=("execution_arrangement",),condition=models.Q(status="saved",usage_purpose="TEST_BUSINESS"),name="test_schedule_one_saved_arr"),
        ]

    def save(self, *args, **kwargs):
        if self._state.adding:
            if not getattr(self, "_business_state_initialization_authorized", False):
                raise ValueError("Formal schedule initialization requires the native state service")
        elif not getattr(self, "_business_state_transition_authorized", False):
            raise ValueError("Formal schedules are immutable except native state transitions")
        return super().save(*args, **kwargs)


class ProcessingReservation(models.Model):
    schedule = models.ForeignKey(FormalProductionSchedule, on_delete=models.PROTECT, related_name="reservations")
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT)
    work_center = models.ForeignKey("pde.WorkCenter", on_delete=models.PROTECT)
    routing_step = models.ForeignKey("pde.RoutingStep", on_delete=models.PROTECT)
    sequence = models.PositiveIntegerField()
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    production_date = models.DateField()
    # Native microsecond boundaries can yield repeating decimal minutes. Keep
    # the proved decimal verbatim rather than quantizing a saved reservation.
    minutes = models.CharField(max_length=100)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "planning_processing_reservation"
        constraints = [models.CheckConstraint(condition=models.Q(end_at__gt=models.F("start_at")), name="processing_reservation_positive_window")]
        indexes = [models.Index(fields=("company", "work_center", "released_at", "start_at", "end_at"), name="processing_reservation_lookup")]


class ScheduleCapacityGrant(models.Model):
    """Append-only exact plan/step use; the old no-date proof is never amended."""
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT)
    production_plan = models.ForeignKey("planning.ProductionPlan", on_delete=models.PROTECT)
    standard_capacity = models.ForeignKey("pde.StandardCapacity", on_delete=models.PROTECT)
    exact_scope = models.JSONField()
    reference_hash = models.CharField(max_length=64)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    instruction_reference = models.CharField(max_length=500)
    payload = models.JSONField()
    content_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120)
    request_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "planning_schedule_capacity_grant"
        constraints = [models.UniqueConstraint(fields=("company", "idempotency_key"), name="schedule_scope_company_idem")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Formal scheduling capacity grants are append-only")
        return super().save(*args, **kwargs)


class Demand(models.Model):
    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("confirmed", "已确认"),
        ("closed", "已关闭"),
    ]
    SOURCE_TYPE_CHOICES = [
        ("manual_demand", "人工计划需求"),
        ("purchase_request", "采购申请"),
        ("sales_order", "销售订单"),
        ("production_material", "正式生产用料"),
    ]

    demand_no = models.CharField(max_length=80, unique=True)
    batch_key = models.CharField(max_length=80, blank=True, default="")
    batch_scope = models.JSONField(default=dict, blank=True)
    source_type = models.CharField(max_length=32, choices=SOURCE_TYPE_CHOICES)
    source_document_type = models.CharField(max_length=80)
    source_document_id = models.CharField(max_length=80)
    source_document_no = models.CharField(max_length=80)
    sales_order_item = models.ForeignKey(
        "sales.SalesOrderItem", on_delete=models.PROTECT, null=True, blank=True,
        related_name="planning_demands",
    )
    product_definition = models.ForeignKey(
        "pde.ProductDefinition", on_delete=models.PROTECT, null=True, blank=True,
        related_name="planning_demands", verbose_name="产品工程定义",
    )
    product_version = models.ForeignKey(
        "pde.ProductVersion", on_delete=models.PROTECT, null=True, blank=True,
        related_name="planning_demands", verbose_name="产品版本",
    )
    manufacturing_output = models.ForeignKey(
        "pde.ProductManufacturingOutput", on_delete=models.PROTECT, null=True, blank=True,
        related_name="planning_demands", verbose_name="工程发布组合",
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, related_name="planning_demands"
    )
    from .fields import ExactDemandQuantityField
    required_qty = ExactDemandQuantityField(max_digits=20, decimal_places=6)
    required_date = models.DateField()
    department = models.ForeignKey(
        "system.Department", on_delete=models.PROTECT, related_name="planning_demands"
    )
    reason = models.CharField(max_length=300)
    acceptance_marker = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_planning_demands"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "planning_demand"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["sales_order_item", "manufacturing_output", "batch_key"],
                condition=models.Q(sales_order_item__isnull=False, manufacturing_output__isnull=False),
                name="planning_demand_item_output_batch_unique",
            ),
            models.UniqueConstraint(
                fields=["sales_order_item"],
                condition=models.Q(sales_order_item__isnull=False, manufacturing_output__isnull=True),
                name="planning_demand_item_unversioned_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(required_qty__gt=0), name="planning_demand_qty_positive"
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.source_type != 'production_material':
            from decimal import Decimal, InvalidOperation
            from django.core.validators import DecimalValidator
            if isinstance(self.required_qty, Decimal):
                try:
                    old = self.required_qty.quantize(Decimal('.0001'))
                    if old != self.required_qty:
                        raise ValueError()
                    loaded = getattr(self, '_loaded_quantity_representation', None)
                    original_read = loaded is not None and loaded == self.required_qty.as_tuple()
                    DecimalValidator(18,4)(old if original_read else self.required_qty)
                except (InvalidOperation, ValueError, ValidationError):
                    errors['required_qty'] = '旧来源仍限原14位整数及4位小数，不得套用新来源精度。'
        if self.sales_order_item_id:
            item = self.sales_order_item
            if self.material_id != item.material_id:
                errors["material"] = "计划需求物料必须与销售订单行一致"
        if self.product_definition_id:
            if not self.product_version_id or not self.manufacturing_output_id:
                errors["manufacturing_output"] = "制造型需求必须保留产品版本和工程发布来源"
            elif self.manufacturing_output.release_status != "released_to_manufacturing":
                errors["manufacturing_output"] = "未发布工程组合不得进入新计划需求"
            elif self.manufacturing_output.product_id != self.product_definition_id:
                errors["product_definition"] = "需求产品必须与工程发布组合一致"
            elif self.manufacturing_output.product_version_id != self.product_version_id:
                errors["product_version"] = "需求产品版本必须与工程发布组合一致"
        if self.manufacturing_output_id and self.manufacturing_output.release_subject_type == "ORDER_ENGINEERED_PRODUCT":
            if not self.sales_order_item_id or self.product_definition_id or self.product_version_id:
                errors["manufacturing_output"] = "订单工程需求必须引用订单行，且不得伪造长期产品或产品版本"
            else:
                from sales.manufacturing_input import ManufacturingInputError, resolve_order_engineered_input
                try:
                    resolved = resolve_order_engineered_input(
                        self.sales_order_item, output_id=self.manufacturing_output_id,
                    )
                    if resolved["output"].pk != self.manufacturing_output_id:
                        errors["manufacturing_output"] = "需求制造输出必须与同一订单行正式工程来源链一致"
                except ManufacturingInputError as exc:
                    errors["manufacturing_output"] = exc.message
        if errors:
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        if 'required_qty' in field_names:
            instance._loaded_quantity_representation = instance.required_qty.as_tuple()
        return instance

    @property
    def quantity_text(self):
        from decimal import Decimal
        value=self.required_qty
        if self.source_type == 'production_material':
            return format(value,'.6f')
        if value != value.quantize(Decimal('.0001')):
            from django.core.exceptions import ValidationError
            raise ValidationError('旧来源数量违反原4位精度合同，禁止截断显示。')
        return str(value.quantize(Decimal('.0001'))) if value.as_tuple().exponent < -4 else str(value)


class MasterProductionScheduleRun(models.Model):
    STATUS_CHOICES = [("proposed", "建议待复核"), ("reviewed", "已人工复核")]

    run_no = models.CharField(max_length=80, unique=True)
    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT, related_name="mps_runs"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="proposed")
    request_id = models.CharField(max_length=160)
    idempotency_key = models.CharField(max_length=160)
    source_version = models.CharField(max_length=40, default="ORDER-MPS-V1")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_mps_runs"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "planning_mps_run"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "idempotency_key"], name="uniq_mps_company_idempotency"
            ),
            models.UniqueConstraint(
                fields=["company", "request_id"], name="uniq_mps_company_request"
            ),
        ]


class MasterProductionScheduleLine(models.Model):
    run = models.ForeignKey(
        MasterProductionScheduleRun, on_delete=models.PROTECT, related_name="lines"
    )
    line_no = models.PositiveIntegerField()
    product_definition = models.ForeignKey(
        "pde.ProductDefinition", on_delete=models.PROTECT, null=True, blank=True,
        related_name="mps_lines",
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, related_name="mps_lines"
    )
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="mps_lines",
    )
    required_date = models.DateField()
    total_qty = models.DecimalField(max_digits=18, decimal_places=4)
    engineering_mode = models.CharField(max_length=24)
    status = models.CharField(max_length=20, default="proposed")

    class Meta:
        db_table = "planning_mps_line"
        ordering = ["run_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["run", "line_no"], name="uniq_mps_run_line"),
            models.CheckConstraint(condition=models.Q(total_qty__gt=0), name="mps_line_qty_positive"),
        ]


class MPSDemandAllocation(models.Model):
    mps_line = models.ForeignKey(
        MasterProductionScheduleLine, on_delete=models.PROTECT, related_name="demand_allocations"
    )
    demand = models.OneToOneField(
        Demand, on_delete=models.PROTECT, related_name="mps_allocation"
    )
    allocated_qty = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        db_table = "planning_mps_demand_allocation"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(allocated_qty__gt=0), name="mps_allocation_qty_positive"
            )
        ]


class MaterialRequirementsPlanningRun(models.Model):
    STATUS_CHOICES = [("proposed", "建议待复核"), ("blocked", "存在阻断")]

    run_no = models.CharField(max_length=80, unique=True)
    company = models.ForeignKey(
        "system.Company", on_delete=models.PROTECT, related_name="mrp_runs"
    )
    mps_run = models.OneToOneField(
        MasterProductionScheduleRun, on_delete=models.PROTECT, related_name="mrp_run"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="proposed")
    request_id = models.CharField(max_length=160)
    idempotency_key = models.CharField(max_length=160)
    source_version = models.CharField(max_length=40, default="ORDER-MRP-V1")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_mrp_runs"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "planning_mrp_run"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "idempotency_key"], name="uniq_mrp_company_idempotency"
            ),
            models.UniqueConstraint(
                fields=["company", "request_id"], name="uniq_mrp_company_request"
            ),
        ]


class MaterialRequirementProposal(models.Model):
    SUPPLY_TYPE_CHOICES = [("MAKE", "自制"), ("BUY", "外购"), ("UNRESOLVED", "待解析")]
    STATUS_CHOICES = [("proposed", "建议待复核"), ("blocked", "已阻断")]

    mrp_run = models.ForeignKey(
        MaterialRequirementsPlanningRun, on_delete=models.PROTECT, related_name="proposals"
    )
    line_no = models.PositiveIntegerField()
    mps_line = models.ForeignKey(
        MasterProductionScheduleLine, on_delete=models.PROTECT, related_name="mrp_proposals"
    )
    demand = models.ForeignKey(Demand, on_delete=models.PROTECT, related_name="mrp_proposals")
    product_definition = models.ForeignKey(
        "pde.ProductDefinition", on_delete=models.PROTECT, null=True, blank=True,
        related_name="mrp_proposals",
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, related_name="mrp_proposals"
    )
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="mrp_proposals",
    )
    source_bom_version = models.ForeignKey(
        "pde.BOMVersion", on_delete=models.PROTECT, null=True, blank=True,
        related_name="mrp_proposals",
    )
    source_bom_item = models.ForeignKey(
        "pde.BOMItem", on_delete=models.PROTECT, null=True, blank=True,
        related_name="mrp_proposals",
    )
    required_qty = models.DecimalField(max_digits=18, decimal_places=4)
    current_inventory = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    allocated_inventory = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    net_requirement = models.DecimalField(max_digits=18, decimal_places=4)
    required_date = models.DateField()
    supply_type = models.CharField(max_length=20, choices=SUPPLY_TYPE_CHOICES)
    suggested_action = models.CharField(max_length=80)
    inventory_status = models.CharField(max_length=32, default="INTEGRATED")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="proposed")
    block_reason = models.CharField(max_length=300, blank=True, default="")
    trace_facts = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "planning_mrp_proposal"
        ordering = ["mrp_run_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["mrp_run", "line_no"], name="uniq_mrp_run_line"),
            models.CheckConstraint(condition=models.Q(required_qty__gt=0), name="mrp_required_qty_positive"),
            models.CheckConstraint(condition=models.Q(net_requirement__gte=0), name="mrp_net_qty_nonnegative"),
        ]


class PlanningRequirement(models.Model):
    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("calculated", "已计算"),
        ("confirmed", "已确认"),
        ("closed", "已关闭"),
    ]
    SUPPLY_TYPE_CHOICES = [
        ("purchase", "采购"),
        ("production", "自制"),
        ("ambiguous", "待确认"),
    ]

    requirement_no = models.CharField(max_length=80, unique=True)
    demand = models.OneToOneField(
        Demand, on_delete=models.PROTECT, related_name="planning_requirement"
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, related_name="planning_requirements"
    )
    demand_qty = models.DecimalField(max_digits=18, decimal_places=4)
    available_qty = models.DecimalField(max_digits=18, decimal_places=4)
    net_required_qty = models.DecimalField(max_digits=18, decimal_places=4)
    required_date = models.DateField()
    supply_type = models.CharField(max_length=20, choices=SUPPLY_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="calculated")
    calculation_facts = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_planning_requirements"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "planning_requirement"
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(demand_qty__gt=0), name="planning_requirement_demand_qty_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(available_qty__gte=0), name="planning_requirement_available_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(net_required_qty__gte=0), name="planning_requirement_net_nonnegative"
            ),
        ]


class PurchasePlan(models.Model):
    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("confirmed", "已确认"),
        ("released", "已下达"),
        ("closed", "已关闭"),
    ]

    plan_no = models.CharField(max_length=80, unique=True)
    planning_requirement = models.OneToOneField(
        PlanningRequirement, on_delete=models.PROTECT, related_name="purchase_plan"
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, related_name="purchase_plans"
    )
    required_qty = models.DecimalField(max_digits=18, decimal_places=4)
    available_qty = models.DecimalField(max_digits=18, decimal_places=4)
    net_required_qty = models.DecimalField(max_digits=18, decimal_places=4)
    required_date = models.DateField()
    source_type = models.CharField(max_length=80, default="PlanningRequirement")
    source_id = models.CharField(max_length=80)
    planning_engine = models.CharField(max_length=40, default="DIRECT_V1")
    run_batch = models.CharField(max_length=80, blank=True, default="")
    source_version = models.CharField(max_length=40, default="DIRECT-V1")
    mps_source_id = models.CharField(max_length=80, blank=True, default="")
    mrp_source_id = models.CharField(max_length=80, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="confirmed")
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="confirmed_purchase_plans"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "planning_purchase_plan"
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(net_required_qty__gt=0), name="planning_purchase_plan_qty_positive"
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.planning_engine == "DIRECT_V1" and (self.mps_source_id or self.mrp_source_id):
            raise ValidationError("历史直接计划不得伪造MPS/MRP来源。")
        if self.planning_engine == "MPS_MRP_V1" and not (
            self.run_batch and self.mps_source_id and self.mrp_source_id
        ):
            raise ValidationError("未来MPS/MRP计划必须记录运行批次及稳定来源。")


class ProductionPlan(models.Model):
    STATUS_CHOICES = PurchasePlan.STATUS_CHOICES

    plan_no = models.CharField(max_length=80, unique=True)
    planning_requirement = models.OneToOneField(
        PlanningRequirement, on_delete=models.PROTECT, related_name="production_plan"
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, related_name="production_plans"
    )
    planned_qty = models.DecimalField(max_digits=18, decimal_places=4)
    required_date = models.DateField()
    planned_start_date = models.DateField("计划开始日期", null=True, blank=True)
    source_type = models.CharField(max_length=80, default="PlanningRequirement")
    source_id = models.CharField(max_length=80)
    planning_engine = models.CharField(max_length=40, default="DIRECT_V1")
    run_batch = models.CharField(max_length=80, blank=True, default="")
    source_version = models.CharField(max_length=40, default="DIRECT-V1")
    mps_source_id = models.CharField(max_length=80, blank=True, default="")
    mrp_source_id = models.CharField(max_length=80, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="confirmed")
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="confirmed_production_plans"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "planning_production_plan"
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(planned_qty__gt=0), name="planning_production_plan_qty_positive"
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.planning_engine == "DIRECT_V1" and (self.mps_source_id or self.mrp_source_id):
            raise ValidationError("历史直接计划不得伪造MPS/MRP来源。")
        if self.planning_engine == "MPS_MRP_V1" and not (
            self.run_batch and self.mps_source_id and self.mrp_source_id
        ):
            raise ValidationError("未来MPS/MRP计划必须记录运行批次及稳定来源。")

# Existing physical MES tables, selectively loaded without replaying schema.
from .work_order_models import ProductionWorkOrder, ProductionWorkOrderOperation

from .work_order_workshop_receipt_models import ProductionWorkOrderWorkshopReceipt

from .workshop_task_models import ProductionWorkshopTask

from .operation_start_models import ProductionOperationStart

from .operation_report_models import ProductionOperationReport

from .operation_handover_models import OperationQuantityAccount, OperationOutputEvidence, OperationOutputAllocation, OperationCustodySlice, OperationHandover, OperationHandoverAllocation, OperationCustodyEvent, OperationCustodyException, OperationInputAllocation
from .operation_completion_generation_models import OperationCompletionGeneration
from .finished_goods_models import ProductionFinishedGoodsTransfer
