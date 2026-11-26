from django.db import models
from django.utils import timezone
from datetime import date
from django.core.exceptions import ValidationError
import uuid


class ScmBusinessObjectBase(models.Model):
    """SCM前七节点共用的、行业无关的业务对象字段。"""

    items = models.JSONField(default=list, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def object_id(self):
        return self.pk

    @property
    def object_type(self):
        return self.__class__.__name__


class PurchaseRequest(ScmBusinessObjectBase):
    PURCHASE_MODE_CHOICES = [
        ("STANDARD", "标准采购"),
        ("AGREED_PRICE", "既定价格采购"),
        ("DIRECT", "直接采购"),
    ]
    STATUS_CHOICES = [
        ("draft", "草稿"), ("submitted", "已提交"), ("approved", "已审批"),
        ("converted", "已转换"), ("closed", "已关闭"),
    ]

    REQUEST_TYPE_CHOICES = [
        ("production", "生产需求"),
        ("stock_replenishment", "库存补充"),
        ("engineering", "工程需求"),
        ("equipment", "设备需求"),
        ("other", "其他需求"),
    ]
    SOURCE_TYPE_CHOICES = [
        ("PDEManufacturingInput", "PDE制造输入"),
        ("MRPRequirement", "MRP需求"),
        ("InventoryReplenishment", "库存补充"),
        ("ManualRequest", "人工申请"),
        ("PurchasePlan", "采购计划"),
    ]

    request_no = models.CharField(max_length=80, unique=True)
    request_date = models.DateField()
    requester = models.CharField(max_length=120)
    department = models.CharField(max_length=120)
    purchase_department = models.CharField(max_length=120, blank=True, default="")
    requester_employee_id = models.BigIntegerField(null=True, blank=True)
    requester_employee_no = models.CharField(max_length=50, blank=True, default="")
    department_master = models.ForeignKey(
        "system.Department", on_delete=models.PROTECT, null=True, blank=True,
        related_name="requested_purchase_requests",
    )
    usage_department_master = models.ForeignKey(
        "system.Department", on_delete=models.PROTECT, null=True, blank=True,
        related_name="used_purchase_requests",
    )
    usage_department = models.CharField(max_length=120, blank=True, default="")
    purchase_department_master = models.ForeignKey(
        "system.Department", on_delete=models.PROTECT, null=True, blank=True,
        related_name="managed_purchase_requests",
    )
    request_type = models.CharField(max_length=32, choices=REQUEST_TYPE_CHOICES, default="other")
    source_type = models.CharField(max_length=40, choices=SOURCE_TYPE_CHOICES, default="ManualRequest")
    project = models.ForeignKey(
        "masterdata.ProjectMaster", on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_requests",
    )
    project_code = models.CharField(max_length=64, blank=True, default="")
    project_name = models.CharField(max_length=200, blank=True, default="")
    project_stage = models.CharField(max_length=64, blank=True, default="")
    cost_center = models.ForeignKey(
        "masterdata.CostCenter", on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_requests",
    )
    cost_center_code = models.CharField(max_length=64, blank=True, default="")
    cost_center_name = models.CharField(max_length=200, blank=True, default="")
    expense_category = models.ForeignKey(
        "masterdata.ExpenseCategory", on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_requests",
    )
    expense_category_code = models.CharField(max_length=64, blank=True, default="")
    expense_category_name = models.CharField(max_length=160, blank=True, default="")
    budget_category = models.ForeignKey(
        "masterdata.BudgetCategory", on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_requests",
    )
    budget_category_code = models.CharField(max_length=64, blank=True, default="")
    budget_category_name = models.CharField(max_length=160, blank=True, default="")
    application_reason = models.TextField(blank=True, default="")
    purchase_purpose = models.TextField(blank=True, default="")
    technical_description = models.TextField(blank=True, default="")
    delivery_requirements = models.TextField(blank=True, default="")
    note_description = models.TextField(blank=True, default="")
    approval_status = models.CharField(max_length=24, blank=True, default="not_submitted")
    approval_current_node = models.CharField(max_length=120, blank=True, default="申请人起草")
    approval_current_approver = models.CharField(max_length=120, blank=True, default="")
    approval_result = models.CharField(max_length=120, blank=True, default="")
    required_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    purchase_mode = models.CharField(
        max_length=24, choices=PURCHASE_MODE_CHOICES, default="STANDARD"
    )
    source_purchase_plan = models.OneToOneField(
        "planning.PurchasePlan",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_request",
        verbose_name="来源采购计划",
    )

    class Meta:
        db_table = "scm_purchase_request"
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="scm_pr_quantity_nonnegative"),
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="scm_pr_amount_nonnegative"),
        ]

    @property
    def object_no(self):
        return self.request_no

    def clean(self):
        super().clean()
        if self.status == "converted" and self.pk and not self.inquiries.exists():
            raise ValidationError({"status": "采购申请转为converted前必须存在下游询价对象。"})


