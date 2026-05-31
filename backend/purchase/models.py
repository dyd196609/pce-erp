from django.db import models

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]
    orderNo = models.CharField(max_length=50, unique=True, verbose_name='订单号')
    customer = models.CharField(max_length=100, verbose_name='客户')
    contact = models.CharField(max_length=50, verbose_name='联系人')
    createDate = models.DateField(verbose_name='创建日期')
    dueDate = models.DateField(verbose_name='截止日期')
    completeDate = models.DateField(null=True, blank=True, verbose_name='完成日期')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='金额')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')

    class Meta:
        db_table = 'purchase_orders'
        ordering = ['-createDate']

    def __str__(self):
        return self.orderNo