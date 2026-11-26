from django.conf import settings
from django.db import models

from payment_instruction_prepare.models import PaymentInstructionPrepare
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    BusinessDocumentNumberReservation,
)
from workflow_runtime.state_models import BusinessStateManagedModel


class FundsAvailabilityAuthority(models.Model):
    funds_evidence_id = models.CharField(max_length=80, unique=True)
    tenant_id = models.CharField(max_length=64)
    legal_entity_id = models.CharField(max_length=80)
    ledger_book_id = models.CharField(max_length=80)
    payer_bank_account_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    available_balance = models.DecimalField(max_digits=18, decimal_places=2)
    committed_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    reserved_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    as_of_time = models.DateTimeField()
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "funds_availability_authorities"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "legal_entity_id", "ledger_book_id", "payer_bank_account_id", "currency"],
                name="uniq_pop_funds_scope",
            )
        ]


class PaymentSigningPolicyAuthority(models.Model):
    signing_policy_id = models.CharField(max_length=80, unique=True)
    policy_code = models.CharField(max_length=80, unique=True)
    document_type = models.CharField(max_length=48, default="paymentOrderPrepare")
    bank_code = models.CharField(max_length=40)
    channel_code = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    amount_min = models.DecimalField(max_digits=18, decimal_places=2)
    amount_max = models.DecimalField(max_digits=18, decimal_places=2)
    required_signatures = models.PositiveIntegerField()
    required_roles = models.JSONField(default=list)
    sequential_signing = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_signing_policy_authorities"
        constraints = [
            models.UniqueConstraint(
                fields=["document_type", "bank_code", "channel_code", "currency", "amount_min", "amount_max"],
                name="uniq_pop_signing_policy_scope",
            )
        ]


class PaymentAuthorizationRouteAuthority(models.Model):
    authorization_route_id = models.CharField(max_length=80, unique=True)
    signing_policy = models.OneToOneField(
        PaymentSigningPolicyAuthority,
        on_delete=models.PROTECT,
        related_name="authorization_route",
    )
    steps = models.JSONField(default=list)
    allow_parallel = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_authorization_route_authorities"


class PaymentSigningCapabilityAuthority(models.Model):
    signing_capability_id = models.CharField(max_length=80, unique=True)
    bank_interface_profile_id = models.CharField(max_length=80, unique=True)
    credential_profile_id_masked = models.CharField(max_length=80)
    credential_status = models.CharField(max_length=24, default="ready")
    certificate_status = models.CharField(max_length=24, default="valid")
    signing_service_status = models.CharField(max_length=24, default="available")
    supported_message_format = models.CharField(max_length=80)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_signing_capability_authorities"


class MakerCheckerSegregationAuthority(models.Model):
    segregation_policy_id = models.CharField(max_length=80, unique=True)
    tenant_id = models.CharField(max_length=64)
    maker_user_id = models.CharField(max_length=80)
    required_checker_roles = models.JSONField(default=list)
    required_authorizer_roles = models.JSONField(default=list)
    maker_cannot_check = models.BooleanField(default=True)
    maker_cannot_authorize = models.BooleanField(default=True)
    checker_cannot_final_authorize = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "maker_checker_segregation_authorities"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "maker_user_id"],
                name="uniq_pop_segregation_scope",
            )
        ]


class PaymentOrderPrepare(BusinessStateManagedModel):
    class Status(models.TextChoices):
        PREPARED = "prepared", "Prepared"
        SUBMITTED = "submitted", "Submitted"

    prepare_no = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PREPARED)
    source_document_type = models.CharField(max_length=48, default="paymentInstructionPrepare")
    source_payment_instruction_prepare = models.OneToOneField(
        PaymentInstructionPrepare,
        on_delete=models.PROTECT,
        related_name="payment_order_prepare",
    )
    source_payment_instruction_prepare_no = models.CharField(max_length=80)
    source_instruction_prepare_version = models.PositiveIntegerField()
    source_instruction_data_version = models.PositiveIntegerField()
    source_instruction_validation_version = models.PositiveIntegerField()
    source_instruction_preview_hash = models.CharField(max_length=64)
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
    order_data_status = models.CharField(max_length=24, default="not_collected")
    validation_status = models.CharField(max_length=24, default="not_validated")
    validation_result_code = models.CharField(max_length=80, default="not_validated")
    validation_issue_count = models.PositiveIntegerField(default=0)
    current_order_data_version = models.PositiveIntegerField(default=0)
    current_validation_version = models.PositiveIntegerField(default=0)
    prepared_at = models.DateTimeField(null=True, blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="prepared_payment_order_prepares",
    )
    idempotency_key = models.CharField(max_length=120)
    number_reservation = models.ForeignKey(
        BusinessDocumentNumberReservation,
        on_delete=models.PROTECT,
        related_name="payment_order_prepares",
    )
    business_transaction = models.OneToOneField(
        BusinessActionTransaction,
        on_delete=models.PROTECT,
        related_name="payment_order_prepare",
    )
    audit_record = models.ForeignKey(
        BusinessActionAuditRecord,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payment_order_prepares",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_payment_order_prepares",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "payment_order_prepares"
        permissions = [
            ("generate_payment_order_prepare", "Can generate payment order prepare"),
            ("edit_payment_order_prepare_data", "Can edit payment order prepare data"),
            ("validate_payment_order_prepare", "Can validate payment order prepare"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_document_type="paymentInstructionPrepare"),
                name="pop_source_type_instruction",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["prepared", "submitted"]),
                name="pop_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_amount__gt=0),
                name="pop_amount_positive",
            ),
        ]


