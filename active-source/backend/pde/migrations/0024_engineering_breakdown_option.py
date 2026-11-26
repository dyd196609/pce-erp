from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("pde", "0023_order_engineering_calculation_bom_closure")]

    operations = [
        migrations.CreateModel(
            name="EngineeringBreakdownOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("option_type", models.CharField(choices=[("door_opening_direction", "门开方向"), ("line_style", "线型"), ("edge_method", "封边方式"), ("packaging_method", "包装方式")], max_length=40, verbose_name="选项类别")),
                ("code", models.CharField(max_length=64, verbose_name="选项编码")),
                ("name", models.CharField(max_length=160, verbose_name="选项名称")),
                ("description", models.CharField(blank=True, max_length=300, verbose_name="说明")),
                ("source_reference", models.CharField(blank=True, max_length=300, verbose_name="来源追溯")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_breakdown_options", to="system.company", verbose_name="所属公司")),
            ],
            options={"db_table": "pde_engineering_breakdown_option", "ordering": ("company_id", "option_type", "code")},
        ),
        migrations.AddConstraint(
            model_name="engineeringbreakdownoption",
            constraint=models.UniqueConstraint(fields=("company", "option_type", "code"), name="pde_eng_breakdown_option_company_type_code_unique"),
        ),
        migrations.AddConstraint(
            model_name="engineeringbreakdownoption",
            constraint=models.UniqueConstraint(fields=("company", "option_type", "name"), name="pde_eng_breakdown_option_company_type_name_unique"),
        ),
    ]