class PurchaseRequestItem(models.Model):
    """服务端持久化明细；物料身份只能引用 EMD Material Master。"""

    purchase_request = models.ForeignKey(
        PurchaseRequest, on_delete=models.CASCADE, related_name="request_items"
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, related_name="purchase_request_items"
    )
    material_code = models.CharField(max_length=50)
    material_name = models.CharField(max_length=200)
    specification = models.CharField(max_length=200, blank=True, default="")
    unit = models.CharField(max_length=20)
    material_category = models.CharField(max_length=100, blank=True, default="")
    purchase_attribute = models.CharField(max_length=80, blank=True, default="")
    suggested_supplier = models.ForeignKey(
        "procurement.Supplier", on_delete=models.PROTECT, null=True, blank=True,
        related_name="suggested_purchase_request_items",
    )
    supplier = models.ForeignKey(
        "procurement.Supplier", on_delete=models.PROTECT, null=True, blank=True,
        related_name="priced_purchase_request_items",
    )
    supplier_material_price = models.ForeignKey(
        "masterdata.SupplierMaterialPrice", on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_request_items",
    )
    price_record_code = models.CharField(max_length=160, blank=True, default="")
    unit_price_snapshot = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    tax_rate_snapshot = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    currency_snapshot = models.CharField(max_length=16, blank=True, default="")
    price_effective_date_snapshot = models.DateField(null=True, blank=True)
    suggested_supplier_code = models.CharField(max_length=50, blank=True, default="")
    suggested_supplier_name = models.CharField(max_length=100, blank=True, default="")
    demand_reason = models.CharField(max_length=500, blank=True, default="")
    technical_requirements = models.CharField(max_length=500, blank=True, default="")
    brand_requirements = models.CharField(max_length=200, blank=True, default="")
    substitute_requirement = models.CharField(max_length=500, blank=True, default="")
    substitute_material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, null=True, blank=True,
        related_name="substitute_purchase_request_items",
    )
    substitute_material_code = models.CharField(max_length=50, blank=True, default="")
    substitute_material_name = models.CharField(max_length=200, blank=True, default="")
    purchase_remark = models.CharField(max_length=500, blank=True, default="")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    required_date = models.DateField()
    remark = models.CharField(max_length=500, blank=True, default="")
    line_no = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "scm_purchase_request_item"
        ordering = ["line_no", "id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="scm_pr_item_quantity_positive"),
            models.UniqueConstraint(fields=["purchase_request", "line_no"], name="scm_pr_item_line_unique"),
        ]


class PurchaseRequestApprovalRecord(models.Model):
    """采购申请审批只读轨迹；不替代统一状态机，也不创建询价对象。"""

    purchase_request = models.ForeignKey(
        PurchaseRequest, on_delete=models.CASCADE, related_name="approval_records"
    )
    action = models.CharField(max_length=32)
    from_status = models.CharField(max_length=24)
    to_status = models.CharField(max_length=24)
    node_name = models.CharField(max_length=120)
    actor = models.CharField(max_length=120, blank=True, default="")
    comment = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "scm_purchase_request_approval_record"
        ordering = ["created_at", "id"]


class PurchaseInquiry(ScmBusinessObjectBase):
    STATUS_CHOICES = [
        ("draft", "草稿"), ("sent", "已发送"), ("quoted", "已报价"),
        ("approved", "已审批"), ("closed", "已关闭"),
    ]

    inquiry_no = models.CharField(max_length=80, unique=True)
    source_purchase_request = models.ForeignKey(
        PurchaseRequest, on_delete=models.PROTECT, related_name="inquiries"
    )
    supplier = models.CharField(max_length=160, blank=True, default="")
    quotation = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    class Meta:
        db_table = "scm_purchase_inquiry"
        ordering = ["-id"]

    @property
    def object_no(self):
        return self.inquiry_no


class SupplierQuotation(ScmBusinessObjectBase):
    STATUS_CHOICES = [
        ("draft", "草稿"), ("saved", "已保存"), ("submitted", "已提交"),
        ("received", "已接收"), ("closed", "已关闭"), ("cancelled", "已取消"),
    ]

    quotation_no = models.CharField(max_length=100, unique=True)
    source_inquiry = models.ForeignKey(
        PurchaseInquiry, on_delete=models.PROTECT, related_name="supplier_quotations"
    )
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    currency = models.CharField(max_length=12, default="CNY")
    quotation_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "scm_supplier_quotation"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_inquiry", "supplier_id"], name="scm_sq_inquiry_supplier_unique"
            ),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="scm_sq_price_nonnegative"),
        ]

    @property
    def object_no(self):
        return self.quotation_no


