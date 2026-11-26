import django.db.models.deletion
from django.db import migrations, models


def classify_existing_substitutes(apps, schema_editor):
    BOMItem = apps.get_model("pde", "BOMItem")
    BOMItemSubstitute = apps.get_model("pde", "BOMItemSubstitute")
    item_ids = BOMItemSubstitute.objects.order_by().values_list("bom_item_id", flat=True).distinct()
    BOMItem.objects.filter(pk__in=item_ids).order_by().update(substitute_status="maintained")


class Migration(migrations.Migration):

    dependencies = [
        ("masterdata", "0010_material_unit_confirmation_a1_final"),
        ("system", "0013_process_workshop_a1_final"),
        ("pde", "0015_standard_capacity_measurement_status_a1_final"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="bomitem",
            name="pde_bom_item_scrap_rate_range",
        ),
        migrations.AddField(
            model_name="bomitem",
            name="scrap_rate_status",
            field=models.CharField(
                choices=[("maintained", "已维护"), ("not_maintained", "待维护")],
                default="maintained",
                max_length=24,
                verbose_name="损耗率维护状态",
            ),
        ),
        migrations.AlterField(
            model_name="bomitem",
            name="scrap_rate",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                default=None,
                help_text="未知时必须为空；明确0只表示已确认零损耗。",
                max_digits=8,
                null=True,
                verbose_name="损耗率",
            ),
        ),
        migrations.AlterField(
            model_name="bomitem",
            name="scrap_rate_status",
            field=models.CharField(
                choices=[("maintained", "已维护"), ("not_maintained", "待维护")],
                default="not_maintained",
                max_length=24,
                verbose_name="损耗率维护状态",
            ),
        ),
        migrations.AddField(
            model_name="bomitem",
            name="substitute_status",
            field=models.CharField(
                choices=[
                    ("not_maintained", "待维护"),
                    ("confirmed_none", "已确认无替代料"),
                    ("maintained", "已维护替代料"),
                ],
                default="not_maintained",
                help_text="无替代记录不等于已确认无替代料。",
                max_length=24,
                verbose_name="替代料维护状态",
            ),
        ),
        migrations.RunPython(classify_existing_substitutes, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="bomitem",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        scrap_rate_status="maintained",
                        scrap_rate__gte=0,
                        scrap_rate__lt=1,
                    )
                    | models.Q(
                        scrap_rate_status="not_maintained",
                        scrap_rate__isnull=True,
                    )
                ),
                name="pde_bom_item_scrap_rate_semantic_valid",
            ),
        ),
        migrations.AlterField(
            model_name="routingstep",
            name="work_center",
            field=models.ForeignKey(
                blank=True,
                help_text="真实资料只确认Workshop时允许待维护，不得虚构工作中心。",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="routing_steps",
                to="pde.workcenter",
                verbose_name="正式工作中心",
            ),
        ),
    ]
