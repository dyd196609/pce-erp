from .supplier_quotation_runtime import load_supplier_quotation_canary_runtime


def load_quote_comparison_canary_runtime(batch_id, scenario_code):
    quotation_runtime = load_supplier_quotation_canary_runtime(batch_id, scenario_code)
    quotation = quotation_runtime["objects"][0]
    sequence = int(quotation["quotationNo"].split("-")[-1])
    comparison_no = f"QC-CAN-{sequence:03d}"
    supplier_quote = {
        "supplierId": quotation["supplierId"],
        "supplierCode": quotation["supplierCode"],
        "supplierName": quotation["supplierName"],
        "quotationNo": quotation["quotationNo"],
        "quotePrice": quotation["quotePrice"],
        "currency": quotation["currency"],
        "priceRank": 1,
    }
    row = {
        "objectId": comparison_no,
        "objectType": "QuoteComparison",
        "quoteComparisonId": comparison_no,
        "sourceInquiryId": quotation["sourceInquiryNo"],
        "sourceInquiryNo": quotation["sourceInquiryNo"],
        "sourceQuotationIds": [quotation["objectId"]],
        "sourceQuotationNos": [quotation["quotationNo"]],
        "materialCode": quotation["materialCode"],
        "materialName": quotation["materialName"],
        "quantity": quotation["quantity"],
        "supplierQuotes": [supplier_quote],
        "lowestQuote": quotation["quotePrice"],
        "comparisonStatus": "comparison_completed" if scenario_code == "HAPPY_PATH" else "blocked",
        "comparisonStatusLabel": "比较完成" if scenario_code == "HAPPY_PATH" else "场景阻断",
        "readOnly": True,
        "dataMode": "canary_acceptance",
        "canaryBatchId": batch_id,
        "scenarioCode": scenario_code,
        "automaticRecommendationCreated": False,
        "priceApprovalCreated": False,
        "purchaseOrderCreated": False,
    }
    return {
        "version": "V1.14.2.8.4.23",
        "pageCode": "quote-comparison-workbench",
        "schema": "QuoteComparisonSchema",
        "factSource": "server",
        "apiUrl": "/api/pce/purchase-canary/quote-comparison-runtime",
        "recordCount": 1,
        "objects": [row],
        "records": [row],
        "dataMode": "canary_acceptance",
        "canaryBatchId": batch_id,
        "scenarioCode": scenario_code,
        "sourceMapping": {
            "quotationNo": quotation["quotationNo"],
            "quoteComparisonNo": comparison_no,
        },
        "businessWriteCount": 0,
        "priceApprovalCreated": False,
        "purchaseOrderCreated": False,
        "productionUserDataWritten": False,
    }