class QuoteComparisonFact(models.Model):
    """不可变的报价比较审计事实；不是交易对象，不负责推进采购流程。"""

    SOURCE_TYPE_CHOICES = [
        ("runtime_fact", "运行时事实"),
        ("server_fact", "服务端事实"),
        ("canary_fact", "金丝雀事实"),
    ]
    VERIFIED_STATUS_CHOICES = [
        ("pending_verification", "待人工核验"),
        ("verified", "已人工核验"),
        ("blocked", "阻断固化"),
    ]
    IMMUTABLE_FIELDS = (
        "comparison_no", "source_inquiry_no", "source_quotation_ids",
        "supplier_quote_evidence", "material_code", "material_name", "quantity",
        "quotation_amount", "lowest_price", "comparison_result", "source_type",
        "fact_version", "generated_at", "source_runtime_key", "source_fingerprint",
    )

    fact_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comparison_no = models.CharField(max_length=120)
    source_inquiry_no = models.CharField(max_length=100)
    source_quotation_ids = models.JSONField(default=list)
    supplier_quote_evidence = models.JSONField(default=list)
    material_code = models.CharField(max_length=100)
    material_name = models.CharField(max_length=240)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    # 一个比较事实含多家供应商报价；本字段保存逐报价金额集合，禁止仅保存最低价供应商。
    quotation_amount = models.JSONField(default=list)
    lowest_price = models.DecimalField(max_digits=18, decimal_places=4)
    comparison_result = models.JSONField(default=dict)
    source_type = models.CharField(max_length=24, choices=SOURCE_TYPE_CHOICES)
    fact_version = models.PositiveIntegerField(default=1)
    verified_status = models.CharField(
        max_length=24, choices=VERIFIED_STATUS_CHOICES, default="pending_verification"
    )
    generated_at = models.DateTimeField()
    source_runtime_key = models.CharField(max_length=180, blank=True, default="")
    source_fingerprint = models.CharField(max_length=64, unique=True)
    verified_by = models.CharField(max_length=120, blank=True, default="")
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scm_quote_comparison_fact"
        ordering = ["comparison_no", "fact_version"]
        constraints = [
            models.UniqueConstraint(
                fields=["comparison_no", "fact_version"],
                name="scm_qcf_comparison_version_unique",
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="scm_qcf_quantity_positive"),
            models.CheckConstraint(condition=models.Q(lowest_price__gte=0), name="scm_qcf_lowest_nonnegative"),
            models.CheckConstraint(condition=models.Q(fact_version__gte=1), name="scm_qcf_version_positive"),
        ]

    def clean(self):
        super().clean()
        if not self.source_quotation_ids or not isinstance(self.source_quotation_ids, list):
            raise ValidationError({"source_quotation_ids": "SOURCE_QUOTATION_IDS_REQUIRED"})
        if not self.supplier_quote_evidence or not isinstance(self.supplier_quote_evidence, list):
            raise ValidationError({"supplier_quote_evidence": "SUPPLIER_QUOTE_EVIDENCE_REQUIRED"})
        required = {"supplierId", "supplierName", "quotationNo", "quotationAmount",
                    "quotationStatus", "receivedAt"}
        if any(not required.issubset(item) or not all(item.get(field) not in (None, "") for field in required)
               for item in self.supplier_quote_evidence):
            raise ValidationError({"supplier_quote_evidence": "SUPPLIER_QUOTE_EVIDENCE_INCOMPLETE"})
        if self.source_type == "runtime_fact" and not self.source_runtime_key:
            raise ValidationError({"source_runtime_key": "RUNTIME_SOURCE_KEY_REQUIRED"})
        if self.verified_status == "verified" and (not self.verified_by or not self.verified_at):
            raise ValidationError({"verified_status": "MANUAL_VERIFICATION_EVIDENCE_REQUIRED"})

    def save(self, *args, **kwargs):
        if self.pk:
            existing = type(self).objects.filter(pk=self.pk).values(*self.IMMUTABLE_FIELDS).first()
            if existing and any(existing[field] != getattr(self, field) for field in self.IMMUTABLE_FIELDS):
                raise ValidationError("QUOTE_COMPARISON_FACT_IMMUTABLE")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("QUOTE_COMPARISON_FACT_DELETE_FORBIDDEN")


