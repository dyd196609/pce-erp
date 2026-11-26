"""User-approved existing finance duty, scoped through original formal proofs."""
from django.core.exceptions import ObjectDoesNotExist
from system.authorization import AuthorizationService
from procurement.models import PurchaseOrder
from procurement.fact_read_access import ReadScopeBlocked, validate_read_identity, scope_fact_missing
from .models import (SupplierSettlementActionAudit, SupplierReconciliation,
                     SupplierPayableConfirmation, SupplierPaymentRequest,
                     SupplierPaymentStatusRecord)
from .formal_services import _chain_from_source, FormalActionBlocked, FORMAL_VERSION, BATCH_ID

FINANCE_ROLE = "supplier_settlement_finance"
EXISTING_DUTY_PERMISSIONS = ("scm.supplier_payable.confirm", "scm.supplier_payment_status.record")
FINANCE_READ_SCOPE_FACTS = {
    "contract": "USER_APPROVED_EXISTING_FINANCE_DUTY_20261116",
    "ownership": "ORIGINAL_TYPED_CHAIN_AND_AUDIT_TENANT_BRIDGE",
    "unprovenOwnership": "WITHHELD_NOT_ASSIGNED_TO_CALLER",
    "countScope": "AUTHORIZED_PROVEN_RECORDS_ONLY",
    "readDoesNotAuthorizeExecution": True,
}


def finance_qualification(user):
    validate_read_identity(user)
    if user.is_superuser:
        if AuthorizationService.decide(user=user, action_code=EXISTING_DUTY_PERMISSIONS[0], organization_id=user.company_id)["allowed"]:
            return
    evidence = [e for e in AuthorizationService.authority_evidence(user) if e.role_code == FINANCE_ROLE]
    codes = AuthorizationService.permission_codes_for_user(user, {FINANCE_ROLE})
    if all(code in codes for code in EXISTING_DUTY_PERMISSIONS):
        for e in evidence:
            if all(AuthorizationService.decide(user=user, action_code=code,
                                              organization_id=e.organization_id)["allowed"] for code in EXISTING_DUTY_PERMISSIONS):
                return
    raise ReadScopeBlocked("FINANCE_READ_DUTY_REQUIRED", "当前身份没有已核定的供应商应付付款只读职责。")


def finance_order_allowed(user, order):
    facts = {"organizationId": order.company_id,
             "departmentId": order.purchase_department_id or order.department_id or "__NOT_PROVIDED__",
             "ownerUserId": order.created_by or "__NOT_PROVIDED__"}
    if not user.is_superuser:
        evidence = [e for e in AuthorizationService.authority_evidence(user, order.company_id)
                    if e.role_code == FINANCE_ROLE and AuthorizationService._scope_matches(e, user, facts, {})]
        if not evidence:
            return False
    return all(AuthorizationService.decide(user=user, action_code=code,
                                          organization_id=order.company_id,
                                          business_object=facts)["allowed"] for code in EXISTING_DUTY_PERMISSIONS)


def _no(value):
    if isinstance(value, SupplierReconciliation): return value.reconciliation_no
    if isinstance(value, SupplierPayableConfirmation): return value.payable_confirmation_no
    return value.payment_request_no


def _audit_proves(value, parent, order, tenant):
    rows = SupplierSettlementActionAudit.objects.filter(
        object_type=value.__class__.__name__, object_id=value.pk, object_no=_no(value),
        tenant_id=tenant, legal_entity_id=str(order.company_id),
        source_object_type=parent.__class__.__name__,
        source_object_no=order.po_no if isinstance(parent, PurchaseOrder) else _no(parent),
        authorization_result__in=("ALLOWED", "ALLOWED_SUPERUSER"))
    for audit in rows:
        proof = audit.evidence or {}
        target = proof.get("target", {})
        if (proof.get("formalVersion") != FORMAL_VERSION or
            not proof.get("authorization", {}).get("allowed") or
            target != {"type": value.__class__.__name__, "id": value.pk, "no": _no(value)}):
            continue
        if isinstance(value, SupplierReconciliation):
            # This is the explicit tenant-to-company bridge: the original audit
            # connects this tenant/target to this typed native order id AND no.
            if {"id": order.pk, "no": order.po_no} not in proof.get("sourceRelations", {}).get("purchaseOrders", []):
                continue
        return True
    return False


