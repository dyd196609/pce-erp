from django.conf import settings
from django.db import models

from payment_order_prepare.models import PaymentOrderPrepare
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)
from workflow_runtime.state_models import BusinessStateManagedModel


class PaymentOrderDraft(BusinessStateManagedModel):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        REVIEWED = "reviewed", "Reviewed"

    draft_no = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.CREATED)
    source_document_type = models.CharField(max_length=48, default="paymentOrderPrepare")
    source_payment_order_prepare = models.OneToOneField(
        PaymentOrderPrepare,
        on_delete=models.PROTECT,
        related_name="payment_order_draft",
    )
    source_payment_order_prepare_no = models.CharField(max_length=80)
    source_order_prepare_version = models.PositiveIntegerField()
    source_order_data_version = models.PositiveIntegerField()
    source_order_validation_version = models.PositiveIntegerField()
    source_order_preview_hash = models.CharField(max_length=64)
    source_payment_request_id = models.BigIntegerField()
    source_payment_request_no = models.CharField(max_length=80)
    source_payment_request_version = models.PositiveIntegerField()
    source_approval_workflow_id = models.BigIntegerField()
    source_approval_evidence_hash = models.CharField(max_length=64)
    source_payment_request_prepare_id = models.BigIntegerField()
    source_payable_confirmation_prepare_id = models.BigIntegerField()
    source_ap_draft_id = models.BigIntegerField()
    source_invoice_prepare_id = models.BigIntegerField()
    source_reconciliation_id = models.BigIntegerField()
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
    planned_execution_date = models.DateField()
    planned_execution_time = models.TimeField(null=True, blank=True)
    payment_method_code = models.CharField(max_length=48)
    payer_bank_account_id = models.CharField(max_length=80)
    payee_bank_account_id = models.CharField(max_length=80)
    payment_route_id = models.CharField(max_length=80)
    bank_interface_profile_id = models.CharField(max_length=80)
    signing_policy_id = models.CharField(max_length=80, blank=True)
    authorization_route_id = models.CharField(max_length=80, blank=True)
    signing_capability_id = models.CharField(max_length=80, blank=True)
    priority = models.CharField(max_length=24, default="normal")
    draft_data_status = models.CharField(max_length=24, default="not_collected")
    review_status = models.CharField(max_length=24, default="not_reviewed")
    review_result_code = models.CharField(max_length=80, default="not_reviewed")
    review_issue_count = models.PositiveIntegerField(default=0)
    current_draft_data_version = models.PositiveIntegerField(default=0)
    current_review_version = models.PositiveIntegerField(default=0)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reviewed_payment_order_drafts",
    )
    idempotency_key = models.CharField(max_length=120)
    number_reservation = models.ForeignKey(
        BusinessDocumentNumberReservation,
        on_delete=models.PROTECT,
        related_name="payment_order_drafts",
    )
    business_transaction = models.OneToOneField(
        BusinessActionTransaction,
        on_delete=models.PROTECT,
        related_name="payment_order_draft",
    )
    audit_record = models.ForeignKey(
        BusinessActionAuditRecord,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payment_order_drafts",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_payment_order_drafts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "payment_order_drafts"
        permissions = [
            ("generate_payment_order_draft", "Can generate payment order draft"),
            ("edit_payment_order_draft_data", "Can edit payment order draft data"),
            ("review_payment_order_draft", "Can review payment order draft"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_document_type="paymentOrderPrepare"),
                name="pod_source_type_order_prepare",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["created", "reviewed"]),
                name="pod_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_amount__gt=0),
                name="pod_amount_positive",
            ),
        ]