class PriceApprovalPreparation(models.Model):
    """由不可变报价比较事实生成、仅由采购人员推进的核价准备对象。"""

    STATUS_CHOICES = [
        ("draft", "草稿"), ("reviewing", "核价中"),
        ("completed", "已完成"),
        ("approved", "历史已核准"), ("rejected", "历史已拒绝"),
    ]
    REVIEW_RESULT_CHOICES = [
        ("pass", "通过"),
        ("reject", "不同意"),
        ("adjust", "调整后重新核价"),
    ]
    FACT_ORIGIN_CHOICES = [
        ("production_fact", "正式事实"),
        ("legacy_verified_fact", "历史验证事实"),
        ("canary_fact", "金丝雀事实"),
    ]

    approval_prepare_no = models.CharField(max_length=160, unique=True)
    source_comparison = models.OneToOneField(
        QuoteComparisonFact, on_delete=models.PROTECT, related_name="price_approval_preparation",
        null=True, blank=True,
    )
    source_projection_id = models.CharField(max_length=80, unique=True, null=True, blank=True)
    source_projection_snapshot = models.JSONField(default=dict, blank=True)
    source_legacy_comparison_no = models.CharField(max_length=160, blank=True, default="")
    source_trace_alias_id = models.CharField(max_length=120, blank=True, default="")
    fact_origin = models.CharField(max_length=32, choices=FACT_ORIGIN_CHOICES, default="production_fact")
    source_confidence = models.CharField(max_length=8, blank=True, default="A")
    source_quotation_evidence = models.JSONField(default=list)
    supplier_candidates = models.JSONField(default=list)
    material_lines = models.JSONField(default=list)
    comparison_basis = models.JSONField(default=dict)
    historical_price_reference = models.JSONField(default=list, blank=True)
    selected_supplier = models.JSONField(default=dict, blank=True)
    review_opinion = models.TextField(blank=True, default="")
    exception_note = models.TextField(blank=True, default="")
    approval_opinion = models.TextField(blank=True, default="")
    review_result = models.CharField(
        max_length=16, choices=REVIEW_RESULT_CHOICES, blank=True, default=""
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    decision_version = models.PositiveIntegerField(default=0)
    reviewer = models.CharField(max_length=120, blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scm_price_approval_preparation"
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(decision_version__gte=0),
                name="scm_pap_decision_version_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(fact_origin="production_fact", source_comparison__isnull=False,
                        source_projection_id__isnull=True)
                    | models.Q(fact_origin="legacy_verified_fact", source_comparison__isnull=True,
                        source_projection_id__isnull=False)
                ),
                name="scm_pap_exactly_one_fact_source",
            ),
        ]

    def clean(self):
        super().clean()
        production_source = self.fact_origin == "production_fact" and self.source_comparison_id
        legacy_source = (self.fact_origin == "legacy_verified_fact" and self.source_projection_id
            and self.source_legacy_comparison_no and self.source_trace_alias_id
            and self.source_projection_snapshot)
        if not production_source and not legacy_source:
            raise ValidationError("PRICE_APPROVAL_FACT_SOURCE_INVALID")
        if not self.source_quotation_evidence or not self.supplier_candidates or not self.material_lines:
            raise ValidationError("PRICE_APPROVAL_PREPARATION_SOURCE_INCOMPLETE")
        if self.status == "completed":
            if self.review_result not in {"pass", "reject", "adjust"}:
                raise ValidationError("PRICE_APPROVAL_REVIEW_RESULT_REQUIRED")
        if self.status == "completed" and self.review_result == "pass":
            supplier_code = str(self.selected_supplier.get("supplierCode") or "").strip()
            candidate_codes = {
                str(item.get("supplierCode") or item.get("supplierId") or "").strip()
                for item in self.supplier_candidates
            }
            if not supplier_code or supplier_code not in candidate_codes:
                raise ValidationError("PRICE_APPROVAL_SELECTED_SUPPLIER_INVALID")
        if self.status == "completed":
            if not self.review_opinion.strip() or not self.approval_opinion.strip() or not self.reviewer.strip():
                raise ValidationError("PRICE_APPROVAL_MANUAL_DECISION_INCOMPLETE")

    @property
    def object_no(self):
        return self.approval_prepare_no


class PriceApproval(ScmBusinessObjectBase):
    STATUS_CHOICES = [
        ("draft", "草稿"), ("reviewing", "评审中"),
        ("approved", "已审批"), ("rejected", "已驳回"),
    ]

    approval_no = models.CharField(max_length=80, unique=True)
    source_inquiry = models.ForeignKey(
        PurchaseInquiry, on_delete=models.PROTECT, related_name="price_approvals"
    )
    supplier = models.CharField(max_length=160, blank=True, default="")
    price = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    class Meta:
        db_table = "scm_price_approval"
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name="scm_pa_price_nonnegative"),
        ]

    @property
    def object_no(self):
        return self.approval_no


