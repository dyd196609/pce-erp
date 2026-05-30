from django.db import models
from django.utils import timezone
from datetime import date


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
    tax_id = models.CharField(max_length=50, blank=True, null=True)
    credit_rating = models.CharField(max_length=1, choices=CREDIT_RATINGS, default="B")
    payment_terms = models.CharField(max_length=50, blank=True, null=True)
    lead_time = models.IntegerField(default=0)
    company_id = models.BigIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier"
        managed = True
        verbose_name = "供应商"
        verbose_name_plural = "供应商"

    def __str__(self):
        return f"{self.code} - {self.name}"


class PurchaseOrder(models.Model):
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

    # ===== 在这里插入 department 字段 =====
    department = models.ForeignKey(
        "system.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="所属部门",
    )
    # =================================

    created_by = models.BigIntegerField(blank=True, null=True)

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
