from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0006_price_approval_result_supplier_material_price_v45_8"),
        ("procurement", "0021_purchase_mode_entry_v46_batch22_r1"),
    ]

    operations = [
        migrations.AddField(model_name="purchaserequestitem", name="supplier",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="priced_purchase_request_items", to="procurement.supplier")),
        migrations.AddField(model_name="purchaserequestitem", name="supplier_material_price",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="purchase_request_items", to="masterdata.suppliermaterialprice")),
        migrations.AddField(model_name="purchaserequestitem", name="price_record_code",
            field=models.CharField(blank=True, default="", max_length=160)),
        migrations.AddField(model_name="purchaserequestitem", name="unit_price_snapshot",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
        migrations.AddField(model_name="purchaserequestitem", name="tax_rate_snapshot",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
        migrations.AddField(model_name="purchaserequestitem", name="currency_snapshot",
            field=models.CharField(blank=True, default="", max_length=16)),
        migrations.AddField(model_name="purchaserequestitem", name="price_effective_date_snapshot",
            field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="purchaseorder", name="source_purchase_request",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="purchase_orders", to="procurement.purchaserequest")),
    ]
