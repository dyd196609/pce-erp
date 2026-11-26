from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from workflow_runtime.state_models import BusinessStateManagedModel


class Customer(models.Model):
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT, related_name="sales_customers")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    acceptance_marker = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sales_customer"
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="uniq_sales_customer_company_code")]


class SalesOrder(BusinessStateManagedModel):
    class BusinessPurpose(models.TextChoices):
        FORMAL_SALE = "FORMAL_SALE", "正式销售订单"
        DEVELOPMENT_VALIDATION = "DEVELOPMENT_VALIDATION", "开发验证订单"
        SYSTEM_TEST = "SYSTEM_TEST", "系统测试订单"

    STATUS_CHOICES = [
        ("draft", "草稿"), ("submitted", "已提交"),
        ("approved", "已批准"), ("confirmed", "已确认（兼容）"),
        ("engineering", "工程准备中"), ("manufacturing_ready", "制造准备完成"),
        ("in_progress", "执行中"), ("delivering", "交付中"),
        ("completed", "已完成"),
        ("closed", "已关闭"), ("cancelled", "已取消"),
    ]
    ORDER_TYPE_CHOICES = [
        ("standard", "标准订单"), ("project", "项目订单"),
        ("sample", "样品订单"), ("service", "服务订单"),
    ]
    SOURCE_CHOICES = [
        ("manual", "手工录入"), ("crm", "CRM"),
        ("edi", "EDI"), ("import", "导入"),
    ]
    company = models.ForeignKey("system.Company", on_delete=models.PROTECT, related_name="sales_orders")
    department = models.ForeignKey("system.Department", on_delete=models.PROTECT, related_name="sales_orders")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales_orders")
    order_no = models.CharField(max_length=80, unique=True)
    order_date = models.DateField()
    required_delivery_date = models.DateField()
    currency = models.CharField(max_length=8, default="CNY")
    order_type = models.CharField(max_length=24, choices=ORDER_TYPE_CHOICES, default="standard")
    order_source = models.CharField(max_length=24, choices=SOURCE_CHOICES, default="manual")
    business_purpose = models.CharField(
        "业务用途",
        max_length=32,
        choices=BusinessPurpose.choices,
        null=True,
        blank=True,
        help_text="订单级正式业务用途；历史空值由只读兼容服务解释，不自动回填。",
    )
    project_reference = models.CharField(max_length=120, blank=True, default="")
    contract_reference = models.CharField(max_length=120, blank=True, default="")
    sales_owner = models.ForeignKey(
        "pfm.Employee", on_delete=models.PROTECT, null=True, blank=True,
        related_name="owned_sales_orders", verbose_name="销售负责人",
    )
    delivery_information = models.JSONField(default=dict, blank=True)
    external_source_no = models.CharField(max_length=120, blank=True, default="")
    engineering_document_version = models.ForeignKey(
        "pde.EngineeringDocumentVersion", on_delete=models.PROTECT,
        null=True, blank=True, related_name="sales_orders",
        verbose_name="订单正式文档引用",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    version = models.PositiveIntegerField(default=1)
    acceptance_marker = models.CharField(max_length=120, blank=True, default="")
    remark = models.CharField(max_length=300, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_sales_orders")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="confirmed_sales_orders")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_sales_orders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sales_order"
        ordering = ["-id"]


class SalesOrderItem(models.Model):
    ENGINEERING_MODE_CHOICES = (
        ("STANDARD", "标准产品"),
        ("TEMPLATE_ASSISTED", "模板辅助配置"),
        ("ORDER_ENGINEERED", "按单工程"),
    )
    PRICE_TAX_MODE_CHOICES = (
        ("tax_inclusive", "含税单价"),
        ("tax_exclusive", "未税单价"),
    )
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name="items")
    line_no = models.PositiveIntegerField()
    material = models.ForeignKey("masterdata.Material", on_delete=models.PROTECT, related_name="sales_order_items")
    product_definition = models.ForeignKey(
        "pde.ProductDefinition", on_delete=models.PROTECT, null=True, blank=True,
        related_name="sales_order_items", verbose_name="产品工程定义",
    )
    product_version = models.ForeignKey(
        "pde.ProductVersion", on_delete=models.PROTECT, null=True, blank=True,
        related_name="sales_order_items", verbose_name="适用产品版本",
    )
    manufacturing_output = models.ForeignKey(
        "pde.ProductManufacturingOutput", on_delete=models.PROTECT, null=True, blank=True,
        related_name="sales_order_items", verbose_name="工程发布组合",
    )
    product_configuration = models.ForeignKey(
        "pde.ProductConfiguration", on_delete=models.PROTECT, null=True, blank=True,
        related_name="sales_order_items", verbose_name="产品配置",
    )
    engineering_mode = models.CharField(
        max_length=24, choices=ENGINEERING_MODE_CHOICES, default="STANDARD",
    )
    space_code = models.CharField(max_length=80, blank=True, default="")
    space_name = models.CharField(max_length=160, blank=True, default="")
    installation_area = models.CharField(max_length=200, blank=True, default="")
    component_category = models.CharField(max_length=120, blank=True, default="")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    uom = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="sales_order_items", verbose_name="订单计量单位",
    )
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    tax_rate = models.DecimalField(max_digits=8, decimal_places=6, default=0)
    price_tax_mode = models.CharField(
        max_length=20, choices=PRICE_TAX_MODE_CHOICES, default="tax_exclusive",
    )
    required_date = models.DateField()
    customer_product_name = models.CharField(max_length=200, blank=True, default="")
    customer_product_description = models.TextField(blank=True, default="")
    specification = models.CharField(max_length=300, blank=True, default="")
    configuration_reference = models.CharField(max_length=120, blank=True, default="")
    engineering_requirements = models.TextField(blank=True, default="")
    quality_requirements = models.TextField(blank=True, default="")
    remark = models.TextField(blank=True, default="")
    external_line_no = models.CharField(max_length=80, blank=True, default="")
    engineering_document_version = models.ForeignKey(
        "pde.EngineeringDocumentVersion", on_delete=models.PROTECT,
        null=True, blank=True, related_name="sales_order_items",
        verbose_name="行图纸/工程资料引用",
    )

    class Meta:
        db_table = "sales_order_item"
        ordering = ["sales_order_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["sales_order", "line_no"], name="uniq_sales_order_line"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="sales_order_item_qty_positive"),
            models.CheckConstraint(condition=models.Q(tax_rate__gte=0, tax_rate__lte=1), name="sales_order_item_tax_rate_valid"),
        ]

    def clean(self):
        errors = {}
        if self.tax_rate < 0 or self.tax_rate > 1:
            errors["tax_rate"] = "税率快照必须在0到1之间"
        if self.engineering_mode == "TEMPLATE_ASSISTED" and not self.product_configuration_id:
            errors["product_configuration"] = "模板辅助配置行必须引用正式产品配置"
        if self.product_configuration_id:
            configuration_company_id = self.product_configuration.template.company_id
            if configuration_company_id != self.sales_order.company_id:
                errors["product_configuration"] = "产品配置必须属于销售订单公司"
            if self.engineering_mode != "TEMPLATE_ASSISTED":
                errors["engineering_mode"] = "只有模板辅助配置行允许引用产品配置"
        if self.engineering_mode == "ORDER_ENGINEERED":
            if self.product_definition_id and self.product_definition.manufacturing_definition_mode != "order_engineered":
                errors["engineering_mode"] = "按单工程行必须引用按单工程制造产品"
            if not self.product_definition_id and not (
                self.customer_product_name or self.customer_product_description
            ):
                errors["customer_product_name"] = "没有长期产品定义的按单工程行必须保留客户产品身份"
        if self.engineering_mode == "STANDARD" and self.product_definition_id:
            if self.product_definition.manufacturing_definition_mode == "order_engineered":
                errors["engineering_mode"] = "标准产品行不得引用按单工程制造产品"
        if self.product_definition_id:
            is_order_engineered = (
                self.product_definition.manufacturing_definition_mode == "order_engineered"
            )
            if not is_order_engineered and not self.product_version_id:
                errors["product_version"] = "标准制造销售明细必须引用正式产品版本"
            if not is_order_engineered and not self.manufacturing_output_id:
                errors["manufacturing_output"] = "标准制造销售明细必须引用正式工程发布组合"
            if self.product_definition.material_id != self.material_id:
                errors["product_definition"] = "产品工程定义必须引用订单行物料"
            if self.product_definition.company_id != self.sales_order.company_id:
                errors["product_definition"] = "产品工程定义必须属于销售订单公司"
        if self.product_version_id:
            if not self.product_definition_id:
                errors["product_version"] = "产品版本必须同时提供产品工程定义"
            elif self.product_version.product_id != self.product_definition_id:
                errors["product_version"] = "产品版本必须属于订单行产品"
        if self.manufacturing_output_id:
            output = self.manufacturing_output
            if output.release_status != "released_to_manufacturing":
                errors["manufacturing_output"] = "未发布或已失效工程组合不得进入新销售制造需求"
            if output.release_subject_type == "LONG_TERM_PRODUCT":
                if not self.product_definition_id or output.product_id != self.product_definition_id:
                    errors["manufacturing_output"] = "长期产品工程发布组合必须属于订单行产品"
                if not self.product_version_id or output.product_version_id != self.product_version_id:
                    errors["manufacturing_output"] = "长期产品工程发布组合必须引用订单行产品版本"
                if (
                    self.product_definition_id
                    and self.product_definition.manufacturing_definition_mode == "order_engineered"
                ):
                    if output.definition_mode != "order_specific":
                        errors["manufacturing_output"] = "按单形成的长期产品必须引用按单制造定义"
                    elif (
                        not output.order_engineering_instance_id
                        or output.order_engineering_instance.sales_order_item_id != self.pk
                    ):
                        errors["manufacturing_output"] = "按单制造定义必须属于当前销售订单明细"
            else:
                if self.engineering_mode != "ORDER_ENGINEERED":
                    errors["manufacturing_output"] = "订单工程产品发布组合只能绑定按单工程订单行"
                elif (
                    not output.order_engineering_instance_id
                    or output.order_engineering_instance.sales_order_item_id != self.pk
                ):
                    errors["manufacturing_output"] = "订单工程产品发布组合必须属于当前销售订单明细"
        if errors:
            raise ValidationError(errors)

    @property
    def amount(self):
        return self.quantity * self.unit_price

    @property
    def legal_entity_id(self):
        return self.sales_order.company_id

    @property
    def supply_admission_order_status(self):
        return self.sales_order.status


