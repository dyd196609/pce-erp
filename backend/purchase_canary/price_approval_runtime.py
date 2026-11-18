from .quote_comparison_runtime import load_quote_comparison_canary_runtime


def load_price_approval_canary_runtime(batch_id, scenario_code):
    comparison_runtime = load_quote_comparison_canary_runtime(batch_id, scenario_code)
    comparison = comparison_runtime["objects"][0]
    sequence = int(comparison["quoteComparisonId"].split("-")[-1])
    preparation_no = f"PA-CAN-{sequence:03d}"
    evidence = [{
        "supplierId": item.get("supplierId"),
        "supplierCode": item.get("supplierCode"),
        "supplierName": item.get("supplierName"),
        "quotationNo": item.get("quotationNo"),
        "quotationAmount": item.get("quotePrice"),
        "quotationStatus": "quotation_received",
        "quotationStatusCode": "quotation_received",
        "quotationStatusLabel": "quotation_received（报价已接收）",
        "receivedAt": "2026-08-07T10:00:00+08:00",
        "currency": item.get("currency", "CNY"),
    } for item in comparison["supplierQuotes"]]
    candidates = [{
        "supplierId": item.get("supplierId"),
        "supplierCode": item.get("supplierCode"),
        "supplierName": item.get("supplierName"),
        "quotationNo": item.get("quotationNo"),
        "quotationAmount": item.get("quotationAmount"),
        "currency": item.get("currency", "CNY"),
    } for item in evidence]
    row = {
        "id": preparation_no,
        "objectType": "PriceApprovalPreparation",
        "approvalPrepareNo": preparation_no,
        "sourceComparisonNo": comparison["quoteComparisonId"],
        "sourceComparisonFactId": f"QCF-{comparison['quoteComparisonId']}",
        "sourceInquiryNo": comparison["sourceInquiryNo"],
        "sourceQuotationEvidence": evidence,
        "supplierCandidates": candidates,
        "materialLines": [{
            "materialCode": comparison["materialCode"],
            "materialName": comparison["materialName"],
            "quantity": comparison["quantity"],
        }],
        "comparisonBasis": {
            "comparisonStatus": comparison["comparisonStatus"],
            "comparisonStatusLabel": comparison["comparisonStatusLabel"],
            "lowestQuote": comparison["lowestQuote"],
        },
        "historicalPriceReference": [],
        "selectedSupplier": {},
        "reviewOpinion": "",
        "exceptionNote": "",
        "approvalOpinion": "",
        "reviewResult": "",
        "reviewResultLabel": "待确认",
        "status": "draft",
        "statusCode": "draft",
        "statusLabel": "草稿",
        "decisionVersion": 0,
        "reviewer": "",
        "reviewedAt": None,
        "createdAt": "2026-08-07T10:00:00+08:00",
        "dataMode": "canary_acceptance",
        "factSource": "QuoteComparisonFact",
        "factOrigin": "canary_fact",
        "sourceConfidence": "acceptance",
        "canaryBatchId": batch_id,
        "scenarioCode": scenario_code,
        "automaticLowestQuoteSelected": False,
        "supplierRecommendationCreated": False,
        "purchaseOrderCreated": False,
    }
    return {
        "version": "V1.14.2.8.4.24",
        "pageCode": "price-approval",
        "schema": "PriceApprovalPreparationSchema",
        "factSource": "QuoteComparisonFact",
        "apiUrl": "/api/pce/purchase-canary/price-approval-runtime",
        "recordCount": 1,
        "objects": [row],
        "records": [row],
        "dataMode": "canary_acceptance",
        "canaryBatchId": batch_id,
        "scenarioCode": scenario_code,
        "sourceMapping": {
            "quoteComparisonNo": comparison["quoteComparisonId"],
            "priceApprovalPreparationNo": preparation_no,
        },
        "businessWriteCount": 0,
        "supplierRecommendationCreated": False,
        "purchaseOrderCreated": False,
        "productionUserDataWritten": False,
    }
