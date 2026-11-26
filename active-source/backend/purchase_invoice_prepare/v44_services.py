import uuid
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from reconciliation.checking import build_invoice_prepare_eligibility
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionIdempotency,
    BusinessActionSourceLock,
    BusinessActionTransaction,
)
from reconciliation.services import ReconciliationError, canonical_hash
from workflow_runtime.state_transitions import transition_business_object

from .models import (
    PurchaseInvoiceDataLine,
    PurchaseInvoiceDataSnapshot,
    PurchaseInvoiceIdentityClaim,
    PurchaseInvoicePrepare,
    PurchaseInvoiceValidationExecution,
    PurchaseInvoiceValidationIssue,
)
from .services import (
    build_purchase_invoice_prepare_state_facts,
    serialize_prepare,
)
from .validation import (
    VALIDATION_POLICY_VERSION,
    build_invoice_identity_key,
    canonical_payload_hash,
    execute_invoice_validation,
    invoice_data_completeness,
    validation_result_code,
)

SAVE_ACTION = "SAVE_PURCHASE_INVOICE_PREPARE_DATA"
VALIDATE_ACTION = "VALIDATE_PURCHASE_INVOICE_PREPARE"
SAVE_FAILURE_STEPS = (
    "after_authorization", "after_object_read", "after_version_check",
    "after_idempotency_registration", "after_snapshot_insert", "after_lines_insert",
    "after_prepare_update", "after_audit_insert", "after_idempotency_committed",
    "before_database_commit", "before_response",
)
VALIDATION_FAILURE_STEPS = (
    "after_authorization", "after_object_lock", "after_data_reload",
    "after_source_reload", "after_source_version_check", "after_authority_read",
    "after_execution_insert", "after_issues_insert", "after_identity_claim_insert",
    "after_prepare_prepared", "after_audit_insert", "after_idempotency_committed",
    "before_database_commit", "before_response",
)


def _inject(step, requested):
    if step != requested:
        return
    if not settings.PCE_PURCHASE_INVOICE_VALIDATION_FAILURE_INJECTION_ENABLED:
        raise ReconciliationError("PIP_VALIDATION_FAILURE_INJECTION_DISABLED", "Failure injection disabled", 403)
    raise ReconciliationError(f"PIP_INJECTED_{step.upper()}", f"Injected failure at {step}", 503, True)


def _authorize(user, prepare, permission, prefix):
    if not user or not user.is_authenticated:
        raise ReconciliationError(f"{prefix}_UNAUTHENTICATED", "Authentication required", 401)
    if not (user.is_superuser or user.has_perm(permission)):
        raise ReconciliationError(f"{prefix}_PERMISSION_DENIED", "Permission required", 403)
    if not user.is_superuser and user.company_id != prepare.company_id:
        raise ReconciliationError(f"{prefix}_SCOPE_DENIED", "Object outside company scope", 403)
    if not settings.PCE_PURCHASE_INVOICE_VALIDATION_FEATURE_ENABLED:
        raise ReconciliationError(f"{prefix}_FEATURE_DISABLED", "Feature flag disabled", 403)
    if (
        prepare.tenant_id not in settings.PCE_PURCHASE_INVOICE_VALIDATION_TEST_TENANTS
        and not settings.PCE_PURCHASE_INVOICE_VALIDATION_PRODUCTION_ROLLOUT_ENABLED
    ):
        raise ReconciliationError(f"{prefix}_PRODUCTION_ROLLOUT_DISABLED", "Production rollout disabled", 403)


def _explicit_action(value, prefix):
    if value is not True:
        raise ReconciliationError(f"{prefix}_EXPLICIT_ACTION_REQUIRED", "Explicit user action required", 400)


