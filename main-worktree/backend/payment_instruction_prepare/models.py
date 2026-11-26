from django.conf import settings
from django.db import models

from payment_request.models import PaymentRequest
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)
from workflow_runtime.state_models import BusinessStateManagedModel


class PaymentRouteAuthority(models.Model):
    route_id = models.CharField(max_length=80, unique=True)
    route_code = models.CharField(max_length=80, unique=True)
    payment_method_code = models.CharField(max_length=48)
    payer_bank_code = models.CharField(max_length=40)
    payee_bank_code = models.CharField(max_length=40)
    currency = models.CharField(max_length=8)
    amount_min = models.DecimalField(max_digits=18, decimal_places=2)
    amount_max = models.DecimalField(max_digits=18, decimal_places=2)
    priority = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_route_authorities"


class BankInterfaceProfileAuthority(models.Model):
    interface_profile_id = models.CharField(max_length=80, unique=True)
    bank_code = models.CharField(max_length=40)
    channel_code = models.CharField(max_length=80)
    supported_currencies = models.JSONField(default=list)
    supported_payment_methods = models.JSONField(default=list)
    message_format = models.CharField(max_length=80)
    connection_status = models.CharField(max_length=24, default="available")
    payment_enabled = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "bank_interface_profile_authorities"
        constraints = [
            models.UniqueConstraint(
                fields=["bank_code", "channel_code"],
                name="uniq_pip_bank_channel",
            )
        ]


class BankPaymentCalendarAuthority(models.Model):
    bank_code = models.CharField(max_length=40)
    calendar_date = models.DateField()
    business_day = models.BooleanField(default=True)
    payment_allowed = models.BooleanField(default=True)
    cutoff_time = models.TimeField()
    timezone = models.CharField(max_length=64, default="Asia/Shanghai")
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "bank_payment_calendar_authorities"
        constraints = [
            models.UniqueConstraint(
                fields=["bank_code", "calendar_date"],
                name="uniq_pip_bank_calendar_date",
            )
        ]


class PaymentLimitAuthority(models.Model):
    legal_entity_id = models.CharField(max_length=80)
    payer_bank_account_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    single_payment_limit = models.DecimalField(max_digits=18, decimal_places=2)
    daily_payment_limit = models.DecimalField(max_digits=18, decimal_places=2)
    current_daily_committed_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_limit_authorities"
        constraints = [
            models.UniqueConstraint(
                fields=["legal_entity_id", "payer_bank_account_id", "currency"],
                name="uniq_pip_payment_limit_scope",
            )
        ]


class PaymentInstructionPrepare(BusinessStateManagedModel):
    class Status(models.TextChoices):
        PREPARED = "prepared", "Prepared"
        VALIDATED = "validated", "Validated"

    prepare_no = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PREPARED)
    source_document_type = models.CharField(max_length=48, default="paymentRequest")
    source_payment_request = models.OneToOneField(
        PaymentRequest, on_delete=models.PROTECT, related_name="payment_instruction_prepare"
    )
    source_payment_request_no = models.CharField(max_length=80)
    source_payment_request_version = models.PositiveIntegerField()
    source_approval_workflow_id = models.BigIntegerField()
    source_approval_evidence_hash = models.CharField(max_length=64)
    source_payment_request_prepare_id = models.BigIntegerField()
    source_payment_request_prepare_no = models.CharField(max_length=80)
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
    planned_execution_date = models.DateField()
    payment_method_code = models.CharField(max_length=48)
    payer_bank_account_id = models.CharField(max_length=80)
    payee_bank_account_id = models.CharField(max_length=80)
    payment_route_id = models.CharField(max_length=80, blank=True)
    bank_interface_profile_id = models.CharField(max_length=80, blank=True)
    priority = models.CharField(max_length=24, default="normal")
    instruction_data_status = models.CharField(max_length=24, default="not_collected")
    validation_status = models.CharField(max_length=24, default="not_validated")
    validation_result_code = models.CharField(max_length=80, default="not_validated")
    validation_issue_count = models.PositiveIntegerField(default=0)
    current_instruction_data_version = models.PositiveIntegerField(default=0)
    current_validation_version = models.PositiveIntegerField(default=0)
    prepared_at = models.DateTimeField(null=True, blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="prepared_payment_instruction_prepares",
    )
    idempotency_key = models.CharField(max_length=120)
    number_reservation = models.ForeignKey(
        BusinessDocumentNumberReservation, on_delete=models.PROTECT,
        related_name="payment_instruction_prepares",
    )
    business_transaction = models.OneToOneField(
        BusinessActionTransaction, on_delete=models.PROTECT,
        related_name="payment_instruction_prepare",
    )
    audit_record = models.ForeignKey(
        BusinessActionAuditRecord, null=True, blank=True, on_delete=models.PROTECT,
        related_name="payment_instruction_prepares",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_payment_instruction_prepares",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "payment_instruction_prepares"
        permissions = [
            ("generate_payment_instruction_prepare", "Can generate payment instruction prepare"),
            ("edit_payment_instruction_prepare_data", "Can edit payment instruction prepare data"),
            ("validate_payment_instruction_prepare", "Can validate payment instruction prepare"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_document_type="paymentRequest"),
                name="pinsp_source_type_request",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["prepared", "validated"]),
                name="pinsp_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_amount__gt=0),
                name="pinsp_amount_positive",
            ),
        ]


