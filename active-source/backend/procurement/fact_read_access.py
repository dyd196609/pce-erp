"""Read fences for existing SCM facts; no new grants or ownership writes."""
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import APIException
from system.authorization import AuthorizationService
from system.models import User
from pfm.models import Employee
from .models import (PurchaseRequest, PurchaseInquiry, SupplierQuotation,
                     PriceApproval, PurchaseOrder, PurchaseReceipt,
                     PurchaseInspection, WarehouseInbound, QuoteComparisonFact,
                     PriceApprovalPreparation)
from .scm_read_permission_catalog import (
    READ_ROLES, INQUIRY_SCOPE, QUOTATION_SCOPE, PREPARATION_SCOPE)


class ReadScopeBlocked(APIException):
    status_code = 403
    default_code = "READ_SCOPE_DENIED"

    def __init__(self, code, message, status=403):
        self.status_code = status
        self.default_code = code
        super().__init__(message, code=code)


# These are existing read permissions. Missing contracts are deliberately not
# inferred from write actions or from another document's read qualification.
PAGE_READ_PERMISSIONS = {
    "purchase-inquiry": INQUIRY_SCOPE,
    "supplier-quotation": QUOTATION_SCOPE,
    "supplier-quote-workbench": QUOTATION_SCOPE,
    "price-approval": PREPARATION_SCOPE,
    "quote-comparison": QUOTATION_SCOPE,
    "purchase-request": ("procurement.purchase_request.view",),
    "purchase-order": ("procurement.purchase_order.view",),
    "purchase-receive-preview": ("procurement.receipt.read",),
    "incoming-inspection": ("quality.purchase_inspection.read",),
    "inventory-balances": ("warehouse.inventory.read", "warehouse.inventory_transaction.read"),
}


def permission_role_evidence(user, code, organization_id):
    """Bind an approved read permission to the scope of its actual granting role."""
    return [row for row in AuthorizationService.authority_evidence(user, organization_id)
            if (code not in READ_ROLES or row.role_code in READ_ROLES[code])
            and code in AuthorizationService.permission_codes_for_user(user, {row.role_code})]


def native_comparison_context(value):
    # Runtime/canary IDs and legacy projections are not typed native identities.
    if value.source_type != "server_fact" or not value.source_quotation_ids:
        return None
    identifiers = value.source_quotation_ids
    if not isinstance(identifiers, list):
        return None
    if any(isinstance(pk, bool) or not isinstance(pk, (int, str))
           or not str(pk).isdigit() for pk in identifiers):
        return None
    ids = [int(pk) for pk in identifiers]
    if len(ids) != len(set(ids)):
        return None
    inquiry = PurchaseInquiry.objects.filter(inquiry_no=value.source_inquiry_no).first()
    if inquiry is None:
        return None
    quotations = list(SupplierQuotation.objects.filter(pk__in=ids))
    if len(quotations) != len(ids) or any(row.source_inquiry_id != inquiry.pk for row in quotations):
        return None
    evidence = value.supplier_quote_evidence
    if not isinstance(evidence, list) or any(not isinstance(row, dict) for row in evidence):
        return None
    if len(evidence) != len(quotations):
        return None
    expected = {(row.quotation_no, str(row.supplier_id)) for row in quotations}
    actual = {(str(row.get("quotationNo") or ""), str(row.get("supplierId") or "")) for row in evidence}
    if actual != expected:
        return None
    from .comparison_registration_service import verify_registered_fact, ComparisonRegistrationError
    try:
        snapshot, _, _ = verify_registered_fact(value)
    except ComparisonRegistrationError:
        return None
    if (snapshot["inquiry"]["id"] != inquiry.pk or
            snapshot["request"]["id"] != inquiry.source_purchase_request_id):
        return None
    return object_read_context(inquiry.source_purchase_request)


def validate_read_identity(user):
    if not user or not user.is_authenticated or not user.is_active:
        raise ReadScopeBlocked("IDENTITY_INVALID", "当前读取身份无效。")
    if not User.objects.filter(pk=user.pk, username=user.username, company_id=user.company_id,
                               is_active=True, is_superuser=user.is_superuser).exists():
        raise ReadScopeBlocked("IDENTITY_CONTEXT_MISMATCH", "当前读取身份与权威账号上下文不一致。")


def read_qualification(user, permissions):
    validate_read_identity(user)
    if not permissions:
        raise ReadScopeBlocked("READ_QUALIFICATION_NOT_CONFIGURED", "该对象的正式读取资格尚未核定，暂不提供业务事实。")
    organizations = {str(user.company_id)} if user.is_superuser else {
        row.organization_id for row in AuthorizationService.authority_evidence(user)
    }
    for org in organizations:
        if all(AuthorizationService.decide(user=user, action_code=code,
                                          organization_id=org)["allowed"]
               and (user.is_superuser or code not in READ_ROLES
                    or permission_role_evidence(user, code, org)) for code in permissions):
            return
    raise ReadScopeBlocked("READ_PERMISSION_DENIED", "现有职责或授权范围不允许读取该类业务事实。")