def _transaction_record(prepare, action_code, idempotency_key):
    transaction_id = f"PIPV44-{uuid.uuid4().hex}"
    source = prepare.source_purchase_reconciliation
    return BusinessActionTransaction.objects.create(
        transaction_id=transaction_id,
        action_code=action_code,
        idempotency_key=idempotency_key,
        tenant_id=prepare.tenant_id,
        source_key=f"purchaseInvoicePrepare:{prepare.pk}",
        command_id=action_code,
        transaction_plan_id="purchase-invoice-validation-atomic-v1",
        review_id=source.review_id,
        review_hash=source.review_hash,
        status=BusinessActionTransaction.Status.IN_PROGRESS,
        outcome="in_progress",
        commit_status="in_progress",
        recovery_status="not_required",
        reconciliation=source,
    )


def _audit(prepare, user, action_code, idempotency_key, tx, evidence):
    source = prepare.source_purchase_reconciliation
    return BusinessActionAuditRecord.objects.create(
        transaction=tx,
        action_code=action_code,
        tenant_id=prepare.tenant_id,
        actor=user,
        source_key=f"purchaseInvoicePrepare:{prepare.pk}",
        reconciliation=source,
        result="committed",
        target_type="purchaseInvoicePrepare",
        target_id=prepare.pk,
        target_no=prepare.prepare_no,
        review_id=source.review_id,
        review_hash=source.review_hash,
        command_id=action_code,
        idempotency_key=idempotency_key,
        actor_name=user.get_username(),
        tenant_or_scope=prepare.tenant_id,
        evidence_hash=canonical_hash(evidence),
        evidence=evidence,
    )


def _commit_records(idempotency, tx, prepare, result_reference):
    tx.status = BusinessActionTransaction.Status.COMMITTED
    tx.outcome = "success"
    tx.commit_status = "committed"
    tx.result_hash = canonical_hash(result_reference)
    tx.save(update_fields=["status", "outcome", "commit_status", "result_hash", "updated_at"])
    idempotency.status = BusinessActionIdempotency.Status.COMMITTED
    idempotency.target_type = "purchaseInvoicePrepare"
    idempotency.target_id = prepare.pk
    idempotency.target_no = prepare.prepare_no
    idempotency.transaction_id = tx.transaction_id
    idempotency.result_reference = result_reference
    idempotency.save(update_fields=[
        "status", "target_type", "target_id", "target_no", "transaction_id",
        "result_reference", "updated_at",
    ])


def serialize_line(line):
    return {
        "lineNo": line.line_no, "itemCode": line.item_code, "itemName": line.item_name,
        "specification": line.specification, "quantity": str(line.quantity), "unit": line.unit,
        "unitPrice": str(line.unit_price), "amountExcludingTax": str(line.amount_excluding_tax),
        "taxRate": str(line.tax_rate), "taxAmount": str(line.tax_amount),
        "amountIncludingTax": str(line.amount_including_tax), "lineHash": line.line_hash,
    }


def serialize_snapshot(snapshot):
    if not snapshot:
        return None
    return {
        "id": snapshot.pk, "dataVersion": snapshot.data_version, "dataSource": snapshot.data_source,
        "invoiceType": snapshot.invoice_type, "invoiceCode": snapshot.invoice_code,
        "invoiceNumber": snapshot.invoice_number,
        "invoiceDate": snapshot.invoice_date.isoformat() if snapshot.invoice_date else None,
        "sellerName": snapshot.seller_name, "sellerTaxId": snapshot.seller_tax_id,
        "buyerName": snapshot.buyer_name, "buyerTaxId": snapshot.buyer_tax_id,
        "currency": snapshot.currency, "amountExcludingTax": str(snapshot.amount_excluding_tax or ""),
        "taxAmount": str(snapshot.tax_amount or ""), "amountIncludingTax": str(snapshot.amount_including_tax or ""),
        "invoiceIdentityKey": snapshot.invoice_identity_key, "dataHash": snapshot.data_hash,
        "lines": [serialize_line(line) for line in snapshot.lines.order_by("line_no")],
    }


def serialize_issue(issue):
    return {
        "ruleCode": issue.rule_code, "dimension": issue.dimension, "lineNo": issue.line_no,
        "expected": issue.expected, "actual": issue.actual, "delta": issue.delta,
        "severity": issue.severity, "blocking": issue.blocking, "message": issue.message,
        "ruleVersion": issue.rule_version,
    }


