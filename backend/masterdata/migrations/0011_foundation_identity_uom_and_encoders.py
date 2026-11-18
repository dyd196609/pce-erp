import django.db.models.deletion
from django.db import migrations, models


COUNT_CODES = {"个", "包", "卷", "台", "块", "套", "张", "把", "支", "本", "条", "瓶", "盒", "罐"}


def establish_uom_governance_and_code_rules(apps, schema_editor):
    UnitOfMeasure = apps.get_model("masterdata", "UnitOfMeasure")
    CodeRule = apps.get_model("masterdata", "CodeRule")
    for unit in UnitOfMeasure.objects.all().iterator():
        if unit.code == "mm" or unit.name == "毫米":
            unit.dimension = "length"
            unit.symbol = "mm"
        elif unit.code in COUNT_CODES or unit.name in COUNT_CODES:
            unit.dimension = "count"
            unit.symbol = unit.code
        else:
            unit.dimension = "other"
            unit.symbol = unit.code
        unit.conversion_factor = 1
        unit.save(update_fields=("dimension", "symbol", "conversion_factor"))
    for entity_type, prefix in (
        ("production_material", "MAT"),
        ("production_workshop", "WS"),
    ):
        CodeRule.objects.get_or_create(
            company_id=1,
            entity_type=entity_type,
            defaults={
                "prefix": prefix, "date_format": "%Y%m",
                "seq_length": 6, "current_seq": 0,
            },
        )


def reverse_governance_seed(apps, schema_editor):
    UnitOfMeasure = apps.get_model("masterdata", "UnitOfMeasure")
    CodeRule = apps.get_model("masterdata", "CodeRule")
    UnitOfMeasure.objects.all().update(
        dimension="other", symbol="", conversion_base_id=None, conversion_factor=1,
    )
    CodeRule.objects.filter(
        company_id=1,
        entity_type__in=("production_material", "production_workshop"),
        current_seq=0,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("masterdata", "0010_material_unit_confirmation_a1_final"),
    ]

    operations = [
        migrations.AddField(
            model_name="unitofmeasure",
            name="symbol",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="unitofmeasure",
            name="dimension",
            field=models.CharField(
                choices=[
                    ("count", "数量"), ("length", "长度"), ("area", "面积"),
                    ("volume", "体积"), ("mass", "质量"), ("time", "时间"),
                    ("other", "其他/待治理"),
                ],
                default="other", max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="unitofmeasure",
            name="conversion_base",
            field=models.ForeignKey(
                blank=True,
                help_text="同公司、同维度的换算基准单位；基准单位本身保持为空。",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="conversion_units",
                to="masterdata.unitofmeasure",
            ),
        ),
        migrations.AddField(
            model_name="unitofmeasure",
            name="conversion_factor",
            field=models.DecimalField(
                decimal_places=10, default=1,
                help_text="1当前单位折合为多少基准单位；必须大于0。",
                max_digits=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="unitofmeasure",
            constraint=models.CheckConstraint(
                condition=models.Q(("conversion_factor__gt", 0)),
                name="uom_conversion_factor_positive",
            ),
        ),
        migrations.AlterField(
            model_name="material",
            name="code",
            field=models.CharField(max_length=50),
        ),
        migrations.AddConstraint(
            model_name="material",
            constraint=models.UniqueConstraint(
                fields=("company_id", "code"), name="material_company_code_unique",
            ),
        ),
        migrations.CreateModel(
            name="ExternalIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("organization_id", models.BigIntegerField()),
                ("source_system", models.CharField(max_length=100)),
                ("source_type", models.CharField(max_length=40)),
                ("source_object_type", models.CharField(max_length=100)),
                ("external_id", models.CharField(max_length=240)),
                ("target_entity_type", models.CharField(max_length=100)),
                ("target_entity_id", models.CharField(blank=True, max_length=100)),
                ("mapping_status", models.CharField(
                    choices=[("CREATE", "待创建"), ("MATCH", "已匹配"), ("REVIEW", "待业务复核"), ("BLOCK", "已阻断")],
                    default="REVIEW", max_length=12,
                )),
                ("source_fingerprint", models.CharField(blank=True, max_length=64)),
                ("audit_metadata", models.JSONField(blank=True, default=dict)),
                ("first_seen", models.DateTimeField(auto_now_add=True)),
                ("last_seen", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "masterdata_external_identity",
                "ordering": ("organization_id", "source_system", "source_object_type", "external_id"),
                "indexes": [models.Index(fields=["organization_id", "target_entity_type", "target_entity_id"], name="md_extid_target_idx")],
                "constraints": [models.UniqueConstraint(
                    fields=("organization_id", "source_system", "source_type", "source_object_type", "external_id"),
                    name="masterdata_external_identity_unique",
                )],
            },
        ),
        migrations.CreateModel(
            name="MasterDataWriteRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("organization_id", models.BigIntegerField()),
                ("action_code", models.CharField(max_length=120)),
                ("entity_type", models.CharField(max_length=100)),
                ("idempotency_key", models.CharField(max_length=160)),
                ("request_hash", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[("RESERVED", "已保留"), ("COMMITTED", "已提交")], default="RESERVED", max_length=12)),
                ("target_entity_id", models.CharField(blank=True, max_length=100)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("audit_metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_identity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="write_requests", to="masterdata.externalidentity")),
            ],
            options={
                "db_table": "masterdata_write_request",
                "ordering": ("organization_id", "action_code", "idempotency_key"),
                "constraints": [models.UniqueConstraint(
                    fields=("organization_id", "action_code", "idempotency_key"),
                    name="masterdata_write_request_unique",
                )],
            },
        ),
        migrations.RunPython(establish_uom_governance_and_code_rules, reverse_governance_seed),
    ]
