from django.conf import settings
from django.db import models
from workflow_runtime.state_models import BusinessStateManagedModel


class PurchaseReconciliationSourceSnapshot(models.Model):
    source_key = models.CharField(max_length=160, unique=True)
    supplier_settlement_no = models.CharField(max_length=80)
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    legal_entity_id = models.CharField(max_length=80)
    ledger_book_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8)
    accounting_period = models.CharField(max_length=7)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    source_payable_check_no = models.CharField(max_length=80)
    source_payable_prepare_no = models.CharField(max_length=80)
    purchase_order_no = models.CharField(max_length=80)
    price_approval_no = models.CharField(max_length=80)
    unit = models.CharField(max_length=24)
    source_candidate_id = models.CharField(max_length=80)
    simulation_request_id = models.CharField(max_length=80)
    simulation_result_id = models.CharField(max_length=80)
    lifecycle_state = models.CharField(max_length=40)
    payable_status = models.CharField(max_length=40)
    simulation_integrity = models.CharField(max_length=40)
    snapshot_hash = models.CharField(max_length=64)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "purchase_reconciliation_source_snapshots"


class PurchaseReconciliationReview(models.Model):
    review_id = models.CharField(max_length=80, unique=True)
    source = models.ForeignKey(PurchaseReconciliationSourceSnapshot, on_delete=models.PROTECT, related_name="reviews")
    state = models.CharField(max_length=40)
    decision = models.CharField(max_length=40)
    simulation_integrity = models.CharField(max_length=40)
    audit_complete = models.BooleanField(default=False)
    fatal_risk_count = models.PositiveIntegerField(default=0)
    source_snapshot_hash = models.CharField(max_length=64)
    business_hash = models.CharField(max_length=64)
    supplier_id = models.CharField(max_length=80)
    legal_entity_id = models.CharField(max_length=80)
    ledger_book_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reviewed_at = models.DateTimeField()

    class Meta:
        db_table = "purchase_reconciliation_reviews"


class SupplierSettlementAuthorityRecord(models.Model):
    authority_object_id = models.CharField(max_length=80, unique=True)
    settlement_no = models.CharField(max_length=80, unique=True)
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    legal_entity_id = models.CharField(max_length=80)
    ledger_book_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    business_status = models.CharField(max_length=40)
    authority_version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)
    occurred_at = models.DateTimeField()

    class Meta:
        db_table = "supplier_settlement_authority_records"


class PayableCheckAuthorityRecord(models.Model):
    authority_object_id = models.CharField(max_length=80, unique=True)
    payable_check_no = models.CharField(max_length=80, unique=True)
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    supplier_id = models.CharField(max_length=80)
    legal_entity_id = models.CharField(max_length=80)
    ledger_book_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    checked_amount = models.DecimalField(max_digits=18, decimal_places=2)
    checked_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    business_status = models.CharField(max_length=40)
    authority_version = models.PositiveIntegerField(default=1)
    business_hash = models.CharField(max_length=64)
    occurred_at = models.DateTimeField()

    class Meta:
        db_table = "payable_check_authority_records"


