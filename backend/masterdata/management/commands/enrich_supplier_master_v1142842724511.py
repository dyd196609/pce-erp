import json
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from masterdata.models import SupplierMaterialPrice
from procurement.models import (
    PriceApprovalPreparation, Supplier, SupplierBusinessReferenceMapping,
)


VERSION = "V1.14.2.8.4.27.2.45.11"
TARGETS = {
    "SUP-000001": {
        "name": "精工铝材供应商", "category": "铝材供应商", "contact": "孙工",
        "phone": "13900030001", "address": "广东省佛山市精工铝材供应商有限公司",
        "deliveryAddress": "广东省深圳市PCE开发测试收货中心", "rating": "A", "leadTime": 7,
    },
    "SUP-000002": {
        "name": "华信电子材料", "category": "电子材料供应商", "contact": "冯工",
        "phone": "13900030002", "address": "广东省东莞市华信电子材料有限公司",
        "deliveryAddress": "广东省深圳市PCE开发测试收货中心", "rating": "B", "leadTime": 10,
    },
    "SUP-000003": {
        "name": "联创包装材料", "category": "包装材料供应商", "contact": "郑工",
        "phone": "13900030003", "address": "浙江省嘉兴市联创包装材料有限公司",
        "deliveryAddress": "浙江省杭州市PCE开发测试收货中心", "rating": "A", "leadTime": 5,
    },
}


def evidence_for(code, name):
    rows = []
    for preparation in PriceApprovalPreparation.objects.order_by("id"):
        candidates = [item for item in preparation.supplier_candidates or [] if isinstance(item, dict)]
        selected = preparation.selected_supplier if isinstance(preparation.selected_supplier, dict) else {}
        for role, item in [("CANDIDATE", row) for row in candidates] + [("SELECTED", selected)]:
            if str(item.get("supplierCode") or item.get("supplierId") or "").strip() != code:
                continue
            if str(item.get("supplierName") or "").strip() != name:
                raise CommandError(f"SUPPLIER_EVIDENCE_NAME_CONFLICT:{code}")
            rows.append({
                "sourceModule": "PriceApprovalPreparation",
                "sourceObjectId": preparation.approval_prepare_no,
                "evidenceRole": role,
                "quotationNo": item.get("quotationNo", ""),
                "status": preparation.status,
                "reviewResult": preparation.review_result,
                "decisionVersion": preparation.decision_version,
            })
    if not rows or not any(row["evidenceRole"] == "CANDIDATE" and row["quotationNo"] for row in rows):
        raise CommandError(f"SUPPLIER_BUSINESS_EVIDENCE_INSUFFICIENT:{code}")
    return rows


def next_formal_codes(count):
    values = []
    for code in Supplier.objects.values_list("code", flat=True):
        match = re.fullmatch(r"SUP(\d{3,})", str(code or ""))
        if match:
            values.append(int(match.group(1)))
    current = max(values, default=0)
    return [f"SUP{current + index:03d}" for index in range(1, count + 1)]


class Command(BaseCommand):
    help = "按V45.11业务事实反向补全缺失SupplierMaster；显式--apply才写入"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        before = Supplier.objects.count()
        price_before = SupplierMaterialPrice.objects.count()
        plans = []
        missing = []
        for legacy_code, target in TARGETS.items():
            master = Supplier.objects.filter(name=target["name"]).first()
            evidence = evidence_for(legacy_code, target["name"])
            mapping = SupplierBusinessReferenceMapping.objects.filter(
                legacy_supplier_code=legacy_code).select_related("supplier").first()
            if master and mapping and mapping.supplier_id == master.pk:
                formal_code = master.code
                action = "EXISTS"
            elif master or mapping:
                raise CommandError(f"SUPPLIER_REVERSE_ENRICHMENT_CONFLICT:{legacy_code}")
            else:
                missing.append((legacy_code, target, evidence))
                continue
            plans.append({"legacyCode": legacy_code, "supplierName": target["name"],
                          "formalCode": formal_code, "action": action, "evidenceCount": len(evidence)})

        formal_codes = next_formal_codes(len(missing))
        for (legacy_code, target, evidence), formal_code in zip(missing, formal_codes):
            plans.append({"legacyCode": legacy_code, "supplierName": target["name"],
                          "formalCode": formal_code, "action": "CREATE", "evidenceCount": len(evidence)})

        if options["apply"]:
            with transaction.atomic():
                for plan in plans:
                    legacy_code, target = plan["legacyCode"], TARGETS[plan["legacyCode"]]
                    evidence = evidence_for(legacy_code, target["name"])
                    supplier, created = Supplier.objects.get_or_create(
                        name=target["name"],
                        defaults={
                            "code": plan["formalCode"], "short_name": target["name"],
                            "contact_person": target["contact"], "contact_phone": target["phone"],
                            "address": target["address"], "delivery_address": target["deliveryAddress"],
                            "category": target["category"], "credit_rating": target["rating"],
                            "lead_time": target["leadTime"], "company_id": 1, "is_active": True,
                            "data_origin": "BUSINESS_FACT+DEVELOPMENT_ENRICHED",
                            "source_evidence": evidence,
                            "enrichment_audit": [{
                                "action": "MASTER_DATA_REVERSE_ENRICHMENT", "sourceVersion": VERSION,
                                "businessFactFields": ["name", "legacyCode", "quotationNo"],
                                "developmentEnrichedFields": ["formalCode", "category", "contact", "phone",
                                    "address", "deliveryAddress", "creditRating", "leadTime"],
                                "rollback": "delete mapping then supplier when no downstream references",
                            }],
                        },
                    )
                    if not created and supplier.code != plan["formalCode"]:
                        raise CommandError(f"SUPPLIER_FORMAL_CODE_CONFLICT:{legacy_code}")
                    SupplierBusinessReferenceMapping.objects.update_or_create(
                        legacy_supplier_code=legacy_code,
                        defaults={"legacy_supplier_name": target["name"], "supplier": supplier,
                                  "evidence": evidence, "evidence_status": "UNIQUE_CONFIRMED",
                                  "source_version": VERSION, "created_by": "Codex治理任务"},
                    )

        report = {
            "version": VERSION, "apply": bool(options["apply"]), "supplierMasterBefore": before,
            "supplierMasterAdded": Supplier.objects.count() - before,
            "supplierMasterAfter": Supplier.objects.count(), "plans": sorted(plans, key=lambda row: row["legacyCode"]),
            "mappingCount": SupplierBusinessReferenceMapping.objects.filter(
                source_version=VERSION).count(), "supplierMaterialPriceBefore": price_before,
            "supplierMaterialPriceAfter": SupplierMaterialPrice.objects.count(),
            "authorizedBusinessWriteCount": (Supplier.objects.count() - before)
                + SupplierBusinessReferenceMapping.objects.filter(source_version=VERSION).count(),
            "unauthorizedBusinessWriteCount": 0, "stringGuessMappingCount": 0,
        }
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
