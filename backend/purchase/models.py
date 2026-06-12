from django.db import models


class PurchaseOrder(models.Model):
    DOCUMENT_STATUS_CHOICES = [
        ("draft", "草稿"),
        ("submitted", "已提交"),
        ("audited", "已审核"),
        ("reviewed", "已复核"),
        ("approved", "已审批"),
        ("rejected", "已驳回"),
        ("cancelled", "已作废"),
        ("closed", "已关闭"),
        ("finished", "已结案"),
    ]

    PROGRESS_STATUS_CHOICES = [
        ("not_started", "未开始"),
        ("arriving", "到货中"),
        ("arrived", "已到货"),
        ("inspecting", "检验中"),
        ("inspected", "已检验"),
        ("warehousing", "入库中"),
        ("warehoused", "已入库"),
        ("settling", "结算中"),
        ("settled", "已结算"),
        ("finished", "已结案"),
    ]

    URGENCY_CHOICES = [
        ("very_urgent", "特急"),
        ("urgent", "紧急"),
        ("normal", "一般"),
        ("loose", "宽松"),
        ("completed", "已完成"),
        ("no_plan", "未计划"),
    ]

    po_no = models.CharField(
        "采购订单号", max_length=50, unique=True, null=True, blank=True
    )
    supplier_name = models.CharField("供应商名称", max_length=100, blank=True)
    buyer_name = models.CharField("采购员", max_length=50, blank=True)

    purchase_department = models.CharField("物料申购部门", max_length=100, blank=True)
    require_department = models.CharField("物料需求部门", max_length=100, blank=True)

    order_date = models.DateField("下单日期", null=True, blank=True)
    expected_date = models.DateField("预计到货日期", null=True, blank=True)
    actual_receive_date = models.DateField("实际到货日期", null=True, blank=True)

    total_plan_amount = models.DecimalField(
        "计划总金额", max_digits=14, decimal_places=2, default=0
    )
    total_actual_amount = models.DecimalField(
        "实际总金额", max_digits=14, decimal_places=2, default=0
    )

    document_status = models.CharField(
        "单据状态",
        max_length=30,
        choices=DOCUMENT_STATUS_CHOICES,
        default="draft",
    )
    progress_status = models.CharField(
        "执行进度",
        max_length=30,
        choices=PROGRESS_STATUS_CHOICES,
        default="not_started",
    )
    urgency_level = models.CharField(
        "紧急程度",
        max_length=30,
        choices=URGENCY_CHOICES,
        default="normal",
    )

    is_on_time_delivery = models.BooleanField("是否准交达成", default=False)
    remark = models.TextField("备注", blank=True)

    created_at = models.DateTimeField(
        "创建时间", auto_now_add=True, null=True, blank=True
    )
    updated_at = models.DateTimeField("更新时间", auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "purchase_orders"
        ordering = ["-order_date", "-id"]
        verbose_name = "采购订单"
        verbose_name_plural = "采购订单"

    def __str__(self):
        return self.po_no


class PurchaseOrderItem(models.Model):
    order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="采购订单",
    )

    material_code = models.CharField("物料编码", max_length=50)
    material_name = models.CharField("物料名称", max_length=100)
    specification = models.CharField("规格型号", max_length=100, blank=True)
    unit = models.CharField("单位", max_length=20, blank=True)

    plan_quantity = models.DecimalField(
        "计划数量", max_digits=14, decimal_places=4, default=0
    )
    actual_quantity = models.DecimalField(
        "实际数量", max_digits=14, decimal_places=4, default=0
    )

    plan_unit_price = models.DecimalField(
        "计划单价", max_digits=14, decimal_places=4, default=0
    )
    actual_unit_price = models.DecimalField(
        "实际单价", max_digits=14, decimal_places=4, default=0
    )

    plan_amount = models.DecimalField(
        "计划金额", max_digits=14, decimal_places=2, default=0
    )
    actual_amount = models.DecimalField(
        "实际金额", max_digits=14, decimal_places=2, default=0
    )

    plan_delivery_date = models.DateField("计划交期", null=True, blank=True)
    actual_delivery_date = models.DateField("实际交期", null=True, blank=True)

    arrival_quantity = models.DecimalField(
        "到货数量", max_digits=14, decimal_places=4, default=0
    )
    qualified_quantity = models.DecimalField(
        "合格数量", max_digits=14, decimal_places=4, default=0
    )
    rejected_quantity = models.DecimalField(
        "不合格数量", max_digits=14, decimal_places=4, default=0
    )
    inbound_quantity = models.DecimalField(
        "入库数量", max_digits=14, decimal_places=4, default=0
    )

    settled_quantity = models.DecimalField(
        "已结算数量", max_digits=14, decimal_places=4, default=0
    )
    settled_amount = models.DecimalField(
        "已结算金额", max_digits=14, decimal_places=2, default=0
    )

    is_on_time_delivery = models.BooleanField("是否准交达成", default=False)
    remark = models.TextField("备注", blank=True)

    class Meta:
        db_table = "purchase_order_items"
        verbose_name = "采购订单明细"
        verbose_name_plural = "采购订单明细"

    def __str__(self):
        return f"{self.order.po_no} - {self.material_name}"


