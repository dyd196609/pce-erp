from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0009_unit_and_code_governance_a1"),
        ("procurement", "0025_purchase_request_purchase_plan_source_v1"),
    ]

    operations = [
        migrations.CreateModel(
            name="WarehouseLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=80, verbose_name="库位编码")),
                ("name", models.CharField(max_length=120, verbose_name="库位名称")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="locations", to="procurement.warehouse", verbose_name="所属仓库")),
            ],
            options={"db_table": "scm_warehouse_location", "ordering": ["warehouse_id", "code"]},
        ),
        migrations.AddConstraint(model_name="warehouselocation", constraint=models.UniqueConstraint(fields=("warehouse", "code"), name="scm_warehouse_location_unique")),
        migrations.CreateModel(
            name="InventoryLot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("lot_no", models.CharField(max_length=100, verbose_name="批号")),
                ("company_id", models.BigIntegerField(verbose_name="所属公司ID")),
                ("production_date", models.DateField(blank=True, null=True, verbose_name="生产日期")),
                ("expiry_date", models.DateField(blank=True, null=True, verbose_name="有效日期")),
                ("reinspection_date", models.DateField(blank=True, null=True, verbose_name="复检日期")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_lots", to="masterdata.material", verbose_name="物料")),
            ],
            options={"db_table": "scm_inventory_lot", "ordering": ["company_id", "material_id", "lot_no"]},
        ),
        migrations.AddConstraint(model_name="inventorylot", constraint=models.UniqueConstraint(fields=("company_id", "material", "lot_no"), name="scm_inventory_lot_unique")),
    ]