def current_snapshot(prepare):
    return prepare.invoice_data_snapshots.filter(data_version=prepare.current_data_version).first()


def current_execution(prepare):
    return prepare.validation_executions.filter(
        data_version=prepare.current_data_version
    ).order_by("-created_at", "-id").first()


def build_ap_draft_eligibility(prepare):
    source = prepare.source_purchase_reconciliation
    source_eligibility = build_invoice_prepare_eligibility(source)
    claim = prepare.invoice_identity_claims.filter(status="active").first()
    draft_model = apps.get_model(
        "purchase_accounts_payable_draft", "PurchaseAccountsPayableDraft"
    )
    target_count = draft_model.objects.filter(
        source_purchase_invoice_prepare=prepare
    ).count()
    reasons = []
    state_facts = build_purchase_invoice_prepare_state_facts(prepare)
    conditions = {
        "stateMachineConsistent": state_facts["stateMachineConsistent"],
        "statusPrepared": prepare.status == "prepared",
        "invoiceDataComplete": prepare.invoice_data_status == "complete",
        "validationPassed": prepare.validation_status == "passed",
        "resultValidated": prepare.validation_result_code == "validated",
        "zeroIssues": prepare.validation_issue_count == 0,
        "identityActive": bool(claim),
        "sourceMatched": source.status == "matched",
        "sourceEligibilityValid": source_eligibility["eligible"],
        "sourceVersionCurrent": prepare.source_reconciliation_version == source.version,
        "checkVersionCurrent": prepare.source_check_version == source_eligibility["checkVersion"],
        "accountsPayableDraftAbsent": target_count == 0,
    }
    for key, passed in conditions.items():
        if not passed:
            reasons.append(key)
    eligible = all(conditions.values())
    return {
        "eligible": eligible,
        "eligibilityCode": "PIP_AP_DRAFT_ELIGIBLE" if eligible else "PIP_AP_DRAFT_BLOCKED",
        "purchaseInvoicePrepareId": prepare.pk,
        "purchaseInvoicePrepareNo": prepare.prepare_no,
        "status": prepare.status,
        "invoiceDataStatus": prepare.invoice_data_status,
        "validationStatus": prepare.validation_status,
        "validationResultCode": prepare.validation_result_code,
        "validationIssueCount": prepare.validation_issue_count,
        "invoiceIdentityStatus": claim.status if claim else "not_claimed",
        "sourcePurchaseReconciliationStatus": source.status,
        "sourceReconciliationVersion": source.version,
        "sourceCheckVersion": source_eligibility["checkVersion"],
        "prepareVersion": prepare.version,
        "invoiceDataVersion": prepare.current_data_version,
        "validationVersion": prepare.current_validation_version,
        "nextStepReadiness": "ready_for_accounts_payable_draft" if eligible else "blocked",
        "blockingReasons": reasons,
        "evaluatedAt": timezone.now().isoformat(),
        "accountsPayableDraftCount": target_count,
        "currentStateSource": "server",
        **state_facts,
    }


