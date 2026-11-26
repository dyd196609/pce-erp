from django.conf import settings
from django.db import models

from payment_request_prepare.models import PaymentRequestPrepare
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)
from workflow_runtime.models import (
    ApprovalPolicyAuthority,
    ApprovalRouteAuthority,
    ProcessDefinition,
    WorkflowInstance,
)
from workflow_runtime.state_models import BusinessStateManagedModel


class PaymentRequest(BusinessStateManagedModel):
    class Status(models.TextChoices):
        PREPARED = "prepared", "Prepared"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class ApprovalStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    request_no = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PREPARED)
    approval_status = models.CharField(
        max_length=24, choices=ApprovalStatus.choices, default=ApprovalStatus.NOT_STARTED
    )
    approval_result_code = models.CharField(max_length=80, default="not_started")
    submission_readiness = models.CharField(max_length=24, default="ready")
    source_document_type = models.CharField(max_length=48, default="paymentRequestPrepare")
    source_payment_request_prepare = models.OneToOneField(
        PaymentRequestPrepare, on_delete=models.PROTECT, related_name="payment_request"
    )
    source_payment_request_prepare_no = models.CharField(max_length=80)
    source_prepare_version = models.PositiveIntegerField()
    source_payment_data_version = models.PositiveIntegerField()
    source_validation_version = models.PositiveIntegerField()
    source_payable_confirmation_prepare_id = models.BigIntegerField()
    source_payable_confirmation_prepare_no = models.CharField(max_length=80)
    source_ap_draft_id = models.BigIntegerField()
    source_ap_draft_no = models.CharField(max_length=80)
    source_invoice_prepare_id = models.BigIntegerField()
    source_invoice_prepare_no = models.CharField(max_length=80)
    source_reconciliation_id = models.BigIntegerField()
    source_reconciliation_no = models.CharField(max_length=80)
    source_key = models.CharField(max_length=200, unique=True)
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    legal_entity_id = models.CharField(max_length=80)
    legal_entity_name = models.CharField(max_length=160)
    ledger_book_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    payment_amount = models.DecimalField(max_digits=18, decimal_places=2)
    planned_payment_date = models.DateField()
    payment_method_code = models.CharField(max_length=48)
    payee_bank_account_id = models.CharField(max_length=80)
    payer_bank_account_id = models.CharField(max_length=80)
    payment_purpose = models.CharField(max_length=240)
    payment_summary = models.CharField(max_length=240)
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payment_requests"
    )
    applicant_name = models.CharField(max_length=160)
    applicant_department_id = models.CharField(max_length=80, blank=True)
    application_reason = models.CharField(max_length=500, blank=True)
    approval_policy = models.ForeignKey(
        ApprovalPolicyAuthority, null=True, blank=True, on_delete=models.PROTECT
    )
    approval_policy_version = models.PositiveIntegerField(default=0)
    workflow_instance = models.OneToOneField(
        WorkflowInstance, null=True, blank=True, on_delete=models.PROTECT,
        related_name="payment_request",
    )
    current_approval_step = models.PositiveIntegerField(default=0)
    total_approval_steps = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="submitted_payment_requests",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    final_decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="final_payment_request_decisions",
    )
    idempotency_key = models.CharField(max_length=120)
    number_reservation = models.ForeignKey(
        BusinessDocumentNumberReservation, on_delete=models.PROTECT,
        related_name="payment_requests",
    )
    business_transaction = models.OneToOneField(
        BusinessActionTransaction, on_delete=models.PROTECT,
        related_name="payment_request",
    )
    audit_record = models.ForeignKey(
        BusinessActionAuditRecord, null=True, blank=True, on_delete=models.PROTECT,
        related_name="payment_requests",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_payment_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "payment_requests"
        permissions = [
            ("generate_payment_request", "Can generate payment request"),
            ("submit_payment_request", "Can submit payment request"),
            ("approve_payment_request", "Can approve payment request"),
            ("reject_payment_request", "Can reject payment request"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_document_type="paymentRequestPrepare"),
                name="payreq_source_type_prepare",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["prepared", "submitted", "approved", "rejected"]),
                name="payreq_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_amount__gt=0),
                name="payreq_amount_positive",
            ),
        ]