class Supplier(models.Model):
    CREDIT_RATINGS = [
        ("A", "A级"),
        ("B", "B级"),
        ("C", "C级"),
        ("D", "D级"),
    ]

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=50, blank=True, null=True)
    contact_person = models.CharField(max_length=50, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.CharField(max_length=100, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    delivery_address = models.CharField(max_length=255, default="")
    category = models.CharField(max_length=40, default="待分类")
    tax_id = models.CharField(max_length=50, blank=True, null=True)
    credit_rating = models.CharField(max_length=1, choices=CREDIT_RATINGS, default="B")
    payment_terms = models.CharField(max_length=50, blank=True, null=True)
    lead_time = models.IntegerField(default=0)
    company_id = models.BigIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    data_origin = models.CharField(max_length=40, default="BUSINESS_FACT")
    source_evidence = models.JSONField(default=list, blank=True)
    enrichment_audit = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "supplier"
        managed = True
        verbose_name = "供应商"
        verbose_name_plural = "供应商"

    def __str__(self):
        return f"{self.code} - {self.name}"


class SupplierBusinessReferenceMapping(models.Model):
    """Audited legacy business reference -> authoritative SupplierMaster mapping."""

    legacy_supplier_code = models.CharField(max_length=80, unique=True)
    legacy_supplier_name = models.CharField(max_length=200)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="business_reference_mappings"
    )
    evidence = models.JSONField(default=list)
    evidence_status = models.CharField(max_length=32, default="UNIQUE_CONFIRMED")
    source_version = models.CharField(max_length=64)
    created_by = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "supplier_business_reference_mapping"
        ordering = ["legacy_supplier_code", "id"]

    def __str__(self):
        return f"{self.legacy_supplier_code} -> {self.supplier.code}"


class SupplierDuplicateReview(models.Model):
    STATUS_PENDING = "待人工确认"
    STATUS_CHOICES = [(STATUS_PENDING, STATUS_PENDING)]

    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="duplicate_reviews"
    )
    supplier_code = models.CharField(max_length=50)
    supplier_name = models.CharField(max_length=100)
    duplicate_reason = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_duplicate_review"
        ordering = ["supplier_code", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "supplier_name"],
                name="supplier_duplicate_review_identity_unique",
            ),
        ]

    def __str__(self):
        return f"{self.supplier_code} - {self.supplier_name} - {self.status}"


