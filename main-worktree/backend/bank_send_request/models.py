from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from bank_send_execution_gate.models import BankSendExecutionGate
from reconciliation.models import BusinessActionAuditRecord, BusinessActionTransaction


class GovernedStatusQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "status" in kwargs:
            raise ValidationError("Bank send request status must use BusinessStateTransition")
        return super().update(**kwargs)


class BankSendRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        VALIDATED = "validated", "Validated"
        READY_TO_DISPATCH = "ready_to_dispatch", "Ready to dispatch"

    request_no = models.CharField(max_length=96, unique=True)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    source_gate = models.OneToOneField(
        BankSendExecutionGate, on_delete=models.PROTECT, related_name="send_request"
    )
    bank_send_execution_gate_no = models.CharField(max_length=96)
    bank_send_task_no = models.CharField(max_length=80)
    formal_payment_order_no = models.CharField(max_length=80)
    company_id = models.BigIntegerField()
    legal_entity_id = models.CharField(max_length=160)
    status = models.CharField(max_length=32, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    source_gate_version = models.PositiveIntegerField()
    source_task_version = models.PositiveIntegerField()
    source_order_version = models.PositiveIntegerField()
    amount_snapshot = models.CharField(max_length=32)
    beneficiary_account_snapshot = models.CharField(max_length=80)
    message_preview_hash_snapshot = models.CharField(max_length=64)
    authorization_hash_snapshot = models.CharField(max_length=64)
    validation_snapshot = models.JSONField(default=dict)
    validation_hash = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=120, unique=True)
    business_transaction = models.ForeignKey(
        BusinessActionTransaction, on_delete=models.PROTECT, related_name="bank_send_requests"
    )
    audit_record = models.ForeignKey(
        BusinessActionAuditRecord, null=True, blank=True, on_delete=models.PROTECT,
        related_name="bank_send_requests"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_bank_send_requests"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = GovernedStatusQuerySet.as_manager()

    class Meta:
        db_table = "bank_send_requests"
        permissions = [
            ("view_bank_send_request_validation", "Can view bank send request validation"),
            ("create_bank_send_request", "Can create bank send request"),
            ("rerun_bank_send_request_validation", "Can rerun bank send request validation"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "validated", "ready_to_dispatch"]),
                name="bsr_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(validation_hash=""), name="bsr_validation_hash_required"
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.pk and self.status and not getattr(
            self, "_business_state_initialization_authorized", False
        ):
            raise ValidationError(
                "Bank send request initial status must use state initialization service"
            )
        if self.pk:
            persisted = type(self).objects.filter(pk=self.pk).values("status").first()
            if (
                persisted and persisted["status"] != self.status
                and not getattr(self, "_business_state_transition_authorized", False)
            ):
                raise ValidationError(
                    "Bank send request status must use BusinessStateTransition"
                )
        return super().save(*args, **kwargs)


class BankSendPreDispatchValidation(models.Model):
    class Result(models.TextChoices):
        PASSED = "passed", "Passed"
        BLOCKED = "blocked", "Blocked"

    validation_no = models.CharField(max_length=112, unique=True)
    request = models.ForeignKey(
        BankSendRequest, on_delete=models.PROTECT, related_name="pre_dispatch_validations"
    )
    attempt_no = models.PositiveIntegerField()
    result = models.CharField(max_length=16, choices=Result.choices)
    checks = models.JSONField(default=dict)
    source_snapshot = models.JSONField(default=dict)
    validation_hash = models.CharField(max_length=64)
    audit_record = models.ForeignKey(
        BusinessActionAuditRecord, on_delete=models.PROTECT,
        related_name="bank_send_pre_dispatch_validations"
    )
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_pre_dispatch_validations"
        constraints = [
            models.UniqueConstraint(
                fields=("request", "attempt_no"), name="bsr_validation_attempt_unique"
            )
        ]


class BankSendRequestCanaryPoolEntry(models.Model):
    class PoolType(models.TextChoices):
        NORMAL = "normal", "Normal"
        BLOCKED = "blocked", "Blocked"
        RESERVE = "reserve", "Reserve"

    pool_no = models.CharField(max_length=96, unique=True)
    tenant_id = models.CharField(max_length=64)
    batch_id = models.CharField(max_length=80)
    pool_type = models.CharField(max_length=16, choices=PoolType.choices)
    scenario_code = models.CharField(max_length=96)
    source_gate = models.ForeignKey(
        BankSendExecutionGate, null=True, blank=True, on_delete=models.PROTECT,
        related_name="send_request_canary_entries"
    )
    validation_snapshot = models.JSONField(default=dict)
    blocking_reason = models.CharField(max_length=160, blank=True)
    reserve_activated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bank_send_request_canary_pool"
        constraints = [
            models.UniqueConstraint(
                fields=("tenant_id", "batch_id", "scenario_code"),
                name="bsr_canary_scenario_unique",
            )
        ]

