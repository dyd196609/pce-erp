from django.conf import settings
from django.db import models


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
    ]

    demand_no = models.CharField(max_length=80, unique=True)
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
    required_qty = models.DecimalField(max_digits=18, decimal_places=4)
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
                fields=["sales_order_item", "manufacturing_output"],
                condition=models.Q(sales_order_item__isnull=False, manufacturing_output__isnull=False),
                name="planning_demand_item_output_unique",
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
        errors = {}
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
