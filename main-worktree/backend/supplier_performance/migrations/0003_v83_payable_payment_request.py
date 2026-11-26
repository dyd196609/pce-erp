from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("supplier_performance", "0002_v82_difference_collaboration")]
    operations = [
        migrations.AddField("buyerperformancemetric", "payable_confirmation_delay", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
        migrations.AddField("buyerperformancemetric", "payment_request_accuracy", models.DecimalField(decimal_places=2, default=100, max_digits=7)),
        migrations.CreateModel(
            name="SupplierPayableConfirmation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payable_confirmation_no", models.CharField(max_length=80, unique=True)),
                ("supplier_id", models.CharField(max_length=80)), ("supplier_name", models.CharField(max_length=160)),
                ("reconciliation_no", models.CharField(max_length=80)), ("period", models.CharField(max_length=7)),
                ("confirmed_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("qualified_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("deduction_amount", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("final_payable_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("source_object_refs", models.JSONField(default=dict)), ("tenant_id", models.CharField(max_length=64)),
                ("batch_id", models.CharField(max_length=80)),
                ("status", models.CharField(choices=[("draft", "草稿"), ("internal_review", "内部审核中"), ("confirmed", "应付已确认"), ("ready_for_payment_request", "可申请付款")], max_length=40)),
                ("version", models.PositiveIntegerField(default=1)), ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ], options={"db_table": "supplier_payable_confirmations"},
        ),
        migrations.AddIndex("supplierpayableconfirmation", models.Index(fields=["tenant_id", "batch_id", "status"], name="supplier_pc_tenant_v83_idx")),
        migrations.CreateModel(
            name="SupplierPaymentRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payment_request_no", models.CharField(max_length=80, unique=True)),
                ("payable_confirmation_no", models.CharField(max_length=80, unique=True)),
                ("supplier_id", models.CharField(max_length=80)), ("supplier_name", models.CharField(max_length=160)),
                ("period", models.CharField(max_length=7)), ("request_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("request_reason", models.CharField(max_length=255)), ("requested_by", models.CharField(max_length=160)),
                ("tenant_id", models.CharField(max_length=64)), ("batch_id", models.CharField(max_length=80)),
                ("status", models.CharField(choices=[("draft", "草稿"), ("submitted", "已提交"), ("approved", "申请已批准"), ("payment_pending", "待后续付款处理")], max_length=40)),
                ("version", models.PositiveIntegerField(default=1)), ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ], options={"db_table": "supplier_payment_requests"},
        ),
        migrations.AddIndex("supplierpaymentrequest", models.Index(fields=["tenant_id", "batch_id", "status"], name="supplier_pr_tenant_v83_idx")),
    ]