def build_validation_read_model(prepare):
    snapshot = current_snapshot(prepare)
    execution = current_execution(prepare)
    issues = list(execution.issues.order_by("id")) if execution else []
    claim = prepare.invoice_identity_claims.filter(status="active").first()
    save_idempotency = BusinessActionIdempotency.objects.filter(
        action_code=SAVE_ACTION, target_id=prepare.pk
    ).order_by("-updated_at").first()
    validation_idempotency = BusinessActionIdempotency.objects.filter(
        action_code=VALIDATE_ACTION, target_id=prepare.pk
    ).order_by("-updated_at").first()
    tx = BusinessActionTransaction.objects.filter(
        action_code__in=[SAVE_ACTION, VALIDATE_ACTION],
        source_key=f"purchaseInvoicePrepare:{prepare.pk}",
    ).order_by("-updated_at").first()
    return {
        "currentStateSource": "server",
        "purchaseInvoicePrepare": serialize_prepare(prepare),
        "invoiceData": serialize_snapshot(snapshot),
        "validation": {
            "status": prepare.validation_status,
            "resultCode": prepare.validation_result_code,
            "policyVersion": VALIDATION_POLICY_VERSION,
            "dataVersion": prepare.current_data_version,
            "sourceVersion": prepare.source_reconciliation_version,
            "checkVersion": prepare.source_check_version,
            "validationVersion": prepare.current_validation_version,
            "ruleCount": execution.rule_count if execution else 0,
            "passedRuleCount": execution.passed_rule_count if execution else 0,
            "blockingRuleCount": execution.blocking_rule_count if execution else 0,
            "issueCount": len(issues),
            "idempotencyKey": execution.idempotency_key if execution else "",
        },
        "validationIssues": [serialize_issue(issue) for issue in issues],
        "invoiceIdentity": {
            "identityKey": claim.invoice_identity_key if claim else (snapshot.invoice_identity_key if snapshot else ""),
            "status": claim.status if claim else "not_claimed",
            "existingPrepareId": claim.purchase_invoice_prepare_id if claim else None,
            "duplicateFound": False,
            "duplicateBlockingCode": "",
            "databaseUniqueConstraint": "uniq_active_purchase_invoice_identity",
        },
        "accountsPayableDraftEligibility": build_ap_draft_eligibility(prepare),
        "versionsAndAudit": {
            "prepareVersion": prepare.version,
            "dataVersion": prepare.current_data_version,
            "validationVersion": prepare.current_validation_version,
            "saveIdempotencyStatus": save_idempotency.status if save_idempotency else "not_started",
            "validationIdempotencyStatus": validation_idempotency.status if validation_idempotency else "not_started",
            "transactionStatus": tx.commit_status if tx else "not_started",
            "auditStatus": "committed" if tx and tx.audit_records.exists() else "not_started",
            "currentStateSource": "server",
        },
        "downstreamCounts": {
            "accountsPayableDrafts": 0, "paymentApplications": 0, "payments": 0,
            "paymentVouchers": 0, "writeoffs": 0, "ledgerEntries": 0,
            "postings": 0, "bankTransactions": 0, "productionTenantWrites": 0,
            "localStorageBusinessWrites": 0,
        },
    }


def _decimal(payload, field):
    try:
        return Decimal(str(payload.get(field))) if payload.get(field) not in (None, "") else None
    except (InvalidOperation, ValueError):
        raise ReconciliationError("PIP_DATA_INVALID_DECIMAL", f"{field} is invalid", 400)


