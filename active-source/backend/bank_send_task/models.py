from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from bank_send_preparation.models import BankMessagePreview, BankSendPreparation
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)


class BankSendTaskQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "status" in kwargs:
            raise ValidationError(
                "Bank send task status must use BusinessStateTransition"
            )
        return super().update(**kwargs)


class BankSendTask(models.Model):
    class Status(models.TextChoices):
        PREPARED = "prepared", "Prepared"
        QUEUED = "queued", "Queued"
        READY_TO_SEND = "ready_to_send", "Ready to send"

    task_no = models.CharField(max_length=80, unique=True)
    source_document_type = models.CharField(
        max_length=48,
        default="bankSendPreparation",
        editable=False,
    )
    source_preparation = models.OneToOneField(
        BankSendPreparation,
        on_delete=models.PROTECT,
        related_name="send_task",
    )
    source_preparation_no = models.CharField(max_length=80)
    source_preparation_version = models.PositiveIntegerField()
    source_formal_payment_order_no = models.CharField(max_length=80)
    message_preview = models.ForeignKey(
        BankMessagePreview,
        on_delete=models.PROTECT,
        related_name="send_tasks",
    )
    message_preview_no = models.CharField(max_length=80)
    message_preview_hash = models.CharField(max_length=64)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    company_id = models.BigIntegerField()
    legal_entity_id = models.CharField(max_length=160)
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    currency = models.CharField(max_length=8)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    planned_execution_date = models.DateField()
    status = models.CharField(max_length=24, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    validation_snapshot = models.JSONField(default=dict)
    validation_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120, unique=True)
    number_reservation = models.ForeignKey(
        BusinessDocumentNumberReservation,
        on_delete=models.PROTECT,
        related_name="bank_send_tasks",
    )
    business_transaction = models.ForeignKey(
        BusinessActionTransaction,
        on_delete=models.PROTECT,
        related_name="bank_send_tasks",
    )
    audit_record = models.ForeignKey(
        BusinessActionAuditRecord,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bank_send_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bank_send_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = BankSendTaskQuerySet.as_manager()

    class Meta:
        db_table = "bank_send_tasks"
        permissions = [
            ("view_bank_send_task_status", "Can view bank send task status"),
            ("view_bank_message_binding", "Can view bank message binding"),
            ("create_bank_send_task", "Can create bank send task"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_document_type="bankSendPreparation"),
                name="bst_source_type_preparation",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["prepared", "queued", "ready_to_send"]
                ),
                name="bst_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="bst_amount_positive",
            ),
            models.CheckConstraint(
                condition=~models.Q(message_preview_hash=""),
                name="bst_preview_hash_required",
            ),
            models.CheckConstraint(
                condition=~models.Q(validation_hash=""),
                name="bst_validation_hash_required",
            ),
        ]

    def save(self, *args, **kwargs):
        if (
            not self.pk
            and self.status
            and not getattr(
                self,
                "_business_state_initialization_authorized",
                False,
            )
        ):
            raise ValidationError(
                "Bank send task initial status must use state initialization service"
            )
        if self.pk:
            persisted = type(self).objects.filter(pk=self.pk).values(
                "status"
            ).first()
            if (
                persisted
                and persisted["status"] != self.status
                and not getattr(
                    self,
                    "_business_state_transition_authorized",
                    False,
                )
            ):
                raise ValidationError(
                    "Bank send task status must use BusinessStateTransition"
                )
        return super().save(*args, **kwargs)


class BankSendTaskCanaryPoolEntry(models.Model):
    """Isolated test-candidate inventory; never a bank-send business state."""

    class PoolType(models.TextChoices):
        NORMAL = "normal", "Normal"
        BLOCKED = "blocked", "Blocked"
        RESERVE = "reserve", "Reserve"

    pool_no = models.CharField(max_length=80, unique=True)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    pool_type = models.CharField(max_length=16, choices=PoolType.choices)
    scenario_code = models.CharField(max_length=80)
    source_preparation = models.ForeignKey(
        BankSendPreparation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bank_send_task_canary_entries",
    )
    eligibility_snapshot = models.JSONField(default=dict)
    blocking_reason = models.CharField(max_length=120, blank=True)
    reserve_activated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_task_canary_pool"
        constraints = [
            models.UniqueConstraint(
                fields=("tenant_id", "batch_id", "scenario_code"),
                name="bst_canary_scenario_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(pool_type__in=["normal", "blocked", "reserve"]),
                name="bst_canary_pool_type_valid",
            ),
        ]