class SalesOrderActionRequest(models.Model):
    """One durable result for one explicit order action request."""

    sales_order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name="action_requests")
    action_code = models.CharField(max_length=120)
    idempotency_key = models.CharField(max_length=160)
    request_id = models.CharField(max_length=160)
    source = models.CharField(max_length=80, default="api")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales_order_action_requests")
    source_state = models.CharField(max_length=40)
    target_state = models.CharField(max_length=40)
    audit_record = models.ForeignKey(
        "system.OrganizationOperatingAuditRecord", on_delete=models.PROTECT,
        related_name="sales_order_action_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sales_order_action_request"
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("sales_order", "action_code", "idempotency_key"),
                name="uniq_sales_order_action_idempotency",
            ),
            models.UniqueConstraint(
                fields=("sales_order", "request_id"),
                name="uniq_sales_order_request_id",
            ),
        ]


class SalesOrderItemEngineeringAttribute(models.Model):
    """Industry-neutral, lossless engineering input fact for one order line."""

    SOURCE_TYPE_CHOICES = (
        ("CUSTOMER", "客户"),
        ("SITE_MEASUREMENT", "现场测量"),
        ("SALES", "销售"),
        ("DESIGN", "设计"),
        ("ENGINEERING_INPUT", "工程输入"),
        ("ENGINEERING_DERIVED", "工程派生"),
        ("MASTER_DATA", "主数据"),
        ("RULE_PARAMETER", "规则参数"),
        ("AGGREGATED", "汇总"),
    )
    VALUE_TYPE_CHOICES = (
        ("string", "文本"),
        ("decimal", "小数"),
        ("integer", "整数"),
        ("boolean", "布尔"),
        ("date", "日期"),
        ("datetime", "日期时间"),
        ("code", "编码"),
        ("json", "结构化值"),
    )
    RAW_IMMUTABLE_FIELDS = (
        "raw_source", "raw_sheet", "external_source", "raw_field", "raw_value",
    )

    sales_order_item = models.ForeignKey(
        SalesOrderItem, on_delete=models.PROTECT,
        related_name="engineering_attributes", verbose_name="销售订单明细",
    )
    sequence = models.PositiveIntegerField(default=1)
    raw_source = models.CharField(max_length=200)
    raw_sheet = models.CharField(max_length=120, blank=True, default="")
    external_source = models.CharField(max_length=200, blank=True, default="")
    raw_field = models.CharField(max_length=160)
    raw_value = models.JSONField()
    canonical_field = models.CharField(max_length=160)
    normalized_value = models.JSONField(null=True, blank=True)
    value_type = models.CharField(max_length=20, choices=VALUE_TYPE_CHOICES)
    unit = models.ForeignKey(
        "masterdata.UnitOfMeasure", on_delete=models.PROTECT, null=True, blank=True,
        related_name="sales_order_engineering_attributes", verbose_name="规范计量单位",
    )
    source_type = models.CharField(max_length=32, choices=SOURCE_TYPE_CHOICES)
    engineering_document_version = models.ForeignKey(
        "pde.EngineeringDocumentVersion", on_delete=models.PROTECT,
        null=True, blank=True, related_name="sales_order_engineering_attributes",
        verbose_name="来源工程资料版本",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_sales_order_engineering_attributes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sales_order_item_engineering_attribute"
        ordering = ("sales_order_item_id", "sequence", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("sales_order_item", "canonical_field", "sequence"),
                name="uniq_sales_item_eng_attr_canonical_sequence",
            )
        ]

    def clean(self):
        errors = {}
        company_id = self.sales_order_item.sales_order.company_id
        if self.unit_id and self.unit.company_id != company_id:
            errors["unit"] = "工程属性单位必须属于销售订单公司"
        if (
            self.engineering_document_version_id
            and (
                self.engineering_document_version.related_product.company_id
                if self.engineering_document_version.related_product_id
                else self.engineering_document_version.order_engineering_instance.company_id
            ) != company_id
        ):
            errors["engineering_document_version"] = "工程资料版本必须属于销售订单公司"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.only(*self.RAW_IMMUTABLE_FIELDS).get(pk=self.pk)
            changed = [
                field for field in self.RAW_IMMUTABLE_FIELDS
                if getattr(original, field) != getattr(self, field)
            ]
            if changed:
                raise ValidationError({field: "原始工程事实创建后不可覆盖" for field in changed})
        return super().save(*args, **kwargs)


