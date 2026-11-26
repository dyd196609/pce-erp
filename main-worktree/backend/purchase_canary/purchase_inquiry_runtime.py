import sqlite3

from .persistent_read_model import persistent_canary_database_for_batch


INQUIRY_SCENARIO_SEQUENCE = {
    "HAPPY_PATH": 1,
    "PRICE_EXCEPTION": 2,
    "QUALITY_FAIL": 3,
    "QUANTITY_DIFFERENCE": 4,
    "SOURCE_MISSING": 5,
    "INVOICE_VALIDATION_FAILED": 6,
    "DUPLICATE_INVOICE": 7,
    "SOURCE_STALE": 8,
}

SCENARIO_LABELS = {
    "HAPPY_PATH": "正常采购链路",
    "PRICE_EXCEPTION": "价格异常",
    "QUALITY_FAIL": "质量不合格",
    "QUANTITY_DIFFERENCE": "数量差异",
    "SOURCE_MISSING": "来源缺失",
    "INVOICE_VALIDATION_FAILED": "发票校验失败",
    "DUPLICATE_INVOICE": "重复发票",
    "SOURCE_STALE": "来源过期",
}


def _candidate(sequence, suffix):
    return {
        "supplierCode": f"SUP-CAN-{sequence:03d}-{suffix}",
        "supplierName": f"金丝雀供应商{sequence:02d}-{suffix}",
        "qualificationStatus": "qualified",
        "readOnly": True,
    }


def load_purchase_inquiry_canary_runtime(batch_id, scenario_code):
    if batch_id != "SCM-CANARY-FLOW-V1":
        raise LookupError(f"Unsupported purchase inquiry canary batch: {batch_id}")
    sequence = INQUIRY_SCENARIO_SEQUENCE.get(scenario_code)
    if sequence is None:
        raise LookupError(f"Unsupported purchase inquiry canary scenario: {scenario_code}")

    database_path = persistent_canary_database_for_batch(batch_id)
    connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        batch = connection.execute(
            "SELECT * FROM pce_purchase_canary_batch WHERE batch_id = ?", (batch_id,),
        ).fetchone()
        if batch is None:
            raise LookupError(f"Purchase inquiry canary batch not found: {batch_id}")
        request_no = f"PRQ-CAN-{sequence:03d}"
        inquiry_no = f"PI-CAN-{sequence:03d}"
        source = connection.execute(
            "SELECT o.*, s.code AS stored_scenario_code FROM pce_purchase_canary_module_object o "
            "JOIN pce_purchase_canary_scenario s ON s.id = o.scenario_id "
            "WHERE s.batch_id = ? AND o.module_code = 'purchase-request' AND o.object_no = ?",
            (batch["id"], request_no),
        ).fetchone()
        inquiry = connection.execute(
            "SELECT o.* FROM pce_purchase_canary_module_object o "
            "WHERE o.scenario_id = ? AND o.module_code = 'purchase-inquiry' AND o.object_no = ?",
            (source["scenario_id"], inquiry_no),
        ).fetchone() if source else None
        if source is None or inquiry is None:
            raise LookupError(f"Purchase inquiry canary lineage is incomplete: {request_no} -> {inquiry_no}")

        candidates = [_candidate(sequence, "A"), _candidate(sequence, "B")]
        status_code = inquiry["object_status"]
        source_allowed = bool(source["next_step_allowed"])
        inquiry_allowed = bool(inquiry["next_step_allowed"])
        row = {
            "id": f"canary:{batch_id}:{scenario_code}:{inquiry_no}",
            "objectId": inquiry_no,
            "objectType": "PurchaseInquiry",
            "objectNo": inquiry_no,
            "businessNo": inquiry_no,
            "inquiryNo": inquiry_no,
            "inquiryTitle": f"{SCENARIO_LABELS[scenario_code]}询价",
            "inquiryDate": "2026-08-07",
            "sourceRequestNo": request_no,
            "sourceObjectNo": request_no,
            "sourceObject": {"objectType": "PurchaseRequest", "objectNo": request_no},
            "buyerName": "金丝雀验收采购员",
            "supplierCount": len(candidates),
            "lineCount": 1,
            "currency": "CNY",
            "statusCode": status_code,
            "statusLabel": "已完成" if status_code == "completed" else "已阻断",
            "runtimeState": "quote_received" if inquiry_allowed else "inquiry_blocked",
            "supplierSendStatus": "sent" if source_allowed else "blocked",
            "supplierSendStatusLabel": "已发送" if source_allowed else "已阻断",
            "quoteReceiveStatus": "received" if inquiry_allowed else "blocked",
            "quoteReceiveStatusLabel": "已接收" if inquiry_allowed else "未接收",
            "lines": [{
                "lineNo": 1,
                "materialCode": f"MAT-CAN-{sequence:03d}",
                "materialName": f"金丝雀验收物料{sequence:02d}",
                "quantity": sequence * 10,
                "unit": "件",
                "requiredDate": "2026-09-30",
                "supplierCandidates": candidates,
            }],
            "suppliers": candidates,
            "supplierCandidates": candidates,
            "sourceEvidence": {
                "sourceType": "PurchaseRequestCanaryLineage",
                "sourceRequestNo": request_no,
                "sourceEvidenceHash": source["evidence_hash"],
                "inquiryEvidenceHash": inquiry["evidence_hash"],
                "storedScenarioCode": source["stored_scenario_code"],
            },
            "blockReason": inquiry["block_reason"],
            "dataMode": "canary_acceptance",
            "canaryBatchId": batch_id,
            "scenarioCode": scenario_code,
            "readOnly": True,
        }
        return {
            "version": "V1.14.2.8.4.21",
            "pageCode": "purchase-inquiry",
            "schema": "PurchaseInquirySchema",
            "factSource": "server",
            "apiUrl": "/api/pce/purchase-canary/purchase-inquiry-runtime",
            "recordCount": 1,
            "status": "available",
            "objects": [row],
            "dataMode": "canary_acceptance",
            "canaryBatchId": batch_id,
            "scenarioCode": scenario_code,
            "sourceMapping": {"requestNo": request_no, "inquiryNo": inquiry_no},
            "businessWriteCount": 0,
            "purchaseOrderCreated": False,
            "productionUserDataWritten": False,
        }
    finally:
        connection.close()
