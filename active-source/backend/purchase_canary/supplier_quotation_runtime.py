from .purchase_inquiry_runtime import load_purchase_inquiry_canary_runtime


def load_supplier_quotation_canary_runtime(batch_id, scenario_code):
    inquiry_runtime = load_purchase_inquiry_canary_runtime(batch_id, scenario_code)
    inquiry = inquiry_runtime["objects"][0]
    sequence = int(inquiry["inquiryNo"].split("-")[-1])
    supplier = inquiry["supplierCandidates"][0]
    line = inquiry["lines"][0]
    received = scenario_code == "HAPPY_PATH"
    quotation_no = f"SQ-CAN-{sequence:03d}"
    row = {
        "rowId": f"canary:{quotation_no}:{line['materialCode']}",
        "objectId": quotation_no,
        "objectType": "SupplierQuotation",
        "quotationNo": quotation_no,
        "sourceInquiryId": inquiry["objectId"],
        "sourceInquiryNo": inquiry["inquiryNo"],
        "supplierId": supplier["supplierCode"],
        "supplierCode": supplier["supplierCode"],
        "supplierName": supplier["supplierName"],
        "items": [{**line, "unitPrice": 100 + sequence}],
        "materialCode": line["materialCode"],
        "materialName": line["materialName"],
        "quantity": line["quantity"],
        "unit": line["unit"],
        "quotePrice": 100 + sequence,
        "price": (100 + sequence) * line["quantity"],
        "currency": "CNY",
        "quotationStatus": "received" if received else "blocked",
        "quotationStatusLabel": "已接收" if received else "场景阻断",
        "receivedAt": "2026-08-07T10:00:00+08:00" if received else None,
        "remark": "金丝雀只读报价事实",
        "quoted": True,
        "readOnly": True,
        "dataMode": "canary_acceptance",
        "canaryBatchId": batch_id,
        "scenarioCode": scenario_code,
    }
    return {
        "version": "V1.14.2.8.4.22",
        "pageCode": "supplier-quotation",
        "schema": "SupplierQuotationSchema",
        "factSource": "server",
        "apiUrl": "/api/pce/purchase-canary/supplier-quotation-runtime",
        "recordCount": 1,
        "objects": [row],
        "sourceInquiryRows": [row],
        "sourceInquiryRowCount": 1,
        "dataMode": "canary_acceptance",
        "canaryBatchId": batch_id,
        "scenarioCode": scenario_code,
        "sourceMapping": {"inquiryNo": inquiry["inquiryNo"], "quotationNo": quotation_no},
        "businessWriteCount": 0,
        "priceApprovalCreated": False,
        "purchaseOrderCreated": False,
        "productionUserDataWritten": False,
    }
