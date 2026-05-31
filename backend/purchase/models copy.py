from django.db import models

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('submitted', '待审批'),
        ('approved', '已审批'),
        ('cancelled', '已取消'),
    ]
    
    po_no = models.CharField(max_length=50, unique=True, verbose_name='订单号')
    supplier = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, verbose_name='供应商')
    supplier_name = models.CharField(max_length=100, blank=True, verbose_name='供应商名称')
    order_date = models.DateField(auto_now_add=True, verbose_name='订单日期')
    expected_date = models.DateField(blank=True, null=True, verbose_name='预计到货日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总金额')
    remark = models.TextField(blank=True, verbose_name='备注')
    created_by = models.IntegerField(blank=True, null=True)
    company_id = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f'{self.po_no} - {self.supplier_name}'
    
    class Meta:
        db_table = 'purchase_order'
        verbose_name = '采购订单'
        verbose_name_plural = '采购订单'


class PurchaseOrderItem(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items', verbose_name='订单')
    product_name = models.CharField(max_length=200, blank=True, null=True, verbose_name='商品名称')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='数量')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='单价')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='小计')
    
    def __str__(self):
        return f'{self.order.po_no} - {self.product_name}'
    
    class Meta:
        db_table = 'purchase_order_item'
        verbose_name = '采购订单明细'
        verbose_name_plural = '采购订单明细'


class Supplier(models.Model):
    name = models.CharField(max_length=100, verbose_name='供应商名称')
    contact_person = models.CharField(max_length=50, blank=True, verbose_name='联系人')
    phone = models.CharField(max_length=20, blank=True, verbose_name='联系电话')
    address = models.TextField(blank=True, verbose_name='地址')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'supplier'
        verbose_name = '供应商'
        verbose_name_plural = '供应商'