def save_invoice_data(*, user, prepare_id, idempotency_key, expected_version,
                      expected_data_version, explicit_user_action, invoice_data, failure_step=""):
    _explicit_action(explicit_user_action, "PIP_DATA")
    request_hash = canonical_payload_hash({
        "prepareId": prepare_id, "expectedVersion": expected_version,
        "expectedDataVersion": expected_data_version, "invoiceData": invoice_data,
    })
    with transaction.atomic():
        prepare = PurchaseInvoicePrepare.objects.select_for_update().get(pk=prepare_id)
        _authorize(user, prepare, "purchase_invoice_prepare.edit_invoice_data", "PIP_DATA")
        _inject("after_authorization", failure_step)
        existing = BusinessActionIdempotency.objects.filter(
            action_code=SAVE_ACTION, idempotency_key=idempotency_key
        ).first()
        if existing:
            if existing.request_hash != request_hash:
                raise ReconciliationError("PIP_DATA_IDEMPOTENCY_CONFLICT", "Idempotency payload differs", 409)
            if existing.status == BusinessActionIdempotency.Status.COMMITTED:
                return {"classification": "existing_result", **build_validation_read_model(prepare)}
        if prepare.status == "prepared":
            raise ReconciliationError("PIP_DATA_PREPARED_IMMUTABLE", "Prepared data is immutable", 409)
        _inject("after_object_read", failure_step)
        if prepare.version != expected_version or prepare.current_data_version != expected_data_version:
            raise ReconciliationError("PIP_DATA_VERSION_CONFLICT", "Prepare or data version changed", 409)
        _inject("after_version_check", failure_step)
        tx = _transaction_record(prepare, SAVE_ACTION, idempotency_key)
        idem = existing or BusinessActionIdempotency.objects.create(
            action_code=SAVE_ACTION, idempotency_key=idempotency_key, tenant_id=prepare.tenant_id,
            source_key=f"purchaseInvoicePrepare:{prepare.pk}", request_hash=request_hash,
            status=BusinessActionIdempotency.Status.IN_PROGRESS, transaction_id=tx.transaction_id,
        )
        BusinessActionSourceLock.objects.update_or_create(
            lock_key=f"purchaseInvoicePrepare:{prepare.pk}",
            defaults={"owner_transaction_id": tx.transaction_id, "state": "held"},
        )
        _inject("after_idempotency_registration", failure_step)
        completeness = invoice_data_completeness(invoice_data)
        version = prepare.current_data_version + 1
        snapshot = PurchaseInvoiceDataSnapshot.objects.create(
            purchase_invoice_prepare=prepare, data_version=version, data_source="manual_entry",
            invoice_type=invoice_data.get("invoiceType", ""), invoice_code=invoice_data.get("invoiceCode", ""),
            invoice_number=invoice_data.get("invoiceNumber", ""), invoice_date=invoice_data.get("invoiceDate") or None,
            seller_name=invoice_data.get("sellerName", ""), seller_tax_id=invoice_data.get("sellerTaxId", ""),
            buyer_name=invoice_data.get("buyerName", ""), buyer_tax_id=invoice_data.get("buyerTaxId", ""),
            currency=invoice_data.get("currency", ""), amount_excluding_tax=_decimal(invoice_data, "amountExcludingTax"),
            tax_amount=_decimal(invoice_data, "taxAmount"), amount_including_tax=_decimal(invoice_data, "amountIncludingTax"),
            data_hash=canonical_payload_hash(invoice_data), created_by=user,
        )
        snapshot.invoice_identity_key = build_invoice_identity_key(prepare, snapshot)
        snapshot.save(update_fields=["invoice_identity_key"])
        _inject("after_snapshot_insert", failure_step)
        for index, line in enumerate(invoice_data.get("lines") or [], 1):
            line_payload = {**line, "lineNo": line.get("lineNo") or index}
            PurchaseInvoiceDataLine.objects.create(
                invoice_data_snapshot=snapshot, line_no=line_payload["lineNo"],
                item_code=line_payload.get("itemCode", ""), item_name=line_payload.get("itemName", ""),
                specification=line_payload.get("specification", ""), quantity=_decimal(line_payload, "quantity"),
                unit=line_payload.get("unit", ""), unit_price=_decimal(line_payload, "unitPrice"),
                amount_excluding_tax=_decimal(line_payload, "amountExcludingTax"),
                tax_rate=_decimal(line_payload, "taxRate"), tax_amount=_decimal(line_payload, "taxAmount"),
                amount_including_tax=_decimal(line_payload, "amountIncludingTax"),
                line_hash=canonical_payload_hash(line_payload),
            )
        _inject("after_lines_insert", failure_step)
        prepare.current_data_version = version
        prepare.invoice_data_status = "complete" if completeness["complete"] else "incomplete"
        prepare.validation_status = "not_validated"
        prepare.validation_result_code = "not_validated"
        prepare.validation_issue_count = 0
        prepare.version += 1
        prepare.save(update_fields=[
            "current_data_version", "invoice_data_status", "validation_status",
            "validation_result_code", "validation_issue_count", "version", "updated_at",
        ])
        _inject("after_prepare_update", failure_step)
        audit = _audit(prepare, user, SAVE_ACTION, idempotency_key, tx, {
            "dataVersion": version, "dataHash": snapshot.data_hash,
            "completeness": completeness, "action": SAVE_ACTION,
        })
        _inject("after_audit_insert", failure_step)
        _commit_records(idem, tx, prepare, f"invoiceDataSnapshot:{snapshot.pk}")
        _inject("after_idempotency_committed", failure_step)
        _inject("before_database_commit", failure_step)
    _inject("before_response", failure_step)
    return {"classification": "saved", "auditRecordId": audit.pk, **build_validation_read_model(prepare)}