class SalesOrderItemSupplyAdmission(models.Model):
    """Immutable order-line decision, not a material or engineering attribute."""

    class SupplyType(models.TextChoices):
        MAKE = "MAKE", "自产"
        BUY = "BUY", "采购"

    sales_order_item = models.OneToOneField(
        SalesOrderItem, on_delete=models.PROTECT, related_name="supply_admission",
    )
    supply_type = models.CharField(max_length=16, choices=SupplyType.choices)
    responsibility_type = models.CharField(
        max_length=64, default="ORDER_LINE_SUPPLY_ADMISSION_CONFIRMER",
    )
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    employee = models.ForeignKey("pfm.Employee", on_delete=models.PROTECT)
    position_responsibility = models.ForeignKey("system.PositionResponsibility", on_delete=models.PROTECT)
    workflow_responsibility = models.ForeignKey("system.PositionWorkflowResponsibility", on_delete=models.PROTECT)
    confirmed_at = models.DateTimeField()
    audit_record = models.OneToOneField("system.OrganizationOperatingAuditRecord", on_delete=models.PROTECT)
    idempotency_key = models.CharField(max_length=160, unique=True)
    request_hash = models.CharField(max_length=64)
    fact_hash = models.CharField(max_length=64)
    reason = models.CharField(max_length=300)
    source_snapshot = models.JSONField()
    responsibility_snapshot = models.JSONField()

    class Meta:
        db_table = "sales_order_item_supply_admission"
        constraints = [
            models.CheckConstraint(condition=models.Q(supply_type__in=("MAKE", "BUY")), name="sales_item_supply_type_supported"),
            models.CheckConstraint(condition=models.Q(responsibility_type="ORDER_LINE_SUPPLY_ADMISSION_CONFIRMER"), name="sales_item_supply_responsibility_type"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("订单行供应承接确认事实不可覆盖；变更须另行授权正式撤回流程。")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("订单行供应承接确认事实及审计不得删除。")

class OrderSourceFormalScope(models.Model):
    """Registered sales lines for one immutable CRM source version."""

    source = models.OneToOneField("pde.EngineeringSourceRecord", on_delete=models.PROTECT)
    source_version = models.CharField(max_length=40)
    content_hash = models.CharField(max_length=64)
    items = models.JSONField()
    registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registered_at = models.DateTimeField(auto_now_add=True)


from .followup_models import CustomerAccountBinding, CustomerProgressPublication, ProductionFollowupAssignment  # noqa: F401
