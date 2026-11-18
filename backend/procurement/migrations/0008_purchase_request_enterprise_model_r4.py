from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0004_enterprise_procurement_dimensions_r4"),
        ("system", "0003_menu_rolemenu"),
        ("procurement", "0007_purchase_request_smart_form_r3"),
    ]

    operations = [
        migrations.AddField(model_name="purchaserequest", name="usage_department", field=models.CharField(blank=True, default="", max_length=120)),
        migrations.AddField(model_name="purchaserequest", name="usage_department_master", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="used_purchase_requests", to="system.department")),
        migrations.AddField(model_name="purchaserequest", name="project", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_requests", to="masterdata.projectmaster")),
        migrations.AddField(model_name="purchaserequest", name="project_code", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="purchaserequest", name="project_name", field=models.CharField(blank=True, default="", max_length=200)),
        migrations.AddField(model_name="purchaserequest", name="project_stage", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="purchaserequest", name="cost_center", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_requests", to="masterdata.costcenter")),
        migrations.AddField(model_name="purchaserequest", name="cost_center_code", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="purchaserequest", name="cost_center_name", field=models.CharField(blank=True, default="", max_length=200)),
        migrations.AddField(model_name="purchaserequest", name="expense_category", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_requests", to="masterdata.expensecategory")),
        migrations.AddField(model_name="purchaserequest", name="expense_category_code", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="purchaserequest", name="expense_category_name", field=models.CharField(blank=True, default="", max_length=160)),
        migrations.AddField(model_name="purchaserequest", name="budget_category", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_requests", to="masterdata.budgetcategory")),
        migrations.AddField(model_name="purchaserequest", name="budget_category_code", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="purchaserequest", name="budget_category_name", field=models.CharField(blank=True, default="", max_length=160)),
        migrations.AddField(model_name="purchaserequestitem", name="suggested_supplier", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="suggested_purchase_request_items", to="procurement.supplier")),
        migrations.AddField(model_name="purchaserequestitem", name="suggested_supplier_code", field=models.CharField(blank=True, default="", max_length=50)),
        migrations.AddField(model_name="purchaserequestitem", name="suggested_supplier_name", field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="purchaserequestitem", name="technical_requirements", field=models.CharField(blank=True, default="", max_length=500)),
        migrations.AddField(model_name="purchaserequestitem", name="brand_requirements", field=models.CharField(blank=True, default="", max_length=200)),
        migrations.AddField(model_name="purchaserequestitem", name="substitute_material", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="substitute_purchase_request_items", to="masterdata.material")),
        migrations.AddField(model_name="purchaserequestitem", name="substitute_material_code", field=models.CharField(blank=True, default="", max_length=50)),
        migrations.AddField(model_name="purchaserequestitem", name="substitute_material_name", field=models.CharField(blank=True, default="", max_length=200)),
        migrations.AddField(model_name="purchaserequestitem", name="purchase_remark", field=models.CharField(blank=True, default="", max_length=500)),
    ]