class PurchaseReconciliation(BusinessStateManagedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        MATCHED = "matched", "Matched"
        DIFFERENCE_FOUND = "difference_found", "Difference found"
        SOURCE_MISSING = "source_missing", "Source missing"

    reconciliation_no = models.CharField(max_length=80, unique=True)
    tenant_id = models.CharField(max_length=64)
    company_id = models.BigIntegerField()
    source_key = models.CharField(max_length=160)
    source_supplier_settlement_no = models.CharField(max_length=80)
    source_payable_check_no = models.CharField(max_length=80)
    source_payable_prepare_no = models.CharField(max_length=80)
    purchase_order_no = models.CharField(max_length=80)
    price_approval_no = models.CharField(max_length=80)
    supplier_id = models.CharField(max_length=80)
    supplier_name = models.CharField(max_length=160)
    legal_entity_id = models.CharField(max_length=80)
    ledger_book_id = models.CharField(max_length=80)
    currency = models.CharField(max_length=8)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8)
    accounting_period = models.CharField(max_length=7)
    settlement_amount = models.DecimalField(max_digits=18, decimal_places=2)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=24)
    source_candidate_id = models.CharField(max_length=80)
    simulation_request_id = models.CharField(max_length=80)
    simulation_result_id = models.CharField(max_length=80)
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.DRAFT)
    source_snapshot_hash = models.CharField(max_length=64)
    review_id = models.CharField(max_length=80)
    review_hash = models.CharField(max_length=64)
    command_id = models.CharField(max_length=80)
    transaction_plan_id = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=120)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchase_reconciliations")
    number_reservation_id = models.BigIntegerField(null=True, blank=True)
    audit_record_id = models.BigIntegerField(null=True, blank=True)
    check_result_code = models.CharField(max_length=80, blank=True)
    difference_count = models.PositiveIntegerField(default=0)
    checked_at = models.DateTimeField(null=True, blank=True)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="checked_purchase_reconciliations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "purchase_reconciliations"
        permissions = [
            ("generate_purchase_reconciliation", "Can generate purchase reconciliation"),
            ("complete_purchase_reconciliation", "Can complete purchase reconciliation check"),
        ]


class PurchaseReconciliationEvidence(models.Model):
    reconciliation = models.ForeignKey(PurchaseReconciliation, on_delete=models.PROTECT, related_name="evidence_records")
    provider_code = models.CharField(max_length=80)
    repository_code = models.CharField(max_length=80)
    authority_type = models.CharField(max_length=80)
    authority_object_id = models.CharField(max_length=80)
    authority_object_no = models.CharField(max_length=80)
    authority_version = models.PositiveIntegerField()
    business_hash = models.CharField(max_length=64)
    evidence = models.JSONField(default=dict)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchase_reconciliation_evidence"
        constraints = [
            models.UniqueConstraint(
                fields=["reconciliation", "authority_type", "authority_object_id"],
                name="uniq_prc_evidence_authority_object",
            ),
        ]


class PurchaseReconciliationDifference(models.Model):
    reconciliation = models.ForeignKey(PurchaseReconciliation, on_delete=models.PROTECT, related_name="differences")
    check_version = models.PositiveIntegerField()
    difference_code = models.CharField(max_length=80)
    field_name = models.CharField(max_length=80)
    expected_value = models.CharField(max_length=240)
    actual_value = models.CharField(max_length=240)
    blocking = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchase_reconciliation_differences"
        constraints = [
            models.UniqueConstraint(
                fields=["reconciliation", "check_version", "difference_code"],
                name="uniq_prc_difference_version_code",
            ),
        ]


class PurchaseReconciliationCheckExecution(models.Model):
    reconciliation = models.ForeignKey(PurchaseReconciliation, on_delete=models.PROTECT, related_name="check_executions")
    idempotency_key = models.CharField(max_length=120, unique=True)
    request_hash = models.CharField(max_length=64)
    expected_version = models.PositiveIntegerField()
    result_status = models.CharField(max_length=40)
    check_result_code = models.CharField(max_length=80)
    difference_count = models.PositiveIntegerField(default=0)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchase_reconciliation_checks")
    result_payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchase_reconciliation_check_executions"


class PurchaseReconciliationSourceRelation(models.Model):
    reconciliation = models.ForeignKey(PurchaseReconciliation, on_delete=models.PROTECT, related_name="source_relations")
    source_key = models.CharField(max_length=160, unique=True)
    source_type = models.CharField(max_length=40, default="supplier_settlement")
    source_document_no = models.CharField(max_length=80)
    source_supplier_settlement_no = models.CharField(max_length=80)
    relationship_type = models.CharField(max_length=40, default="source_of")
    source_snapshot_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchase_reconciliation_source_relations"
        constraints = [models.UniqueConstraint(fields=["reconciliation", "source_type", "source_document_no"], name="uniq_prc_relation_target_source")]


