from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("supplier_performance", "0001_initial")]

    operations = [
        migrations.AddField("buyerperformancemetric", "difference_responsibility_count", models.PositiveIntegerField(default=0)),
        migrations.AddField("buyerperformancemetric", "supplier_issue_count", models.PositiveIntegerField(default=0)),
        migrations.AddField("buyerperformancemetric", "price_difference_count", models.PositiveIntegerField(default=0)),
        migrations.AddField("buyerperformancemetric", "delivery_delay_count", models.PositiveIntegerField(default=0)),
        migrations.CreateModel(
            name="SupplierReconciliationDifference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("difference_no", models.CharField(max_length=80, unique=True)),
                ("reconciliation_no", models.CharField(max_length=80)),
                ("supplier_id", models.CharField(max_length=80)),
                ("supplier_name", models.CharField(max_length=160)),
                ("buyer_id", models.CharField(blank=True, max_length=80)),
                ("buyer_name", models.CharField(blank=True, max_length=160)),
                ("difference_type", models.CharField(choices=[("quantity_difference", "数量差异"), ("quality_difference", "质量差异"), ("price_difference", "价格差异"), ("delivery_difference", "交付差异"), ("other_difference", "其他差异")], max_length=40)),
                ("difference_amount", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("difference_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("responsibility_type", models.CharField(choices=[("supplier", "供应商责任"), ("buyer", "采购责任"), ("warehouse", "仓库责任"), ("quality", "质量责任"), ("unknown", "待确认")], max_length=40)),
                ("occurred_at", models.DateField()),
                ("source_object_refs", models.JSONField(default=dict)),
                ("tenant_id", models.CharField(max_length=64)),
                ("batch_id", models.CharField(max_length=80)),
                ("status", models.CharField(choices=[("draft", "草稿"), ("analyzing", "分析中"), ("responsibility_confirmed", "责任已确认"), ("supplier_communicating", "供应商沟通中"), ("closed", "已关闭")], max_length=40)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "supplier_reconciliation_differences"},
        ),
        migrations.AddIndex("supplierreconciliationdifference", models.Index(fields=["tenant_id", "batch_id", "status"], name="supplier_di_tenant__a82_idx")),
        migrations.AddIndex("supplierreconciliationdifference", models.Index(fields=["supplier_id", "occurred_at"], name="supplier_di_supplie_a82_idx")),
        migrations.CreateModel(
            name="SupplierReconciliationConfirmation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("confirmation_no", models.CharField(max_length=80, unique=True)),
                ("difference_no", models.CharField(max_length=80, unique=True)),
                ("supplier_id", models.CharField(max_length=80)),
                ("supplier_response", models.CharField(max_length=40)),
                ("supplier_comment", models.TextField(blank=True)),
                ("confirmed_by", models.CharField(blank=True, max_length=160)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("tenant_id", models.CharField(max_length=64)),
                ("batch_id", models.CharField(max_length=80)),
                ("status", models.CharField(choices=[("waiting_supplier", "等待供应商确认"), ("supplier_confirmed", "供应商已确认"), ("internal_verified", "内部已复核"), ("completed", "协同确认完成")], max_length=40)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "supplier_reconciliation_confirmations"},
        ),
        migrations.AddIndex("supplierreconciliationconfirmation", models.Index(fields=["tenant_id", "batch_id", "status"], name="supplier_co_tenant__a82_idx")),
    ]
