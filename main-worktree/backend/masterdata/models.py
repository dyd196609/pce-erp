from django.db import models


class UnitOfMeasure(models.Model):
    """A1 canonical unit fact shared by Material and production masters."""

    class Dimension(models.TextChoices):
        COUNT = "count", "数量"
        LENGTH = "length", "长度"
        AREA = "area", "面积"
        VOLUME = "volume", "体积"
        MASS = "mass", "质量"
        TIME = "time", "时间"
        OTHER = "other", "其他/待治理"

    code = models.CharField(max_length=20)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=20, blank=True)
    dimension = models.CharField(
        max_length=20, choices=Dimension.choices, default=Dimension.OTHER,
    )
    conversion_base = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="conversion_units",
        help_text="同公司、同维度的换算基准单位；基准单位本身保持为空。",
    )
    conversion_factor = models.DecimalField(
        max_digits=20, decimal_places=10, default=1,
        help_text="1当前单位折合为多少基准单位；必须大于0。",
    )
    company_id = models.BigIntegerField()
    decimal_places = models.PositiveSmallIntegerField(default=4)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "unit_of_measure"
        ordering = ["company_id", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "code"], name="uom_company_code_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(decimal_places__lte=6),
                name="uom_decimal_places_lte_6",
            ),
            models.CheckConstraint(
                condition=models.Q(conversion_factor__gt=0),
                name="uom_conversion_factor_positive",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.conversion_base_id:
            if self.conversion_base_id == self.pk:
                errors["conversion_base"] = "计量单位不能以自身作为换算基准"
            elif self.conversion_base.company_id != self.company_id:
                errors["conversion_base"] = "换算基准单位必须属于同一公司"
            elif self.conversion_base.dimension != self.dimension:
                errors["conversion_base"] = "换算单位与基准单位必须属于同一计量维度"
        elif self.conversion_factor != 1:
            errors["conversion_factor"] = "未指定换算基准时，换算系数必须为1"
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.code} - {self.name}"


class MaterialCategory(models.Model):
    """物料分类表"""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        db_column="parent_id",
    )
    company_id = models.BigIntegerField()
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material_category"
        managed = True
        verbose_name = "物料分类"
        verbose_name_plural = "物料分类"

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.parent_id:
            if self.parent_id == self.pk:
                errors["parent"] = "物料类别不能以自身作为上级"
            elif self.parent.company_id != self.company_id:
                errors["parent"] = "上级物料类别必须属于同一公司"
            elif not self.parent.is_active:
                errors["parent"] = "停用物料类别不得作为正式上级类别"
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name


class Material(models.Model):
    """物料主数据表"""

    UNIT_STATUS_CHOICES = [
        ("confirmed", "已确认"),
        ("not_confirmed", "待维护"),
    ]

    MATERIAL_TYPES = [
        ("raw", "原材料"),
        ("semi", "半成品"),
        ("finished", "成品"),
        ("auxiliary", "辅料"),
        ("fixed_asset", "固定资产"),
    ]
    SUPPLY_TYPES = [
        ("purchase", "采购件"),
        ("production", "自制件"),
        ("pending_confirmation", "待确认"),
    ]
    COST_METHODS = [
        ("weighted_avg", "月加权平均"),
        ("specific_id", "分批认定法"),
        ("standard", "标准成本法"),
    ]

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    purpose = models.CharField(max_length=200, blank=True, default="")
    specification = models.CharField(max_length=200, blank=True, null=True)
    application_notes = models.TextField(blank=True, default="")
    category = models.ForeignKey(
        MaterialCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="category_id",
    )
    unit = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="兼容单位投影；正式基本单位未知时必须为空。",
    )
    unit_status = models.CharField(
        max_length=20,
        choices=UNIT_STATUS_CHOICES,
        default="confirmed",
        help_text="来源未提供基本单位时使用not_confirmed，不得猜填工程派生单位。",
    )
    price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="单价"
    )
    purchase_unit = models.CharField(max_length=20, blank=True, null=True)
    base_uom = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="base_materials",
    )
    purchase_uom = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_materials",
    )
    conversion_rate = models.DecimalField(max_digits=12, decimal_places=4, default=1)
    material_type = models.CharField(
        max_length=20, choices=MATERIAL_TYPES, default="raw"
    )
    safety_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_point = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    economic_order_qty = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True
    )
    lead_time = models.IntegerField(default=0)
    is_purchased = models.BooleanField(default=False)
    is_produced = models.BooleanField(default=False)
    cost_method = models.CharField(
        max_length=20, choices=COST_METHODS, default="weighted_avg"
    )
    standard_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    last_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    company_id = models.BigIntegerField()
    is_active = models.BooleanField(default=True)
    created_by = models.BigIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "material"
        managed = True
        verbose_name = "物料"
        verbose_name_plural = "物料"
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "code"], name="material_company_code_unique",
            ),
            models.CheckConstraint(
                condition=~(models.Q(is_purchased=True) & models.Q(is_produced=True)),
                name="material_supply_flags_not_conflicting",
            ),
            models.CheckConstraint(
                condition=models.Q(material_type__in=[
                    "raw", "semi", "finished", "auxiliary", "fixed_asset",
                ]),
                name="material_type_formal_enum",
            ),
        ]

    @property
    def supply_type(self):
        """Canonical supply classification derived from the two legacy columns."""
        if self.is_purchased and not self.is_produced:
            return "purchase"
        if self.is_produced and not self.is_purchased:
            return "production"
        return "pending_confirmation"

    @property
    def supply_type_display(self):
        return dict(self.SUPPLY_TYPES)[self.supply_type]

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        legacy_unit = (self.unit or "").strip()
        if self.unit_status == "confirmed":
            if not legacy_unit and not self.base_uom_id:
                errors["unit_status"] = "单位已确认时必须维护兼容单位或正式基本单位"
        elif legacy_unit or self.base_uom_id:
            errors["unit_status"] = "单位待维护时兼容单位和正式基本单位必须为空"
        if self.base_uom_id and self.base_uom.company_id != self.company_id:
            errors["base_uom"] = "基本单位必须属于物料所在公司"
        if self.purchase_uom_id and self.purchase_uom.company_id != self.company_id:
            errors["purchase_uom"] = "采购单位必须属于物料所在公司"
        if self.category_id:
            if self.category.company_id != self.company_id:
                errors["category"] = "物料类别必须属于物料所在公司"
            elif not self.category.is_active:
                errors["category"] = "停用物料类别不得用于正式物料"
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.code} - {self.name}"


