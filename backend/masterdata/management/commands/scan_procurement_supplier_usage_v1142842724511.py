import json
from collections import defaultdict

from django.core.management.base import BaseCommand

from masterdata.master_data_statistics_runtime import SupplierMaterialPriceRuntime, SupplierPriceFactRuntime
from masterdata.material_supplier_relation_runtime import MaterialSupplierRelationRuntime
from masterdata.models import PriceApprovalResult, SupplierMaterialPrice
from masterdata.supplier_master_runtime import SupplierBusinessMapping
from procurement.models import (
    PriceApproval, PriceApprovalPreparation, PurchaseInquiry, PurchaseOrder,
    PurchaseRequestItem, QuoteComparisonFact, Supplier, SupplierQuotation,
)


def text(value):
    return str(value or "").strip()


class Command(BaseCommand):
    help = "只读输出采购业务供应商使用全集与V45.11反向补全候选"

    def handle(self, *args, **options):
        inventory = defaultdict(lambda: {"usageCount": 0, "sources": [], "names": set()})

        def record(module, object_id, code="", name="", evidence=None):
            code, name = text(code), text(name)
            if not code and not name:
                return
            key = code or f"NAME:{name}"
            row = inventory[key]
            row["rawSupplierCode"] = code
            if name:
                row["names"].add(name)
            row["usageCount"] += 1
            row["sources"].append({
                "sourceModule": module,
                "sourceObjectId": text(object_id),
                "evidence": evidence or {},
            })

        def record_identity(module, object_id, identity="", name="", evidence=None):
            identity = text(identity)
            if identity.isdigit():
                supplier = Supplier.objects.filter(pk=int(identity)).first()
                record(module, object_id, supplier.code if supplier else "",
                       name or (supplier.name if supplier else ""),
                       {**(evidence or {}), "sourceSupplierId": identity})
            else:
                record(module, object_id, identity, name, evidence)

        for item in PurchaseRequestItem.objects.select_related("purchase_request", "suggested_supplier"):
            supplier = item.suggested_supplier
            record("PurchaseRequest", item.purchase_request.request_no,
                   item.suggested_supplier_code or (supplier.code if supplier else ""),
                   item.suggested_supplier_name or (supplier.name if supplier else ""),
                   {"lineNo": item.line_no, "materialCode": item.material_code})
        for inquiry in PurchaseInquiry.objects.all():
            record("PurchaseInquiry", inquiry.inquiry_no, inquiry.supplier)
            payload = inquiry.quotation if isinstance(inquiry.quotation, dict) else {}
            for candidate in payload.get("supplierCandidates", payload.get("suppliers", [])) or []:
                if isinstance(candidate, dict):
                    record("PurchaseInquiryCandidate", inquiry.inquiry_no,
                           candidate.get("supplierCode") or candidate.get("supplierId"),
                           candidate.get("supplierName"), candidate)
        for quotation in SupplierQuotation.objects.all():
            record_identity("SupplierQuotation", quotation.quotation_no, quotation.supplier_id,
                            quotation.supplier_name, {"status": quotation.quotation_status})
            for line in quotation.items or []:
                if isinstance(line, dict):
                    record_identity("SupplierQuotationItem", f"{quotation.quotation_no}#L{line.get('lineNo', '')}",
                                    line.get("supplierCode") or quotation.supplier_id,
                                    line.get("supplierName") or quotation.supplier_name,
                                    {"materialCode": line.get("materialCode"), "unitPrice": line.get("unitPrice")})
        for fact in QuoteComparisonFact.objects.all():
            for evidence in fact.supplier_quote_evidence or []:
                if isinstance(evidence, dict):
                    record("QuoteComparisonFact", fact.comparison_no,
                           evidence.get("supplierCode") or evidence.get("supplierId"),
                           evidence.get("supplierName"), evidence)
        for preparation in PriceApprovalPreparation.objects.all():
            for candidate in preparation.supplier_candidates or []:
                if isinstance(candidate, dict):
                    record("PriceApprovalPreparationCandidate", preparation.approval_prepare_no,
                           candidate.get("supplierCode") or candidate.get("supplierId"),
                           candidate.get("supplierName"), candidate)
            selected = preparation.selected_supplier if isinstance(preparation.selected_supplier, dict) else {}
            record("PriceApprovalPreparationSelection", preparation.approval_prepare_no,
                   selected.get("supplierCode") or selected.get("supplierId"), selected.get("supplierName"),
                   {"status": preparation.status, "reviewResult": preparation.review_result,
                    "decisionVersion": preparation.decision_version})
        for approval in PriceApproval.objects.all():
            record("PriceApproval", approval.approval_no, approval.supplier,
                   evidence={"status": approval.status, "price": str(approval.price)})
        for result in PriceApprovalResult.objects.select_related("supplier", "preparation"):
            record("PriceApprovalResult", result.result_no, result.supplier.code,
                   result.supplier.name, {"preparation": result.preparation_identity})
        for price in SupplierMaterialPrice.objects.select_related("supplier", "material"):
            record("SupplierMaterialPrice", price.price_no, price.supplier.code, price.supplier.name,
                   {"materialCode": price.material.code, "unitPrice": str(price.approved_price)})
        for order in PurchaseOrder.objects.select_related("supplier"):
            record("PurchaseOrder", order.po_no or order.pk, order.supplier.code, order.supplier.name)
        for relation in MaterialSupplierRelationRuntime.list_runtime_models():
            record("MaterialSupplierRelation", relation.relationCode, relation.supplierCode,
                   relation.supplierName, {"materialCode": relation.materialCode,
                                           "sourceReference": relation.sourceReference})
        for fact in SupplierPriceFactRuntime.list_runtime_models():
            record("SupplierPriceFact", fact.priceFactId, fact.supplierCode, fact.supplierName,
                   {"materialCode": fact.materialCode, "sourceType": fact.sourceType,
                    "sourceReference": fact.sourceReference})

        master_by_code = {row.code: row for row in Supplier.objects.all()}
        output = []
        for key, value in sorted(inventory.items()):
            names = sorted(value.pop("names"))
            name = names[0] if len(names) == 1 else " / ".join(names)
            code = value["rawSupplierCode"]
            master = SupplierBusinessMapping._resolve(supplier_code=code, supplier_name=name)
            code_master = master_by_code.get(code)
            if master:
                status = "MATCHED"
            elif code_master:
                status = "WAITING_MANUAL_REVIEW"
            else:
                status = "MASTER_DATA_MISSING"
            output.append({
                **value,
                "rawSupplierName": name,
                "supplierMasterMatch": ({"id": master.pk, "code": master.code, "name": master.name}
                                        if master else None),
                "mappingStatus": status,
            })

        focus = [row for row in output if row["rawSupplierName"] in {
            "联创包装材料", "精工铝材供应商", "华信电子材料"
        }]
        report = {
            "version": "V1.14.2.8.4.27.2.45.11",
            "supplierMasterCount": Supplier.objects.count(),
            "supplierUsageIdentityCount": len(output),
            "usageCount": sum(row["usageCount"] for row in output),
            "inventory": output,
            "focusSuppliers": focus,
            "priceArchiveMappingBlocked": sum(
                row.get("archiveStatus") == "MAPPING_PENDING"
                for row in SupplierMaterialPriceRuntime.price_source_consistency_report()["priceArchiveReconciliation"]
            ),
            "stringGuessMappingCount": 0,
        }
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
