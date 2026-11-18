from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("procurement", "0026_location_lot_identity_a1")]

    operations = [
        migrations.RemoveConstraint(model_name="inventorylot", name="scm_inventory_lot_unique"),
        migrations.AddField(model_name="inventorylot", name="warehouse", field=models.ForeignKey(blank=True, help_text="历史批号允许为空；A1.5以后新业务可记录正式仓库维度。", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inventory_lots", to="procurement.warehouse", verbose_name="所属仓库")),
        migrations.AddConstraint(model_name="inventorylot", constraint=models.UniqueConstraint(fields=("company_id", "material", "warehouse", "lot_no"), name="scm_inventory_lot_unique")),
        migrations.AddField(model_name="warehouseinbound", name="location", field=models.ForeignKey(blank=True, help_text="历史入库允许为空；新业务可记录正式默认库位。", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_inbounds", to="procurement.warehouselocation")),
        migrations.RemoveConstraint(model_name="inventorybalance", name="scm_inventory_balance_unique"),
        migrations.AddField(model_name="inventorybalance", name="location", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inventory_balances", to="procurement.warehouselocation")),
        migrations.AddField(model_name="inventorybalance", name="lot", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inventory_balances", to="procurement.inventorylot")),
        migrations.AddConstraint(model_name="inventorybalance", constraint=models.UniqueConstraint(condition=models.Q(("location__isnull", True), ("lot__isnull", True)), fields=("warehouse", "material"), name="scm_inventory_balance_legacy_unique")),
        migrations.AddConstraint(model_name="inventorybalance", constraint=models.UniqueConstraint(condition=models.Q(("location__isnull", False), ("lot__isnull", True)), fields=("warehouse", "material", "location"), name="scm_inventory_balance_location_unique")),
        migrations.AddConstraint(model_name="inventorybalance", constraint=models.UniqueConstraint(condition=models.Q(("location__isnull", True), ("lot__isnull", False)), fields=("warehouse", "material", "lot"), name="scm_inventory_balance_lot_unique")),
        migrations.AddConstraint(model_name="inventorybalance", constraint=models.UniqueConstraint(condition=models.Q(("location__isnull", False), ("lot__isnull", False)), fields=("warehouse", "material", "location", "lot"), name="scm_inventory_balance_dimension_unique")),
        migrations.AddField(model_name="inventorytransaction", name="location", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inventory_transactions", to="procurement.warehouselocation")),
        migrations.AddField(model_name="inventorytransaction", name="lot", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="inventory_transactions", to="procurement.inventorylot")),
    ]
