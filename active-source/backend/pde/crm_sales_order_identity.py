"""Server-authoritative CRM review to SalesOrder business identity checks.

The check is intentionally read-only.  It is used before a new 0032 relation is
persisted and when an existing relation is projected back to a user.  Historical
relations are never rewritten by this module.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import re
import unicodedata


MATCH = "MATCH"
DIFFERENT = "DIFFERENT"
NOT_AVAILABLE = "NOT_AVAILABLE"


def normalize_business_text(value):
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return re.sub(r"[\s\-_—/\\·,，。:：;；()（）]+", "", text)


def source_business_identity(source, review=None):
    payload = source.source_payload if isinstance(source.source_payload, dict) else {}
    reference = payload.get("businessOrderReference")
    reference = reference if isinstance(reference, dict) else {}
    return {
        "companyId": source.company_id,
        "customerName": str(reference.get("customerName") or "").strip(),
        "projectReference": str(
            reference.get("projectName") or reference.get("projectReference") or ""
        ).strip(),
        "contractReference": str(
            reference.get("contractNo") or reference.get("contractReference") or ""
        ).strip(),
        "sourceOrderNo": str(
            reference.get("sourceOrderNo")
            or (review.source_order_no if review else "")
            or source.source_no
        ).strip(),
        "sourceRecordId": source.pk,
        "sourceVersion": source.source_version,
        "sourceContentHash": source.content_hash,
    }


def _comparison(field, expected, actual, *, required=True, normalized=True):
    expected_text = str(expected or "").strip()
    actual_text = str(actual or "").strip()
    if not expected_text or not actual_text:
        status = NOT_AVAILABLE
    elif (
        normalize_business_text(expected_text) == normalize_business_text(actual_text)
        if normalized else expected_text == actual_text
    ):
        status = MATCH
    else:
        status = DIFFERENT
    return {
        "field": field,
        "expected": expected,
        "actual": actual,
        "status": status,
        "required": required,
    }


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def formal_order_source_scope(source):
    import os

    if os.environ.get("PCE_CRM_REGISTERED_SCOPE_ENABLED") == "1":
        from sales.models import OrderSourceFormalScope

        registered = OrderSourceFormalScope.objects.filter(
            source=source, source_version=source.source_version, content_hash=source.content_hash,
        ).first()
        if registered is not None:
            return {"authority": "CRM_REGISTERED_SCOPE", "items": registered.items}

    payload = source.source_payload if isinstance(source.source_payload, dict) else {}
    return (
        payload.get("formalSalesOrderScope")
        or payload.get("salesOrderScope")
        or (payload.get("businessOrderReference") or {}).get("orderItemScope")
    )


def _scope_items_from_source(source):
    scope = formal_order_source_scope(source)
    if not isinstance(scope, dict) or not isinstance(scope.get("items"), list):
        return None, ""
    result = []
    for index, row in enumerate(scope["items"], 1):
        if not isinstance(row, dict):
            return None, str(scope.get("authority") or "")
        name = str(
            row.get("customerProductName")
            or row.get("productName")
            or row.get("materialName")
            or row.get("component")
            or ""
        ).strip()
        unit = str(row.get("unit") or row.get("uom") or row.get("uomCode") or "").strip()
        quantity = _decimal(row.get("quantity"))
        if not name or not unit or quantity is None or quantity <= 0:
            return None, str(scope.get("authority") or "")
        result.append({
            "key": str(row.get("key") or row.get("sourceKey") or index),
            "name": name,
            "unit": unit,
            "quantity": quantity,
        })
    return result, str(scope.get("authority") or "SERVER_SOURCE_SCOPE")


def _scope_items_from_order(order_items):
    result = []
    for item in order_items or []:
        material = getattr(item, "material", None)
        uom = getattr(item, "uom", None)
        name = str(
            getattr(material, "name", "")
            or getattr(item, "customer_product_name", "")
            or ""
        ).strip()
        unit = str(
            getattr(uom, "code", "")
            or getattr(uom, "name", "")
            or getattr(material, "unit", "")
            or ""
        ).strip()
        quantity = _decimal(getattr(item, "quantity", None))
        if not name or not unit or quantity is None or quantity <= 0:
            return None
        result.append({"name": name, "unit": unit, "quantity": quantity})
    return result


def _scope_counter(items):
    counter = Counter()
    for row in items:
        key = (normalize_business_text(row["name"]), normalize_business_text(row["unit"]))
        counter[key] += row["quantity"]
    return counter


def assess_crm_sales_order_identity(
        *, source, review, company_id, customer_name, project_reference,
        contract_reference, external_source_no, scope_mode, order_items,
        selected_source_scope_keys=None, relation_source_hash=None):
    """Return a field-level, fail-closed identity assessment.

    Source item scope must be an explicit server-side formal scope.  Engineering
    preview rows are deliberately not promoted into sales order lines.
    """

    expected = source_business_identity(source, review)
    comparisons = [
        _comparison("company", expected["companyId"], company_id, normalized=False),
        _comparison("sourceRecord", expected["sourceRecordId"], review.source_record_id, normalized=False),
        _comparison("sourceVersion", expected["sourceVersion"], review.source_version, normalized=False),
        _comparison("sourceContentHash", expected["sourceContentHash"], review.source_content_hash, normalized=False),
        _comparison("customer", expected["customerName"], customer_name),
        _comparison("project", expected["projectReference"], project_reference),
        _comparison(
            "contract", expected["contractReference"], contract_reference,
            required=bool(expected["contractReference"]),
        ),
        _comparison("sourceOrderNo", expected["sourceOrderNo"], external_source_no, normalized=False),
    ]
    if relation_source_hash is not None:
        comparisons.append(_comparison(
            "relationSourceHash", expected["sourceContentHash"], relation_source_hash,
            normalized=False,
        ))

    normalized_mode = str(scope_mode or "").strip().upper()
    comparisons.append({
        "field": "reviewScopeMode",
        "expected": "WHOLE_ORDER or SELECTED_ITEMS",
        "actual": normalized_mode,
        "status": MATCH if normalized_mode in {"WHOLE_ORDER", "SELECTED_ITEMS"} else DIFFERENT,
        "required": True,
    })

    source_scope, scope_authority = _scope_items_from_source(source)
    actual_scope = _scope_items_from_order(order_items)
    if source_scope is None or actual_scope is None:
        scope_status = NOT_AVAILABLE
        expected_scope = "明确的服务端正式订单行范围"
        actual_scope_value = "来源未形成正式订单行范围" if source_scope is None else "订单行身份不完整"
    else:
        selected_keys = {
            str(value).strip() for value in (selected_source_scope_keys or [])
            if str(value).strip()
        }
        if normalized_mode == "SELECTED_ITEMS":
            if not selected_keys:
                source_scope = None
            else:
                source_scope = [row for row in source_scope if row["key"] in selected_keys]
                if len(source_scope) != len(selected_keys):
                    source_scope = None
        if source_scope is None:
            scope_status = NOT_AVAILABLE
            expected_scope = "SELECTED_ITEMS必须提供唯一的来源范围键"
            actual_scope_value = sorted(selected_keys)
        else:
            expected_counter = _scope_counter(source_scope)
            actual_counter = _scope_counter(actual_scope)
            scope_status = MATCH if expected_counter == actual_counter else DIFFERENT
            expected_scope = [
                {"name": name, "unit": unit, "quantity": str(quantity)}
                for (name, unit), quantity in sorted(expected_counter.items())
            ]
            actual_scope_value = [
                {"name": name, "unit": unit, "quantity": str(quantity)}
                for (name, unit), quantity in sorted(actual_counter.items())
            ]
    comparisons.append({
        "field": "salesOrderItemScope",
        "expected": expected_scope,
        "actual": actual_scope_value,
        "status": scope_status,
        "required": True,
        "authority": scope_authority,
    })

    required = [row for row in comparisons if row["required"]]
    if any(row["status"] == DIFFERENT for row in required):
        status_code = "CONFLICT"
        status_label = "来源业务身份冲突"
    elif any(row["status"] == NOT_AVAILABLE for row in required):
        status_code = "NOT_PROVEN"
        status_label = "来源业务身份尚未完整证明"
    else:
        status_code = "MATCH"
        status_label = "来源业务身份一致"
    return {
        "statusCode": status_code,
        "statusLabel": status_label,
        "allowed": status_code == "MATCH",
        "comparisons": comparisons,
        "sourceIdentity": expected,
    }


def assess_relation_identity(relation):
    review = relation.review
    order = relation.sales_order
    scope_rows = list(relation.scope_items.select_related(
        "sales_order_item__material", "sales_order_item__uom",
    ).order_by("line_no_snapshot", "pk"))
    items = [row.sales_order_item for row in scope_rows]
    return assess_crm_sales_order_identity(
        source=review.source_record,
        review=review,
        company_id=order.company_id,
        customer_name=order.customer.name,
        project_reference=order.project_reference,
        contract_reference=order.contract_reference,
        external_source_no=order.external_source_no,
        scope_mode=relation.scope_mode,
        order_items=items,
        selected_source_scope_keys=[
            row.external_line_no_snapshot for row in scope_rows
            if row.external_line_no_snapshot
        ],
        relation_source_hash=relation.source_content_hash_snapshot,
    )

