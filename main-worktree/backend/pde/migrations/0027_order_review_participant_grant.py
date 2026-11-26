from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("pde", "0026_order_review_itemized"), ("system", "0007_remove_department_cost_center_and_more")]

    operations = [
        migrations.CreateModel(
            name="OrderReviewParticipantGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("review_version_snapshot", models.PositiveIntegerField(verbose_name="评审版本")),
                ("source_version_snapshot", models.CharField(max_length=80, verbose_name="来源版本")),
                ("can_view", models.BooleanField(default=True, verbose_name="可查看本评审")),
                ("can_maintain_own_opinion", models.BooleanField(default=True, verbose_name="可维护本人负责项")),
                ("can_sign_own_items", models.BooleanField(default=True, verbose_name="可签认本人负责项")),
                ("active", models.BooleanField(default=True, verbose_name="是否有效")),
                ("reason", models.CharField(max_length=300, verbose_name="授权依据")),
                ("audit_hash", models.CharField(max_length=64, unique=True, verbose_name="审计哈希")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_review_participant_grants", to="system.company", verbose_name="所属公司")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_order_review_participant_grants", to="system.user", verbose_name="配置人")),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_review_participant_grants", to="pfm.employee", verbose_name="责任人员工")),
                ("review", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="participant_grants", to="pde.ordercrossfunctionalreview", verbose_name="授权评审")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_review_participant_grants", to="system.user", verbose_name="办理账号")),
            ],
            options={"db_table": "pde_order_review_participant_grant", "ordering": ("review_id", "employee_id")},
        ),
        migrations.AddConstraint(
            model_name="orderreviewparticipantgrant",
            constraint=models.UniqueConstraint(fields=("review", "employee", "user"), name="pde_order_review_participant_unique"),
        ),
    ]
