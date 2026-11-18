import django.db.models.deletion
from django.db import migrations, models


CALCULATION_ACTIONS = [
    ("production.engineering.calculation.view", "查看工程计算与追踪"),
    ("production.engineering.calculation.execute", "执行工程计算"),
]


def preserve_existing_calculation_evidence(apps, schema_editor):
    Calculation = apps.get_model("pde", "EngineeringCalculationRecord")
    DerivedFact = apps.get_model("pde", "EngineeringDerivedFact")
    for calculation in Calculation.objects.select_related(
        "engineering_instance__source_record", "engineering_instance__sales_order_item"
    ).filter(engineering_instance__isnull=False).order_by("pk"):
        instance = calculation.engineering_instance
        Calculation.objects.filter(pk=calculation.pk).update(
            company_id=instance.company_id,
            scope="order_engineering",
            source_record_id=instance.source_record_id,
            sales_order_item_id=instance.sales_order_item_id,
        )
    for fact in DerivedFact.objects.filter(canonical_field="").order_by("pk"):
        DerivedFact.objects.filter(pk=fact.pk).update(canonical_field=fact.fact_code)


def configure_do3_authority_and_codes(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    Role = apps.get_model("system", "Role")
    RolePermission = apps.get_model("system", "RolePermission")
    Company = apps.get_model("system", "Company")
    CodeRule = apps.get_model("masterdata", "CodeRule")

    permissions = {}
    for code, name in CALCULATION_ACTIONS:
        permissions[code], _ = Permission.objects.update_or_create(
            code=code, defaults={"name": name, "module": "PRODUCTION"},
        )
    plan_role = Role.objects.filter(code="PLAN_OPERATOR_V1").first()
    if plan_role:
        for permission in permissions.values():
            RolePermission.objects.get_or_create(role=plan_role, permission=permission)
    for company_id in Company.objects.order_by("pk").values_list("pk", flat=True):
        CodeRule.objects.get_or_create(
            company_id=company_id,
            entity_type="production_engineering_calculation",
            defaults={
                "prefix": "EC",
                "date_format": "%Y%m",
                "seq_length": 6,
                "current_seq": 0,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0010_material_unit_confirmation_a1_final"),
        ("pde", "0017_engineering_rule_foundation_do2"),
        ("sales", "0003_industrial_order_engineering_input_do1"),
        ("system", "0013_process_workshop_a1_final"),
    ]

    operations = [
        migrations.CreateModel(
            name="EngineeringCalculationDetail",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField(verbose_name="执行顺序")),
                ("rule_code", models.CharField(max_length=80, verbose_name="规则编码快照")),
                ("rule_version", models.CharField(max_length=40, verbose_name="规则版本快照")),
                ("expression_snapshot", models.TextField(verbose_name="表达式快照")),
                ("input_snapshot", models.JSONField(default=dict, verbose_name="输入快照")),
                ("dependency_snapshot", models.JSONField(default=list, verbose_name="依赖快照")),
                ("output_name", models.CharField(max_length=160, verbose_name="输出规范名")),
                ("output_value", models.JSONField(blank=True, null=True, verbose_name="输出值")),
                ("precision", models.PositiveSmallIntegerField(verbose_name="计算精度")),
                ("rounding", models.CharField(max_length=32, verbose_name="舍入策略")),
                ("status", models.CharField(choices=[("running", "执行中"), ("succeeded", "成功"), ("failed", "失败")], default="running", max_length=24, verbose_name="状态")),
                ("error_code", models.CharField(blank=True, default="", max_length=80, verbose_name="错误编码")),
                ("error_message", models.TextField(blank=True, default="", verbose_name="错误信息")),
                ("started_at", models.DateTimeField(verbose_name="开始时间")),
                ("finished_at", models.DateTimeField(blank=True, null=True, verbose_name="完成时间")),
            ],
            options={
                "db_table": "pde_engineering_calculation_detail",
                "ordering": ("calculation_id", "sequence"),
            },
        ),
        migrations.AddField(
            model_name="engineeringcalculationrecord", name="company",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="engineering_calculations", to="system.company", verbose_name="所属公司"),
        ),
        migrations.AddField(model_name="engineeringcalculationrecord", name="scope", field=models.CharField(choices=[("validation", "规则技术验证"), ("order_engineering", "正式订单工程核算")], default="order_engineering", max_length=24, verbose_name="计算范围")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="source_record", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="calculation_records", to="pde.engineeringsourcerecord", verbose_name="工程来源记录")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="sales_order_item", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="engineering_calculations", to="sales.salesorderitem", verbose_name="销售订单明细")),
        migrations.AlterField(model_name="engineeringcalculationrecord", name="engineering_instance", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="calculation_records", to="pde.orderengineeringinstance", verbose_name="订单工程实例")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="revision", field=models.PositiveIntegerField(default=1, verbose_name="修订号")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="supersedes", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="revisions", to="pde.engineeringcalculationrecord", verbose_name="替代的历史计算")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="idempotency_key", field=models.CharField(blank=True, default="", max_length=64, verbose_name="幂等键")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="input_hash", field=models.CharField(blank=True, default="", max_length=64, verbose_name="规范输入哈希")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="rule_graph_hash", field=models.CharField(blank=True, default="", max_length=64, verbose_name="规则图哈希")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="result_hash", field=models.CharField(blank=True, default="", max_length=64, verbose_name="结果哈希")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="error_code", field=models.CharField(blank=True, default="", max_length=80, verbose_name="错误编码")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="error_message", field=models.TextField(blank=True, default="", verbose_name="错误信息")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="started_at", field=models.DateTimeField(blank=True, null=True, verbose_name="开始时间")),
        migrations.AddField(model_name="engineeringcalculationrecord", name="finished_at", field=models.DateTimeField(blank=True, null=True, verbose_name="完成时间")),
        migrations.AlterField(
            model_name="engineeringcalculationrecord", name="status",
            field=models.CharField(choices=[("draft", "草稿"), ("prepared", "已准备"), ("running", "执行中"), ("completed", "计算完成"), ("failed", "计算失败"), ("superseded", "已被新修订替代"), ("obsolete", "已失效")], default="draft", max_length=24, verbose_name="状态"),
        ),
        migrations.AddField(model_name="engineeringderivedfact", name="canonical_field", field=models.CharField(blank=True, default="", max_length=160, verbose_name="规范字段")),
        migrations.AddField(model_name="engineeringderivedfact", name="value_type", field=models.CharField(default="decimal", max_length=20, verbose_name="值类型")),
        migrations.AddField(model_name="engineeringderivedfact", name="source_type", field=models.CharField(default="ENGINEERING_DERIVED", max_length=32, verbose_name="来源类型")),
        migrations.AddField(model_name="engineeringderivedfact", name="status", field=models.CharField(default="active", max_length=24, verbose_name="状态")),
        migrations.RunPython(preserve_existing_calculation_evidence, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="engineeringcalculationrecord", constraint=models.UniqueConstraint(condition=models.Q(("company__isnull", False)), fields=("company", "calculation_no"), name="pde_eng_calc_company_no_unique")),
        migrations.AddConstraint(model_name="engineeringcalculationrecord", constraint=models.UniqueConstraint(condition=models.Q(("idempotency_key", ""), _negated=True), fields=("company", "idempotency_key"), name="pde_eng_calc_company_idempotency_unique")),
        migrations.AddField(model_name="engineeringcalculationdetail", name="calculation", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="details", to="pde.engineeringcalculationrecord", verbose_name="计算记录")),
        migrations.AddField(model_name="engineeringcalculationdetail", name="rule", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="calculation_details", to="pde.engineeringruledefinition", verbose_name="规则定义")),
        migrations.AddField(model_name="engineeringcalculationdetail", name="uom", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="engineering_calculation_details", to="masterdata.unitofmeasure", verbose_name="计量单位")),
        migrations.AddField(model_name="engineeringderivedfact", name="source_detail", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="derived_facts", to="pde.engineeringcalculationdetail", verbose_name="来源计算明细")),
        migrations.AddConstraint(model_name="engineeringcalculationdetail", constraint=models.UniqueConstraint(fields=("calculation", "sequence"), name="pde_eng_calc_detail_sequence_unique")),
        migrations.RunPython(configure_do3_authority_and_codes, migrations.RunPython.noop),
    ]