class PaymentInstructionPrepareSourceSnapshot(models.Model):
    payment_instruction_prepare = models.OneToOneField(
        PaymentInstructionPrepare, on_delete=models.PROTECT, related_name="source_snapshot"
    )
    source_payment_request_id = models.BigIntegerField()
    source_payment_request_no = models.CharField(max_length=80)
    source_payment_request_version = models.PositiveIntegerField()
    source_submission_snapshot_id = models.BigIntegerField()
    source_approval_workflow_id = models.BigIntegerField()
    source_approval_policy_id = models.BigIntegerField()
    source_approval_policy_version = models.PositiveIntegerField()
    source_approval_route_hash = models.CharField(max_length=64)
    source_approval_evidence_hash = models.CharField(max_length=64)
    source_payment_request_prepare_id = models.BigIntegerField()
    source_payment_data_snapshot_id = models.BigIntegerField()
    source_validation_execution_id = models.BigIntegerField()
    source_payment_request_hash = models.CharField(max_length=64)
    source_approval_hash = models.CharField(max_length=64)
    source_eligibility_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_instruction_prepare_source_snapshots"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Payment instruction prepare source snapshot is immutable")
        return super().save(*args, **kwargs)


class PaymentInstructionDataSnapshot(models.Model):
    payment_instruction_prepare = models.ForeignKey(
        PaymentInstructionPrepare, on_delete=models.PROTECT,
        related_name="instruction_data_snapshots",
    )
    instruction_data_version = models.PositiveIntegerField()
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
    instruction_reference = models.CharField(max_length=120)
    authority_evidence = models.JSONField(default=dict)
    data_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_instruction_data_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_instruction_prepare", "instruction_data_version"],
                name="uniq_pip_instruction_data_version",
            )
        ]


class PaymentInstructionPreview(models.Model):
    instruction_data_snapshot = models.ForeignKey(
        PaymentInstructionDataSnapshot, on_delete=models.PROTECT, related_name="previews"
    )
    preview_version = models.PositiveIntegerField()
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
    payment_reference = models.CharField(max_length=120)
    purpose = models.CharField(max_length=240)
    preview_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_instruction_previews"
        constraints = [
            models.UniqueConstraint(
                fields=["instruction_data_snapshot", "preview_version"],
                name="uniq_pip_preview_version",
            )
        ]


class PaymentInstructionPrepareValidationExecution(models.Model):
    payment_instruction_prepare = models.ForeignKey(
        PaymentInstructionPrepare, on_delete=models.PROTECT,
        related_name="validation_executions",
    )
    action_id = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=120)
    instruction_data_version = models.PositiveIntegerField()
    source_payment_request_version = models.PositiveIntegerField()
    source_workflow_version = models.PositiveIntegerField()
    source_approval_evidence_hash = models.CharField(max_length=64)
    validation_policy_version = models.CharField(max_length=64)
    status = models.CharField(max_length=24)
    result_code = models.CharField(max_length=80)
    input_hash = models.CharField(max_length=64)
    result_hash = models.CharField(max_length=64)
    issue_count = models.PositiveIntegerField(default=0)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payment_instruction_prepare_validation_executions"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_instruction_prepare", "instruction_data_version"],
                name="uniq_pip_validation_data_version",
            ),
            models.UniqueConstraint(
                fields=["action_id", "idempotency_key"],
                name="uniq_pip_validation_action_key",
            ),
        ]


class PaymentInstructionPrepareValidationIssue(models.Model):
    validation_execution = models.ForeignKey(
        PaymentInstructionPrepareValidationExecution, on_delete=models.PROTECT,
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
        db_table = "payment_instruction_prepare_validation_issues"
        constraints = [
            models.UniqueConstraint(
                fields=["validation_execution", "rule_code"],
                name="uniq_pip_validation_issue_rule",
            )
        ]


class PaymentInstructionPrepareSourceRelation(models.Model):
    payment_instruction_prepare = models.ForeignKey(
        PaymentInstructionPrepare, on_delete=models.PROTECT, related_name="source_relations"
    )
    source_type = models.CharField(max_length=48, default="paymentRequest")
    source_id = models.BigIntegerField()
    source_no = models.CharField(max_length=80)
    source_version = models.PositiveIntegerField()
    relationship_type = models.CharField(max_length=40, default="generated_from")
    source_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_instruction_prepare_source_relations"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_instruction_prepare", "source_type", "source_id"],
                name="uniq_pip_target_source",
            ),
            models.UniqueConstraint(
                fields=["source_type", "source_id", "relationship_type"],
                name="uniq_pip_source_generated",
            ),
        ]


class PaymentInstructionPrepareCanaryScenario(models.Model):
    batch_id = models.CharField(max_length=80)
    scenario_code = models.CharField(max_length=80)
    scenario_class = models.CharField(max_length=32, default="blocked")
    blocking_rule_code = models.CharField(max_length=80)
    blocking_reason = models.CharField(max_length=240)
    formal_object_count = models.PositiveIntegerField(default=0)
    next_step_allowed = models.BooleanField(default=False)
    scenario_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_instruction_prepare_canary_scenarios"
        constraints = [
            models.UniqueConstraint(
                fields=["batch_id", "scenario_code"],
                name="uniq_pip_canary_scenario",
            )
        ]
