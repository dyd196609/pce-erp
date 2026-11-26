from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("procurement", "0018_supplier_delivery_address_v11428427228")]

    operations = [
        migrations.AddField(
            model_name="supplier", name="data_origin",
            field=models.CharField(default="BUSINESS_FACT", max_length=40),
        ),
        migrations.AddField(
            model_name="supplier", name="source_evidence",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="supplier", name="enrichment_audit",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name="SupplierBusinessReferenceMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("legacy_supplier_code", models.CharField(max_length=80, unique=True)),
                ("legacy_supplier_name", models.CharField(max_length=200)),
                ("evidence", models.JSONField(default=list)),
                ("evidence_status", models.CharField(default="UNIQUE_CONFIRMED", max_length=32)),
                ("source_version", models.CharField(max_length=64)),
                ("created_by", models.CharField(max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="business_reference_mappings", to="procurement.supplier")),
            ],
            options={"db_table": "supplier_business_reference_mapping",
                     "ordering": ["legacy_supplier_code", "id"]},
        ),
    ]
