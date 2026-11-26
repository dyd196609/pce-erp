import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("masterdata", "0012_standard_uom_initialization_v12"),
        ("pde", "0035_order_engineered_release_subject_contract"),
        ("sales", "0006_salesorder_business_purpose"),
        ("system", "0018_normalize_process_display_order_schema"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LegacyInFlightOrderAdoption",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID",
                    ),
                ),
                ("adoption_no", models.CharField(max_length=120, verbose_name="承接编号")),
                (
                    "reason_code",
                    models.CharField(
                        choices=[
                            (
                                "PRE_ADMISSION_MODEL_IN_FLIGHT",
                                "新准入模型上线前历史在制订单",
                            ),
                        ],
                        default="PRE_ADMISSION_MODEL_IN_FLIGHT",
                        max_length=48,
                        verbose_name="承接原因编码",
                    ),
                ),
                ("business_reason", models.CharField(max_length=500, verbose_name="业务授权依据")),
                ("evidence_snapshot", models.JSONField(default=dict, verbose_name="不可变承接证据快照")),
                ("evidence_hash", models.CharField(max_length=64, unique=True, verbose_name="承接证据哈希")),
                ("cutoff_evidence", models.JSONField(default=dict, verbose_name="Admission模型上线时间证据")),
                ("idempotency_key", models.CharField(max_length=160, verbose_name="幂等键")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="承接时间")),
                (
                    "action_request",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="legacy_inflight_order_adoption",
                        to="masterdata.masterdatawriterequest",
                        verbose_name="幂等动作请求",
                    ),
                ),
                (
                    "audit_record",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="legacy_inflight_order_adoption",
                        to="system.organizationoperatingauditrecord",
                        verbose_name="组织审计记录",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="legacy_inflight_order_adoptions",
                        to="system.company",
                        verbose_name="所属公司",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_legacy_inflight_order_adoptions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="执行人",
                    ),
                ),
                (
                    "engineering_baseline",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="legacy_inflight_order_adoptions",
                        to="pde.orderengineeringbaseline",
                        verbose_name="确认工程基线",
                    ),
                ),
                (
                    "sales_order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="legacy_inflight_adoption",
                        to="sales.salesorder",
                        verbose_name="历史在制销售订单",
                    ),
                ),
                (
                    "source_identity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="legacy_inflight_order_adoptions",
                        to="masterdata.externalidentity",
                        verbose_name="正式来源身份",
                    ),
                ),
                (
                    "source_record",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="legacy_inflight_order_adoptions",
                        to="pde.engineeringsourcerecord",
                        verbose_name="正式工程来源",
                    ),
                ),
            ],
            options={
                "db_table": "pde_legacy_inflight_order_adoption",
                "ordering": ("company_id", "sales_order_id", "pk"),
                "indexes": [
                    models.Index(
                        fields=["company", "created_at"],
                        name="pde_lioa_company_created_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "adoption_no"),
                        name="pde_lioa_company_no_unique",
                    ),
                    models.UniqueConstraint(
                        fields=("company", "idempotency_key"),
                        name="pde_lioa_company_idem_unique",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(reason_code="PRE_ADMISSION_MODEL_IN_FLIGHT"),
                        name="pde_lioa_reason_pre_model",
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(business_reason=""),
                        name="pde_lioa_business_reason_required",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="LegacyInFlightOrderAdoptionRevocation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID",
                    ),
                ),
                ("revocation_no", models.CharField(max_length=120, verbose_name="撤销编号")),
                (
                    "reason_code",
                    models.CharField(
                        choices=[
                            ("BUSINESS_IDENTITY_CONFLICT", "业务身份冲突"),
                            ("EVIDENCE_INVALIDATED", "承接证据失效"),
                        ],
                        max_length=40,
                        verbose_name="撤销原因编码",
                    ),
                ),
                ("reason", models.CharField(max_length=500, verbose_name="撤销原因")),
                ("evidence_snapshot", models.JSONField(default=dict, verbose_name="撤销证据快照")),
                ("evidence_hash", models.CharField(max_length=64, unique=True, verbose_name="撤销证据哈希")),
                ("idempotency_key", models.CharField(max_length=160, verbose_name="幂等键")),
                ("effective_at", models.DateTimeField(verbose_name="撤销生效时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="记录时间")),
                (
                    "action_request",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="legacy_inflight_order_adoption_revocation",
                        to="masterdata.masterdatawriterequest",
                        verbose_name="幂等动作请求",
                    ),
                ),
                (
                    "adoption",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="revocation",
                        to="pde.legacyinflightorderadoption",
                        verbose_name="被撤销承接事实",
                    ),
                ),
                (
                    "audit_record",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="legacy_inflight_order_adoption_revocation",
                        to="system.organizationoperatingauditrecord",
                        verbose_name="组织审计记录",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="legacy_inflight_order_adoption_revocations",
                        to="system.company",
                        verbose_name="所属公司",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_legacy_inflight_order_adoption_revocations",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="执行人",
                    ),
                ),
            ],
            options={
                "db_table": "pde_legacy_inflight_order_adoption_revocation",
                "ordering": ("company_id", "effective_at", "pk"),
                "indexes": [
                    models.Index(
                        fields=["company", "effective_at"],
                        name="pde_lioar_company_eff_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "revocation_no"),
                        name="pde_lioar_company_no_unique",
                    ),
                    models.UniqueConstraint(
                        fields=("company", "idempotency_key"),
                        name="pde_lioar_company_idem_unique",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            reason_code__in=(
                                "BUSINESS_IDENTITY_CONFLICT",
                                "EVIDENCE_INVALIDATED",
                            ),
                        ),
                        name="pde_lioar_reason_valid",
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(reason=""),
                        name="pde_lioar_reason_required",
                    ),
                ],
            },
        ),
    ]