class PurchaseApprovalRecord(models.Model):
    APPROVAL_LEVEL_CHOICES = [
        ("audit", "审核"),
        ("review", "复核"),
        ("approve", "审批"),
    ]

    APPROVAL_RESULT_CHOICES = [
        ("pending", "待处理"),
        ("passed", "通过"),
        ("rejected", "驳回"),
    ]

    order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="approval_records",
        verbose_name="采购订单",
    )

    approval_level = models.CharField(
        "审批级别", max_length=30, choices=APPROVAL_LEVEL_CHOICES
    )
    approver_name = models.CharField("审批人", max_length=50, blank=True)
    approval_result = models.CharField(
        "审批结果",
        max_length=30,
        choices=APPROVAL_RESULT_CHOICES,
        default="pending",
    )
    approval_comment = models.TextField("审批意见", blank=True)
    approved_at = models.DateTimeField("审批时间", null=True, blank=True)

    created_at = models.DateTimeField(
        "创建时间", auto_now_add=True, null=True, blank=True
    )

    class Meta:
        db_table = "purchase_approval_records"
        verbose_name = "采购审批记录"
        verbose_name_plural = "采购审批记录"

    def __str__(self):
        return f"{self.order.po_no} - {self.get_approval_level_display()}"


class PurchaseExecutionRecord(models.Model):
    ACTION_TYPE_CHOICES = [
        ("arrival", "到货"),
        ("inspect", "检验"),
        ("inbound", "入库"),
        ("settle", "结算"),
        ("finish", "结案"),
        ("close", "关闭"),
        ("cancel", "作废"),
        ("restart", "重启"),
    ]

    order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="execution_records",
        verbose_name="采购订单",
    )
    item = models.ForeignKey(
        PurchaseOrderItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_records",
        verbose_name="采购订单明细",
    )

    action_type = models.CharField(
        "执行动作", max_length=30, choices=ACTION_TYPE_CHOICES
    )
    quantity = models.DecimalField("数量", max_digits=14, decimal_places=4, default=0)
    amount = models.DecimalField("金额", max_digits=14, decimal_places=2, default=0)

    operator_name = models.CharField("操作人", max_length=50, blank=True)
    action_date = models.DateField("执行日期", null=True, blank=True)
    remark = models.TextField("备注", blank=True)

    created_at = models.DateTimeField(
        "创建时间", auto_now_add=True, null=True, blank=True
    )

    class Meta:
        db_table = "purchase_execution_records"
        verbose_name = "采购执行记录"
        verbose_name_plural = "采购执行记录"

    def __str__(self):
        return f"{self.order.po_no} - {self.get_action_type_display()}"
