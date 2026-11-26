from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0003_materialcategory_parent"),
        ("system", "0003_menu_rolemenu"),
        ("procurement", "0006_purchase_request_lifecycle_v1142142"),
    ]

    operations = [
        migrations.AddField(model_name="purchaserequest", name="request_type", field=models.CharField(choices=[("production", "生产需求"), ("stock_replenishment", "库存补充"), ("engineering", "工程需求"), ("equipment", "设备需求"), ("other", "其他需求")], default="other", max_length=32)),
        migrations.AddField(model_name="purchaserequest", name="source_type", field=models.CharField(choices=[("PDEManufacturingInput", "PDE制造输入"), ("MRPRequirement", "MRP需求"), ("InventoryReplenishment", "库存补充"), ("ManualRequest", "人工申请")], default="ManualRequest", max_length=40)),
        migrations.AddField(model_name="purchaserequest", name="requester_employee_no", field=models.CharField(blank=True, default="", max_length=50)),
        migrations.AddField(model_name="purchaserequest", name="requester_employee_id", field=models.BigIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="purchaserequest", name="department_master", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="requested_purchase_requests", to="system.department")),
        migrations.AddField(model_name="purchaserequest", name="purchase_department_master", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="managed_purchase_requests", to="system.department")),
        migrations.CreateModel(
            name="PurchaseRequestItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("material_code", models.CharField(max_length=50)),
                ("material_name", models.CharField(max_length=200)),
                ("specification", models.CharField(blank=True, default="", max_length=200)),
                ("unit", models.CharField(max_length=20)),
                ("material_category", models.CharField(blank=True, default="", max_length=100)),
                ("purchase_attribute", models.CharField(blank=True, default="", max_length=80)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("required_date", models.DateField()),
                ("remark", models.CharField(blank=True, default="", max_length=500)),
                ("line_no", models.PositiveIntegerField(default=1)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_request_items", to="masterdata.material")),
                ("purchase_request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="request_items", to="procurement.purchaserequest")),
            ],
            options={"db_table": "scm_purchase_request_item", "ordering": ["line_no", "id"]},
        ),
        migrations.AddConstraint(model_name="purchaserequestitem", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="scm_pr_item_quantity_positive")),
        migrations.AddConstraint(model_name="purchaserequestitem", constraint=models.UniqueConstraint(fields=("purchase_request", "line_no"), name="scm_pr_item_line_unique")),
    ]