def object_read_context(value):
    """Use typed native relations, never local IDs, names or number prefixes."""
    if value is None:
        return None
    try:
        if isinstance(value, PurchaseOrder):
            if not value.company_id:
                return None
            return {"organizationId": value.company_id,
                    "departmentId": value.purchase_department_id or value.department_id,
                    "ownerUserId": value.created_by}
        if isinstance(value, PurchaseRequest):
            departments = [d for d in (value.department_master, value.usage_department_master,
                                      value.purchase_department_master) if d is not None]
            companies = {d.company_id for d in departments}
            employee = Employee.objects.select_related("department_ref").filter(
                pk=value.requester_employee_id).first() if value.requester_employee_id else None
            if employee and employee.department_ref:
                companies.add(employee.department_ref.company_id)
            if len(companies) != 1:
                return None
            company = next(iter(companies))
            if employee and value.requester_employee_no and employee.employee_no != value.requester_employee_no:
                return None
            return {"organizationId": company,
                    "departmentId": value.purchase_department_master_id or value.department_master_id,
                    "ownerUserId": employee.user_id if employee else None}
        if isinstance(value, PurchaseInquiry):
            return object_read_context(value.source_purchase_request)
        if isinstance(value, (SupplierQuotation, PriceApproval)):
            return object_read_context(value.source_inquiry)
        if isinstance(value, QuoteComparisonFact):
            return native_comparison_context(value)
        if isinstance(value, PriceApprovalPreparation):
            if value.fact_origin != "production_fact" or value.source_comparison_id is None:
                return None
            return native_comparison_context(value.source_comparison)
        if isinstance(value, PurchaseReceipt):
            return object_read_context(value.source_purchase_order)
        if isinstance(value, PurchaseInspection):
            return object_read_context(value.source_receipt)
        if isinstance(value, WarehouseInbound):
            if value.source_inspection_id:
                return object_read_context(value.source_inspection)
            # A manufacturing inbound is not a purchase inbound. Its warehouse
            # is still a native company authority; no purchase relation invented.
            warehouse = value.warehouse
            employee = value.operator_employee
            return {"organizationId": warehouse.company_id,
                    "departmentId": employee.department_ref_id if employee else None,
                    "ownerUserId": employee.user_id if employee else None}
    except ObjectDoesNotExist:
        return None
    return None


def context_allowed(user, permissions, context):
    if not context or not context.get("organizationId"):
        return False
    # The original authorization service permits omitted SELF/DEPARTMENT facts.
    # A read of an actual row must supply them, or explicitly remain unmatched.
    facts = {**context,
             "departmentId": context.get("departmentId") or "__NOT_PROVIDED__",
             "ownerUserId": context.get("ownerUserId") or "__NOT_PROVIDED__"}
    if not user.is_superuser:
        for code in permissions:
            if code in READ_ROLES and not any(
                    AuthorizationService._scope_matches(row, user, facts, {})
                    for row in permission_role_evidence(user, code, context["organizationId"])):
                return False
    return all(AuthorizationService.decide(
        user=user, action_code=code, organization_id=context["organizationId"],
        business_object=facts)["allowed"] for code in permissions)


def scope_fact_missing(user, context, role_code=None):
    if not context or not context.get("organizationId"):
        return True
    if user.is_superuser:
        return False
    evidence = [e for e in AuthorizationService.authority_evidence(user, context["organizationId"])
                if role_code is None or e.role_code == role_code]
    return any((e.scope_code == "SELF" and not context.get("ownerUserId")) or
               (e.scope_code == "DEPARTMENT" and not context.get("departmentId")) for e in evidence)


def scoped_queryset(queryset, user, permissions):
    read_qualification(user, permissions)
    ids = []; unresolved = False
    for value in queryset:
        context = object_read_context(value)
        if context is None:
            unresolved = True
        elif context_allowed(user, permissions, context):
            ids.append(value.pk)
        elif scope_fact_missing(user, context):
            unresolved = True
    if not ids and unresolved:
        raise ReadScopeBlocked("SOURCE_OWNERSHIP_UNRESOLVED", "来源归属尚未核明，不能将待核记录显示为空结果。", 409)
    return queryset.filter(pk__in=ids)


def reference_visible(user, value):
    if value is None:
        return False
    context = object_read_context(value)
    permissions = ("procurement.purchase_request.view",) if isinstance(value, PurchaseRequest) else (
        "procurement.purchase_order.view",) if isinstance(value, PurchaseOrder) else None
    if isinstance(value, PurchaseInquiry): permissions = INQUIRY_SCOPE
    if isinstance(value, SupplierQuotation): permissions = QUOTATION_SCOPE
    if isinstance(value, QuoteComparisonFact): permissions = QUOTATION_SCOPE
    if isinstance(value, PriceApprovalPreparation): permissions = PREPARATION_SCOPE
    # Other typed child references inherit only the native root relation's scope;
    # they do not grant access to another endpoint or an execution action.
    if permissions is None:
        permissions = ("procurement.purchase_order.view",)
    return context_allowed(user, permissions, context)


READ_SCOPE_FACTS = {"contract": "EXISTING_NATIVE_READ_AUTHORITY",
                    "ownership": "TYPED_NATIVE_RELATIONS_ONLY",
                    "unprovenOwnership": "WITHHELD_NOT_ASSIGNED_TO_CALLER",
                    "countScope": "AUTHORIZED_PROVEN_RECORDS_ONLY",
                    "scopeParametersGrantAccess": False}
