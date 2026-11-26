from django.conf import settings
from django.db import models

from payable_confirmation_prepare.models import PayableConfirmationPrepare
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)
from workflow_runtime.state_models import BusinessStateManagedModel


class PayeeBankAccountAuthority(models.Model):
    bank_account_id = models.CharField(max_length=80, unique=True)
    tenant_id = models.CharField(max_length=64)
    supplier_id = models.CharField(max_length=80)
    account_name = models.CharField(max_length=160)
    masked_account_no = models.CharField(max_length=40)
    bank_name = models.CharField(max_length=120)
    bank_branch = models.CharField(max_length=160)
    bank_code = models.CharField(max_length=40)
    currency = models.CharField(max_length=8)
    active = models.BooleanField(default=True)
    payment_enabled = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payee_bank_account_authorities"


class PayerBankAccountAuthority(models.Model):
    bank_account_id = models.CharField(max_length=80, unique=True)
    tenant_id = models.CharField(max_length=64)
    legal_entity_id = models.CharField(max_length=80)
    ledger_book_id = models.CharField(max_length=80)
    account_name = models.CharField(max_length=160)
    masked_account_no = models.CharField(max_length=40)
    bank_name = models.CharField(max_length=120)
    currency = models.CharField(max_length=8)
    available_for_payment = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payer_bank_account_authorities"


class PaymentMethodAuthority(models.Model):
    payment_method_code = models.CharField(max_length=48, unique=True)
    payment_method_name = models.CharField(max_length=120)
    active = models.BooleanField(default=True)
    supported_currency = models.JSONField(default=list)
    requires_bank_account = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_method_authorities"


class PaymentCalendarAuthority(models.Model):
    calendar_date = models.DateField(unique=True)
    business_day = models.BooleanField(default=True)
    payment_allowed = models.BooleanField(default=True)
    holiday_code = models.CharField(max_length=48, blank=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_calendar_authorities"


class PaymentHoldAuthority(models.Model):
    source_object_id = models.CharField(max_length=80, unique=True)
    hold_status = models.CharField(max_length=24, default="released")
    hold_reason = models.CharField(max_length=240, blank=True)
    release_required = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_hold_authorities"


class PaymentRequestPrepare(BusinessStateManagedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PREPARED = "prepared", "已准备"

    class PaymentDataStatus(models.TextChoices):
        NOT_COLLECTED = "not_collected", "未采集"
        INCOMPLETE = "incomplete", "不完整"
        COMPLETE = "complete", "完整"

    prepare_no = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    source_document_type = models.CharField(max_length=48, default="payableConfirmationPrepare")
    source_payable_confirmation_prepare = models.OneToOneField(
        PayableConfirmationPrepare,
        on_delete=models.PROTECT,
        related_name="payment_request_prepare",
    )
    source_payable_confirmation_prepare_no = models.CharField(max_length=80)
    source_confirmation_version = models.PositiveIntegerField()
    source_accounting_data_version = models.PositiveIntegerField()
    source_validation_version = models.PositiveIntegerField()
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
    payable_amount = models.DecimalField(max_digits=18, decimal_places=2)
    payment_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    payment_data_status = models.CharField(
        max_length=24,
        choices=PaymentDataStatus.choices,
        default=PaymentDataStatus.NOT_COLLECTED,
    )
    validation_status = models.CharField(max_length=24, default="not_validated")
    validation_result_code = models.CharField(max_length=80, default="not_validated")
    validation_issue_count = models.PositiveIntegerField(default=0)
    current_payment_data_version = models.PositiveIntegerField(default=0)
    current_validation_version = models.PositiveIntegerField(default=0)
    prepared_at = models.DateTimeField(null=True, blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="prepared_payment_request_prepares",
    )
    idempotency_key = models.CharField(max_length=120)
    number_reservation = models.ForeignKey(
        BusinessDocumentNumberReservation,
        on_delete=models.PROTECT,
        related_name="payment_request_prepares",
    )
    business_transaction = models.OneToOneField(
        BusinessActionTransaction,
        on_delete=models.PROTECT,
        related_name="payment_request_prepare",
    )
    audit_record = models.OneToOneField(
        BusinessActionAuditRecord,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payment_request_prepare",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payment_request_prepares",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "payment_request_prepares"
        permissions = [
            ("generate_payment_request_prepare", "Can generate payment request prepare"),
            ("edit_payment_request_prepare_data", "Can edit payment request prepare data"),
            ("validate_payment_request_prepare", "Can validate payment request prepare"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_document_type="payableConfirmationPrepare"),
                name="prp_source_type_confirmation",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "prepared"]),
                name="prp_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(payable_amount__gt=0),
                name="prp_payable_positive",
            ),
        ]


