from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0005_project_selector_linkage_r5"),
        ("procurement", "0018_supplier_delivery_address_v11428427228"),
    ]

    operations = [
        migrations.CreateModel(
            name="PriceApprovalResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("result_no", models.CharField(max_length=160, unique=True)),
                ("preparation_identity", models.CharField(max_length=160, unique=True)),
                ("original_source_type", models.CharField(max_length=64)),
                ("original_source_object_id", models.CharField(blank=True, default="", max_length=160)),
                ("original_source_reference", models.CharField(max_length=255)),
                ("source_trace", models.JSONField(default=dict)),
                ("approved_price", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency", models.CharField(max_length=16)),
                ("tax_rate", models.DecimalField(decimal_places=2, max_digits=5)),
                ("tax_rate_source", models.CharField(max_length=100)),
                ("approval_conclusion", models.CharField(default="pass", max_length=16)),
                ("selected_supplier", models.JSONField(default=dict)),
                ("approved_by", models.CharField(max_length=120)),
                ("approved_at", models.DateTimeField()),
                ("confirmed_by", models.CharField(max_length=120)),
                ("confirmed_at", models.DateTimeField()),
                ("review_opinion", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="formal_price_approval_results", to="masterdata.material")),
                ("preparation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="formal_price_approval_results", to="procurement.priceapprovalpreparation")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="formal_price_approval_results", to="procurement.supplier")),
            ],
            options={"db_table": "supplier_price_approval_result", "ordering": ["-confirmed_at", "-id"]},
        ),
        migrations.CreateModel(
            name="SupplierMaterialPrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price_no", models.CharField(max_length=160, unique=True)),
                ("approved_price", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency", models.CharField(max_length=16)),
                ("tax_rate", models.DecimalField(decimal_places=2, max_digits=5)),
                ("tax_rate_source", models.CharField(max_length=100)),
                ("effective_date", models.DateField()),
                ("expiry_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("ACTIVE", "有效"), ("INACTIVE", "失效")], default="ACTIVE", max_length=16)),
                ("price_source_type", models.CharField(default="PriceApprovalResult", max_length=64)),
                ("price_source_label", models.CharField(default="人工核价确认", max_length=100)),
                ("original_source_type", models.CharField(max_length=64)),
                ("original_source_reference", models.CharField(max_length=255)),
                ("approved_by", models.CharField(max_length=120)),
                ("approved_at", models.DateTimeField()),
                ("confirmed_by", models.CharField(max_length=120)),
                ("confirmed_at", models.DateTimeField()),
                ("modified_by", models.CharField(blank=True, default="", max_length=120)),
                ("modified_at", models.DateTimeField(blank=True, null=True)),
                ("modification_reason", models.TextField(blank=True, default="")),
                ("modification_audit", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="effective_supplier_prices", to="masterdata.material")),
                ("price_approval_result", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="effective_price", to="masterdata.priceapprovalresult")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="effective_material_prices", to="procurement.supplier")),
            ],
            options={"db_table": "supplier_material_price", "ordering": ["-confirmed_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="suppliermaterialprice",
            constraint=models.CheckConstraint(condition=models.Q(("approved_price__gt", 0)), name="supplier_material_price_positive_price"),
        ),
    ]
