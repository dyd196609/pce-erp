from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from bank_send_task.models import BankSendTask
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
)


class BankSendExecutionGateQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "status" in kwargs:
            raise ValidationError(
                "Bank send execution gate status must use "
                "BusinessStateTransition"
            )
        return super().update(**kwargs)


class BankSendExecutionGate(models.Model):
    class Status(models.TextChoices):
        PENDING_REVIEW = "pending_review", "Pending review"
        APPROVED = "approved", "Approved"
        READY_FOR_EXECUTION = (
            "ready_for_execution",
            "Ready for execution",
        )

    gate_no = models.CharField(max_length=96, unique=True)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    source_task = models.OneToOneField(
        BankSendTask,
        on_delete=models.PROTECT,
        related_name="execution_gate",
    )
    bank_send_task_no = models.CharField(max_length=80)
    formal_payment_order_no = models.CharField(max_length=80)
    company_id = models.BigIntegerField()
    legal_entity_id = models.CharField(max_length=160)
    status = models.CharField(max_length=32, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    authorization_snapshot = models.JSONField(default=dict)
    authorization_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120, unique=True)
    business_transaction = models.ForeignKey(
        BusinessActionTransaction,
        on_delete=models.PROTECT,
        related_name="bank_send_execution_gates",
    )
    audit_record = models.ForeignKey(
        BusinessActionAuditRecord,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bank_send_execution_gates",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_bank_send_execution_gates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = BankSendExecutionGateQuerySet.as_manager()

    class Meta:
        db_table = "bank_send_execution_gates"
        permissions = [
            (
                "view_bank_send_execution_gate_conditions",
                "Can view bank send execution gate conditions",
            ),
            (
                "submit_bank_send_final_authorization_review",
                "Can submit bank send final authorization review",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pending_review",
                        "approved",
                        "ready_for_execution",
                    ]
                ),
                name="bseg_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(authorization_hash=""),
                name="bseg_authorization_hash_required",
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
                "Bank send execution gate initial status must use "
                "state initialization service"
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
                    "Bank send execution gate status must use "
                    "BusinessStateTransition"
                )
        return super().save(*args, **kwargs)


class BankSendExecutionGateCanaryPoolEntry(models.Model):
    class PoolType(models.TextChoices):
        NORMAL = "normal", "Normal"
        BLOCKED = "blocked", "Blocked"
        RESERVE = "reserve", "Reserve"

    pool_no = models.CharField(max_length=96, unique=True)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    pool_type = models.CharField(max_length=16, choices=PoolType.choices)
    scenario_code = models.CharField(max_length=96)
    source_task = models.ForeignKey(
        BankSendTask,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="execution_gate_canary_entries",
    )
    eligibility_snapshot = models.JSONField(default=dict)
    blocking_reason = models.CharField(max_length=160, blank=True)
    reserve_activated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_execution_gate_canary_pool"
        constraints = [
            models.UniqueConstraint(
                fields=("tenant_id", "batch_id", "scenario_code"),
                name="bseg_canary_scenario_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    pool_type__in=["normal", "blocked", "reserve"]
                ),
                name="bseg_canary_pool_type_valid",
            ),
        ]