class PaymentRequestPrepareSourceSnapshot(models.Model):
    payment_request_prepare = models.OneToOneField(
        PaymentRequestPrepare,
        on_delete=models.PROTECT,
        related_name="source_snapshot",
    )
    source_payable_confirmation_prepare_id = models.BigIntegerField()
    source_confirmation_version = models.PositiveIntegerField()
    source_accounting_snapshot_id = models.BigIntegerField()
    source_accounting_data_version = models.PositiveIntegerField()
    source_confirmation_validation_execution_id = models.BigIntegerField()
    source_validation_version = models.PositiveIntegerField()
    source_ap_draft_id = models.BigIntegerField()
    source_invoice_prepare_id = models.BigIntegerField()
    source_reconciliation_id = models.BigIntegerField()
    source_confirmation_hash = models.CharField(max_length=64)
    source_accounting_hash = models.CharField(max_length=64)
    source_validation_hash = models.CharField(max_length=64)
    source_eligibility_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_request_prepare_source_snapshots"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Payment request prepare source snapshot is immutable")
        return super().save(*args, **kwargs)


class PaymentRequestDataSnapshot(models.Model):
    payment_request_prepare = models.ForeignKey(
        PaymentRequestPrepare,
        on_delete=models.PROTECT,
        related_name="payment_data_snapshots",
    )
    payment_data_version = models.PositiveIntegerField()
    payee_bank_account_id = models.CharField(max_length=80)
    payee_account_name = models.CharField(max_length=160)
    payee_account_no_masked = models.CharField(max_length=40)
    payee_bank_name = models.CharField(max_length=120)
    payer_bank_account_id = models.CharField(max_length=80)
    payer_account_name = models.CharField(max_length=160)
    payer_account_no_masked = models.CharField(max_length=40)
    payer_bank_name = models.CharField(max_length=120)
    payment_method_code = models.CharField(max_length=48)
    planned_payment_date = models.DateField()
    currency = models.CharField(max_length=8)
    payment_amount = models.DecimalField(max_digits=18, decimal_places=2)
    payment_purpose = models.CharField(max_length=240)
    payment_summary = models.CharField(max_length=240)
    authority_evidence = models.JSONField(default=dict)
    data_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payment_request_data_snapshots",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_request_data_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_request_prepare", "payment_data_version"],
                name="uniq_prp_payment_data_version",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Payment request data snapshot is immutable")
        return super().save(*args, **kwargs)


class PaymentRequestPrepareValidationExecution(models.Model):
    payment_request_prepare = models.ForeignKey(
        PaymentRequestPrepare,
        on_delete=models.PROTECT,
        related_name="validation_executions",
    )
    action_id = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=120)
    payment_data_version = models.PositiveIntegerField()
    source_confirmation_version = models.PositiveIntegerField()
    source_accounting_data_version = models.PositiveIntegerField()
    source_validation_version = models.PositiveIntegerField()
    validation_policy_version = models.CharField(max_length=64)
    status = models.CharField(max_length=24)
    result_code = models.CharField(max_length=80)
    input_hash = models.CharField(max_length=64)
    result_hash = models.CharField(max_length=64)
    issue_count = models.PositiveIntegerField(default=0)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payment_request_prepare_validations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payment_request_prepare_validation_executions"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_request_prepare", "payment_data_version"],
                name="uniq_prp_validation_data_version",
            ),
        ]


class PaymentRequestPrepareValidationIssue(models.Model):
    validation_execution = models.ForeignKey(
        PaymentRequestPrepareValidationExecution,
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
        db_table = "payment_request_prepare_validation_issues"
        constraints = [
            models.UniqueConstraint(
                fields=["validation_execution", "rule_code"],
                name="uniq_prp_validation_issue_rule",
            ),
        ]


class PaymentRequestPrepareSourceRelation(models.Model):
    payment_request_prepare = models.ForeignKey(
        PaymentRequestPrepare,
        on_delete=models.PROTECT,
        related_name="source_relations",
    )
    source_type = models.CharField(max_length=48, default="payableConfirmationPrepare")
    source_id = models.BigIntegerField()
    source_no = models.CharField(max_length=80)
    source_version = models.PositiveIntegerField()
    relationship_type = models.CharField(max_length=40, default="generated_from")
    source_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_request_prepare_source_relations"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_request_prepare", "source_type", "source_id"],
                name="uniq_prp_target_source",
            ),
            models.UniqueConstraint(
                fields=["source_type", "source_id", "relationship_type"],
                name="uniq_prp_source_generated",
            ),
            models.CheckConstraint(
                condition=models.Q(source_type="payableConfirmationPrepare"),
                name="prp_relation_source_confirmation",
            ),
            models.CheckConstraint(
                condition=models.Q(relationship_type="generated_from"),
                name="prp_relation_generated_from",
            ),
        ]


class PaymentRequestPrepareCanaryScenario(models.Model):
    batch_id = models.CharField(max_length=80)
    scenario_code = models.CharField(max_length=80)
    scenario_class = models.CharField(max_length=32, default="blocked")
    scenario_role = models.CharField(max_length=100)
    blocking_module = models.CharField(max_length=80)
    blocking_rule_code = models.CharField(max_length=80)
    blocking_reason = models.CharField(max_length=240)
    current_last_valid_object_no = models.CharField(max_length=80, blank=True)
    formal_object_count = models.PositiveIntegerField(default=0)
    next_step_allowed = models.BooleanField(default=False)
    scenario_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_request_prepare_canary_scenarios"
        constraints = [
            models.UniqueConstraint(
                fields=["batch_id", "scenario_code"],
                name="uniq_prp_canary_scenario",
            ),
        ]
