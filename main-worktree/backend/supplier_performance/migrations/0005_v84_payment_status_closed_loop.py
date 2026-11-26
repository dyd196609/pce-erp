from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("supplier_performance", "0004_v831_workflow_actions")]

    operations = [
        migrations.AddField(
            model_name="buyerperformancemetric",
            name="payment_request_timeliness_rate",
            field=models.DecimalField(decimal_places=2, default=100, max_digits=7),
        ),
        migrations.AddField(
            model_name="buyerperformancemetric",
            name="settlement_exception_rate",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
        migrations.AddField(
            model_name="buyerperformancemetric",
            name="source_settlement_completion_nos",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="supplierperformancemetric",
            name="completed_settlement_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="supplierperformancemetric",
            name="timely_payment_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="supplierperformancemetric",
            name="abnormal_settlement_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="supplierperformancemetric",
            name="source_settlement_completion_nos",
            field=models.JSONField(default=list),
        ),
        migrations.CreateModel(
            name="SupplierPaymentStatusRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payment_request_no", models.CharField(max_length=80, unique=True)),
                ("supplier_id", models.CharField(max_length=80)),
                ("supplier_name", models.CharField(max_length=160)),
                ("payment_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("status", models.CharField(choices=[("draft", "待提交"), ("submitted", "审核中"), ("approved", "已批准"), ("payment_scheduled", "付款安排中"), ("payment_completed", "付款完成"), ("settlement_completed", "结算完成")], max_length=40)),
                ("operator", models.CharField(max_length=160)),
                ("operate_time", models.DateTimeField()),
                ("remark", models.CharField(blank=True, max_length=255)),
                ("tenant_id", models.CharField(max_length=64)),
                ("batch_id", models.CharField(max_length=80)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "supplier_payment_status_records"},
        ),
        migrations.CreateModel(
            name="SupplierSettlementCompletion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("settlement_no", models.CharField(max_length=80, unique=True)),
                ("supplier_id", models.CharField(max_length=80)),
                ("supplier_name", models.CharField(max_length=160)),
                ("reconciliation_no", models.CharField(max_length=80)),
                ("payment_request_no", models.CharField(max_length=80, unique=True)),
                ("status", models.CharField(choices=[("pending", "待确认"), ("completed", "结算完成")], max_length=40)),
                ("completion_date", models.DateField(blank=True, null=True)),
                ("performance_update_flag", models.BooleanField(default=False)),
                ("tenant_id", models.CharField(max_length=64)),
                ("batch_id", models.CharField(max_length=80)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "supplier_settlement_completions"},
        ),
        migrations.AddIndex(
            model_name="supplierpaymentstatusrecord",
            index=models.Index(fields=["tenant_id", "batch_id", "status"], name="supplier_psr_tenant_v84_idx"),
        ),
        migrations.AddIndex(
            model_name="suppliersettlementcompletion",
            index=models.Index(fields=["tenant_id", "batch_id", "status"], name="supplier_sc_tenant_v84_idx"),
        ),
    ]