class PaymentOrderDraftSourceSnapshot(models.Model):
    payment_order_draft = models.OneToOneField(
        PaymentOrderDraft,
        on_delete=models.PROTECT,
        related_name="source_snapshot",
    )
    source_payment_order_prepare_id = models.BigIntegerField()
    source_payment_order_prepare_no = models.CharField(max_length=80)
    source_order_prepare_version = models.PositiveIntegerField()
    source_order_data_snapshot_id = models.BigIntegerField()
    source_order_data_version = models.PositiveIntegerField()
    source_order_validation_execution_id = models.BigIntegerField()
    source_order_validation_version = models.PositiveIntegerField()
    source_order_preview_hash = models.CharField(max_length=64)
    source_payment_request_id = models.BigIntegerField()
    source_payment_request_version = models.PositiveIntegerField()
    source_submission_snapshot_id = models.BigIntegerField()
    source_approval_workflow_id = models.BigIntegerField()
    source_approval_evidence_hash = models.CharField(max_length=64)
    source_order_prepare_hash = models.CharField(max_length=64)
    source_validation_hash = models.CharField(max_length=64)
    source_eligibility_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_order_draft_source_snapshots"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Payment order draft source snapshot is immutable")
        return super().save(*args, **kwargs)


class PaymentOrderDraftDataSnapshot(models.Model):
    payment_order_draft = models.ForeignKey(
        PaymentOrderDraft,
        on_delete=models.PROTECT,
        related_name="draft_data_snapshots",
    )
    draft_data_version = models.PositiveIntegerField()
    payer_bank_account_id = models.CharField(max_length=80)
    payer_account_no_masked = models.CharField(max_length=40)
    payee_bank_account_id = models.CharField(max_length=80)
    payee_account_no_masked = models.CharField(max_length=40)
    payment_route_id = models.CharField(max_length=80)
    payment_route_code = models.CharField(max_length=80)
    bank_interface_profile_id = models.CharField(max_length=80)
    channel_code = models.CharField(max_length=80)
    message_format = models.CharField(max_length=80)
    payment_method_code = models.CharField(max_length=48)
    planned_execution_date = models.DateField()
    planned_execution_time = models.TimeField()
    currency = models.CharField(max_length=8)
    payment_amount = models.DecimalField(max_digits=18, decimal_places=2)
    payment_purpose = models.CharField(max_length=240)
    payment_summary = models.CharField(max_length=240)
    priority = models.CharField(max_length=24)
    payment_reference = models.CharField(max_length=120)
    maker_user_id = models.CharField(max_length=80)
    signing_policy_id = models.CharField(max_length=80)
    authorization_route_id = models.CharField(max_length=80)
    signing_capability_id = models.CharField(max_length=80)
    draft_payload_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_order_draft_data_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_order_draft", "draft_data_version"],
                name="uniq_pod_draft_data_version",
            )
        ]


class PaymentOrderDraftAuthoritySnapshot(models.Model):
    payment_order_draft = models.ForeignKey(
        PaymentOrderDraft,
        on_delete=models.PROTECT,
        related_name="authority_snapshots",
    )
    draft_data_version = models.PositiveIntegerField()
    evidence = models.JSONField(default=dict)
    authority_snapshot_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_order_draft_authority_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_order_draft", "draft_data_version"],
                name="uniq_pod_authority_data_version",
            )
        ]


class PaymentOrderDraftCreationPreview(models.Model):
    draft_data_snapshot = models.ForeignKey(
        PaymentOrderDraftDataSnapshot,
        on_delete=models.PROTECT,
        related_name="creation_previews",
    )
    creation_preview_version = models.PositiveIntegerField()
    proposed_formal_order_reference = models.CharField(max_length=120)
    debtor_name = models.CharField(max_length=160)
    debtor_account_masked = models.CharField(max_length=40)
    creditor_name = models.CharField(max_length=160)
    creditor_account_masked = models.CharField(max_length=40)
    currency = models.CharField(max_length=8)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    payment_method_code = models.CharField(max_length=48)
    route_code = models.CharField(max_length=80)
    channel_code = models.CharField(max_length=80)
    execution_date = models.DateField()
    execution_time = models.TimeField()
    payment_reference = models.CharField(max_length=120)
    payment_purpose = models.CharField(max_length=240)
    signing_policy_code = models.CharField(max_length=80)
    required_signature_count = models.PositiveIntegerField()
    authorization_step_count = models.PositiveIntegerField()
    creation_preview_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_order_draft_creation_previews"
        constraints = [
            models.UniqueConstraint(
                fields=["draft_data_snapshot", "creation_preview_version"],
                name="uniq_pod_creation_preview_version",
            )
        ]


