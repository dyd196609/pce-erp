from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pde", "0024_engineering_breakdown_option"),
        ("system", "0017_team_operation_capability"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderCrossFunctionalReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("review_type", models.CharField(choices=[("CRM_ORDER_REVIEW", "订单评审"), ("PDE_PRODUCTION_FEASIBILITY", "生产可行性评审")], max_length=40, verbose_name="评审类型")),
                ("source_order_no", models.CharField(max_length=80, verbose_name="来源订单标识")),
                ("source_version", models.CharField(max_length=80, verbose_name="评审依据版本")),
                ("source_content_hash", models.CharField(max_length=64, verbose_name="评审依据哈希")),
                ("review_version", models.PositiveIntegerField(verbose_name="评审记录版本")),
                ("conclusion", models.CharField(choices=[("CONDITIONAL", "有条件通过"), ("ACCEPT", "通过"), ("RETURN_FOR_COMPLETION", "退回补充"), ("REJECT", "不通过")], max_length=32, verbose_name="评审结论")),
                ("review_opinion", models.TextField(verbose_name="评审意见")),
                ("evidence", models.JSONField(default=dict, verbose_name="评审依据")),
                ("missing_conditions", models.JSONField(default=list, verbose_name="待补条件")),
                ("responsibility_feedback", models.JSONField(default=dict, verbose_name="处理责任及反馈")),
                ("idempotency_key", models.CharField(max_length=120, verbose_name="幂等键")),
                ("audit_hash", models.CharField(max_length=64, unique=True, verbose_name="审计哈希")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_cross_functional_reviews", to="system.company", verbose_name="所属公司")),
                ("reviewer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_cross_functional_reviews", to="system.user", verbose_name="执行人")),
                ("source_record", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cross_functional_reviews", to="pde.engineeringsourcerecord", verbose_name="工程来源")),
            ],
            options={"db_table": "pde_order_cross_functional_review", "ordering": ("company_id", "source_order_no", "review_type", "-review_version")},
        ),
        migrations.AddConstraint(model_name="ordercrossfunctionalreview", constraint=models.UniqueConstraint(fields=("company", "review_type", "source_order_no", "review_version"), name="pde_order_review_type_version_unique")),
        migrations.AddConstraint(model_name="ordercrossfunctionalreview", constraint=models.UniqueConstraint(fields=("company", "review_type", "idempotency_key"), name="pde_order_review_idempotency_unique")),
    ]