class PurchaseOrder(models.Model):
    PURCHASE_MODE_CHOICES = [
        ("STANDARD", "标准采购"),
        ("AGREED_PRICE", "既定价格采购"),
        ("DIRECT", "直接采购"),
        ("LEGACY", "历史兼容"),
    ]
    PRICE_TRACE_STATUS_CHOICES = [
        ("CURRENT_LINKED", "当前已链接"),
        ("LEGACY_UNTRACED", "历史未追溯"),
    ]
    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("submitted", "已提交"),
        ("approved", "已审核"),
        ("reviewed", "已复核"),
        ("final_approved", "已审批"),
        ("received", "已收货"),
        ("inspected", "已检验"),
        ("stored", "已入库"),
        ("closed", "已结案"),
        ("cancelled", "已取消"),
    ]

    po_no = models.CharField(max_length=50, unique=True, blank=True, null=True)
    supplier = models.ForeignKey(
        "Supplier", on_delete=models.CASCADE, db_column="supplier_id"
    )
    order_date = models.DateField()
    expected_date = models.DateField(blank=True, null=True)
    actual_receive_date = models.DateField(
        blank=True, null=True, verbose_name="实际到货日期"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remark = models.TextField(blank=True, null=True)
    buyer = models.CharField("采购员", max_length=50, blank=True, null=True)
    buyer_employee = models.ForeignKey(
        "pfm.Employee", on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_orders_as_buyer", verbose_name="采购员正式人员档案",
    )
    purchase_mode = models.CharField(
        max_length=24, choices=PURCHASE_MODE_CHOICES, default="LEGACY"
    )
    source_type = models.CharField(max_length=64, blank=True, default="")
    source_reference = models.CharField(max_length=255, blank=True, default="")
    source_trace = models.JSONField(default=dict, blank=True)
    price_trace_status = models.CharField(
        max_length=24, choices=PRICE_TRACE_STATUS_CHOICES, default="LEGACY_UNTRACED"
    )
    supplier_code_snapshot = models.CharField(max_length=50, blank=True, default="")
    supplier_name_snapshot = models.CharField(max_length=100, blank=True, default="")
    supplier_contact_snapshot = models.CharField(max_length=50, blank=True, default="")
    supplier_phone_snapshot = models.CharField(max_length=20, blank=True, default="")
    supplier_address_snapshot = models.CharField(max_length=255, blank=True, default="")
    delivery_address_snapshot = models.CharField(max_length=255, blank=True, default="")

    # ===== 在这里插入 department 字段 =====
    department = models.ForeignKey(
        "system.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="所属部门",
    )

    purchase_department = models.ForeignKey(
        "system.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders",
        verbose_name="物料申购部门",
    )

    source_price_approval = models.ForeignKey(
        "PriceApproval",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
        verbose_name="来源核价",
    )
    source_purchase_request = models.ForeignKey(
        "PurchaseRequest", on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_orders",
    )

    require_department = models.ForeignKey(
        "system.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="require_orders",
        verbose_name="物料需求部门",
    )

    created_by = models.BigIntegerField(blank=True, null=True)
    company_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "purchase_order"
        managed = True
        verbose_name = "采购订单"
        verbose_name_plural = "采购订单"
        ordering = ["-id"]
        permissions = [
            ("can_submit_purchaseorder", "可以提交订单"),
            ("can_approve_purchaseorder", "可以审核订单"),
            ("can_review_purchaseorder", "可以复核订单"),
            ("can_final_approve_purchaseorder", "可以审批订单"),
            ("can_receive_purchaseorder", "可以收货"),
            ("can_inspect_purchaseorder", "可以检验"),
            ("can_store_purchaseorder", "可以入库"),
            ("can_close_purchaseorder", "可以结案"),
            ("can_cancel_purchaseorder", "可以取消订单"),
            ("can_restart_purchaseorder", "可以重启订单"),
        ]

    def __str__(self):
        return f"{self.po_no} - {self.supplier.name}"

    @property
    def object_id(self):
        return self.pk

    @property
    def object_type(self):
        return "PurchaseOrder"

    @property
    def object_no(self):
        return self.po_no

    def has_valid_approval_source(self):
        approval = self.source_price_approval
        return bool(approval and approval.status == "approved" and self.items.filter(quantity__gt=0).exists())

    @property
    def days_to_expiry(self):
        """采购订单-到期天数"""
        # 已达成或已收货的订单不显示到期天数
        if self.is_fulfilled or self.status in ["received", "closed", "cancelled"]:
            return None
        if not self.expected_date:
            return None
        delta = self.expected_date - date.today()
        return delta.days

    @property
    def urgency_level(self):
        """采购订单-紧急程度"""
        # 已达成
        if self.is_fulfilled or self.status in ["received", "closed"]:
            return "completed"

        days = self.days_to_expiry
        if days is None:
            return "unscheduled"

        if days <= 0:
            return "urgent"  # 特急
        elif days <= 3:
            return "emergency"  # 紧急
        elif days <= 7:
            return "normal"  # 一般
        else:
            return "relaxed"  # 宽松

    @property
    def is_fulfilled(self):
        """采购订单-是否达成"""
        # 订单状态必须是终态（已收货、已检验、已入库、已结案）
        if self.status not in ["received", "inspected", "stored", "closed"]:
            return False

        # 检查所有明细的实际交货数量总和是否等于计划数量总和
        total_planned = self.items.aggregate(total=models.Sum("quantity"))["total"] or 0
        total_actual = (
            self.items.aggregate(total=models.Sum("actual_quantity"))["total"] or 0
        )

        return total_planned > 0 and total_actual >= total_planned


class PurchaseOrderItem(models.Model):
    po = models.ForeignKey(
        "PurchaseOrder",
        on_delete=models.CASCADE,
        related_name="items",
        db_column="po_id",
    )
    material = models.ForeignKey(
        "masterdata.Material",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="物料",
    )
    source_purchase_request_item = models.ForeignKey(
        "PurchaseRequestItem", on_delete=models.PROTECT, null=True, blank=True,
        related_name="standard_purchase_order_items",
    )
    price_approval_result = models.ForeignKey(
        "masterdata.PriceApprovalResult", on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_order_items",
    )
    supplier_material_price = models.ForeignKey(
        "masterdata.SupplierMaterialPrice", on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_order_items",
    )
    material_code_snapshot = models.CharField(max_length=50, blank=True, default="")
    material_name_snapshot = models.CharField(max_length=200, blank=True, default="")
    specification_snapshot = models.CharField(max_length=200, blank=True, default="")
    unit_snapshot = models.CharField(max_length=40, blank=True, default="")
    unit_price_snapshot = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    tax_rate_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    currency_snapshot = models.CharField(max_length=16, blank=True, default="")
    product_name = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="商品名称"
    )
    specification = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="规格型号"
    )

    # 计划字段（只定义一次，添加 verbose_name）
    quantity = models.DecimalField("计划数量", max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(
        "计划单价", max_digits=12, decimal_places=4, default=0
    )
    amount = models.DecimalField("计划金额", max_digits=12, decimal_places=2, default=0)

    # 实际交货字段（新增）
    actual_quantity = models.DecimalField(
        "实际交货数量", max_digits=12, decimal_places=2, null=True, blank=True
    )
    actual_unit_price = models.DecimalField(
        "实际交货单价", max_digits=12, decimal_places=4, null=True, blank=True
    )
    actual_amount = models.DecimalField(
        "实际交货金额", max_digits=12, decimal_places=2, null=True, blank=True
    )
    actual_arrival_date = models.DateField("实际到货日期", null=True, blank=True)

    # 其他原有字段
    expected_date = models.DateField(blank=True, null=True)
    remark = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.po.po_no} - {self.product_name}"

    class Meta:
        db_table = "purchase_order_item"
        managed = True
        verbose_name = "采购订单明细"
        verbose_name_plural = "采购订单明细"


