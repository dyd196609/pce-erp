from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pde", "0014_alter_productcategory_industry_type"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="standardcapacity",
            name="pde_standard_capacity_quantity_positive",
        ),
        migrations.AddField(
            model_name="standardcapacity",
            name="measurement_status",
            field=models.CharField(
                choices=[
                    ("measured", "已测定"),
                    ("not_determinable", "适用但无法确定"),
                ],
                default="measured",
                help_text="已测定必须有正数量；适用但无法确定时数量为空。无此工序不创建记录。",
                max_length=24,
                verbose_name="产能测量状态",
            ),
        ),
        migrations.AlterField(
            model_name="standardcapacity",
            name="quantity",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=18,
                null=True,
                verbose_name="标准产能数量",
            ),
        ),
        migrations.AddConstraint(
            model_name="standardcapacity",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(measurement_status="measured", quantity__gt=0)
                    | models.Q(measurement_status="not_determinable", quantity__isnull=True)
                ),
                name="pde_standard_capacity_measurement_valid",
            ),
        ),
    ]