class PaymentOrderPrepareSourceSnapshot(models.Model):
    payment_order_prepare = models.OneToOneField(
        PaymentOrderPrepare,
        on_delete=models.PROTECT,
        related_name="source_snapshot",
    )
    source_payment_instruction_prepare_id = models.BigIntegerField()
    source_payment_instruction_prepare_no = models.CharField(max_length=80)
    source_instruction_prepare_version = models.PositiveIntegerField()
    source_instruction_data_snapshot_id = models.BigIntegerField()
    source_instruction_data_version = models.PositiveIntegerField()
    source_instruction_validation_execution_id = models.BigIntegerField()
    source_instruction_validation_version = models.PositiveIntegerField()
    source_instruction_preview_hash = models.CharField(max_length=64)
    source_payment_request_id = models.BigIntegerField()
    source_payment_request_version = models.PositiveIntegerField()
    source_submission_snapshot_id = models.BigIntegerField()
    source_approval_workflow_id = models.BigIntegerField()
    source_approval_evidence_hash = models.CharField(max_length=64)
    source_instruction_prepare_hash = models.CharField(max_length=64)
    source_validation_hash = models.CharField(max_length=64)
    source_eligibility_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_order_prepare_source_snapshots"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Payment order prepare source snapshot is immutable")
        return super().save(*args, **kwargs)


class PaymentOrderPrepareDataSnapshot(models.Model):
    payment_order_prepare = models.ForeignKey(
        PaymentOrderPrepare,
        on_delete=models.PROTECT,
        related_name="order_data_snapshots",
    )
    order_data_version = models.PositiveIntegerField()
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
    data_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_order_prepare_data_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_order_prepare", "order_data_version"],
                name="uniq_pop_order_data_version",
            )
        ]


class PaymentOrderPrepareAuthoritySnapshot(models.Model):
    payment_order_prepare = models.ForeignKey(
        PaymentOrderPrepare,
        on_delete=models.PROTECT,
        related_name="authority_snapshots",
    )
    order_data_version = models.PositiveIntegerField()
    evidence = models.JSONField(default=dict)
    authority_snapshot_hash = models.CharField(max_length=64)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_order_prepare_authority_snapshots"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_order_prepare", "order_data_version"],
                name="uniq_pop_authority_data_version",
            )
        ]


class PaymentOrderPreparePreview(models.Model):
    order_data_snapshot = models.ForeignKey(
        PaymentOrderPrepareDataSnapshot,
        on_delete=models.PROTECT,
        related_name="previews",
    )
    preview_version = models.PositiveIntegerField()
    proposed_order_reference = models.CharField(max_length=120)
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
    preview_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_order_prepare_previews"
        constraints = [
            models.UniqueConstraint(
                fields=["order_data_snapshot", "preview_version"],
                name="uniq_pop_preview_version",
            )
        ]


class PaymentOrderPrepareValidationExecution(models.Model):
    payment_order_prepare = models.ForeignKey(
        PaymentOrderPrepare,
        on_delete=models.PROTECT,
        related_name="validation_executions",
    )
    action_id = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=120)
    order_data_version = models.PositiveIntegerField()
    source_instruction_prepare_version = models.PositiveIntegerField()
    source_instruction_validation_version = models.PositiveIntegerField()
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
        db_table = "payment_order_prepare_validation_executions"
        constraints = [
            models.UniqueConstraint(
                fields=["action_id", "idempotency_key"],
                name="uniq_pop_validation_action_key",
            ),
            models.UniqueConstraint(
                fields=["payment_order_prepare", "order_data_version"],
                name="uniq_pop_validation_data_version",
            ),
        ]


class PaymentOrderPrepareValidationIssue(models.Model):
    validation_execution = models.ForeignKey(
        PaymentOrderPrepareValidationExecution,
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
        db_table = "payment_order_prepare_validation_issues"
        constraints = [
            models.UniqueConstraint(
                fields=["validation_execution", "rule_code"],
                name="uniq_pop_validation_issue_rule",
            )
        ]


class PaymentOrderPrepareSourceRelation(models.Model):
    payment_order_prepare = models.ForeignKey(
        PaymentOrderPrepare,
        on_delete=models.PROTECT,
        related_name="source_relations",
    )
    source_type = models.CharField(max_length=48, default="paymentInstructionPrepare")
    source_id = models.BigIntegerField()
    source_no = models.CharField(max_length=80)
    source_version = models.PositiveIntegerField()
    relationship_type = models.CharField(max_length=40, default="generated_from")
    source_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_order_prepare_source_relations"
        constraints = [
            models.UniqueConstraint(
                fields=["payment_order_prepare", "source_type", "source_id"],
                name="uniq_pop_target_source",
            ),
            models.UniqueConstraint(
                fields=["source_type", "source_id", "relationship_type"],
                name="uniq_pop_source_generated",
            ),
        ]


class PaymentOrderPrepareCanaryScenario(models.Model):
    batch_id = models.CharField(max_length=80)
    scenario_code = models.CharField(max_length=80)
    scenario_class = models.CharField(max_length=32, default="blocked")
    blocking_rule_code = models.CharField(max_length=80)
    blocking_reason = models.CharField(max_length=240)
    formal_object_count = models.PositiveIntegerField(default=0)
    next_step_allowed = models.BooleanField(default=False)
    scenario_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "payment_order_prepare_canary_scenarios"
        constraints = [
            models.UniqueConstraint(
                fields=["batch_id", "scenario_code"],
                name="uniq_pop_canary_scenario",
            )
        ]
