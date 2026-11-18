from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0006_price_approval_result_supplier_material_price_v45_8"),
        ("procurement", "0019_supplier_master_reverse_enrichment_v1142842724511"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorder", name="purchase_mode",
            field=models.CharField(choices=[("STANDARD", "标准采购"), ("LEGACY", "历史兼容")], default="LEGACY", max_length=24),
        ),
        migrations.AddField(model_name="purchaseorder", name="source_type", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="purchaseorder", name="source_reference", field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(model_name="purchaseorder", name="source_trace", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(
            model_name="purchaseorder", name="price_trace_status",
            field=models.CharField(choices=[("CURRENT_LINKED", "当前已链接"), ("LEGACY_UNTRACED", "历史未追溯")], default="LEGACY_UNTRACED", max_length=24),
        ),
        migrations.AddField(model_name="purchaseorder", name="supplier_code_snapshot", field=models.CharField(blank=True, default="", max_length=50)),
        migrations.AddField(model_name="purchaseorder", name="supplier_name_snapshot", field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="purchaseorder", name="supplier_contact_snapshot", field=models.CharField(blank=True, default="", max_length=50)),
        migrations.AddField(model_name="purchaseorder", name="supplier_phone_snapshot", field=models.CharField(blank=True, default="", max_length=20)),
        migrations.AddField(model_name="purchaseorder", name="supplier_address_snapshot", field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(model_name="purchaseorder", name="delivery_address_snapshot", field=models.CharField(blank=True, default="", max_length=255)),
        migrations.AddField(
            model_name="purchaseorderitem", name="source_purchase_request_item",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="standard_purchase_order_items", to="procurement.purchaserequestitem"),
        ),
        migrations.AddField(
            model_name="purchaseorderitem", name="price_approval_result",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_order_items", to="masterdata.priceapprovalresult"),
        ),
        migrations.AddField(
            model_name="purchaseorderitem", name="supplier_material_price",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_order_items", to="masterdata.suppliermaterialprice"),
        ),
        migrations.AddField(model_name="purchaseorderitem", name="material_code_snapshot", field=models.CharField(blank=True, default="", max_length=50)),
        migrations.AddField(model_name="purchaseorderitem", name="material_name_snapshot", field=models.CharField(blank=True, default="", max_length=200)),
        migrations.AddField(model_name="purchaseorderitem", name="specification_snapshot", field=models.CharField(blank=True, default="", max_length=200)),
        migrations.AddField(model_name="purchaseorderitem", name="unit_snapshot", field=models.CharField(blank=True, default="", max_length=40)),
        migrations.AddField(model_name="purchaseorderitem", name="unit_price_snapshot", field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
        migrations.AddField(model_name="purchaseorderitem", name="tax_rate_snapshot", field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
        migrations.AddField(model_name="purchaseorderitem", name="currency_snapshot", field=models.CharField(blank=True, default="", max_length=16)),
    ]
