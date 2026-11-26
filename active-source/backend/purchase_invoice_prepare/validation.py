import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from reconciliation.checking import build_invoice_prepare_eligibility

from .authority import LegalEntityInvoiceAuthorityProvider, SupplierInvoiceAuthorityProvider

VALIDATION_POLICY_VERSION = "pip-invoice-validation-v1"
CURRENCY_MINOR_UNITS = {"CNY": 2}
MONEY_ROUNDING_MODE = ROUND_HALF_UP
AMOUNT_TOLERANCE = Decimal("0.01")
TAX_TOLERANCE = Decimal("0.01")
INVOICE_TYPE_POLICIES = {
    "vat_special": {
        "invoiceCodeRequired": True,
        "numberPattern": re.compile(r"^[A-Z0-9-]{8,32}$"),
    },
    "vat_electronic": {
        "invoiceCodeRequired": False,
        "numberPattern": re.compile(r"^[A-Z0-9-]{8,32}$"),
    },
}

RULE_CODES = (
    "PIP_VALIDATE_SOURCE_RECONCILIATION_EXISTS",
    "PIP_VALIDATE_SOURCE_RECONCILIATION_MATCHED",
    "PIP_VALIDATE_SOURCE_VERSION_CURRENT",
    "PIP_VALIDATE_CHECK_VERSION_CURRENT",
    "PIP_VALIDATE_SUPPLIER_AUTHORITY_AVAILABLE",
    "PIP_VALIDATE_LEGAL_ENTITY_AUTHORITY_AVAILABLE",
    "PIP_VALIDATE_SELLER_MATCH",
    "PIP_VALIDATE_BUYER_MATCH",
    "PIP_VALIDATE_CURRENCY_MATCH",
    "PIP_VALIDATE_QUANTITY_MATCH",
    "PIP_VALIDATE_HEADER_ARITHMETIC",
    "PIP_VALIDATE_LINE_SUM",
    "PIP_VALIDATE_TAX_CALCULATION",
    "PIP_VALIDATE_RECONCILIATION_AMOUNT_MATCH",
    "PIP_VALIDATE_INVOICE_IDENTITY_VALID",
    "PIP_VALIDATE_INVOICE_IDENTITY_UNIQUE",
    "PIP_VALIDATE_INVOICE_DATE_VALID",
    "PIP_VALIDATE_NO_FATAL_ISSUE",
    "PIP_VALIDATE_AP_DRAFT_READINESS",
)


def canonical_payload_hash(payload):
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def decimal_value(value, default=None):
    if value in (None, ""):
        if default is not None:
            return default
        raise InvalidOperation
    return Decimal(str(value))


def money(value, currency="CNY"):
    precision = CURRENCY_MINOR_UNITS.get(currency, 2)
    quantum = Decimal(1).scaleb(-precision)
    return decimal_value(value).quantize(quantum, rounding=MONEY_ROUNDING_MODE)


