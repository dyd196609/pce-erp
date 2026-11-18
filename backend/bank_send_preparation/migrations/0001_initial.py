import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("formal_payment_order", "0004_state_consistency_contract"),
        ("reconciliation", "0003_businessdocumentnumberreservation_reusable"),
    ]

    operations = [
        migrations.CreateModel(
            name="BankSendPreparation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("prepare_no", models.CharField(max_length=80, unique=True)),
                (
                    "source_document_type",
                    models.CharField(
                        default="formalPaymentOrder",
                        editable=False,
                        max_length=48,
                    ),
                ),
                (
                    "source_formal_payment_order_no",
                    models.CharField(max_length=80),
                ),
                (
                    "source_formal_payment_order_version",
                    models.PositiveIntegerField(),
                ),
                ("source_freeze_hash", models.CharField(max_length=64)),
                ("tenant_id", models.CharField(max_length=64)),
                ("company_id", models.BigIntegerField()),
                ("legal_entity_id", models.CharField(max_length=160)),
                ("supplier_id", models.CharField(max_length=80)),
                ("supplier_name", models.CharField(max_length=160)),
                ("currency", models.CharField(max_length=8)),
                (
                    "amount",
                    models.DecimalField(decimal_places=2, max_digits=18),
                ),
                ("planned_execution_date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("prepared", "Prepared"),
                        ],
                        max_length=24,
                    ),
                ),
                ("version", models.PositiveIntegerField(default=1)),
                ("gate_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "audit_record",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bank_send_preparations",
                        to="reconciliation.businessactionauditrecord",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_bank_send_preparations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source_formal_payment_order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bank_send_preparation",
                        to="formal_payment_order.formalpaymentorder",
                    ),
                ),
            ],
            options={
                "db_table": "bank_send_preparations",
                "permissions": [
                    ("view_bank_send_gate", "Can view bank send gate"),
                    (
                        "generate_bank_message_preview",
                        "Can generate bank message preview",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="BankSendGate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("source_status_passed", models.BooleanField(default=False)),
                ("approval_passed", models.BooleanField(default=False)),
                ("freeze_hash_passed", models.BooleanField(default=False)),
                ("risk_review_passed", models.BooleanField(default=False)),
                ("funds_available", models.BooleanField(default=False)),
                (
                    "bank_interface_available",
                    models.BooleanField(default=False),
                ),
                (
                    "signing_capability_ready",
                    models.BooleanField(default=False),
                ),
                ("segregation_valid", models.BooleanField(default=False)),
                ("eligible", models.BooleanField(default=False)),
                ("blocking_reasons", models.JSONField(default=list)),
                ("source_freeze_hash", models.CharField(max_length=64)),
                ("current_freeze_hash", models.CharField(max_length=64)),
                (
                    "bank_interface_code",
                    models.CharField(blank=True, max_length=120),
                ),
                (
                    "bank_interface_status",
                    models.CharField(blank=True, max_length=40),
                ),
                ("gate_hash", models.CharField(max_length=64, unique=True)),
                ("evaluated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "preparation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="send_gate",
                        to="bank_send_preparation.banksendpreparation",
                    ),
                ),
            ],
            options={"db_table": "bank_send_gates"},
        ),
        migrations.CreateModel(
            name="BankMessagePreview",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("preview_no", models.CharField(max_length=80, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("preview_only", "Preview only")],
                        default="preview_only",
                        editable=False,
                        max_length=24,
                    ),
                ),
                (
                    "message_type",
                    models.CharField(
                        default="payment_instruction_preview",
                        editable=False,
                        max_length=48,
                    ),
                ),
                ("sanitized_payload", models.JSONField(default=dict)),
                ("payload_hash", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "audit_record",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bank_message_previews",
                        to="reconciliation.businessactionauditrecord",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_bank_message_previews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "preparation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="message_preview",
                        to="bank_send_preparation.banksendpreparation",
                    ),
                ),
            ],
            options={"db_table": "bank_message_previews"},
        ),
        migrations.AddConstraint(
            model_name="banksendpreparation",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("source_document_type", "formalPaymentOrder")
                ),
                name="bsp_source_type_formal_payment_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="banksendpreparation",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ["draft", "prepared"])),
                name="bsp_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="banksendpreparation",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)),
                name="bsp_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="banksendpreparation",
            constraint=models.CheckConstraint(
                condition=~models.Q(("source_freeze_hash", "")),
                name="bsp_source_freeze_hash_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="banksendpreparation",
            constraint=models.CheckConstraint(
                condition=~models.Q(("gate_hash", "")),
                name="bsp_gate_hash_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="bankmessagepreview",
            constraint=models.CheckConstraint(
                condition=models.Q(("status", "preview_only")),
                name="bmp_preview_only_enforced",
            ),
        ),
    ]

