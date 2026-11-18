from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from payment_risk_review.models import PaymentRiskReview
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)
from workflow_runtime.models import WorkflowInstance


class FormalPaymentOrderQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "status" in kwargs:
            raise ValidationError(
                "Formal payment order status must use BusinessStateTransition"
            )
        return super().update(**kwargs)


class FormalPaymentOrder(models.Model):
    class Status(models.TextChoices):
        PREPARED = "prepared", "Prepared"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        FROZEN_FOR_EXECUTION = "frozen_for_execution", "Frozen for execution"

    order_no = models.CharField(max_length=80, unique=True)
    source_document_type = models.CharField(max_length=48, default="paymentRiskReview")
    source_risk_review = models.OneToOneField(
        PaymentRiskReview,
        on_delete=models.PROTECT,
        related_name="formal_payment_order",
    )
    source_risk_review_no = models.CharField(max_length=80)
    source_risk_review_version = models.PositiveIntegerField()
    source_risk_rule_version = models.CharField(max_length=64)
    source_risk_review_hash = models.CharField(max_length=64)
    source_scenario_code = models.CharField(max_length=80, editable=False)
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    legal_entity = models.CharField(max_length=160)
    ledger_book = models.CharField(max_length=160)
    currency = models.CharField(max_length=8)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    planned_execution_date = models.DateField()
    status = models.CharField(max_length=24, choices=Status.choices)
    version = models.PositiveIntegerField(default=1)
    idempotency_key = models.CharField(max_length=120)
    number_reservation = models.ForeignKey(
        BusinessDocumentNumberReservation,
        on_delete=models.PROTECT,
        related_name="formal_payment_orders",
    )
    business_transaction = models.OneToOneField(
        BusinessActionTransaction,
        on_delete=models.PROTECT,
        related_name="formal_payment_order",
    )
    audit_record = models.ForeignKey(
        BusinessActionAuditRecord,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="formal_payment_orders",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_formal_payment_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = FormalPaymentOrderQuerySet.as_manager()

    class Meta:
        db_table = "formal_payment_orders"
        permissions = [
            ("generate_formal_payment_order", "Can generate formal payment order"),
            ("submit_formal_payment_order", "Can submit formal payment order"),
            ("approve_formal_payment_order", "Can approve formal payment order"),
            ("freeze_formal_payment_order", "Can freeze formal payment order"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_document_type="paymentRiskReview"),
                name="fpo_source_type_risk_review",
            ),
            models.CheckConstraint(
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
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="fpo_amount_positive",
            ),
            models.CheckConstraint(
                condition=~models.Q(source_scenario_code=""),
                name="fpo_source_scenario_not_empty",
            ),
        ]

    EXECUTION_FIELDS = (
        "amount",
        "currency",
        "planned_execution_date",
    )

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
                "Formal payment order initial status must use state initialization service"
            )
        if self.pk:
            persisted = type(self).objects.filter(pk=self.pk).values(
                "status", *self.EXECUTION_FIELDS
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
                    "Formal payment order status must use BusinessStateTransition"
                )
            if persisted and persisted["status"] == self.Status.FROZEN_FOR_EXECUTION:
                changed = [
                    field
                    for field in self.EXECUTION_FIELDS
                    if persisted[field] != getattr(self, field)
                ]
                if changed:
                    raise ValidationError(
                        "Frozen formal payment order execution fields are immutable: "
                        + ", ".join(changed)
                    )
        return super().save(*args, **kwargs)


class FormalPaymentOrderApproval(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    formal_payment_order = models.OneToOneField(
        FormalPaymentOrder,
        on_delete=models.PROTECT,
        related_name="approval",
    )
    workflow_instance = models.OneToOneField(
        WorkflowInstance,
        on_delete=models.PROTECT,
        related_name="formal_payment_order_approval",
    )
    approval_status = models.CharField(max_length=24, choices=Status.choices)
    submitted_at = models.DateTimeField()
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_formal_payment_orders",
    )
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "formal_payment_order_approvals"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(approval_status__in=["pending", "approved", "rejected"]),
                name="fpo_approval_status_valid",
            ),
        ]


