from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("procurement", "0009_purchase_request_business_flow_r7")]

    operations = [
        migrations.CreateModel(
            name="SupplierQuotation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("items", models.JSONField(blank=True, default=list)),
                ("quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quotation_no", models.CharField(max_length=100, unique=True)),
                ("supplier_id", models.CharField(max_length=80)),
                ("supplier_name", models.CharField(max_length=200)),
                ("price", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("currency", models.CharField(default="CNY", max_length=12)),
                ("quotation_status", models.CharField(choices=[("draft", "草稿"), ("saved", "已保存"), ("submitted", "已提交"), ("received", "已接收"), ("closed", "已关闭"), ("cancelled", "已取消")], default="draft", max_length=20)),
                ("received_at", models.DateTimeField(blank=True, null=True)),
                ("source_inquiry", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_quotations", to="procurement.purchaseinquiry")),
            ],
            options={"db_table": "scm_supplier_quotation", "ordering": ["-id"]},
        ),
        migrations.AddConstraint(
            model_name="supplierquotation",
            constraint=models.UniqueConstraint(fields=("source_inquiry", "supplier_id"), name="scm_sq_inquiry_supplier_unique"),
        ),
        migrations.AddConstraint(
            model_name="supplierquotation",
            constraint=models.CheckConstraint(condition=models.Q(("price__gte", 0)), name="scm_sq_price_nonnegative"),
        ),
    ]
