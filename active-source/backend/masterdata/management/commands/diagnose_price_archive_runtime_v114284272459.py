import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from masterdata.master_data_statistics_runtime import SupplierMaterialPriceRuntime
from masterdata.models import Material, PriceApprovalResult, SupplierMaterialPrice
from procurement.models import PriceApprovalPreparation, Supplier


class Command(BaseCommand):
    help = "只读诊断核价归档数据库与运行层（V1.14.2.8.4.27.2.45.9）"

    def handle(self, *args, **options):
        prices = SupplierMaterialPrice.objects.all()
        runtime_models = SupplierMaterialPriceRuntime.list_runtime_models()
        report = {
            "databaseEngine": settings.DATABASES["default"]["ENGINE"],
            "databaseName": str(settings.DATABASES["default"]["NAME"]),
            "tableName": SupplierMaterialPrice._meta.db_table,
            "tableCount": prices.count(),
            "activeCount": prices.filter(status="ACTIVE").count(),
            "inactiveCount": prices.exclude(status="ACTIVE").count(),
            "priceApprovalResultCount": PriceApprovalResult.objects.count(),
            "runtimeCount": len(runtime_models),
            "databaseIds": list(prices.values_list("price_no", flat=True)),
            "runtimeIds": [model.priceNo for model in runtime_models],
            "supplierMasters": list(Supplier.objects.values("id", "code", "name")),
            "targetSupplierNameMatches": list(Supplier.objects.filter(
                name__in=["精工铝材供应商", "华信电子材料"]
            ).values("id", "code", "name")),
            "materialMasters": list(Material.objects.filter(code__in=["MT001", "MT003", "MT006", "MT019"]).values("id", "code", "name")),
            "pendingPreparations": [],
            "dryRunArchiveTraces": [],
        }
        for preparation in PriceApprovalPreparation.objects.order_by("id"):
            if SupplierMaterialPrice.objects.filter(
                price_approval_result__preparation_identity=str(preparation.pk)
            ).exists():
                continue
            selected = preparation.selected_supplier if isinstance(preparation.selected_supplier, dict) else {}
            evidence = preparation.source_quotation_evidence or []
            selected_code = str(selected.get("supplierCode") or selected.get("supplierId") or "")
            selected_evidence = next((item for item in evidence if str(
                item.get("supplierCode") or item.get("supplierId") or ""
            ) == selected_code), {})
            report["pendingPreparations"].append({
                "id": preparation.pk,
                "approvalPrepareNo": preparation.approval_prepare_no,
                "factOrigin": preparation.fact_origin,
                "status": preparation.status,
                "reviewResult": preparation.review_result,
                "selectedSupplier": selected,
                "materialLines": preparation.material_lines,
                "selectedEvidence": selected_evidence,
                "reviewer": preparation.reviewer,
                "reviewedAt": preparation.reviewed_at.isoformat() if preparation.reviewed_at else "",
                "reviewOpinion": preparation.review_opinion,
            })
        target_ids = [3, 5, 6, 9]
        for preparation_id in target_ids:
            before_results = PriceApprovalResult.objects.count()
            before_prices = SupplierMaterialPrice.objects.count()
            try:
                with transaction.atomic():
                    outcome = SupplierMaterialPriceRuntime.archive_price_approval_preparation(
                        preparation_id, {"diagnosticMode": "ROLLBACK"}
                    )
                    wrote_result = PriceApprovalResult.objects.count() > before_results
                    wrote_price = SupplierMaterialPrice.objects.count() > before_prices
                    transaction.set_rollback(True)
                report["dryRunArchiveTraces"].append({
                    "preparationId": preparation_id,
                    "serviceEntered": True,
                    "status": "WOULD_SUCCEED",
                    "databaseWriteAttempted": wrote_result or wrote_price,
                    "databaseCommitted": False,
                    "response": outcome,
                })
            except Exception as exc:
                report["dryRunArchiveTraces"].append({
                    "preparationId": preparation_id,
                    "serviceEntered": True,
                    "status": "BLOCKED",
                    "databaseWriteAttempted": False,
                    "databaseCommitted": False,
                    "errorType": type(exc).__name__,
                    "errorCode": str(exc),
                })
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