class PriceApprovalResult(models.Model):
    """Explicit human price confirmation; authoritative for effective-price archive."""

    result_no = models.CharField(max_length=160, unique=True)
    preparation = models.ForeignKey(
        "procurement.PriceApprovalPreparation", on_delete=models.PROTECT,
        null=True, blank=True, related_name="formal_price_approval_results",
    )
    preparation_identity = models.CharField(max_length=160, unique=True)
    original_source_type = models.CharField(max_length=64)
    original_source_object_id = models.CharField(max_length=160, blank=True, default="")
    original_source_reference = models.CharField(max_length=255)
    source_trace = models.JSONField(default=dict)
    supplier = models.ForeignKey(
        "procurement.Supplier", on_delete=models.PROTECT,
        related_name="formal_price_approval_results",
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="formal_price_approval_results",
    )
    approved_price = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=16)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    tax_rate_source = models.CharField(max_length=100)
    approval_conclusion = models.CharField(max_length=16, default="pass")
    selected_supplier = models.JSONField(default=dict)
    approved_by = models.CharField(max_length=120)
    approved_at = models.DateTimeField()
    confirmed_by = models.CharField(max_length=120)
    confirmed_at = models.DateTimeField()
    review_opinion = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "supplier_price_approval_result"
        ordering = ["-confirmed_at", "-id"]


class SupplierMaterialPrice(models.Model):
    """Persisted enterprise effective price approved through PriceApprovalResult."""

    STATUS_CHOICES = [("ACTIVE", "有效"), ("INACTIVE", "失效")]

    price_no = models.CharField(max_length=160, unique=True)
    supplier = models.ForeignKey(
        "procurement.Supplier", on_delete=models.PROTECT,
        related_name="effective_material_prices",
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="effective_supplier_prices",
    )
    approved_price = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=16)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    tax_rate_source = models.CharField(max_length=100)
    effective_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="ACTIVE")
    price_source_type = models.CharField(max_length=64, default="PriceApprovalResult")
    price_source_label = models.CharField(max_length=100, default="人工核价确认")
    price_approval_result = models.OneToOneField(
        PriceApprovalResult, on_delete=models.PROTECT, related_name="effective_price",
        null=True, blank=True,
    )
    original_source_type = models.CharField(max_length=64)
    original_source_reference = models.CharField(max_length=255)
    approved_by = models.CharField(max_length=120)
    approved_at = models.DateTimeField()
    confirmed_by = models.CharField(max_length=120)
    confirmed_at = models.DateTimeField()
    modified_by = models.CharField(max_length=120, blank=True, default="")
    modified_at = models.DateTimeField(null=True, blank=True)
    modification_reason = models.TextField(blank=True, default="")
    modification_audit = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_material_price"
        ordering = ["-confirmed_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(approved_price__gt=0),
                name="supplier_material_price_positive_price",
            ),
        ]