class FormalPaymentOrderFreezeSnapshot(models.Model):
    formal_payment_order = models.OneToOneField(
        FormalPaymentOrder,
        on_delete=models.PROTECT,
        related_name="execution_freeze",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=8)
    payer_account_id = models.CharField(max_length=80)
    payee_account_id = models.CharField(max_length=80)
    bank_route = models.CharField(max_length=120)
    execution_date = models.DateField()
    risk_version = models.PositiveIntegerField()
    approval_version = models.PositiveIntegerField()
    freeze_hash = models.CharField(max_length=64, unique=True)
    frozen_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="frozen_formal_payment_orders",
    )
    frozen_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "formal_payment_order_freezes"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Formal payment order freeze snapshot is immutable")
        return super().save(*args, **kwargs)


class FormalPaymentOrderSendGateCanaryScenario(models.Model):
    batch_id = models.CharField(max_length=80)
    scenario_code = models.CharField(max_length=80)
    scenario_class = models.CharField(max_length=24, default="blocked")
    blocking_fact = models.CharField(max_length=80)
    blocking_reason = models.CharField(max_length=240)
    bank_send_eligible = models.BooleanField(default=False)
    bank_message_count = models.PositiveIntegerField(default=0)
    payment_execution_count = models.PositiveIntegerField(default=0)
    scenario_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "formal_payment_order_send_gate_canary_scenarios"
        constraints = [
            models.UniqueConstraint(
                fields=["batch_id", "scenario_code"],
                name="uniq_fpo_send_gate_canary_scenario",
            ),
        ]


class FormalPaymentOrderSourceSnapshot(models.Model):
    formal_payment_order = models.OneToOneField(
        FormalPaymentOrder,
        on_delete=models.PROTECT,
        related_name="source_snapshot",
    )
    source_risk_review_id = models.BigIntegerField()
    source_risk_review_no = models.CharField(max_length=80)
    risk_review_version = models.PositiveIntegerField()
    risk_rule_version = models.CharField(max_length=64)
    source_hash = models.CharField(max_length=64)
    draft_version = models.PositiveIntegerField()
    source_payment_order_draft_id = models.BigIntegerField()
    source_payment_order_draft_no = models.CharField(max_length=80)
    eligibility_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "formal_payment_order_source_snapshots"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Formal payment order source snapshot is immutable")
        return super().save(*args, **kwargs)


class FormalPaymentOrderEvidenceSnapshot(models.Model):
    formal_payment_order = models.OneToOneField(
        FormalPaymentOrder,
        on_delete=models.PROTECT,
        related_name="evidence_snapshot",
    )
    funds_evidence = models.JSONField(default=dict)
    bank_interface_evidence = models.JSONField(default=dict)
    account_evidence = models.JSONField(default=dict)
    risk_review_evidence = models.JSONField(default=dict)
    segregation_evidence = models.JSONField(default=dict)
    evidence_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "formal_payment_order_evidence_snapshots"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Formal payment order evidence snapshot is immutable")
        return super().save(*args, **kwargs)


class FormalPaymentOrderSourceRelation(models.Model):
    formal_payment_order = models.OneToOneField(
        FormalPaymentOrder,
        on_delete=models.PROTECT,
        related_name="source_relation",
    )
    source_document_type = models.CharField(max_length=48)
    source_object_id = models.BigIntegerField()
    source_object_no = models.CharField(max_length=80)
    relation_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "formal_payment_order_source_relations"
        constraints = [
            models.UniqueConstraint(
                fields=["source_document_type", "source_object_id"],
                name="uniq_fpo_source_relation",
            ),
        ]


class FormalPaymentOrderCanaryScenario(models.Model):
    batch_id = models.CharField(max_length=80)
    scenario_code = models.CharField(max_length=80)
    scenario_class = models.CharField(max_length=24, default="blocked")
    blocking_rule_code = models.CharField(max_length=80)
    blocking_reason = models.CharField(max_length=240)
    formal_object_count = models.PositiveIntegerField(default=0)
    next_step_allowed = models.BooleanField(default=False)
    scenario_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "formal_payment_order_canary_scenarios"
        constraints = [
            models.UniqueConstraint(
                fields=["batch_id", "scenario_code"],
                name="uniq_fpo_canary_scenario",
            ),
        ]
