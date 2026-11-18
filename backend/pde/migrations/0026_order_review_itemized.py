from django.db import migrations, models
import django.db.models.deletion


CRM_ITEMS = [
    ("01", "客户需求与供货范围：本次供货及服务范围已经明确。"),
    ("02", "报价条件：本次报价及计价口径可以接受。"),
    ("03", "成本依据：本次预计成本已有可复核依据。"),
    ("04", "订单效益：预计效益达到本订单适用的接单要求。"),
    ("05", "承诺交期：拟承诺交期有当前阶段可复核的实现依据。"),
    ("06", "付款条件：本次付款安排及相应回款风险可以接受。"),
    ("07", "交付责任：本次运输、安装和验收的责任划分已经明确。"),
    ("08", "商务风险：已识别的合同例外和商务风险有可接受的处理方案。"),
]
PDE_ITEMS = [
    ("01", "技术需求：客户技术要求足以支持本阶段可行性判断。"),
    ("02", "产品结构：当前产品结构方案具备实现依据。"),
    ("03", "工艺方案：拟采用的工艺能够满足相应技术要求。"),
    ("04", "用料要求：已明确的材料规格和性能能够满足产品要求。"),
    ("05", "物料准备：所需材料具备按实施需要取得的可行安排。"),
    ("06", "人员条件：所需人员技能及可用安排能够满足实施需要。"),
    ("07", "设备条件：所需设备能力及可用安排能够满足实施需要。"),
    ("08", "实现周期：当前技术周期及资源安排能够支持目标交期。"),
    ("09", "质量验证：产品质量要求具有可行的检验或验证方法。"),
]


def seed_templates(apps, schema_editor):
    Template = apps.get_model("pde", "OrderReviewTemplate")
    Item = apps.get_model("pde", "OrderReviewTemplateItem")
    reasons = ["依据不足", "条件未落实", "风险不可接受", "需补充确认", "其它"]
    for review_type, title, rows in (
        ("CRM_ORDER_REVIEW", "订单评审固定项目", CRM_ITEMS),
        ("PDE_PRODUCTION_FEASIBILITY", "生产可行性评审固定项目", PDE_ITEMS),
    ):
        template, _ = Template.objects.get_or_create(review_type=review_type, version="V1.0", defaults={"title": title, "is_active": True})
        for order, (code, text) in enumerate(rows, 1):
            Item.objects.get_or_create(template=template, item_code=code, defaults={"item_text": text, "display_order": order, "is_applicable": True, "disagreement_reasons": reasons})


