# Generated for V1.14.2.8.4.7.54.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("formal_payment_order", "0002_formalpaymentorder_source_scenario_code"),
        ("workflow_runtime", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="formalpaymentorder",
            name="fpo_status_valid",
        ),
        migrations.AlterField(
            model_name="formalpaymentorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("prepared", "Prepared"),
                    ("submitted", "Submitted"),
                    ("approved", "Approved"),
                    ("frozen_for_execution", "Frozen for execution"),
                ],
                max_length=24,
            ),
        ),
        migrations.AddConstraint(
            model_name="formalpaymentorder",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "prepared",
                        "submitted",
                        "approved",
                        "frozen_for_execution",
                    ]
                ),
                name="fpo_status_valid",
            ),
        ),
        migrations.AlterModelOptions(
            name="formalpaymentorder",
            options={
                "permissions": [
                    ("generate_formal_payment_order", "Can generate formal payment order"),
                    ("submit_formal_payment_order", "Can submit formal payment order"),
                    ("approve_formal_payment_order", "Can approve formal payment order"),
                    ("freeze_formal_payment_order", "Can freeze formal payment order"),
                ]
            },
        ),
        migrations.CreateModel(
            name="FormalPaymentOrderApproval",
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
                (
                    "approval_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        max_length=24,
                    ),
                ),
                ("submitted_at", models.DateTimeField()),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approved_formal_payment_orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "formal_payment_order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approval",
                        to="formal_payment_order.formalpaymentorder",
                    ),
                ),
                (
                    "workflow_instance",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="formal_payment_order_approval",
                        to="workflow_runtime.workflowinstance",
                    ),
                ),
            ],
            options={
                "db_table": "formal_payment_order_approvals",
            },
        ),
        migrations.AddConstraint(
            model_name="formalpaymentorderapproval",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    approval_status__in=["pending", "approved", "rejected"]
                ),
                name="fpo_approval_status_valid",
            ),
        ),
        migrations.CreateModel(
            name="FormalPaymentOrderFreeze",
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
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("currency", models.CharField(max_length=8)),
                ("payer_account_id", models.CharField(max_length=80)),
                ("payee_account_id", models.CharField(max_length=80)),
                ("bank_route", models.CharField(max_length=120)),
                ("execution_date", models.DateField()),
                ("risk_version", models.PositiveIntegerField()),
                ("approval_version", models.PositiveIntegerField()),
                ("freeze_hash", models.CharField(max_length=64, unique=True)),
                ("frozen_at", models.DateTimeField(auto_now_add=True)),
                ("version", models.PositiveIntegerField(default=1)),
                (
                    "formal_payment_order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="execution_freeze",
                        to="formal_payment_order.formalpaymentorder",
                    ),
                ),
                (
                    "frozen_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="frozen_formal_payment_orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "formal_payment_order_freezes",
            },
        ),
        migrations.CreateModel(
            name="FormalPaymentOrderSendGateCanaryScenario",
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
                ("batch_id", models.CharField(max_length=80)),
                ("scenario_code", models.CharField(max_length=80)),
                ("scenario_class", models.CharField(default="blocked", max_length=24)),
                ("blocking_fact", models.CharField(max_length=80)),
                ("blocking_reason", models.CharField(max_length=240)),
                ("bank_send_eligible", models.BooleanField(default=False)),
                ("bank_message_count", models.PositiveIntegerField(default=0)),
                ("payment_execution_count", models.PositiveIntegerField(default=0)),
                ("scenario_hash", models.CharField(max_length=64)),
            ],
            options={
                "db_table": "formal_payment_order_send_gate_canary_scenarios",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("batch_id", "scenario_code"),
                        name="uniq_fpo_send_gate_canary_scenario",
                    )
                ],
            },
        ),
    ]