def financial_source_order(value):
    try:
        order, reconciliation, payable, request, payment = _chain_from_source(value)
        chain = [x for x in (reconciliation, payable, request, payment) if x is not None]
        if not chain or any(x.tenant_id != value.tenant_id or x.batch_id != BATCH_ID for x in chain):
            return None
        if any(str(x.supplier_id) != str(order.supplier.code) for x in chain):
            return None
        parent = order
        for obj in chain:
            if not _audit_proves(obj, parent, order, value.tenant_id):
                return None
            parent = obj
        return order
    except (ObjectDoesNotExist, FormalActionBlocked, TypeError, ValueError):
        return None


def scoped_financial_queryset(queryset, user):
    finance_qualification(user)
    ids = []; unresolved = False
    for value in queryset:
        order = financial_source_order(value)
        if order is None:
            unresolved = True
        elif finance_order_allowed(user, order):
            ids.append(value.pk)
        elif scope_fact_missing(user, {"organizationId": order.company_id,
                                      "departmentId": order.purchase_department_id or order.department_id,
                                      "ownerUserId": order.created_by}, FINANCE_ROLE):
            unresolved = True
    if not ids and unresolved:
        raise ReadScopeBlocked("FINANCE_SOURCE_OWNERSHIP_UNRESOLVED", "原单据及审计尚不能证明归属，记录保持待核，不显示为空结果。", 409)
    return queryset.filter(pk__in=ids)


def financial_audit_ids(values):
    ids = []
    for value in values:
        order = financial_source_order(value)
        if order is not None:
            ids.extend(SupplierSettlementActionAudit.objects.filter(
                object_type=value.__class__.__name__, object_id=value.pk,
                object_no=_no(value), tenant_id=value.tenant_id,
                legal_entity_id=str(order.company_id)).values_list("pk", flat=True))
    return ids


def filter_financial_audits(payload, value):
    references = {f"SupplierSettlementActionAudit:{pk}" for pk in financial_audit_ids([value])}
    return [row for row in payload if row.get("auditReference") in references]


def require_financial_chain(user, order_id):
    finance_qualification(user)
    order = PurchaseOrder.objects.filter(pk=order_id).first()
    if order is None or not finance_order_allowed(user, order):
        raise ReadScopeBlocked("SOURCE_NOT_AVAILABLE_IN_READ_SCOPE", "该对象不在当前可读范围。", 404)
    # The original chain readback joins by persisted document number. Verify its
    # candidates before allowing that original projection to produce details.
    reconciliations = [row for row in SupplierReconciliation.objects.all()
                       if order.po_no in (row.purchase_order_ids or [])]
    if len(reconciliations) > 1:
        raise ReadScopeBlocked("FINANCE_SOURCE_CHAIN_AMBIGUOUS", "存在未核定的多条来源链，不能猜选。", 409)
    for rec in reconciliations:
        if len(rec.purchase_order_ids or []) != 1 or not _audit_proves(rec, order, order, rec.tenant_id):
            raise ReadScopeBlocked("FINANCE_SOURCE_OWNERSHIP_UNRESOLVED", "关联链归属尚未核明。", 409)
        payables = SupplierPayableConfirmation.objects.filter(reconciliation_no=rec.reconciliation_no)
        for payable in payables:
            if financial_source_order(payable) is None:
                raise ReadScopeBlocked("FINANCE_SOURCE_OWNERSHIP_UNRESOLVED", "关联链归属尚未核明。", 409)
            for request in SupplierPaymentRequest.objects.filter(payable_confirmation_no=payable.payable_confirmation_no):
                if financial_source_order(request) is None:
                    raise ReadScopeBlocked("FINANCE_SOURCE_OWNERSHIP_UNRESOLVED", "关联链归属尚未核明。", 409)
                for payment in SupplierPaymentStatusRecord.objects.filter(payment_request_no=request.payment_request_no):
                    if financial_source_order(payment) is None:
                        raise ReadScopeBlocked("FINANCE_SOURCE_OWNERSHIP_UNRESOLVED", "关联链归属尚未核明。", 409)
    return order, (reconciliations[0].tenant_id if reconciliations else None)
