import hashlib
import json

BATCH_ID = "PURCHASE-FLOW-DEMO-V1"
TENANT_ID = "tenant-canary-demo"
PURPOSE = "persistent_demonstration"

MODULES = (
    ("purchase-request", "采购申请", "/procurement/purchase-requests", "PRQ"),
    ("purchase-inquiry", "采购询价", "/procurement/inquiries", "INQ"),
    ("purchase-price-approval", "采购定价审批", "/procurement/price-approvals", "PRA"),
    ("purchase-order", "采购订单", "/purchase/orders", "PO"),
    ("purchase-arrival-prepare", "采购到货预备", "/wms/purchase-arrivals", "ARR"),
    ("purchase-receive-prepare", "采购收货预备", "/wms/purchase-receives", "RCV"),
    ("incoming-inspection", "来料检验", "/quality/incoming-inspections", "IQC"),
    ("payable-prepare", "采购应付预备", "/finance/payable-prepares", "PYP"),
    ("payable-check", "采购应付核对", "/finance/payable-checks", "PYC"),
    ("supplier-settlement", "供应商结算", "/scm/supplier-settlements", "SET"),
    ("purchase-reconciliation", "采购对账", "/scm/purchase-reconciliations", "PRC"),
    ("invoice-prepare", "采购发票准备", "/finance/purchase-invoice-prepares", "PIP"),
    ("account-payable-draft", "采购应付账款草稿", "/finance/ap-drafts", "APD"),
)

SCENARIOS = (
    ("HAPPY_PATH", "完整正常链路", "ap_draft_ready", ""),
    ("AMOUNT_DIFFERENCE", "金额差异", "blocked_at_reconciliation", "采购对账存在金额差异"),
    ("QUANTITY_DIFFERENCE", "数量差异", "blocked_at_reconciliation", "采购对账存在数量差异"),
    ("SOURCE_MISSING", "权威来源缺失", "blocked_at_reconciliation", "采购对账权威来源缺失"),
    ("INVOICE_VALIDATION_FAILED", "发票要素校验失败", "blocked_at_invoice_prepare", "发票要素校验失败"),
    ("DUPLICATE_INVOICE", "重复发票", "blocked_at_invoice_prepare", "发票号码重复"),
    ("SOURCE_STALE", "来源版本过期", "blocked_at_invoice_prepare", "来源版本已变化"),
    ("EXISTING_TARGET", "目标对象已存在", "existing_target", "目标对象已存在，不允许重复生成"),
)


def stable_hash(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def scenario_rows(code):
    short = "".join(part[0] for part in code.split("_"))
    rows = []
    stop_index = {
        "AMOUNT_DIFFERENCE": 10,
        "QUANTITY_DIFFERENCE": 10,
        "SOURCE_MISSING": 10,
        "INVOICE_VALIDATION_FAILED": 11,
        "DUPLICATE_INVOICE": 11,
        "SOURCE_STALE": 11,
    }.get(code, 12)
    for index, (module_code, module_name, route_path, prefix) in enumerate(MODULES):
        exists = index <= stop_index
        object_no = f"{prefix}-DEMO-{short}-001" if exists else ""
        status = "completed"
        if module_code == "purchase-reconciliation":
            status = {
                "AMOUNT_DIFFERENCE": "difference_found",
                "QUANTITY_DIFFERENCE": "difference_found",
                "SOURCE_MISSING": "source_missing",
            }.get(code, "matched")
        elif module_code == "invoice-prepare":
            status = {
                "INVOICE_VALIDATION_FAILED": "validation_failed",
                "DUPLICATE_INVOICE": "validation_failed",
                "SOURCE_STALE": "source_stale",
            }.get(code, "validated")
        elif module_code == "account-payable-draft":
            status = "draft" if exists else "not_created"
        next_allowed = exists and index < stop_index
        if code == "EXISTING_TARGET" and module_code == "account-payable-draft":
            status, next_allowed = "draft_existing_target", False
        rows.append({
            "sequence": index + 1,
            "module_code": module_code,
            "module_name": module_name,
            "route_path": route_path,
            "object_no": object_no or f"{prefix}-NOT-CREATED",
            "object_status": status if exists else "not_created",
            "next_step_allowed": next_allowed,
        })
    return rows
