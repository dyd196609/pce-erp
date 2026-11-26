import json

from django.core.management.base import BaseCommand

from masterdata.master_data_statistics_runtime import SupplierMaterialPriceRuntime
from masterdata.models import SupplierMaterialPrice
from procurement.models import PriceApprovalPreparation, Supplier


class Command(BaseCommand):
    help = "只读输出V45.10核价逐对象动作矩阵和历史主数据映射证据"

    def handle(self, *args, **options):
        reconciliation = {
            str(row["preparationId"]): row
            for row in SupplierMaterialPriceRuntime.price_source_consistency_report()["priceArchiveReconciliation"]
        }
        matrix = []
        for preparation in PriceApprovalPreparation.objects.order_by("id"):
            row = reconciliation.get(str(preparation.pk), {})
            diagnostic = SupplierMaterialPriceRuntime.diagnose_price_approval_preparation(preparation)
            selected = preparation.selected_supplier if isinstance(preparation.selected_supplier, dict) else {}
            material = next((item for item in (preparation.material_lines or []) if isinstance(item, dict)), {})
            action = row.get("actionAvailability", {})
            matrix.append({
                "preparationId": preparation.pk,
                "preparationNo": preparation.approval_prepare_no,
                "sourceType": preparation.fact_origin,
                "approvalStatus": preparation.status,
                "approvalConclusion": preparation.review_result or ("pass" if preparation.status == "approved" else ""),
                "archiveStatus": row.get("archiveStatus", "NOT_ALLOWED"),
                "supplierRaw": {"code": selected.get("supplierCode") or selected.get("supplierId"), "name": selected.get("supplierName")},
                "materialRaw": {"code": material.get("materialCode") or material.get("materialId"), "name": material.get("materialName")},
                "existingSupplierMaterialPrice": row.get("supplierMaterialPriceId", ""),
                "expectedConfirmAction": bool(diagnostic["canArchive"] and not row.get("supplierMaterialPriceId")),
                "actualConfirmAction": bool(action.get("confirmQuotation")),
                "reasonCode": row.get("blockReasonCode") or diagnostic["blockReasonCode"],
                "reason": row.get("archiveBlockReason") or diagnostic["blockReason"],
            })
        blocked = [row for row in matrix if row["reasonCode"] in ("SUPPLIER_MAPPING_FAILED", "MATERIAL_MAPPING_FAILED")]
        target_names = sorted({row["supplierRaw"]["name"] for row in blocked if row["supplierRaw"]["name"]})
        result = {
            "version": "V1.14.2.8.4.27.2.45.10",
            "totalApprovalObjects": len(matrix),
            "alreadyArchived": sum(bool(row["existingSupplierMaterialPrice"]) for row in matrix),
            "mappingBlocked": len(blocked),
            "notApproved": sum(row["reasonCode"] == "PRICE_APPROVAL_NOT_PASSED" for row in matrix),
            "notCompleted": sum(row["reasonCode"] == "PRICE_APPROVAL_NOT_COMPLETED" for row in matrix),
            "confirmable": sum(row["expectedConfirmAction"] for row in matrix),
            "confirmActionVisible": sum(row["actualConfirmAction"] for row in matrix),
            "supplierMaterialPriceCount": SupplierMaterialPrice.objects.count(),
            "globalActionSuppression": False,
            "matrix": matrix,
            "mappingEvidence": {
                "blockedSupplierNames": target_names,
                "formalExactNameMatches": list(Supplier.objects.filter(name__in=target_names).values("id", "code", "name")),
                "authoritativeConclusion": "WAITING_MANUAL_MAPPING" if blocked else "NOT_REQUIRED",
                "stringGuessMappingCount": 0,
            },
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
