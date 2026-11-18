from django.db import migrations, models
import django.db.models.deletion


def create_baseline_permissions(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    for code, name in (
        ("production.engineering.baseline.save", "保存订单工程基线草稿"),
        ("production.engineering.baseline.confirm", "确认订单工程基线"),
    ):
        Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "module": "PRODUCTION"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("pde", "0029_product_design_plan_group_scope"),
        ("sales", "0005_sales_order_item_tax_snapshot"),
        ("system", "0017_team_operation_capability"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderEngineeringBaseline",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("baseline_no", models.CharField(max_length=120, verbose_name="工程基线编号")),
                ("sequence", models.PositiveIntegerField(verbose_name="订单内基线序号")),
                ("status", models.CharField(choices=(("draft", "草稿"), ("confirmed", "已确认")), default="draft", max_length=16, verbose_name="状态")),
                ("reason", models.CharField(max_length=500, verbose_name="保存原因")),
                ("candidate_hash", models.CharField(max_length=64, verbose_name="候选范围哈希")),
                ("snapshot_hash", models.CharField(max_length=64, verbose_name="基线内容哈希")),
                ("scope_item_count", models.PositiveIntegerField(verbose_name="工程范围项数")),
                ("confirmable_item_count", models.PositiveIntegerField(verbose_name="可确认项数")),
                ("blocker_count", models.PositiveIntegerField(verbose_name="确认阻断项数")),
                ("blocker_summary", models.JSONField(default=dict, verbose_name="确认阻断汇总")),
                ("version", models.PositiveIntegerField(default=1, verbose_name="乐观并发版本")),
                ("confirmed_at", models.DateTimeField(blank=True, null=True, verbose_name="确认时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="保存时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_engineering_baselines", to="system.company", verbose_name="所属公司")),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="confirmed_order_engineering_baselines", to="system.user", verbose_name="确认人")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_order_engineering_baselines", to="system.user", verbose_name="保存人")),
                ("sales_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_baselines", to="sales.salesorder", verbose_name="销售订单")),
            ],
            options={"db_table": "pde_order_engineering_baseline", "ordering": ("sales_order_id", "-sequence")},
        ),
        migrations.CreateModel(
            name="OrderEngineeringBaselineItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_type", models.CharField(choices=(("DESIGN_REVISION", "设计修订"), ("PERSISTED_DESIGN_CONTENT", "已持久保存的工程内容"), ("SOURCE_CONTENT", "稳定来源内容"), ("MISSING", "缺少必要工程内容")), max_length=40, verbose_name="快照来源类型")),
                ("item_no_snapshot", models.CharField(max_length=120, verbose_name="设计项编号快照")),
                ("item_name_snapshot", models.CharField(max_length=200, verbose_name="设计项名称快照")),
                ("design_item_version", models.PositiveIntegerField(verbose_name="设计项并发版本")),
                ("design_revision_no", models.PositiveIntegerField(blank=True, null=True, verbose_name="设计修订号")),
                ("design_nature_snapshot", models.CharField(blank=True, default="", max_length=32, verbose_name="设计性质快照")),
                ("source_version_snapshot", models.CharField(max_length=80, verbose_name="来源版本快照")),
                ("source_content_hash_snapshot", models.CharField(max_length=64, verbose_name="来源内容哈希快照")),
                ("content_snapshot", models.JSONField(default=dict, verbose_name="工程内容快照")),
                ("content_hash", models.CharField(max_length=64, verbose_name="工程内容哈希")),
                ("confirmable", models.BooleanField(default=False, verbose_name="可用于基线确认")),
                ("blocker_code", models.CharField(blank=True, default="", max_length=80, verbose_name="确认阻断编码")),
                ("blocker_label", models.CharField(blank=True, default="", max_length=240, verbose_name="确认阻断说明")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="快照时间")),
                ("baseline", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="pde.orderengineeringbaseline", verbose_name="订单工程基线")),
                ("design_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_baseline_items", to="pde.productdesignitem", verbose_name="产品设计项")),
                ("design_revision", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="engineering_baseline_items", to="pde.productdesignrevision", verbose_name="精确设计修订")),
                ("source_attribute", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_baseline_items", to="sales.salesorderitemengineeringattribute", verbose_name="稳定来源行")),
                ("source_record", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_baseline_items", to="pde.engineeringsourcerecord", verbose_name="来源记录")),
            ],
            options={"db_table": "pde_order_engineering_baseline_item", "ordering": ("baseline_id", "design_item_id")},
        ),
        migrations.AddConstraint(model_name="orderengineeringbaseline", constraint=models.UniqueConstraint(fields=("company", "baseline_no"), name="pde_order_eng_baseline_company_no_unique")),
        migrations.AddConstraint(model_name="orderengineeringbaseline", constraint=models.UniqueConstraint(fields=("sales_order", "sequence"), name="pde_order_eng_baseline_order_sequence_unique")),
        migrations.AddIndex(model_name="orderengineeringbaseline", index=models.Index(fields=["company", "sales_order", "status"], name="pde_oeb_scope_status_idx")),
        migrations.AddIndex(model_name="orderengineeringbaseline", index=models.Index(fields=["sales_order", "created_at"], name="pde_oeb_order_created_idx")),
        migrations.AddConstraint(model_name="orderengineeringbaselineitem", constraint=models.UniqueConstraint(fields=("baseline", "design_item"), name="pde_order_eng_baseline_item_unique")),
        migrations.AddIndex(model_name="orderengineeringbaselineitem", index=models.Index(fields=["design_item", "created_at"], name="pde_oebi_item_created_idx")),
        migrations.AddIndex(model_name="orderengineeringbaselineitem", index=models.Index(fields=["baseline", "confirmable"], name="pde_oebi_confirmable_idx")),
        migrations.RunPython(create_baseline_permissions, migrations.RunPython.noop),
    ]
