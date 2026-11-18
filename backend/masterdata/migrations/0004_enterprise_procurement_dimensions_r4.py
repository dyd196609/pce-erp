from django.db import migrations, models
import django.db.models.deletion


def seed_enterprise_dimensions(apps, schema_editor):
    Department = apps.get_model("system", "Department")
    ProjectMaster = apps.get_model("masterdata", "ProjectMaster")
    CostCenter = apps.get_model("masterdata", "CostCenter")
    ExpenseCategory = apps.get_model("masterdata", "ExpenseCategory")
    BudgetCategory = apps.get_model("masterdata", "BudgetCategory")
    purchase_department = Department.objects.filter(code="CGB").first()
    ProjectMaster.objects.get_or_create(
        code="PRJ-PCE-ERP-2026",
        defaults={"name": "PCE-ERP制造数字化建设", "stage": "实施阶段", "department": purchase_department, "is_active": True},
    )
    CostCenter.objects.get_or_create(
        code="CC-PROCUREMENT",
        defaults={"name": "采购管理成本中心", "department": purchase_department, "is_active": True},
    )
    ExpenseCategory.objects.get_or_create(code="EXP-MATERIAL", defaults={"name": "生产物料采购费", "is_active": True})
    ExpenseCategory.objects.get_or_create(code="EXP-EQUIPMENT", defaults={"name": "设备采购费", "is_active": True})
    BudgetCategory.objects.get_or_create(code="BUD-PRODUCTION", defaults={"name": "生产物料预算", "is_active": True})
    BudgetCategory.objects.get_or_create(code="BUD-PROJECT", defaults={"name": "项目预算", "is_active": True})


class Migration(migrations.Migration):
    dependencies = [
        ("system", "0003_menu_rolemenu"),
        ("masterdata", "0003_materialcategory_parent"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExpenseCategory",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("code", models.CharField(max_length=64, unique=True)), ("name", models.CharField(max_length=160)), ("is_active", models.BooleanField(default=True))],
            options={"db_table": "expense_category_master", "ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="BudgetCategory",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("code", models.CharField(max_length=64, unique=True)), ("name", models.CharField(max_length=160)), ("is_active", models.BooleanField(default=True))],
            options={"db_table": "budget_category_master", "ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="ProjectMaster",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("code", models.CharField(max_length=64, unique=True)), ("name", models.CharField(max_length=200)), ("stage", models.CharField(max_length=64)), ("is_active", models.BooleanField(default=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("department", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="master_projects", to="system.department"))],
            options={"db_table": "project_master", "ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="CostCenter",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("code", models.CharField(max_length=64, unique=True)), ("name", models.CharField(max_length=200)), ("is_active", models.BooleanField(default=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("department", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cost_centers", to="system.department"))],
            options={"db_table": "cost_center_master", "ordering": ["code"]},
        ),
        migrations.RunPython(seed_enterprise_dimensions, migrations.RunPython.noop),
    ]
