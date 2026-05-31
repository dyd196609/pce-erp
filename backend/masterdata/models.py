from django.db import models


class MaterialCategory(models.Model):
    """物料分类表"""
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True,
                               blank=True, related_name='children', db_column='parent_id')
    company_id = models.BigIntegerField()
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'material_category'
        managed = True
        verbose_name = '物料分类'
        verbose_name_plural = '物料分类'

    def __str__(self):
        return self.name


class Material(models.Model):
    """物料主数据表"""
    MATERIAL_TYPES = [
        ('raw', '原材料'),
        ('semi', '半成品'),
        ('finished', '成品'),
        ('auxiliary', '辅料'),
    ]
    COST_METHODS = [
        ('weighted_avg', '月加权平均'),
        ('specific_id', '分批认定法'),
        ('standard', '标准成本法'),
    ]

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    specification = models.CharField(max_length=200, blank=True, null=True)
    category = models.ForeignKey(
        MaterialCategory, on_delete=models.SET_NULL, null=True, blank=True, db_column='category_id')
    unit = models.CharField(max_length=20)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='单价')
    purchase_unit = models.CharField(max_length=20, blank=True, null=True)
    conversion_rate = models.DecimalField(
        max_digits=12, decimal_places=4, default=1)
    material_type = models.CharField(
        max_length=20, choices=MATERIAL_TYPES, default='raw')
    safety_stock = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    max_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_point = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    economic_order_qty = models.DecimalField(
        max_digits=12, decimal_places=2, blank=True, null=True)
    lead_time = models.IntegerField(default=0)
    is_purchased = models.BooleanField(default=False)
    is_produced = models.BooleanField(default=False)
    cost_method = models.CharField(
        max_length=20, choices=COST_METHODS, default='weighted_avg')
    standard_cost = models.DecimalField(
        max_digits=12, decimal_places=4, default=0)
    last_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    company_id = models.BigIntegerField()
    is_active = models.BooleanField(default=True)
    created_by = models.BigIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'material'
        managed = True
        verbose_name = '物料'
        verbose_name_plural = '物料'

    def __str__(self):
        return f"{self.code} - {self.name}"


class CodeRule(models.Model):
    """编码规则表"""
    entity_type = models.CharField(max_length=50, unique=True)
    prefix = models.CharField(max_length=20, blank=True, null=True)
    date_format = models.CharField(max_length=20, blank=True, null=True)
    seq_length = models.IntegerField(default=4)
    current_seq = models.IntegerField(default=0)
    company_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'code_rule'
        managed = False
        verbose_name = '编码规则'
        verbose_name_plural = '编码规则'

    def get_next_code(self):
        """生成下一个编码"""
        import datetime
        seq = str(self.current_seq + 1).zfill(self.seq_length)
        date_part = datetime.datetime.now().strftime(
            self.date_format) if self.date_format else ''
        code = f"{self.prefix or ''}{date_part}{seq}"
        self.current_seq += 1
        self.save()
        return code