def normalize_tax_id(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def normalize_invoice_token(value):
    return re.sub(r"[^A-Z0-9-]", "", str(value or "").upper())


def build_invoice_identity_key(prepare, snapshot):
    policy = INVOICE_TYPE_POLICIES.get(snapshot.invoice_type)
    invoice_number = normalize_invoice_token(snapshot.invoice_number)
    invoice_code = normalize_invoice_token(snapshot.invoice_code)
    seller_tax_id = normalize_tax_id(snapshot.seller_tax_id)
    if not policy or not invoice_number or not seller_tax_id:
        return ""
    if policy["invoiceCodeRequired"] and not invoice_code:
        return ""
    identity = {
        "tenantId": prepare.tenant_id,
        "legalEntityId": prepare.legal_entity_id,
        "sellerTaxId": seller_tax_id,
        "invoiceType": snapshot.invoice_type,
        "invoiceCode": invoice_code or "-",
        "invoiceNumber": invoice_number,
    }
    return canonical_payload_hash(identity)


def invoice_data_completeness(payload):
    required = {
        "PIP_DATA_INVOICE_TYPE_REQUIRED": payload.get("invoiceType"),
        "PIP_DATA_INVOICE_NUMBER_REQUIRED": payload.get("invoiceNumber"),
        "PIP_DATA_INVOICE_DATE_REQUIRED": payload.get("invoiceDate"),
        "PIP_DATA_SELLER_NAME_REQUIRED": payload.get("sellerName"),
        "PIP_DATA_SELLER_TAX_ID_REQUIRED": payload.get("sellerTaxId"),
        "PIP_DATA_BUYER_NAME_REQUIRED": payload.get("buyerName"),
        "PIP_DATA_BUYER_TAX_ID_REQUIRED": payload.get("buyerTaxId"),
        "PIP_DATA_CURRENCY_REQUIRED": payload.get("currency"),
        "PIP_DATA_LINES_REQUIRED": payload.get("lines"),
    }
    missing = [code for code, value in required.items() if not value]
    policy = INVOICE_TYPE_POLICIES.get(payload.get("invoiceType"))
    if policy and policy["invoiceCodeRequired"] and not payload.get("invoiceCode"):
        missing.append("PIP_DATA_INVOICE_CODE_REQUIRED")
    try:
        amounts_valid = all(
            decimal_value(payload.get(field)) >= 0
            for field in ("amountExcludingTax", "taxAmount", "amountIncludingTax")
        )
    except (InvalidOperation, ValueError):
        amounts_valid = False
    if not amounts_valid:
        missing.append("PIP_DATA_HEADER_AMOUNTS_VALID")
    return {"complete": not missing, "missingCodes": missing}


def _result(code, passed, category, actual="", expected="", line_no=None, message=""):
    return {
        "code": code,
        "category": category,
        "status": "passed" if passed else "failed",
        "severity": "info" if passed else "error",
        "blocking": not passed,
        "actual": str(actual),
        "expected": str(expected),
        "message": message or ("passed" if passed else f"{code} failed"),
        "sourceField": category,
        "lineNo": line_no,
    }


def execute_invoice_validation(prepare, snapshot, identity_claim_exists=False):
    source = prepare.source_purchase_reconciliation
    supplier = SupplierInvoiceAuthorityProvider().read(prepare)
    legal = LegalEntityInvoiceAuthorityProvider().read(prepare)
    eligibility = build_invoice_prepare_eligibility(source)
    lines = list(snapshot.lines.order_by("line_no"))
    currency = snapshot.currency or prepare.currency
    header_ex = money(snapshot.amount_excluding_tax, currency)
    header_tax = money(snapshot.tax_amount, currency)
    header_inc = money(snapshot.amount_including_tax, currency)
    line_ex = sum((money(line.amount_excluding_tax, currency) for line in lines), Decimal("0.00"))
    line_tax = sum((money(line.tax_amount, currency) for line in lines), Decimal("0.00"))
    line_inc = sum((money(line.amount_including_tax, currency) for line in lines), Decimal("0.00"))
    line_quantity = sum((line.quantity for line in lines), Decimal("0.0000"))
    tax_mismatches = [
        line.line_no
        for line in lines
        if abs(money(line.amount_excluding_tax * line.tax_rate, currency) - money(line.tax_amount, currency))
        > TAX_TOLERANCE
    ]
    identity_key = build_invoice_identity_key(prepare, snapshot)
    policy = INVOICE_TYPE_POLICIES.get(snapshot.invoice_type)
    number_valid = bool(
        policy
        and policy["numberPattern"].fullmatch(normalize_invoice_token(snapshot.invoice_number))
        and (not policy["invoiceCodeRequired"] or normalize_invoice_token(snapshot.invoice_code))
    )
    invoice_date_valid = bool(snapshot.invoice_date and snapshot.invoice_date <= date.today())
    source_current = prepare.source_reconciliation_version == source.version
    check_current = prepare.source_check_version == eligibility["checkVersion"]
    results = [
        _result(RULE_CODES[0], bool(source), "source", bool(source), True),
        _result(RULE_CODES[1], source.status == "matched", "sourceStatus", source.status, "matched"),
        _result(RULE_CODES[2], source_current, "sourceVersion", source.version, prepare.source_reconciliation_version),
        _result(RULE_CODES[3], check_current, "checkVersion", eligibility["checkVersion"], prepare.source_check_version),
        _result(RULE_CODES[4], bool(supplier), "supplierAuthority", bool(supplier), True),
        _result(RULE_CODES[5], bool(legal), "legalEntityAuthority", bool(legal), True),
        _result(
            RULE_CODES[6],
            bool(supplier) and normalize_tax_id(snapshot.seller_tax_id) == normalize_tax_id(supplier.seller_tax_id),
            "sellerTaxId",
            snapshot.seller_tax_id,
            supplier.seller_tax_id if supplier else "authority_required",
        ),
        _result(
            RULE_CODES[7],
            bool(legal) and normalize_tax_id(snapshot.buyer_tax_id) == normalize_tax_id(legal.buyer_tax_id),
            "buyerTaxId",
            snapshot.buyer_tax_id,
            legal.buyer_tax_id if legal else "authority_required",
        ),
        _result(
            RULE_CODES[8],
            snapshot.currency == prepare.currency and bool(legal) and snapshot.currency == legal.currency,
            "currency",
            snapshot.currency,
            prepare.currency,
        ),
        _result(RULE_CODES[9], line_quantity == prepare.quantity, "quantity", line_quantity, prepare.quantity),
        _result(
            RULE_CODES[10],
            abs((header_ex + header_tax) - header_inc) <= AMOUNT_TOLERANCE,
            "headerAmount",
            header_ex + header_tax,
            header_inc,
        ),
        _result(
            RULE_CODES[11],
            all(
                (
                    abs(line_ex - header_ex) <= AMOUNT_TOLERANCE,
                    abs(line_tax - header_tax) <= TAX_TOLERANCE,
                    abs(line_inc - header_inc) <= AMOUNT_TOLERANCE,
                )
            ),
            "lineTotal",
            f"{line_ex}/{line_tax}/{line_inc}",
            f"{header_ex}/{header_tax}/{header_inc}",
        ),
        _result(RULE_CODES[12], not tax_mismatches, "taxCalculation", tax_mismatches, []),
        _result(
            RULE_CODES[13],
            abs(header_inc - money(prepare.settlement_amount, currency)) <= AMOUNT_TOLERANCE,
            "reconciliationAmount",
            header_inc,
            prepare.settlement_amount,
        ),
        _result(RULE_CODES[14], bool(identity_key and number_valid), "invoiceIdentity", identity_key, "valid"),
        _result(RULE_CODES[15], not identity_claim_exists, "duplicateInvoice", identity_claim_exists, False),
        _result(RULE_CODES[16], invoice_date_valid, "invoiceDate", snapshot.invoice_date, f"<= {date.today()}"),
    ]
    fatal_free = all(item["status"] == "passed" for item in results)
    results.append(_result(RULE_CODES[17], fatal_free, "fatalIssue", not fatal_free, False))
    results.append(
        _result(
            RULE_CODES[18],
            fatal_free and eligibility["eligible"],
            "accountsPayableDraftReadiness",
            eligibility["nextStepReadiness"],
            "ready_for_invoice_prepare",
        )
    )
    return {
        "policyVersion": VALIDATION_POLICY_VERSION,
        "identityKey": identity_key,
        "supplierAuthority": supplier,
        "legalEntityAuthority": legal,
        "sourceEligibility": eligibility,
        "results": results,
        "issues": [item for item in results if item["blocking"]],
        "passed": all(item["status"] == "passed" for item in results),
    }


def validation_result_code(issues):
    if not issues:
        return "validated"
    if len(issues) > 1:
        return "multiple_errors"
    mapping = {
        "PIP_VALIDATE_SELLER_MATCH": "seller_mismatch",
        "PIP_VALIDATE_BUYER_MATCH": "buyer_mismatch",
        "PIP_VALIDATE_CURRENCY_MATCH": "currency_mismatch",
        "PIP_VALIDATE_QUANTITY_MATCH": "quantity_mismatch",
        "PIP_VALIDATE_HEADER_ARITHMETIC": "header_amount_invalid",
        "PIP_VALIDATE_LINE_SUM": "line_total_mismatch",
        "PIP_VALIDATE_TAX_CALCULATION": "tax_calculation_mismatch",
        "PIP_VALIDATE_RECONCILIATION_AMOUNT_MATCH": "reconciliation_amount_mismatch",
        "PIP_VALIDATE_INVOICE_DATE_VALID": "invoice_date_invalid",
        "PIP_VALIDATE_INVOICE_IDENTITY_UNIQUE": "duplicate_invoice",
        "PIP_VALIDATE_SOURCE_VERSION_CURRENT": "source_stale",
        "PIP_VALIDATE_CHECK_VERSION_CURRENT": "source_stale",
    }
    return mapping.get(issues[0]["code"], "validation_integrity_failed")