class Migration(migrations.Migration):
    dependencies = [("pde", "0025_order_cross_functional_review"), ("pfm", "0003_enterprise_organization_model_v1")]

    operations = [
        migrations.AlterField(model_name="ordercrossfunctionalreview", name="conclusion", field=models.CharField(blank=True, choices=[("CONDITIONAL", "有条件通过"), ("ACCEPT", "通过"), ("RETURN_FOR_COMPLETION", "退回补充"), ("REJECT", "不通过")], default="", max_length=32, verbose_name="评审结论")),
        migrations.AlterField(model_name="ordercrossfunctionalreview", name="review_opinion", field=models.TextField(blank=True, default="", verbose_name="评审意见")),
        migrations.AddField(model_name="ordercrossfunctionalreview", name="record_status", field=models.CharField(choices=[("DRAFT", "草稿"), ("SUBMITTED", "已提交")], default="SUBMITTED", max_length=16, verbose_name="记录状态")),
        migrations.AddField(model_name="ordercrossfunctionalreview", name="template_version", field=models.CharField(blank=True, default="", max_length=40, verbose_name="评审模板版本")),
        migrations.AddField(model_name="ordercrossfunctionalreview", name="item_summary", field=models.JSONField(blank=True, default=dict, verbose_name="逐项汇总")),
        migrations.AddField(model_name="ordercrossfunctionalreview", name="submitted_at", field=models.DateTimeField(blank=True, null=True, verbose_name="提交时间")),
        migrations.AddField(model_name="ordercrossfunctionalreview", name="updated_at", field=models.DateTimeField(auto_now=True)),
        migrations.CreateModel(name="OrderReviewTemplate", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("review_type", models.CharField(choices=[("CRM_ORDER_REVIEW", "订单评审"), ("PDE_PRODUCTION_FEASIBILITY", "生产可行性评审")], max_length=40, verbose_name="评审类型")), ("version", models.CharField(max_length=40, verbose_name="模板版本")), ("title", models.CharField(max_length=120, verbose_name="模板名称")), ("is_active", models.BooleanField(default=True, verbose_name="是否启用")), ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")), ("created_at", models.DateTimeField(auto_now_add=True))], options={"db_table": "pde_order_review_template"}),
        migrations.AddConstraint(model_name="orderreviewtemplate", constraint=models.UniqueConstraint(fields=("review_type", "version"), name="pde_order_review_template_version_unique")),
        migrations.CreateModel(name="OrderReviewTemplateItem", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("item_code", models.CharField(max_length=20, verbose_name="项目编码")), ("item_text", models.CharField(max_length=300, verbose_name="评审项目")), ("display_order", models.PositiveIntegerField(verbose_name="显示顺序")), ("is_applicable", models.BooleanField(default=True, verbose_name="是否适用")), ("disagreement_reasons", models.JSONField(default=list, verbose_name="标准不同意原因")), ("template", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="pde.orderreviewtemplate"))], options={"db_table": "pde_order_review_template_item", "ordering": ("display_order", "id")}),
        migrations.AddConstraint(model_name="orderreviewtemplateitem", constraint=models.UniqueConstraint(fields=("template", "item_code"), name="pde_order_review_template_item_code_unique")),
        migrations.CreateModel(name="OrderCrossFunctionalReviewItem", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("stable_key", models.CharField(max_length=64, verbose_name="稳定条目身份")), ("item_kind", models.CharField(choices=[("FIXED", "固定项目"), ("OTHER", "其它评审事项")], max_length=12, verbose_name="项目类型")), ("item_code", models.CharField(max_length=20, verbose_name="项目编码快照")), ("item_text", models.CharField(max_length=300, verbose_name="评审项目快照")), ("evidence_note", models.TextField(blank=True, default="", verbose_name="依据说明")), ("decision", models.CharField(blank=True, choices=[("AGREE", "同意"), ("DISAGREE", "不同意")], default="", max_length=12, verbose_name="判定")), ("disagreement_reason_code", models.CharField(blank=True, default="", max_length=40, verbose_name="不同意原因编码")), ("disagreement_reason_text", models.TextField(blank=True, default="", verbose_name="不同意具体说明")), ("signed_employee_id_snapshot", models.BigIntegerField(blank=True, null=True)), ("signed_employee_no_snapshot", models.CharField(blank=True, default="", max_length=50)), ("signed_employee_name_snapshot", models.CharField(blank=True, default="", max_length=50)), ("signature_status", models.CharField(choices=[("UNSIGNED", "未签认"), ("SIGNED", "已签认")], default="UNSIGNED", max_length=12, verbose_name="签认状态")), ("signed_at", models.DateTimeField(blank=True, null=True)), ("signature_content_hash", models.CharField(blank=True, default="", max_length=64)), ("content_revision", models.PositiveIntegerField(default=1)), ("display_order", models.PositiveIntegerField(default=0)), ("is_removed", models.BooleanField(default=False)), ("removed_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("responsible_employee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="responsible_order_review_items", to="pfm.employee")), ("review", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="pde.ordercrossfunctionalreview")), ("signed_by_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="signed_order_review_items", to="system.user")), ("template_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="pde.orderreviewtemplateitem"))], options={"db_table": "pde_order_cross_functional_review_item", "ordering": ("display_order", "id")}),
        migrations.AddConstraint(model_name="ordercrossfunctionalreviewitem", constraint=models.UniqueConstraint(fields=("review", "stable_key"), name="pde_order_review_item_stable_unique")),
        migrations.CreateModel(name="OrderReviewItemAudit", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("action", models.CharField(max_length=32, verbose_name="动作")), ("before_snapshot", models.JSONField(default=dict)), ("after_snapshot", models.JSONField(default=dict)), ("audit_hash", models.CharField(max_length=64, unique=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_review_item_audits", to="system.user")), ("item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="audits", to="pde.ordercrossfunctionalreviewitem")), ("review", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="item_audits", to="pde.ordercrossfunctionalreview"))], options={"db_table": "pde_order_review_item_audit", "ordering": ("created_at", "id")}),
        migrations.RunPython(seed_templates, migrations.RunPython.noop),
    ]
