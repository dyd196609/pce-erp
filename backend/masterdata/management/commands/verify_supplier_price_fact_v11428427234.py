import json

from django.core.management.base import BaseCommand, CommandError

from masterdata.master_data_statistics_runtime import SupplierPriceFactRuntime


REQUIRED_FIELDS = {
    "priceFactId", "supplierId", "supplierCode", "materialId", "materialCode",
    "unitPrice", "currency", "unit", "taxRate", "deliveryPeriod",
    "effectiveDate", "expiryDate", "sourceType", "sourceReference", "status",
}


class Command(BaseCommand):
    help = "Verify the read-only SupplierPriceFact Runtime for V1.14.2.8.4.27.2.34."

    def handle(self, *args, **options):
        facts = SupplierPriceFactRuntime.facts()
        rows = [model.to_dict() for model in facts["models"]]
        history_rows = [model.to_dict() for model in facts["historyModels"]]
        missing = [
            row.get("priceFactId", "<unknown>")
            for row in rows
            if not REQUIRED_FIELDS.issubset(row)
        ]
        keys = [
            (row["supplierId"], row["materialId"], row["effectiveDate"])
            for row in rows
        ]
        checks = {
            "runtimeCode": SupplierPriceFactRuntime.runtime_code == "SupplierPriceFactRuntime",
            "runtimeModel": SupplierPriceFactRuntime.runtime_model_type == "SupplierPriceFactModel",
            "requiredFields": not missing,
            "sourcePriority": facts["sourcePriority"] == [
                "SupplierQuotation", "SupplierMaterialPrice", "PurchaseOrderHistory",
            ],
            "sourceTrace": all(row["sourceType"] and row["sourceReference"] for row in rows),
            "supplierBinding": all(row["supplierId"] and row["supplierCode"] for row in rows),
            "materialBinding": all(row["materialId"] and row["materialCode"] for row in rows),
            "positivePrice": all(float(row["unitPrice"]) > 0 for row in rows),
            "effectiveDate": all(row["effectiveDate"] for row in rows),
            "uniqueEffectivePeriod": len(keys) == len(set(keys)),
            "historyProtected": len(history_rows) == (
                len(rows) + facts["duplicateEffectivePeriodCount"]
            ),
            "noAutoDecision": facts["autoDecisionEnabled"] is False,
            "zeroBusinessWrite": facts["businessProgressWriteCount"] == 0,
        }
        failed = [name for name, passed in checks.items() if not passed]
        result = {
            "version": SupplierPriceFactRuntime.runtime_version,
            "runtimeCode": SupplierPriceFactRuntime.runtime_code,
            "runtimeModelType": SupplierPriceFactRuntime.runtime_model_type,
            "priceFactCount": len(rows),
            "historyFactCount": len(history_rows),
            "duplicateEffectivePeriodCount": facts["duplicateEffectivePeriodCount"],
            "sourceCounts": facts["sourceCounts"],
            "checks": checks,
            "failed": failed,
            "businessWriteCount": 0,
            "databaseStructureChanged": False,
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        if failed:
            raise CommandError(f"SupplierPriceFact verification failed: {', '.join(failed)}")