def validate_invoice_data(*, user, prepare_id, idempotency_key, expected_version,
                          expected_data_version, expected_reconciliation_version,
                          expected_check_version, explicit_user_action, failure_step=""):
    _explicit_action(explicit_user_action, "PIP_VALIDATION")
    try:
        with transaction.atomic():
            prepare = PurchaseInvoicePrepare.objects.select_for_update().get(pk=prepare_id)
            _authorize(user, prepare, "purchase_invoice_prepare.validate_invoice_data", "PIP_VALIDATION")
            _inject("after_authorization", failure_step)
            existing = BusinessActionIdempotency.objects.filter(
                action_code=VALIDATE_ACTION, idempotency_key=idempotency_key
            ).first()
            if existing and existing.status == BusinessActionIdempotency.Status.COMMITTED:
                return {"classification": "existing_result", **build_validation_read_model(prepare)}
            if prepare.status == "prepared":
                raise ReconciliationError("PIP_DATA_PREPARED_IMMUTABLE", "Prepared data is immutable", 409)
            if prepare.version != expected_version or prepare.current_data_version != expected_data_version:
                raise ReconciliationError("PIP_VALIDATION_VERSION_CONFLICT", "Prepare or data version changed", 409)
            _inject("after_object_lock", failure_step)
            snapshot = current_snapshot(prepare)
            if not snapshot or prepare.invoice_data_status != "complete":
                raise ReconciliationError("PIP_VALIDATION_DATA_INCOMPLETE", "Invoice data incomplete", 409)
            _inject("after_data_reload", failure_step)
            source = prepare.source_purchase_reconciliation
            _inject("after_source_reload", failure_step)
            source_eligibility = build_invoice_prepare_eligibility(source)
            if source.version != expected_reconciliation_version or source_eligibility["checkVersion"] != expected_check_version:
                raise ReconciliationError("PIP_VALIDATION_SOURCE_STALE", "Source version changed", 409)
            _inject("after_source_version_check", failure_step)
            request_hash = canonical_payload_hash({
                "prepareId": prepare_id, "dataVersion": expected_data_version,
                "sourceVersion": expected_reconciliation_version, "checkVersion": expected_check_version,
            })
            tx = _transaction_record(prepare, VALIDATE_ACTION, idempotency_key)
            idem = existing or BusinessActionIdempotency.objects.create(
                action_code=VALIDATE_ACTION, idempotency_key=idempotency_key, tenant_id=prepare.tenant_id,
                source_key=f"purchaseInvoicePrepare:{prepare.pk}", request_hash=request_hash,
                status=BusinessActionIdempotency.Status.IN_PROGRESS, transaction_id=tx.transaction_id,
            )
            BusinessActionSourceLock.objects.update_or_create(
                lock_key=f"purchaseInvoicePrepare:{prepare.pk}",
                defaults={"owner_transaction_id": tx.transaction_id, "state": "held"},
            )
            duplicate = PurchaseInvoiceIdentityClaim.objects.filter(
                tenant_id=prepare.tenant_id, legal_entity_id=prepare.legal_entity_id,
                invoice_identity_key=snapshot.invoice_identity_key, status="active",
            ).exclude(purchase_invoice_prepare=prepare).exists()
            validation = execute_invoice_validation(prepare, snapshot, identity_claim_exists=duplicate)
            _inject("after_authority_read", failure_step)
            issues = validation["issues"]
            result_code = validation_result_code(issues)
            execution = PurchaseInvoiceValidationExecution.objects.create(
                purchase_invoice_prepare=prepare, idempotency_key=idempotency_key,
                data_version=prepare.current_data_version,
                source_reconciliation_version=source.version,
                source_check_version=source_eligibility["checkVersion"],
                validation_policy_version=VALIDATION_POLICY_VERSION,
                status="passed" if validation["passed"] else "failed",
                result_code=result_code, input_hash=request_hash,
                result_hash=canonical_payload_hash(validation["results"]),
                issue_count=len(issues), rule_count=len(validation["results"]),
                passed_rule_count=sum(item["status"] == "passed" for item in validation["results"]),
                blocking_rule_count=len(issues), actor=user, transaction_id=tx.transaction_id,
                completed_at=timezone.now(),
            )
            _inject("after_execution_insert", failure_step)
            for issue in issues:
                PurchaseInvoiceValidationIssue.objects.create(
                    validation_execution=execution, rule_code=issue["code"],
                    dimension=issue["category"], line_no=issue["lineNo"],
                    expected=issue["expected"], actual=issue["actual"], delta="",
                    severity=issue["severity"], blocking=issue["blocking"],
                    message=issue["message"], rule_version="v1",
                )
            _inject("after_issues_insert", failure_step)
            validation_passed = validation["passed"]
            if validation_passed:
                PurchaseInvoiceIdentityClaim.objects.create(
                    tenant_id=prepare.tenant_id, legal_entity_id=prepare.legal_entity_id,
                    invoice_identity_key=validation["identityKey"],
                    purchase_invoice_prepare=prepare, invoice_data_snapshot=snapshot, status="active",
                )
                _inject("after_identity_claim_insert", failure_step)
                prepare.validation_status = "passed"
                prepare.validation_result_code = "validated"
                prepare.prepared_at = timezone.now()
                prepare.prepared_by = user
            else:
                prepare.validation_status = "failed"
                prepare.validation_result_code = result_code
            prepare.current_validation_version += 1
            prepare.validation_issue_count = len(issues)
            prepare.save(update_fields=[
                "validation_status", "validation_result_code",
                "current_validation_version", "validation_issue_count",
                "prepared_at", "prepared_by", "updated_at",
            ])
            audit = _audit(prepare, user, VALIDATE_ACTION, idempotency_key, tx, {
                "validationExecutionId": execution.pk, "dataVersion": snapshot.data_version,
                "resultCode": result_code, "issueCount": len(issues),
                "identityKey": validation["identityKey"], "policyVersion": VALIDATION_POLICY_VERSION,
            })
            if validation_passed:
                transition_business_object(
                    business_object=prepare,
                    object_type="purchase_invoice_prepare",
                    source_state=PurchaseInvoicePrepare.Status.DRAFT,
                    target_state=PurchaseInvoicePrepare.Status.PREPARED,
                    action_code=VALIDATE_ACTION,
                    operator=user,
                    reason="Purchase invoice data validation passed",
                    audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
                    allowed_transitions={
                        (
                            PurchaseInvoicePrepare.Status.DRAFT,
                            PurchaseInvoicePrepare.Status.PREPARED,
                        ),
                    },
                )
            else:
                prepare.version += 1
                prepare.save(update_fields=["version", "updated_at"])
            _inject("after_prepare_prepared", failure_step)
            execution.audit_record_id = audit.pk
            execution.save(update_fields=["audit_record_id"])
            _inject("after_audit_insert", failure_step)
            _commit_records(idem, tx, prepare, f"invoiceValidation:{execution.pk}")
            _inject("after_idempotency_committed", failure_step)
            _inject("before_database_commit", failure_step)
        _inject("before_response", failure_step)
        return {
            "classification": "validated" if validation["passed"] else "validation_failed",
            **build_validation_read_model(prepare),
        }
    except IntegrityError as exc:
        if "uniq_active_purchase_invoice_identity" in str(exc) or "UNIQUE constraint failed" in str(exc):
            raise ReconciliationError("PIP_VALIDATION_DUPLICATE_INVOICE", "Invoice identity already active", 409)
        raise


def recover_validation_result(idempotency_key, user):
    execution = PurchaseInvoiceValidationExecution.objects.filter(idempotency_key=idempotency_key).first()
    if not execution:
        raise ReconciliationError("PIP_VALIDATION_RESULT_NOT_FOUND", "Validation result not found", 404)
    prepare = execution.purchase_invoice_prepare
    if not user.is_superuser and user.company_id != prepare.company_id:
        raise ReconciliationError("PIP_VALIDATION_SCOPE_DENIED", "Object outside company scope", 403)
    return {"classification": "existing_result", **build_validation_read_model(prepare)}