class ProjectMaster(models.Model):
    """企业项目主数据。"""

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    stage = models.CharField(max_length=64)
    owner = models.CharField(max_length=100, blank=True, default="")
    department = models.ForeignKey(
        "system.Department", on_delete=models.PROTECT, null=True, blank=True,
        related_name="master_projects",
    )
    recommended_cost_center = models.ForeignKey(
        "masterdata.CostCenter", on_delete=models.PROTECT, null=True, blank=True,
        related_name="recommended_projects",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_master"
        ordering = ["code"]


class CostCenter(models.Model):
    """企业成本中心主数据。"""

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    department = models.ForeignKey(
        "system.Department", on_delete=models.PROTECT, null=True, blank=True,
        related_name="cost_centers",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cost_center_master"
        ordering = ["code"]


class ExpenseCategory(models.Model):
    """费用类别主数据。"""

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "expense_category_master"
        ordering = ["code"]


class BudgetCategory(models.Model):
    """预算类别主数据。"""

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "budget_category_master"
        ordering = ["code"]


class CodeRule(models.Model):
    """编码规则表"""

    entity_type = models.CharField(max_length=50)
    prefix = models.CharField(max_length=20, blank=True, null=True)
    date_format = models.CharField(max_length=20, blank=True, null=True)
    seq_length = models.IntegerField(default=4)
    current_seq = models.IntegerField(default=0)
    company_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "code_rule"
        managed = True
        verbose_name = "编码规则"
        verbose_name_plural = "编码规则"
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "entity_type"], name="code_rule_company_entity_unique"
            )
        ]

    @classmethod
    def next_code(cls, *, entity_type, company_id):
        """Allocate one code with an atomic compare-and-swap sequence increment."""
        import datetime
        from django.db import transaction
        from django.db.models import F

        for _attempt in range(50):
            with transaction.atomic():
                rule = cls.objects.get(entity_type=entity_type, company_id=company_id)
                previous = rule.current_seq
                updated = cls.objects.filter(pk=rule.pk, current_seq=previous).update(
                    current_seq=F("current_seq") + 1,
                )
                if updated:
                    next_sequence = previous + 1
                    seq = str(next_sequence).zfill(rule.seq_length)
                    date_part = datetime.datetime.now().strftime(rule.date_format) if rule.date_format else ""
                    return f"{rule.prefix or ''}{date_part}{seq}"
        raise RuntimeError("编码序列并发更新重试次数已耗尽")

    def get_next_code(self):
        return self.next_code(entity_type=self.entity_type, company_id=self.company_id)


class ExternalIdentity(models.Model):
    """Reusable source identity for master data owned by any formal domain."""

    class MappingStatus(models.TextChoices):
        CREATE = "CREATE", "待创建"
        MATCH = "MATCH", "已匹配"
        REVIEW = "REVIEW", "待业务复核"
        BLOCK = "BLOCK", "已阻断"

    organization_id = models.BigIntegerField()
    source_system = models.CharField(max_length=100)
    source_type = models.CharField(max_length=40)
    source_object_type = models.CharField(max_length=100)
    external_id = models.CharField(max_length=240)
    target_entity_type = models.CharField(max_length=100)
    target_entity_id = models.CharField(max_length=100, blank=True)
    mapping_status = models.CharField(
        max_length=12, choices=MappingStatus.choices, default=MappingStatus.REVIEW,
    )
    source_fingerprint = models.CharField(max_length=64, blank=True)
    audit_metadata = models.JSONField(default=dict, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "masterdata_external_identity"
        ordering = ("organization_id", "source_system", "source_object_type", "external_id")
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "organization_id", "source_system", "source_type",
                    "source_object_type", "external_id",
                ),
                name="masterdata_external_identity_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=("organization_id", "target_entity_type", "target_entity_id"),
                name="md_extid_target_idx",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.mapping_status == self.MappingStatus.MATCH and not self.target_entity_id:
            raise ValidationError({"target_entity_id": "已匹配来源身份必须指向正式主数据"})
        if self.mapping_status == self.MappingStatus.CREATE and self.target_entity_id:
            raise ValidationError({"target_entity_id": "待创建来源身份不得预填正式对象身份"})


class MasterDataWriteRequest(models.Model):
    """Database-backed idempotency ledger for the single formal write chain."""

    class Status(models.TextChoices):
        RESERVED = "RESERVED", "已保留"
        COMMITTED = "COMMITTED", "已提交"

    organization_id = models.BigIntegerField()
    action_code = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=100)
    idempotency_key = models.CharField(max_length=160)
    request_hash = models.CharField(max_length=64)
    source_identity = models.ForeignKey(
        ExternalIdentity, on_delete=models.PROTECT, related_name="write_requests",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RESERVED)
    target_entity_id = models.CharField(max_length=100, blank=True)
    result = models.JSONField(default=dict, blank=True)
    audit_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "masterdata_write_request"
        ordering = ("organization_id", "action_code", "idempotency_key")
        constraints = [
            models.UniqueConstraint(
                fields=("organization_id", "action_code", "idempotency_key"),
                name="masterdata_write_request_unique",
            ),
        ]
