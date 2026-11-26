import datetime

import django.db.models.deletion
from django.db import migrations, models


def backfill_workshop_codes(apps, schema_editor):
    Workshop = apps.get_model("system", "Workshop")
    CodeRule = apps.get_model("masterdata", "CodeRule")
    for workshop in Workshop.objects.filter(code="").order_by("company_id", "pk"):
        rule = CodeRule.objects.get(
            company_id=workshop.company_id, entity_type="production_workshop",
        )
        rule.current_seq += 1
        rule.save(update_fields=("current_seq",))
        date_part = datetime.datetime.now().strftime(rule.date_format) if rule.date_format else ""
        workshop.code = f"{rule.prefix or ''}{date_part}{str(rule.current_seq).zfill(rule.seq_length)}"
        workshop.save(update_fields=("code",))


class Migration(migrations.Migration):

    dependencies = [
        ("masterdata", "0011_foundation_identity_uom_and_encoders"),
        ("system", "0013_process_workshop_a1_final"),
    ]

    operations = [
        migrations.AddField(
            model_name="process",
            name="operation_kind",
            field=models.CharField(
                choices=[("atomic", "单工序"), ("group", "工序组")],
                default="atomic", max_length=20, verbose_name="工序类型",
            ),
        ),
        migrations.AddField(
            model_name="process",
            name="calculation_basis",
            field=models.CharField(
                choices=[
                    ("count", "数量"), ("length", "长度"), ("area", "面积"),
                    ("volume", "体积"), ("mass", "质量"), ("time", "时间"),
                    ("other", "其他"), ("undetermined", "待确认"),
                ],
                default="undetermined",
                help_text="描述作业量的计量维度；面积是维度，不等同于具体计量单位。",
                max_length=20, verbose_name="核算维度",
            ),
        ),
        migrations.AddField(
            model_name="process",
            name="calculation_uom",
            field=models.ForeignKey(
                blank=True,
                help_text="具体正式UOM；来源只给出维度而未给具体单位时保持为空。",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="calculated_operations",
                to="masterdata.unitofmeasure",
                verbose_name="核算计量单位",
            ),
        ),
        migrations.AddField(
            model_name="process",
            name="quantity_driver",
            field=models.CharField(
                blank=True,
                help_text="受治理的作业量来源标识；未知或无法核算时保持为空。",
                max_length=120, verbose_name="投产量驱动",
            ),
        ),
        migrations.RunPython(backfill_workshop_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="workshop",
            name="code",
            field=models.CharField(max_length=20, verbose_name="车间编码"),
        ),
        migrations.AddConstraint(
            model_name="workshop",
            constraint=models.UniqueConstraint(
                fields=("company", "code"), name="system_workshop_company_code_unique",
            ),
        ),
    ]