class PurchaseReceipt(ScmBusinessObjectBase):
    STATUS_CHOICES = [
        ("draft", "草稿"), ("receiving", "收货中"),
        ("received", "已收货"), ("closed", "已关闭"),
    ]

    receipt_no = models.CharField(max_length=80, unique=True)
    source_purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="scm_receipts"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    receipt_date = models.DateField(default=date.today)
    operator_employee = models.ForeignKey(
        "pfm.Employee", on_delete=models.PROTECT, related_name="purchase_receipts",
        verbose_name="收货执行员工",
    )
    operator_account_id = models.BigIntegerField(verbose_name="收货执行账号ID")

    class Meta:
        db_table = "scm_purchase_receipt"
        ordering = ["-id"]

    @property
    def object_no(self):
        return self.receipt_no


class PurchaseInspection(ScmBusinessObjectBase):
    STATUS_CHOICES = [
        ("pending", "待检验"), ("inspecting", "检验中"),
        ("qualified", "合格"), ("rejected", "不合格"),
    ]

    inspection_no = models.CharField(max_length=80, unique=True)
    source_receipt = models.ForeignKey(
        PurchaseReceipt, on_delete=models.PROTECT, related_name="inspections"
    )
    qualified_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    rejected_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    inspection_date = models.DateField(null=True, blank=True)
    inspector_employee = models.ForeignKey(
        "pfm.Employee", on_delete=models.PROTECT, related_name="purchase_inspections",
        verbose_name="检验执行员工",
    )
    inspector_account_id = models.BigIntegerField(verbose_name="检验执行账号ID")

    class Meta:
        db_table = "scm_purchase_inspection"
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(qualified_quantity__gte=0), name="scm_inspection_qualified_nonnegative"),
            models.CheckConstraint(condition=models.Q(rejected_quantity__gte=0), name="scm_inspection_rejected_nonnegative"),
        ]

    @property
    def object_no(self):
        return self.inspection_no


class Warehouse(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    location_code = models.CharField(max_length=80, blank=True, default="")
    company_id = models.BigIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scm_warehouse"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class WarehouseLocation(models.Model):
    """Canonical warehouse location identity; no inventory movement is implied."""

    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT,
        related_name="locations", verbose_name="所属仓库",
    )
    code = models.CharField("库位编码", max_length=80)
    name = models.CharField("库位名称", max_length=120)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scm_warehouse_location"
        ordering = ["warehouse_id", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "code"], name="scm_warehouse_location_unique"
            )
        ]


class InventoryLot(models.Model):
    """Formal lot/batch identity; quantities remain owned by inventory ledgers."""

    lot_no = models.CharField("批号", max_length=100)
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT,
        related_name="inventory_lots", verbose_name="物料",
    )
    company_id = models.BigIntegerField("所属公司ID")
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, null=True, blank=True,
        related_name="inventory_lots", verbose_name="所属仓库",
        help_text="历史批号允许为空；A1.5以后新业务可记录正式仓库维度。",
    )
    production_date = models.DateField("生产日期", null=True, blank=True)
    expiry_date = models.DateField("有效日期", null=True, blank=True)
    reinspection_date = models.DateField("复检日期", null=True, blank=True)
    is_active = models.BooleanField("是否启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scm_inventory_lot"
        ordering = ["company_id", "material_id", "lot_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "material", "warehouse", "lot_no"],
                name="scm_inventory_lot_unique",
            )
        ]

    def clean(self):
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            raise ValidationError({"warehouse": "批号仓库必须属于批号所在公司"})
        if self.material_id and self.material.company_id != self.company_id:
            raise ValidationError({"material": "批号物料必须属于批号所在公司"})