class BusinessActionIdempotency(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMMITTED = "committed", "Committed"
        FAILED_RETRYABLE = "failed_retryable", "Failed retryable"
        FAILED_TERMINAL = "failed_terminal", "Failed terminal"
        COMMIT_UNKNOWN = "commit_unknown", "Commit unknown"

    action_code = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=120)
    tenant_id = models.CharField(max_length=64)
    source_key = models.CharField(max_length=160)
    request_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=40, choices=Status.choices)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.BigIntegerField(null=True, blank=True)
    target_no = models.CharField(max_length=80, blank=True)
    transaction_id = models.CharField(max_length=80, blank=True)
    result_reference = models.CharField(max_length=160, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "business_action_idempotency"
        constraints = [models.UniqueConstraint(fields=["action_code", "idempotency_key"], name="uniq_business_action_idempotency")]


class BusinessDocumentNumberReservation(models.Model):
    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserved"
        CONSUMED = "consumed", "Consumed"
        ABORTED = "aborted", "Aborted"

    document_type = models.CharField(max_length=40)
    number_policy_version = models.CharField(max_length=40)
    number_scope = models.CharField(max_length=320)
    legal_entity_id = models.CharField(max_length=80)
    ledger_book_id = models.CharField(max_length=80)
    reserved_number = models.CharField(max_length=80, unique=True)
    tenant_id = models.CharField(max_length=64)
    accounting_period = models.CharField(max_length=7)
    idempotency_key = models.CharField(max_length=120)
    status = models.CharField(max_length=24, choices=Status.choices)
    target = models.ForeignKey(PurchaseReconciliation, null=True, blank=True, on_delete=models.PROTECT, related_name="number_reservations")
    created_at = models.DateTimeField(auto_now_add=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    aborted_at = models.DateTimeField(null=True, blank=True)
    abort_reason = models.CharField(max_length=160, blank=True)
    reusable = models.BooleanField(default=False)

    class Meta:
        db_table = "business_document_number_reservations"


class BusinessActionTransaction(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMMITTING = "committing", "Committing"
        COMMITTED = "committed", "Committed"
        FAILED = "failed", "Failed"

    transaction_id = models.CharField(max_length=80, unique=True)
    action_code = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=120)
    tenant_id = models.CharField(max_length=64)
    source_key = models.CharField(max_length=160)
    command_id = models.CharField(max_length=80)
    transaction_plan_id = models.CharField(max_length=80)
    review_id = models.CharField(max_length=80)
    review_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=32, choices=Status.choices)
    outcome = models.CharField(max_length=40)
    commit_status = models.CharField(max_length=40)
    recovery_status = models.CharField(max_length=40)
    requires_recovery = models.BooleanField(default=False)
    requires_manual_intervention = models.BooleanField(default=False)
    result_hash = models.CharField(max_length=64, blank=True)
    reconciliation = models.ForeignKey(PurchaseReconciliation, null=True, blank=True, on_delete=models.PROTECT, related_name="transactions")
    error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "business_action_transactions"


class BusinessActionAuditRecord(models.Model):
    transaction = models.ForeignKey(BusinessActionTransaction, on_delete=models.PROTECT, related_name="audit_records")
    action_code = models.CharField(max_length=80)
    tenant_id = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="business_action_audits")
    source_key = models.CharField(max_length=160)
    reconciliation = models.ForeignKey(PurchaseReconciliation, on_delete=models.PROTECT, related_name="audit_records")
    result = models.CharField(max_length=32)
    target_type = models.CharField(max_length=80)
    target_id = models.BigIntegerField()
    target_no = models.CharField(max_length=80)
    review_id = models.CharField(max_length=80)
    review_hash = models.CharField(max_length=64)
    command_id = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=120)
    actor_name = models.CharField(max_length=160)
    tenant_or_scope = models.CharField(max_length=160)
    evidence_hash = models.CharField(max_length=64)
    evidence = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "business_action_audit_records"


class BusinessActionSourceLock(models.Model):
    lock_key = models.CharField(max_length=200, unique=True)
    owner_transaction_id = models.CharField(max_length=80)
    state = models.CharField(max_length=24)
    acquired_at = models.DateTimeField(auto_now=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "business_action_source_locks"


class BusinessDocumentNumberSequence(models.Model):
    number_scope = models.CharField(max_length=320, unique=True)
    current_value = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "business_document_number_sequences"
