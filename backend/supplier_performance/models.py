from django.db import models
from workflow_runtime.state_models import BusinessStateManagedModel


class SupplierReconciliation(BusinessStateManagedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        INTERNAL_REVIEW = "internal_review", "内部审核中"
        SUPPLIER_CONFIRMING = "supplier_confirming", "供应商确认中"
        COMPLETED = "completed", "对账完成"

    reconciliation_no = models.CharField(max_length=80, unique=True)
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    period = models.CharField(max_length=7)
    purchase_order_ids = models.JSONField(default=list)
    receipt_ids = models.JSONField(default=list)
    inspection_ids = models.JSONField(default=list)
    warehouse_receipt_ids = models.JSONField(default=list)
    inventory_transaction_ids = models.JSONField(default=list)
    purchase_amount = models.DecimalField(max_digits=18, decimal_places=2)
    received_amount = models.DecimalField(max_digits=18, decimal_places=2)
    qualified_amount = models.DecimalField(max_digits=18, decimal_places=2)
    reconciliation_amount = models.DecimalField(max_digits=18, decimal_places=2)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    status = models.CharField(max_length=40, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_reconciliations"
        indexes = [models.Index(fields=["tenant_id", "batch_id", "period"])]


class BuyerPerformanceMetric(models.Model):
    metric_no = models.CharField(max_length=80, unique=True)
    buyer_id = models.CharField(max_length=80)
    buyer_name = models.CharField(max_length=160)
    period = models.CharField(max_length=7)
    purchase_order_count = models.PositiveIntegerField()
    on_time_purchase_rate = models.DecimalField(max_digits=7, decimal_places=2)
    price_optimization_rate = models.DecimalField(max_digits=7, decimal_places=2)
    supplier_issue_response_time = models.DecimalField(max_digits=10, decimal_places=2)
    process_compliance_rate = models.DecimalField(max_digits=7, decimal_places=2)
    overall_score = models.DecimalField(max_digits=7, decimal_places=2)
    source_purchase_order_ids = models.JSONField(default=list)
    difference_responsibility_count = models.PositiveIntegerField(default=0)
    supplier_issue_count = models.PositiveIntegerField(default=0)
    price_difference_count = models.PositiveIntegerField(default=0)
    delivery_delay_count = models.PositiveIntegerField(default=0)
    payable_confirmation_delay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_request_accuracy = models.DecimalField(max_digits=7, decimal_places=2, default=100)
    payment_request_timeliness_rate = models.DecimalField(max_digits=7, decimal_places=2, default=100)
    settlement_exception_rate = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    source_settlement_completion_nos = models.JSONField(default=list)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "buyer_performance_metrics"
        constraints = [
            models.UniqueConstraint(fields=["buyer_id", "period", "tenant_id"], name="uniq_buyer_metric_period")
        ]


class SupplierPerformanceMetric(models.Model):
    metric_no = models.CharField(max_length=80, unique=True)
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    period = models.CharField(max_length=7)
    delivery_on_time_rate = models.DecimalField(max_digits=7, decimal_places=2)
    quality_pass_rate = models.DecimalField(max_digits=7, decimal_places=2)
    price_trend_score = models.DecimalField(max_digits=7, decimal_places=2)
    service_score = models.DecimalField(max_digits=7, decimal_places=2)
    reconciliation_accuracy_rate = models.DecimalField(max_digits=7, decimal_places=2)
    overall_score = models.DecimalField(max_digits=7, decimal_places=2)
    source_reconciliation_ids = models.JSONField(default=list)
    completed_settlement_count = models.PositiveIntegerField(default=0)
    timely_payment_count = models.PositiveIntegerField(default=0)
    abnormal_settlement_count = models.PositiveIntegerField(default=0)
    source_settlement_completion_nos = models.JSONField(default=list)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "supplier_performance_metrics"
        constraints = [
            models.UniqueConstraint(fields=["supplier_id", "period", "tenant_id"], name="uniq_supplier_metric_period")
        ]


class SupplierReconciliationDifference(BusinessStateManagedModel):
    class DifferenceType(models.TextChoices):
        QUANTITY = "quantity_difference", "数量差异"
        QUALITY = "quality_difference", "质量差异"
        PRICE = "price_difference", "价格差异"
        AMOUNT = "amount_difference", "金额差异"
        DELIVERY = "delivery_difference", "交付差异"
        OTHER = "other_difference", "其他差异"

    class ResponsibilityType(models.TextChoices):
        SUPPLIER = "supplier", "供应商责任"
        BUYER = "buyer", "采购责任"
        WAREHOUSE = "warehouse", "仓库责任"
        QUALITY = "quality", "质量责任"
        UNKNOWN = "unknown", "待确认"

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        ANALYZING = "analyzing", "分析中"
        RESPONSIBILITY_CONFIRMED = "responsibility_confirmed", "责任已确认"
        SUPPLIER_COMMUNICATING = "supplier_communicating", "供应商沟通中"
        CLOSED = "closed", "已关闭"

    difference_no = models.CharField(max_length=80, unique=True)
    reconciliation_no = models.CharField(max_length=80)
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    buyer_id = models.CharField(max_length=80, blank=True)
    buyer_name = models.CharField(max_length=160, blank=True)
    difference_type = models.CharField(max_length=40, choices=DifferenceType.choices)
    difference_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    difference_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    responsibility_type = models.CharField(max_length=40, choices=ResponsibilityType.choices)
    occurred_at = models.DateField()
    source_object_refs = models.JSONField(default=dict)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    status = models.CharField(max_length=40, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_reconciliation_differences"
        indexes = [
            models.Index(
                fields=["tenant_id", "batch_id", "status"],
                name="supplier_di_tenant__a82_idx",
            ),
            models.Index(
                fields=["supplier_id", "occurred_at"],
                name="supplier_di_supplie_a82_idx",
            ),
        ]


class SupplierReconciliationConfirmation(BusinessStateManagedModel):
    class Status(models.TextChoices):
        WAITING_SUPPLIER = "waiting_supplier", "等待供应商确认"
        SUPPLIER_CONFIRMED = "supplier_confirmed", "供应商已确认"
        INTERNAL_VERIFIED = "internal_verified", "内部已复核"
        COMPLETED = "completed", "协同确认完成"

    confirmation_no = models.CharField(max_length=80, unique=True)
    difference_no = models.CharField(max_length=80, unique=True)
    supplier_id = models.CharField(max_length=80)
    supplier_response = models.CharField(max_length=40)
    supplier_comment = models.TextField(blank=True)
    confirmed_by = models.CharField(max_length=160, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    status = models.CharField(max_length=40, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_reconciliation_confirmations"
        indexes = [
            models.Index(
                fields=["tenant_id", "batch_id", "status"],
                name="supplier_co_tenant__a82_idx",
            )
        ]


class SupplierPayableConfirmation(BusinessStateManagedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        INTERNAL_REVIEW = "internal_review", "内部审核中"
        CONFIRMED = "confirmed", "应付已确认"
        READY_FOR_PAYMENT_REQUEST = "ready_for_payment_request", "可申请付款"

    payable_confirmation_no = models.CharField(max_length=80, unique=True)
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    reconciliation_no = models.CharField(max_length=80)
    period = models.CharField(max_length=7)
    confirmed_amount = models.DecimalField(max_digits=18, decimal_places=2)
    qualified_amount = models.DecimalField(max_digits=18, decimal_places=2)
    deduction_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    final_payable_amount = models.DecimalField(max_digits=18, decimal_places=2)
    source_object_refs = models.JSONField(default=dict)
    tenant_id = models.CharField(max_length=64)
    legal_entity_id = models.CharField(max_length=80, default="LE-CANARY-001")
    batch_id = models.CharField(max_length=80)
    status = models.CharField(max_length=40, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_payable_confirmations"
        indexes = [
            models.Index(
                fields=["tenant_id", "batch_id", "status"],
                name="supplier_pc_tenant_v83_idx",
            )
        ]


class SupplierPaymentRequest(BusinessStateManagedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        SUBMITTED = "submitted", "已提交"
        APPROVED = "approved", "申请已批准"
        PAYMENT_PENDING = "payment_pending", "待后续付款处理"

    payment_request_no = models.CharField(max_length=80, unique=True)
    payable_confirmation_no = models.CharField(max_length=80, unique=True)
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    period = models.CharField(max_length=7)
    request_amount = models.DecimalField(max_digits=18, decimal_places=2)
    request_reason = models.CharField(max_length=255)
    requested_by = models.CharField(max_length=160)
    tenant_id = models.CharField(max_length=64)
    legal_entity_id = models.CharField(max_length=80, default="LE-CANARY-001")
    batch_id = models.CharField(max_length=80)
    status = models.CharField(max_length=40, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_payment_requests"
        indexes = [
            models.Index(
                fields=["tenant_id", "batch_id", "status"],
                name="supplier_pr_tenant_v83_idx",
            )
        ]


class SupplierPaymentStatusRecord(BusinessStateManagedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "待提交"
        SUBMITTED = "submitted", "审核中"
        APPROVED = "approved", "已批准"
        PAYMENT_SCHEDULED = "payment_scheduled", "付款安排中"
        PAYMENT_COMPLETED = "payment_completed", "付款完成"
        SETTLEMENT_COMPLETED = "settlement_completed", "结算完成"

    payment_request_no = models.CharField(max_length=80, unique=True)
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    payment_amount = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=40, choices=Status.choices)
    operator = models.CharField(max_length=160)
    operate_time = models.DateTimeField()
    remark = models.CharField(max_length=255, blank=True)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_payment_status_records"
        indexes = [
            models.Index(
                fields=["tenant_id", "batch_id", "status"],
                name="supplier_psr_tenant_v84_idx",
            )
        ]


class SupplierSettlementCompletion(BusinessStateManagedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "待确认"
        COMPLETED = "completed", "结算完成"

    settlement_no = models.CharField(max_length=80, unique=True)
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    reconciliation_no = models.CharField(max_length=80)
    payment_request_no = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=40, choices=Status.choices)
    completion_date = models.DateField(null=True, blank=True)
    performance_update_flag = models.BooleanField(default=False)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_settlement_completions"
        indexes = [
            models.Index(
                fields=["tenant_id", "batch_id", "status"],
                name="supplier_sc_tenant_v84_idx",
            )
        ]


class SupplierSettlementActionAudit(models.Model):
    action_no = models.CharField(max_length=80, unique=True)
    action_code = models.CharField(max_length=80)
    operator = models.ForeignKey(
        "system.User",
        on_delete=models.PROTECT,
        related_name="supplier_settlement_action_audits",
    )
    role = models.CharField(max_length=80)
    object_type = models.CharField(max_length=80)
    object_id = models.BigIntegerField()
    object_no = models.CharField(max_length=80)
    before_status = models.CharField(max_length=40)
    after_status = models.CharField(max_length=40)
    reason = models.CharField(max_length=240)
    source_object_type = models.CharField(max_length=80, blank=True, default="")
    source_object_no = models.CharField(max_length=80, blank=True, default="")
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    authorization_result = models.CharField(max_length=40, blank=True, default="")
    evidence = models.JSONField(default=dict)
    tenant_id = models.CharField(max_length=64)
    legal_entity_id = models.CharField(max_length=80)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "supplier_settlement_action_audits"
        indexes = [
            models.Index(
                fields=["object_type", "object_id", "timestamp"],
                name="supplier_sa_object_v831_idx",
            )
        ]