class WarehouseInbound(ScmBusinessObjectBase):
    STATUS_CHOICES = [
        ("planned", "待入库"), ("processing", "入库中"),
        ("completed", "已入库"), ("closed", "已关闭"),
    ]

    inbound_no = models.CharField(max_length=80, unique=True)
    source_inspection = models.ForeignKey(
        PurchaseInspection, on_delete=models.PROTECT, related_name="warehouse_inbounds"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="purchase_inbounds"
    )
    location = models.ForeignKey(
        WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True,
        related_name="purchase_inbounds",
        help_text="历史入库允许为空；新业务可记录正式默认库位。",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    inbound_date = models.DateField(default=date.today)
    operator_employee = models.ForeignKey(
        "pfm.Employee", on_delete=models.PROTECT, related_name="warehouse_inbounds",
        verbose_name="入库执行员工",
    )
    operator_account_id = models.BigIntegerField(verbose_name="入库执行账号ID")

    class Meta:
        db_table = "scm_warehouse_inbound"
        ordering = ["-id"]

    @property
    def object_no(self):
        return self.inbound_no

    def clean(self):
        if self.location_id and self.location.warehouse_id != self.warehouse_id:
            raise ValidationError({"location": "入库库位必须属于所选仓库"})


class InventoryBalance(models.Model):
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="inventory_balances"
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, related_name="inventory_balances"
    )
    location = models.ForeignKey(
        WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True,
        related_name="inventory_balances",
    )
    lot = models.ForeignKey(
        InventoryLot, on_delete=models.PROTECT, null=True, blank=True,
        related_name="inventory_balances",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scm_inventory_balance"
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "material"],
                condition=models.Q(location__isnull=True, lot__isnull=True),
                name="scm_inventory_balance_legacy_unique",
            ),
            models.UniqueConstraint(
                fields=["warehouse", "material", "location"],
                condition=models.Q(location__isnull=False, lot__isnull=True),
                name="scm_inventory_balance_location_unique",
            ),
            models.UniqueConstraint(
                fields=["warehouse", "material", "lot"],
                condition=models.Q(location__isnull=True, lot__isnull=False),
                name="scm_inventory_balance_lot_unique",
            ),
            models.UniqueConstraint(
                fields=["warehouse", "material", "location", "lot"],
                condition=models.Q(location__isnull=False, lot__isnull=False),
                name="scm_inventory_balance_dimension_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0), name="scm_inventory_balance_nonnegative"
            ),
        ]

    def clean(self):
        errors = {}
        if self.location_id and self.location.warehouse_id != self.warehouse_id:
            errors["location"] = "库存库位必须属于库存仓库"
        if self.lot_id:
            if self.lot.material_id != self.material_id:
                errors["lot"] = "库存批号必须属于库存物料"
            if self.lot.warehouse_id and self.lot.warehouse_id != self.warehouse_id:
                errors["lot"] = "库存批号必须属于库存仓库"
        if errors:
            raise ValidationError(errors)


class InventoryTransaction(models.Model):
    DIRECTION_CHOICES = [("IN", "入库"), ("OUT", "出库")]

    transaction_no = models.CharField(max_length=80, unique=True)
    source_inbound = models.ForeignKey(
        WarehouseInbound, on_delete=models.PROTECT, related_name="inventory_transactions"
    )
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="inventory_transactions"
    )
    material = models.ForeignKey(
        "masterdata.Material", on_delete=models.PROTECT, related_name="inventory_transactions"
    )
    location = models.ForeignKey(
        WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True,
        related_name="inventory_transactions",
    )
    lot = models.ForeignKey(
        InventoryLot, on_delete=models.PROTECT, null=True, blank=True,
        related_name="inventory_transactions",
    )
    direction = models.CharField(max_length=8, choices=DIRECTION_CHOICES, default="IN")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    before_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    after_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    operator_employee = models.ForeignKey(
        "pfm.Employee", on_delete=models.PROTECT, related_name="inventory_transactions"
    )
    operator_account_id = models.BigIntegerField()
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "scm_inventory_transaction"
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_inbound", "material"],
                name="scm_inventory_transaction_inbound_material_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="scm_inventory_transaction_positive"
            ),
        ]

    @property
    def object_no(self):
        return self.transaction_no

    def clean(self):
        errors = {}
        if self.location_id and self.location.warehouse_id != self.warehouse_id:
            errors["location"] = "库存流水库位必须属于库存仓库"
        if self.lot_id:
            if self.lot.material_id != self.material_id:
                errors["lot"] = "库存流水批号必须属于库存物料"
            if self.lot.warehouse_id and self.lot.warehouse_id != self.warehouse_id:
                errors["lot"] = "库存流水批号必须属于库存仓库"
        if errors:
            raise ValidationError(errors)


# class PurchaseReceipt(models.Model):
#    receipt_no = models.CharField(max_length=50, unique=True)
#    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, db_column='po_id')
#    receipt_date = models.DateField()
#    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, db_column='supplier_id')
#    total_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#    remark = models.TextField(blank=True, null=True)
#    created_by = models.BigIntegerField(blank=True, null=True)
#    company_id = models.BigIntegerField()
#    created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         db_table = 'purchase_receipt'
#         managed = False
#         verbose_name = '采购入库单'
#         verbose_name_plural = '采购入库单'

# class PurchaseReceiptItem(models.Model):
#     receipt = models.ForeignKey(PurchaseReceipt, on_delete=models.CASCADE, related_name='items', db_column='receipt_id')
#     po_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.CASCADE, db_column='po_item_id')
#     material = models.ForeignKey('masterdata.Material', on_delete=models.CASCADE, db_column='material_id')
#     quantity = models.DecimalField(max_digits=12, decimal_places=2)
#     unit_price = models.DecimalField(max_digits=12, decimal_places=4, default=0)
#     amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#
#     class Meta:
#         db_table = 'purchase_receipt_item'
#         managed = False
#         verbose_name = '采购入库明细'
#         verbose_name_plural = '采购入库明细'