class PaymentOrderDraftReviewExecution(models.Model):
    payment_order_draft = models.ForeignKey(
        PaymentOrderDraft,
        on_delete=models.PROTECT,
        related_name="review_executions",
    )
    action_id = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=120)
    draft_data_version = models.PositiveIntegerField()
    source_order_prepare_version = models.PositiveIntegerField()
    source_order_validation_version = models.PositiveIntegerField()
    source_payment_request_version = models.PositiveIntegerField()
    source_workflow_version = models.PositiveIntegerField()
    source_approval_evidence_hash = models.CharField(max_length=64)
    review_policy_version = models.CharField(max_length=64)
    status = models.CharField(max_length=24)
    result_code = models.CharField(max_length=80)
    input_hash = models.CharField(max_length=64)
    result_hash = models.CharField(max_length=64)
    issue_count = models.PositiveIntegerField(default=0)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payment_order_draft_review_executions"
        constraints = [
            models.UniqueConstraint(
                fields=["action_id", "idempotency_key"],
                name="uniq_pod_review_action_key",
            ),
            models.UniqueConstraint(
                fields=["payment_order_draft", "draft_data_version"],
                name="uniq_pod_review_data_version",
            ),
        ]


class PaymentOrderDraftReviewIssue(models.Model):
    review_execution = models.ForeignKey(
        PaymentOrderDraftReviewExecution,
        on_delete=models.PROTECT,
        related_name="issues",
    )
    rule_code = models.CharField(max_length=80)
    dimension = models.CharField(max_length=80)
    expected = models.CharField(max_length=240)
    actual = models.CharField(max_length=240)
    severity = models.CharField(max_length=24, default="error")
    blocking = models.BooleanField(default=True)
    message = models.CharField(max_length=240)
    source_field = models.CharField(max_length=120)

    class Meta:
        db_table = "payment_order_draft_review_issues"
        constraints = [
            models.UniqueConstraint(
                fields=["review_execution", "rule_code"],
                name="uniq_pod_review_issue_rule",
            )
        ]


class PaymentOrderDraftSourceRelation(models.Model):
    payment_order_draft = models.ForeignKey(
        PaymentOrderDraft,
        on_delete=models.PROTECT,
        related_name="source_relations",
    )
    source_type = models.CharField(max_length=48, default="paymentOrderPrepare")
    source_id = models.BigIntegerField()
    source_no = models.CharField(max_length=80)
    source_version = models.PositiveIntegerField()
    relationship_type = models.CharField(max_length=40, default="generated_from")
    source_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_order_draft_source_relations"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_order_draft", "source_type", "source_id"],
                name="uniq_pod_target_source",
            ),
            models.UniqueConstraint(
                fields=["source_type", "source_id", "relationship_type"],
                name="uniq_pod_source_generated",
            ),
        ]


class PaymentOrderDraftCanaryScenario(models.Model):
    batch_id = models.CharField(max_length=80)
    scenario_code = models.CharField(max_length=80)
    scenario_class = models.CharField(max_length=32, default="blocked")
    blocking_rule_code = models.CharField(max_length=80)
    blocking_reason = models.CharField(max_length=240)
    formal_object_count = models.PositiveIntegerField(default=0)
    next_step_allowed = models.BooleanField(default=False)
    scenario_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_order_draft_canary_scenarios"
        constraints = [
            models.UniqueConstraint(
                fields=["batch_id", "scenario_code"],
                name="uniq_pod_canary_scenario",
            )
        ]