class PaymentRequestSourceSnapshot(models.Model):
    payment_request = models.OneToOneField(
        PaymentRequest, on_delete=models.PROTECT, related_name="source_snapshot"
    )
    source_payment_request_prepare_id = models.BigIntegerField()
    source_payment_request_prepare_no = models.CharField(max_length=80)
    source_prepare_version = models.PositiveIntegerField()
    source_payment_data_snapshot_id = models.BigIntegerField()
    source_payment_data_version = models.PositiveIntegerField()
    source_validation_execution_id = models.BigIntegerField()
    source_validation_version = models.PositiveIntegerField()
    source_payable_confirmation_prepare_id = models.BigIntegerField()
    source_ap_draft_id = models.BigIntegerField()
    source_invoice_prepare_id = models.BigIntegerField()
    source_reconciliation_id = models.BigIntegerField()
    source_prepare_hash = models.CharField(max_length=64)
    source_payment_data_hash = models.CharField(max_length=64)
    source_validation_hash = models.CharField(max_length=64)
    source_eligibility_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_request_source_snapshots"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Payment request source snapshot is immutable")
        return super().save(*args, **kwargs)


class PaymentRequestSubmissionSnapshot(models.Model):
    payment_request = models.ForeignKey(
        PaymentRequest, on_delete=models.PROTECT, related_name="submission_snapshots"
    )
    submission_version = models.PositiveIntegerField()
    applicant_user_id = models.BigIntegerField()
    applicant_department_id = models.CharField(max_length=80, blank=True)
    application_reason = models.CharField(max_length=500)
    payment_purpose = models.CharField(max_length=240)
    payment_summary = models.CharField(max_length=240)
    payment_amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=8)
    planned_payment_date = models.DateField()
    approval_policy_id = models.BigIntegerField()
    approval_policy_version = models.PositiveIntegerField()
    approval_route_hash = models.CharField(max_length=64)
    source_state_hash = models.CharField(max_length=64)
    submission_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_request_submission_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_request", "submission_version"],
                name="uniq_payreq_submission_version",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Payment request submission snapshot is immutable")
        return super().save(*args, **kwargs)


class PaymentRequestWorkflowRelation(models.Model):
    payment_request = models.ForeignKey(
        PaymentRequest, on_delete=models.PROTECT, related_name="workflow_relations"
    )
    workflow_instance = models.ForeignKey(
        WorkflowInstance, on_delete=models.PROTECT, related_name="payment_request_relations"
    )
    process_definition = models.ForeignKey(ProcessDefinition, on_delete=models.PROTECT)
    process_definition_version = models.PositiveIntegerField()
    approval_policy = models.ForeignKey(ApprovalPolicyAuthority, on_delete=models.PROTECT)
    approval_route = models.ForeignKey(ApprovalRouteAuthority, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_request_workflow_relations"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_request", "workflow_instance"],
                name="uniq_payreq_workflow_relation",
            )
        ]


class PaymentRequestSourceRelation(models.Model):
    payment_request = models.ForeignKey(
        PaymentRequest, on_delete=models.PROTECT, related_name="source_relations"
    )
    source_type = models.CharField(max_length=48, default="paymentRequestPrepare")
    source_id = models.BigIntegerField()
    source_no = models.CharField(max_length=80)
    source_version = models.PositiveIntegerField()
    relationship_type = models.CharField(max_length=40, default="generated_from")
    source_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_request_source_relations"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_request", "source_type", "source_id"],
                name="uniq_payreq_target_source",
            ),
            models.UniqueConstraint(
                fields=["source_type", "source_id", "relationship_type"],
                name="uniq_payreq_source_generated",
            ),
        ]


class PaymentRequestCanaryScenario(models.Model):
    batch_id = models.CharField(max_length=80)
    scenario_code = models.CharField(max_length=80)
    scenario_class = models.CharField(max_length=32, default="blocked")
    scenario_role = models.CharField(max_length=120)
    blocking_module = models.CharField(max_length=80)
    blocking_rule_code = models.CharField(max_length=80)
    blocking_reason = models.CharField(max_length=240)
    current_last_valid_object_no = models.CharField(max_length=80, blank=True)
    formal_object_count = models.PositiveIntegerField(default=0)
    next_step_allowed = models.BooleanField(default=False)
    scenario_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_request_canary_scenarios"
        constraints = [
            models.UniqueConstraint(
                fields=["batch_id", "scenario_code"],
                name="uniq_payreq_canary_scenario",
            )
        ]
