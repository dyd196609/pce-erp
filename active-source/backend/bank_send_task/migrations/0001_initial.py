import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("bank_send_preparation", "0001_initial"),
        ("reconciliation", "0003_businessdocumentnumberreservation_reusable"),
    ]

    operations = [
        migrations.CreateModel(
            name="BankSendTask",
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
                ("task_no", models.CharField(max_length=80, unique=True)),
                (
                    "source_document_type",
                    models.CharField(
                        default="bankSendPreparation",
                        editable=False,
                        max_length=48,
                    ),
                ),
                ("source_preparation_no", models.CharField(max_length=80)),
                (
                    "source_preparation_version",
                    models.PositiveIntegerField(),
                ),
                (
                    "source_formal_payment_order_no",
                    models.CharField(max_length=80),
                ),
                ("message_preview_no", models.CharField(max_length=80)),
                ("message_preview_hash", models.CharField(max_length=64)),
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
                            ("prepared", "Prepared"),
                            ("queued", "Queued"),
                            ("ready_to_send", "Ready to send"),
                        ],
                        max_length=24,
                    ),
                ),
                ("version", models.PositiveIntegerField(default=1)),
                ("validation_snapshot", models.JSONField(default=dict)),
                ("validation_hash", models.CharField(max_length=64)),
                (
                    "idempotency_key",
                    models.CharField(max_length=120, unique=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "audit_record",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bank_send_tasks",
                        to="reconciliation.businessactionauditrecord",
                    ),
                ),
                (
                    "business_transaction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bank_send_tasks",
                        to="reconciliation.businessactiontransaction",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_bank_send_tasks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "message_preview",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="send_tasks",
                        to="bank_send_preparation.bankmessagepreview",
                    ),
                ),
                (
                    "number_reservation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bank_send_tasks",
                        to="reconciliation.businessdocumentnumberreservation",
                    ),
                ),
                (
                    "source_preparation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="send_task",
                        to="bank_send_preparation.banksendpreparation",
                    ),
                ),
            ],
            options={
                "db_table": "bank_send_tasks",
                "permissions": [
                    (
                        "view_bank_send_task_status",
                        "Can view bank send task status",
                    ),
                    (
                        "view_bank_message_binding",
                        "Can view bank message binding",
                    ),
                    ("create_bank_send_task", "Can create bank send task"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="banksendtask",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("source_document_type", "bankSendPreparation")
                ),
                name="bst_source_type_preparation",
            ),
        ),
        migrations.AddConstraint(
            model_name="banksendtask",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("status__in", ["prepared", "queued", "ready_to_send"])
                ),
                name="bst_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="banksendtask",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)),
                name="bst_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="banksendtask",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("message_preview_hash", ""),
                    _negated=True,
                ),
                name="bst_preview_hash_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="banksendtask",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("validation_hash", ""),
                    _negated=True,
                ),
                name="bst_validation_hash_required",
            ),
        ),
    ]
