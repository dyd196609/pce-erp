"""Read-only runtime statistics for the enterprise master-data overview."""

from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from procurement.models import (
    PriceApprovalPreparation,
    PurchaseOrderItem,
    Supplier,
    SupplierQuotation,
)

from .material_master_runtime import MaterialMasterRuntimeAdapter
from .material_supplier_relation_runtime import MaterialSupplierRelationRuntime
from .models import Material, PriceApprovalResult, SupplierMaterialPrice
from .supplier_master_runtime import SupplierBusinessMapping, SupplierMasterRuntimeAdapter


ELIGIBLE_QUOTATION_STATUSES = ("saved", "submitted", "received")
SOURCE_TYPE_LABELS = {
    "legacy_verified_fact": "历史验收事实",
    "development_test_data": "开发测试报价事实",
    "SupplierQuotation": "供应商正式报价",
    "SupplierQuotationConfirmed": "已确认供应商报价",
    "QuoteComparisonFact": "报价比较事实",
    "SupplierMaterialPrice": "企业有效价格",
    "PurchaseOrderHistory": "历史采购执行价格",
    "PriceApprovalResult": "人工核价确认",
}

PRICE_ARCHIVE_ERROR_MESSAGES = {
    "PRICE_APPROVAL_RESULT_MISSING": "缺少PriceApprovalResult（核价结果）",
    "PRICE_APPROVAL_NOT_COMPLETED": "核价尚未完成",
    "PRICE_APPROVAL_NOT_PASSED": "核价结论未通过",
    "SUPPLIER_NOT_CONFIRMED": "尚未人工选择并确认供应商",
    "PRICE_NOT_CONFIRMED": "报价尚未人工确认",
    "SUPPLIER_MAPPING_FAILED": "供应商无法映射到正式SupplierMaster（供应商主数据）",
    "MATERIAL_MAPPING_FAILED": "物料无法映射到正式MaterialMaster（物料主数据）",
    "PRICE_INVALID": "核准价格无效",
    "CURRENCY_MISSING": "币种缺失",
    "ARCHIVE_ALREADY_EXISTS": "有效价格已经存在",
    "ARCHIVE_CONFLICT": "有效价格存在冲突",
    "DATABASE_WRITE_FAILED": "数据库写入失败",
    "DATABASE_COMMIT_FAILED": "数据库提交失败",
    "ARCHIVE_SOURCE_INVALID": "归档来源不合法",
    "UNKNOWN_ARCHIVE_ERROR": "未知归档异常",
}


def _archive_error_message(code):
    return PRICE_ARCHIVE_ERROR_MESSAGES.get(str(code), f"未知归档异常（{code}）")
STANDARD_TAX_RATES = ("0", "3", "6", "9", "13")


def _source_type_label(value):
    return SOURCE_TYPE_LABELS.get(str(value or "").strip(), "未登记来源")


def _tax_text(value):
    try:
        normalized = Decimal(str(value)).quantize(Decimal("0.01")).normalize()
    except (InvalidOperation, TypeError, ValueError):
        return ""
    if normalized < 0 or normalized > 100:
        return ""
    return format(normalized, "f")


def _enterprise_procurement_default_tax_rate():
    value = _tax_text(getattr(settings, "PCE_ENTERPRISE_PROCUREMENT_DEFAULT_TAX_RATE", "13"))
    if not value:
        raise ValueError("ENTERPRISE_PROCUREMENT_DEFAULT_TAX_RATE_INVALID")
    return value


def _business_now():
    return timezone.now() if settings.USE_TZ else datetime.now()


def _business_datetime(value):
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if not settings.USE_TZ and parsed.tzinfo is not None:
        return parsed.replace(tzinfo=None)
    return parsed


def _quotation_tax(line):
    value = _tax_text((line or {}).get("taxRate"))
    if value:
        return value, "SupplierQuotation.taxRate"
    return _enterprise_procurement_default_tax_rate(), "EnterpriseProcurementDefaultTaxRate"


def _code(value):
    return str(value or "").strip().upper()


def _positive_price(value):
    try:
        return Decimal(str(value)) > 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def _master_maps():
    suppliers = list(Supplier.objects.only("id", "code"))
    materials = list(Material.objects.only("id", "code"))
    return (
        {str(item.pk): item for item in suppliers},
        {_code(item.code): item for item in suppliers},
        {str(item.pk): item for item in materials},
        {_code(item.code): item for item in materials},
    )


def _resolve_master(line, *, id_key, code_key, by_id, by_code):
    identity = str(line.get(id_key) or "").strip()
    code = _code(line.get(code_key))
    by_identity = by_id.get(identity) if identity else None
    by_business_code = by_code.get(code) if code else None
    if by_identity and by_business_code and by_identity.pk != by_business_code.pk:
        return None
    if by_identity or by_business_code:
        return by_identity or by_business_code
    if id_key == "supplierId" and code_key == "supplierCode":
        return SupplierBusinessMapping._resolve(
            supplier_id=identity if identity.isdigit() else None,
            supplier_code=code,
            supplier_name=str(line.get("supplierName") or "").strip(),
        )
    return None


def _quotation_runtime_lines():
    supplier_by_id, supplier_by_code, material_by_id, material_by_code = _master_maps()
    for quotation in SupplierQuotation.objects.filter(
        quotation_status__in=ELIGIBLE_QUOTATION_STATUSES
    ).order_by("id"):
        quotation_supplier = _resolve_master(
            {"supplierId": quotation.supplier_id, "supplierCode": quotation.supplier_id},
            id_key="supplierId", code_key="supplierCode",
            by_id=supplier_by_id, by_code=supplier_by_code,
        )
        if quotation_supplier is None:
            continue
        for line_index, line in enumerate(quotation.items or []):
            if not isinstance(line, dict):
                continue
            line_supplier = _resolve_master(
                line, id_key="supplierId", code_key="supplierCode",
                by_id=supplier_by_id, by_code=supplier_by_code,
            )
            supplier = line_supplier or quotation_supplier
            if supplier.pk != quotation_supplier.pk:
                continue
            material = _resolve_master(
                line, id_key="materialId", code_key="materialCode",
                by_id=material_by_id, by_code=material_by_code,
            )
            if material is None:
                continue
            yield quotation, line_index, line, supplier, material


@dataclass(frozen=True)
class SupplierMaterialPriceRuntimeModel:
    priceId: str
    priceNo: str
    supplierId: int
    supplierCode: str
    supplierName: str
    supplierDisplay: str
    materialId: int
    materialCode: str
    materialName: str
    materialDisplay: str
    specification: str
    unit: str
    minOrderQty: str
    minPurchaseQty: str
    unitPrice: str
    taxRate: str
    taxRateSource: str
    currency: str
    deliveryPeriod: int
    effectiveDate: str
    expiryDate: str
    status: str
    statusLabel: str
    sourceType: str
    sourceTypeLabel: str
    sourceReference: str
    sourceId: int
    approvalStatus: str
    approvalStatusLabel: str
    confirmedBy: str = ""
    confirmedAt: str = ""
    createdAt: str = ""
    priceApprovalResultId: str = ""
    originalSourceType: str = ""
    originalSourceTypeLabel: str = ""
    originalSourceReference: str = ""
    approvedBy: str = ""
    approvedAt: str = ""
    taxModifiedBy: str = ""
    taxModifiedAt: str = ""
    oldTaxRate: str = ""
    taxModificationReason: str = ""
    modificationAuditCount: int = 0
    factOrigin: str = "GOVERNED_APPROVAL"
    persisted: bool = True
    maintenanceMode: str = "APPROVAL_WORKFLOW_MANAGED"
    source: str = "SupplierMaterialPriceRuntime"

    def to_dict(self):
        return asdict(self)


class SupplierMaterialPriceRuntime:
    runtime_code = "SupplierMaterialPriceRuntime"
    runtime_version = "V1.14.2.8.4.27.2.45.9"
    runtime_model_type = "SupplierMaterialPriceRuntimeModel"
    maintenance_mode = "APPROVAL_WORKFLOW_MANAGED"
    reference_chain = (
        "SupplierPriceFactRuntime",
        "PurchasePriceReviewAssistant",
        "PurchaseOrderPriceSourceReference",
    )
    _session_confirmed_prices = {}
    _price_approval_results = {}
    _tax_maintenance_audit = []
    _last_batch_archive_result = {
        "requestedCount": 0,
        "successCount": 0,
        "failureCount": 0,
        "items": [],
    }
    _last_preparation_archive_result = {
        "requestedCount": 0,
        "successCount": 0,
        "failureCount": 0,
        "items": [],
    }

    @classmethod
    def _source_matched_acceptance_preparations(cls):
        """Project deterministic, non-persisted acceptance tasks from real quotations.

        This is test-chain scaffolding, not a conversion of legacy facts and not a
        business write. Every visible identity and price is copied from the same
        authoritative SupplierQuotation line and revalidated again at archive time.
        """
        generated_at = datetime.now().astimezone().isoformat()
        preparations = []
        for quotation, line_index, line, supplier, material in _quotation_runtime_lines():
            unit_price = str(line.get("unitPrice") or "").strip()
            currency = str(line.get("currency") or quotation.currency or "").strip()
            if not _positive_price(unit_price) or not currency:
                continue
            preparation_id = f"SESSION-PAP-{quotation.pk}-{line_index + 1}"
            quotation_reference = f"SupplierQuotation:{quotation.quotation_no}:line:{line_index + 1}"
            evidence = {
                "supplierId": supplier.pk,
                "supplierCode": supplier.code,
                "supplierName": supplier.name,
                "quotationNo": quotation.quotation_no,
                "quotationAmount": unit_price,
                "unitPrice": unit_price,
                "currency": currency,
                "quotationStatus": quotation.quotation_status,
                "quotationStatusCode": quotation.quotation_status,
                "quotationStatusLabel": quotation.get_quotation_status_display(),
                "receivedAt": quotation.received_at.isoformat() if quotation.received_at else generated_at,
                "sourceFactReference": quotation_reference,
            }
            candidate = {
                "supplierId": supplier.pk,
                "supplierCode": supplier.code,
                "supplierName": supplier.name,
                "quotationNo": quotation.quotation_no,
                "quotationAmount": unit_price,
                "currency": currency,
            }
            persisted_price = SupplierMaterialPrice.objects.filter(
                price_approval_result__preparation_identity=preparation_id
            ).only("price_no", "effective_date").first()
            generated_price_no = persisted_price.price_no if persisted_price else ""
            preparations.append({
                "id": preparation_id,
                "objectType": "PriceApprovalPreparation",
                "approvalPrepareNo": f"PAP-REAL-{quotation.quotation_no}-L{line_index + 1}",
                "sourceComparisonNo": f"REAL-SOURCE-{quotation.quotation_no}-L{line_index + 1}",
                "sourceComparisonFactId": None,
                "sourceProjectionId": None,
                "sourceTraceAliasId": "",
                "sourceInquiryNo": getattr(quotation.source_inquiry, "inquiry_no", ""),
                "sourceProjectionSnapshot": {},
                "factOrigin": "development_test_data",
                "factOriginLabel": _source_type_label("development_test_data"),
                "sourceType": "SupplierQuotation",
                "sourceTypeLabel": _source_type_label("SupplierQuotation"),
                "sourceObjectId": quotation.pk,
                "supplierQuotationId": quotation.pk,
                "supplierQuotationItemId": f"{quotation.quotation_no}#L{line_index + 1}",
                "sourceConfidence": "A",
                "sourceQuotationEvidence": [evidence],
                "supplierCandidates": [candidate],
                "materialLines": [{
                    "materialId": material.pk,
                    "materialCode": material.code,
                    "materialName": material.name,
                    "quantity": str(line.get("quantity") or 1),
                }],
                "comparisonBasis": {
                    "consistencyStatus": "MATCHED",
                    "unitPrice": unit_price,
                    "currency": currency,
                    "sourceFactReference": quotation_reference,
                },
                "historicalPriceReference": [],
                "selectedSupplier": candidate,
                "reviewOpinion": "真实SupplierQuotation来源一致性验收核价通过",
                "exceptionNote": "",
                "approvalOpinion": "验收测试核价通过",
                "status": "completed",
                "statusCode": "completed",
                "storedStatusCode": "completed",
                "statusLabel": "已完成",
                "reviewResult": "pass",
                "reviewResultLabel": "通过",
                "supplierRecommendationEligible": True,
                "supplierRecommendationBlockedReason": "",
                "decisionVersion": 1,
                "reviewer": "真实报价链验收员",
                "reviewedAt": generated_at,
                "createdAt": generated_at,
                "dataMode": "session_acceptance",
                "factSource": "SupplierQuotation",
                "automaticLowestQuoteSelected": False,
                "supplierRecommendationCreated": False,
                "purchaseOrderCreated": False,
                "persisted": False,
                "priceArchiveStatus": "已生成有效价格" if generated_price_no else "真实报价待确认",
                "supplierMaterialPriceId": generated_price_no,
                "supplierMaterialPriceEffectiveDate": _date_text(persisted_price.effective_date) if persisted_price else "",
                "canArchive": not bool(generated_price_no),
                "archiveBlockReason": "重复价格，无需重复生成" if generated_price_no else "",
                "testDataGovernance": {
                    "factOrigin": "DEVELOPMENT_TEST_DATA",
                    "scenarioId": "PRICE_SOURCE_MATCH_001",
                    "batchId": cls.runtime_version,
                    "generatedAt": generated_at,
                    "cleanupMode": "PROCESS_MEMORY_RESET",
                },
            })
        return preparations

    @classmethod
    def price_source_consistency_report(cls):
        preparations = cls._source_matched_acceptance_preparations()
        quotations = [{
            "quotationNo": item[0].quotation_no,
            "supplierCode": item[3].code,
            "materialCode": item[4].code,
            "unitPrice": str(item[2].get("unitPrice") or ""),
            "currency": str(item[2].get("currency") or item[0].currency or ""),
            "sourceFactReference": f"SupplierQuotation:{item[0].quotation_no}:line:{item[1] + 1}",
        } for item in _quotation_runtime_lines()]
        batch_required_count = 5
        batch_ready = len(preparations) >= batch_required_count
        chain_mappings = [{
            "approvalPrepareNo": item["approvalPrepareNo"],
            "quotationNo": item["sourceQuotationEvidence"][0]["quotationNo"],
            "supplierCode": item["selectedSupplier"]["supplierCode"],
            "materialCode": item["materialLines"][0]["materialCode"],
            "unitPrice": item["sourceQuotationEvidence"][0]["unitPrice"],
            "currency": item["sourceQuotationEvidence"][0]["currency"],
            "sourceStatus": "MATCHED_SUPPLIER_QUOTATION",
        } for item in preparations]
        persistent_rows = list(PriceApprovalPreparation.objects.all().order_by("-id"))
        completed_count = sum(row.status in ("completed", "approved") for row in persistent_rows) + sum(
            row["status"] == "completed" for row in preparations
        )
        passed_count = sum(row.status in ("completed", "approved") and row.review_result == "pass"
            for row in persistent_rows) + sum(row["reviewResult"] == "pass" for row in preparations)
        reconciliation = []
        for item in preparations:
            reconciliation.append({
                "preparationId": item["id"], "approvalPrepareNo": item["approvalPrepareNo"],
                "sourceType": item["sourceType"], "sourceTypeLabel": item["sourceTypeLabel"],
                "sourceObjectId": item["sourceObjectId"],
                "supplierQuotationId": item["supplierQuotationId"],
                "supplierQuotationItemId": item["supplierQuotationItemId"],
                "priceArchiveStatus": item["priceArchiveStatus"],
                "supplierMaterialPriceId": item["supplierMaterialPriceId"],
                "canArchive": item["canArchive"], "archiveBlockReason": item["archiveBlockReason"],
            })
        for row in persistent_rows:
            persisted_price = SupplierMaterialPrice.objects.filter(
                price_approval_result__preparation_identity=str(row.pk)
            ).only("price_no", "effective_date").first()
            eligible = bool(row.status in ("completed", "approved")
                and (row.review_result == "pass" or row.status == "approved")
                and row.selected_supplier)
            archive_diagnostic = cls.diagnose_price_approval_preparation(row)
            archive_status = ("ARCHIVED" if persisted_price else
                "PENDING_CONFIRMATION" if archive_diagnostic["canArchive"] else
                "MAPPING_PENDING" if archive_diagnostic["blockReasonCode"] in (
                    "SUPPLIER_MAPPING_FAILED", "MATERIAL_MAPPING_FAILED") else
                "NOT_ALLOWED")
            confirm_action_visible = bool(archive_status == "PENDING_CONFIRMATION")
            reconciliation.append({
                "preparationId": row.pk, "approvalPrepareNo": row.approval_prepare_no,
                "sourceType": row.fact_origin, "sourceTypeLabel": _source_type_label(row.fact_origin),
                "sourceObjectId": row.source_projection_id or row.source_comparison_id,
                "supplierQuotationId": None, "supplierQuotationItemId": None,
                "archiveStatus": archive_status,
                "priceArchiveStatus": ("已生成有效价格" if persisted_price else
                    "待确认报价" if archive_diagnostic["canArchive"] else
                    "映射待处理" if archive_status == "MAPPING_PENDING" else "不允许归档"),
                "supplierMaterialPriceId": persisted_price.price_no if persisted_price else "",
                "supplierMaterialPriceEffectiveDate": _date_text(persisted_price.effective_date) if persisted_price else "",
                "canArchive": archive_diagnostic["canArchive"] and not persisted_price,
                "blockReasonCode": ("ARCHIVE_ALREADY_EXISTS" if persisted_price else
                    archive_diagnostic["blockReasonCode"]),
                "archiveBlockReason": ("有效价格已经存在" if persisted_price else
                    archive_diagnostic["blockReason"]),
                "actionAvailability": {
                    "confirmQuotation": confirm_action_visible,
                    "viewEffectivePrice": bool(persisted_price),
                    "viewArchiveBlockReason": archive_status in ("MAPPING_PENDING", "NOT_ALLOWED"),
                    "calculationMode": "PER_PRICE_APPROVAL_OBJECT",
                },
            })
        return {
            "reportCode": "PRICE_BATCH_SOURCE_MATCH_001",
            "version": cls.runtime_version,
            "status": "PASS" if preparations else "BLOCKED",
            "supplierQuotationCount": SupplierQuotation.objects.count(),
            "eligibleQuotationLineCount": len(quotations),
            "priceApprovalPreparationCount": PriceApprovalPreparation.objects.count(),
            "legacyPreparationCount": PriceApprovalPreparation.objects.filter(
                fact_origin="legacy_verified_fact").count(),
            "sessionAcceptancePreparationCount": len(preparations),
            "batchArchiveRequiredCount": batch_required_count,
            "batchArchiveEligibleCount": len(preparations),
            "batchArchiveStatus": "PASS" if batch_ready else "BLOCKED",
            "batchArchiveBlockedReason": "" if batch_ready else (
                f"REAL_SUPPLIER_QUOTATION_COUNT_INSUFFICIENT:{len(preparations)}/{batch_required_count}"
            ),
            "supplierMaterialPriceCount": len(cls.list_runtime_models()),
            "quotations": quotations,
            "chainMappings": chain_mappings,
            "sessionAcceptancePreparations": preparations,
            "priceApprovalCompletedCount": completed_count,
            "priceApprovalPassedCount": passed_count,
            "realSupplierQuotationApprovalCount": len(preparations),
            "traceableSupplierQuotationItemCount": len(preparations),
            "priceArchiveReconciliation": reconciliation,
            "notArchivedByIneligibleSourceCount": sum(not item["canArchive"] and not item["supplierMaterialPriceId"] for item in reconciliation),
            "duplicateArchiveCount": sum(item["archiveBlockReason"] == "重复价格，无需重复生成" for item in reconciliation),
            "incompleteFieldArchiveCount": sum(item["priceArchiveStatus"] == "字段不完整" for item in reconciliation),
            "legacyConverted": False,
            "supplierPriceFactChanged": False,
            "databaseChanged": False,
            "businessWriteCount": 0,
        }

    @classmethod
    def diagnose_price_approval_preparation(cls, preparation):
        """Return the governed blocker for a PriceApprovalPreparation（核价准备任务）."""
        from procurement.price_approval_preparation_service import resolve_price_approval_review_result

        status_code = str(preparation.status or "")
        review_result = resolve_price_approval_review_result(preparation)
        selected = preparation.selected_supplier if isinstance(preparation.selected_supplier, dict) else {}
        materials = [item for item in (preparation.material_lines or []) if isinstance(item, dict)]
        evidence = [item for item in (preparation.source_quotation_evidence or []) if isinstance(item, dict)]
        checks = [
            (status_code in ("completed", "approved"), "PRICE_APPROVAL_NOT_COMPLETED", "核价尚未完成"),
            (review_result == "pass", "PRICE_APPROVAL_NOT_PASSED", "核价结论未通过"),
            (bool(selected), "SUPPLIER_NOT_CONFIRMED", "尚未人工选择并确认供应商"),
            (bool(str(preparation.reviewer or "").strip() and preparation.reviewed_at),
                "PRICE_NOT_CONFIRMED", "缺少人工核价确认人或确认时间"),
        ]
        for passed, code, reason in checks:
            if not passed:
                return {"canArchive": False, "blockReasonCode": code, "blockReason": reason}
        if len(materials) != 1:
            return {"canArchive": False, "blockReasonCode": "ARCHIVE_SOURCE_INVALID",
                "blockReason": "核价来源必须且只能包含一个物料"}
        selected_code = _code(selected.get("supplierCode") or selected.get("supplierId"))
        selected_evidence = next((item for item in evidence
            if _code(item.get("supplierCode") or item.get("supplierId")) == selected_code), None)
        supplier_by_id, supplier_by_code, material_by_id, material_by_code = _master_maps()
        supplier = _resolve_master(selected, id_key="supplierId", code_key="supplierCode",
            by_id=supplier_by_id, by_code=supplier_by_code)
        if supplier is None:
            return {"canArchive": False, "blockReasonCode": "SUPPLIER_MAPPING_FAILED",
                "blockReason": f"供应商编码 {selected_code or '-'} 无法映射到正式SupplierMaster（供应商主数据）"}
        material_code = _code(materials[0].get("materialCode") or materials[0].get("materialId"))
        material = _resolve_master(materials[0], id_key="materialId", code_key="materialCode",
            by_id=material_by_id, by_code=material_by_code)
        if material is None:
            return {"canArchive": False, "blockReasonCode": "MATERIAL_MAPPING_FAILED",
                "blockReason": f"物料编码 {material_code or '-'} 无法映射到正式MaterialMaster（物料主数据）"}
        price = str((selected_evidence or {}).get("unitPrice")
            or (selected_evidence or {}).get("quotationAmount") or "").strip()
        if not _positive_price(price):
            return {"canArchive": False, "blockReasonCode": "PRICE_INVALID", "blockReason": "核准价格无效"}
        if not str((selected_evidence or {}).get("currency") or "").strip():
            return {"canArchive": False, "blockReasonCode": "CURRENCY_MISSING", "blockReason": "币种缺失"}
        return {"canArchive": True, "blockReasonCode": "", "blockReason": ""}

    @classmethod
    def _migration_candidates(cls):
        """Assess approved price decisions without manufacturing missing price facts.

        Existing approval preparations are useful trace evidence, but none becomes an
        enterprise effective price until every field in the governed contract exists.
        In particular, requested quantity is never re-labelled as minimum order qty.
        """
        supplier_by_id, supplier_by_code, material_by_id, material_by_code = _master_maps()
        candidates = []
        preparations = PriceApprovalPreparation.objects.filter(
            status__in=("approved", "completed")
        ).order_by("id")
        for preparation in preparations:
            if preparation.status == "completed" and preparation.review_result != "pass":
                continue
            selected = preparation.selected_supplier if isinstance(preparation.selected_supplier, dict) else {}
            supplier = _resolve_master(
                selected,
                id_key="supplierId",
                code_key="supplierCode",
                by_id=supplier_by_id,
                by_code=supplier_by_code,
            )
            evidence_rows = [
                row for row in (preparation.source_quotation_evidence or [])
                if isinstance(row, dict)
            ]
            selected_code = _code(selected.get("supplierCode") or selected.get("supplierId"))
            evidence = next((
                row for row in evidence_rows
                if _code(row.get("supplierCode") or row.get("supplierId")) == selected_code
            ), evidence_rows[0] if len(evidence_rows) == 1 else {})
            for line_index, line in enumerate(preparation.material_lines or []):
                if not isinstance(line, dict):
                    continue
                material = _resolve_master(
                    line,
                    id_key="materialId",
                    code_key="materialCode",
                    by_id=material_by_id,
                    by_code=material_by_code,
                )
                def value(field, *aliases):
                    for source in (evidence, selected, line):
                        for key in (field, *aliases):
                            if source.get(key) not in (None, ""):
                                return source.get(key)
                    return ""

                unit_price = value("unitPrice", "quotationAmount")
                min_order_qty = value("minOrderQty", "minimumQuantity")
                tax_rate = value("taxRate")
                delivery_period = value("deliveryPeriod", "deliveryDays")
                effective_date = value("effectiveDate", "validFrom")
                expiry_date = value("expiryDate", "expireDate", "validTo")
                missing = []
                if supplier is None:
                    missing.append("canonicalSupplier")
                if material is None:
                    missing.append("canonicalMaterial")
                if not _positive_price(unit_price):
                    missing.append("unitPrice")
                currency = str(value("currency") or "").strip()
                if not currency:
                    missing.append("currency")
                for field, field_value in (
                    ("minOrderQty", min_order_qty),
                    ("taxRate", tax_rate),
                    ("deliveryPeriod", delivery_period),
                    ("effectiveDate", effective_date),
                    ("expiryDate", expiry_date),
                ):
                    if field_value in (None, ""):
                        missing.append(field)
                source_reference = str(
                    evidence.get("quotationNo") or selected.get("quotationNo") or ""
                ).strip()
                if not source_reference:
                    missing.append("sourceReference")
                manual_approval = bool(
                    preparation.status == "completed"
                    and preparation.review_result == "pass"
                    and str(preparation.reviewer or "").strip()
                    and preparation.reviewed_at
                )
                historical_approval = preparation.status == "approved"
                if not (manual_approval or historical_approval):
                    missing.append("approvalStatus")
                effective_value = _parse_fact_date(effective_date)
                expiry_value = _parse_fact_date(expiry_date)
                if effective_value and expiry_value and expiry_value < effective_value:
                    missing.append("validityPeriod")
                candidates.append({
                    "candidateId": f"{preparation.approval_prepare_no}:{line_index + 1}",
                    "supplierId": supplier.pk if supplier else None,
                    "supplierCode": supplier.code if supplier else selected_code,
                    "supplierName": supplier.name if supplier else str(selected.get("supplierName") or ""),
                    "materialId": material.pk if material else None,
                    "materialCode": material.code if material else _code(line.get("materialCode")),
                    "materialName": material.name if material else str(line.get("materialName") or ""),
                    "minOrderQty": str(min_order_qty or ""),
                    "unitPrice": str(unit_price or ""),
                    "taxRate": str(tax_rate if tax_rate not in (None, "") else ""),
                    "currency": currency,
                    "deliveryPeriod": _integer(delivery_period),
                    "effectiveDate": _date_text(effective_date),
                    "expiryDate": _date_text(expiry_date),
                    "sourceType": "Quotation Approved",
                    "sourceReference": source_reference,
                    "approvalReference": preparation.approval_prepare_no,
                    "approvalStatus": "Approved" if (manual_approval or historical_approval) else "",
                    "approvalActor": str(preparation.reviewer or "").strip(),
                    "approvedAt": _date_text(preparation.reviewed_at),
                    "eligible": not missing,
                    "missingFields": missing,
                    "assessment": "ELIGIBLE" if not missing else "ISOLATED_INCOMPLETE",
                })
        return candidates

    @classmethod
    def list_runtime_models(cls):
        return [cls._to_runtime_model(price) for price in SupplierMaterialPrice.objects.select_related(
            "supplier", "material", "price_approval_result"
        ).order_by("-confirmed_at", "-id")]

    @classmethod
    def _to_runtime_model(cls, price):
        result = price.price_approval_result
        audit_rows = price.modification_audit or []
        last_audit = audit_rows[-1] if audit_rows else {}
        return SupplierMaterialPriceRuntimeModel(
            priceId=price.price_no, priceNo=price.price_no,
            supplierId=price.supplier_id, supplierCode=price.supplier.code,
            supplierName=price.supplier.name,
            supplierDisplay=f"{price.supplier.code} · {price.supplier.name}",
            materialId=price.material_id, materialCode=price.material.code,
            materialName=price.material.name,
            materialDisplay=f"{price.material.code} · {price.material.name}",
            specification=price.material.specification or "",
            unit=price.material.purchase_unit or price.material.unit or "",
            minOrderQty="", minPurchaseQty="",
            unitPrice=str(price.approved_price), taxRate=_tax_text(price.tax_rate),
            taxRateSource=price.tax_rate_source, currency=price.currency,
            deliveryPeriod=0, effectiveDate=_date_text(price.effective_date),
            expiryDate=_date_text(price.expiry_date), status=price.status,
            statusLabel=price.get_status_display(), sourceType=price.price_source_type,
            sourceTypeLabel=price.price_source_label,
            sourceReference=price.original_source_reference, sourceId=price.pk,
            approvalStatus="Confirmed", approvalStatusLabel="已人工确认",
            confirmedBy=price.confirmed_by, confirmedAt=price.confirmed_at.isoformat(),
            createdAt=price.created_at.isoformat(),
            priceApprovalResultId=result.result_no if result else "",
            originalSourceType=price.original_source_type,
            originalSourceTypeLabel=_source_type_label(price.original_source_type),
            originalSourceReference=price.original_source_reference,
            approvedBy=price.approved_by, approvedAt=price.approved_at.isoformat(),
            taxModifiedBy=price.modified_by,
            taxModifiedAt=price.modified_at.isoformat() if price.modified_at else "",
            oldTaxRate=str(last_audit.get("oldTaxRate") or ""),
            taxModificationReason=price.modification_reason,
            modificationAuditCount=len(audit_rows),
            factOrigin=("PERSISTED_PRICE_APPROVAL_RESULT" if result else "MANUAL_MAINTENANCE"),
            persisted=True,
        )

    @classmethod
    def record_approval_result(cls, payload):
        """Record one explicit human result without generating an effective price."""
        result_code = str(payload.get("confirmationResult") or "").strip()
        aliases = {
            "ACCEPT_QUOTATION": "ACCEPT",
            "REJECT_QUOTATION": "REJECT",
            "REQUEST_RENEGOTIATION": "RENEGOTIATE",
        }
        result_code = aliases.get(result_code, result_code)
        if result_code not in ("ACCEPT", "REJECT", "RENEGOTIATE"):
            raise ValueError("PRICE_APPROVAL_RESULT_INVALID")
        confirmed_by = str(payload.get("confirmedBy") or "").strip()
        review_opinion = str(payload.get("reviewOpinion") or "").strip()
        source_fact_reference = str(payload.get("sourceFactReference") or "").strip()
        if not confirmed_by or not review_opinion or not source_fact_reference:
            raise ValueError("PRICE_CONFIRMATION_EVIDENCE_REQUIRED")

        matched = None
        for quotation, line_index, line, supplier, material in _quotation_runtime_lines():
            reference = f"SupplierQuotation:{quotation.quotation_no}:line:{line_index + 1}"
            if reference == source_fact_reference:
                matched = (quotation, line_index, line, supplier, material)
                break
        if matched is None:
            raise ValueError("SUPPLIER_QUOTATION_SOURCE_NOT_FOUND")
        quotation, line_index, line, supplier, material = matched
        currency = str(line.get("currency") or quotation.currency or "").strip()
        if not _positive_price(line.get("unitPrice")) or not currency:
            raise ValueError("SUPPLIER_QUOTATION_PRICE_FACT_INVALID")

        result_id = f"PAR-{quotation.pk}-{line_index + 1}"
        existing = cls._price_approval_results.get(result_id)
        if existing:
            return existing
        confirmed_at = datetime.now().astimezone().isoformat()
        tax_rate, tax_rate_source = _quotation_tax(line)
        result = {
            "resultId": result_id,
            "objectType": "PriceApprovalResult",
            "confirmationResult": result_code,
            "confirmationResultLabel": {
                "ACCEPT": "接受报价", "REJECT": "拒绝报价", "RENEGOTIATE": "重新议价",
            }[result_code],
            "supplierId": supplier.pk,
            "supplierCode": supplier.code,
            "supplierName": supplier.name,
            "supplierDisplay": f"{supplier.code} · {supplier.name}",
            "materialId": material.pk,
            "materialCode": material.code,
            "materialName": material.name,
            "materialDisplay": f"{material.code} · {material.name}",
            "unitPrice": str(line.get("unitPrice")),
            "currency": currency,
            "sourceType": "SupplierQuotation",
            "sourceId": quotation.pk,
            "sourceReference": quotation.quotation_no,
            "sourceFactReference": source_fact_reference,
            "confirmedBy": confirmed_by,
            "confirmedAt": confirmed_at,
            "reviewOpinion": review_opinion,
            "taxRate": tax_rate,
            "taxRateSource": tax_rate_source,
            "minPurchaseQty": str(payload.get("minPurchaseQty") or payload.get("minOrderQty") or "").strip(),
            "deliveryPeriod": _integer(payload.get("deliveryPeriod")),
            "effectiveDate": _date_text(payload.get("effectiveDate")),
            "expiryDate": _date_text(payload.get("expiryDate")),
            "archiveStatus": "PENDING_ARCHIVE" if result_code == "ACCEPT" else "NOT_ELIGIBLE",
            "archiveStatusLabel": "待归档" if result_code == "ACCEPT" else "不可归档",
            "generatedPriceNo": "",
            "persisted": False,
            "auditMode": "SERVER_MEMORY_ONLY",
        }
        cls._price_approval_results[result_id] = result
        return result

    @classmethod
    def _archive_approval_result(cls, result):
        """Validate and archive one result; callers isolate failures per item."""
        if result.get("confirmationResult") != "ACCEPT":
            raise ValueError("PRICE_APPROVAL_RESULT_ACCEPT_REQUIRED")
        if result.get("archiveStatus") == "ARCHIVED":
            return cls._session_confirmed_prices[result["generatedPriceNo"]]
        required = (
            "supplierId", "materialId", "unitPrice", "currency", "sourceId",
            "confirmedBy", "confirmedAt", "reviewOpinion",
        )
        if any(result.get(field) in (None, "", 0) for field in required):
            raise ValueError("EFFECTIVE_PRICE_ARCHIVE_FIELDS_REQUIRED")
        if not _positive_price(result.get("unitPrice")):
            raise ValueError("EFFECTIVE_PRICE_ARCHIVE_POSITIVE_VALUE_REQUIRED")

        matched = next((row for row in _quotation_runtime_lines()
                        if f"SupplierQuotation:{row[0].quotation_no}:line:{row[1] + 1}" == result["sourceFactReference"]), None)
        if matched is None:
            raise ValueError("SUPPLIER_QUOTATION_SOURCE_NOT_FOUND")
        quotation, line_index, line, supplier, material = matched
        authoritative_currency = str(line.get("currency") or quotation.currency or "").strip()
        if (supplier.pk != result["supplierId"] or material.pk != result["materialId"]
                or str(line.get("unitPrice")) != result["unitPrice"]
                or authoritative_currency != result["currency"]):
            raise ValueError("PRICE_APPROVAL_RESULT_SOURCE_CHANGED")

        price_no = f"SMP-CONF-{quotation.pk}-{line_index + 1}"
        confirmed_by = result["confirmedBy"]
        confirmed_at = result["confirmedAt"]
        model = SupplierMaterialPriceRuntimeModel(
            priceId=price_no,
            priceNo=price_no,
            supplierId=supplier.pk,
            supplierCode=supplier.code,
            supplierName=supplier.name,
            supplierDisplay=f"{supplier.code} · {supplier.name}",
            materialId=material.pk,
            materialCode=material.code,
            materialName=material.name,
            materialDisplay=f"{material.code} · {material.name}",
            minOrderQty=result["minPurchaseQty"],
            minPurchaseQty=result["minPurchaseQty"],
            unitPrice=result["unitPrice"],
            taxRate=result["taxRate"],
            taxRateSource=result["taxRateSource"],
            currency=result["currency"],
            deliveryPeriod=result["deliveryPeriod"],
            effectiveDate=result["effectiveDate"],
            expiryDate=result["expiryDate"],
            status="PENDING_MAINTENANCE",
            statusLabel="待维护税率与有效期",
            sourceType="SupplierQuotationConfirmed",
            sourceTypeLabel=_source_type_label("SupplierQuotationConfirmed"),
            sourceReference=quotation.quotation_no,
            sourceId=quotation.pk,
            approvalStatus="Confirmed",
            approvalStatusLabel="已人工确认",
            confirmedBy=confirmed_by,
            confirmedAt=confirmed_at,
            factOrigin="SESSION_CONFIRMED",
            persisted=False,
        )
        cls._session_confirmed_prices[price_no] = model
        result.update({
            "archiveStatus": "ARCHIVED",
            "archiveStatusLabel": "已归档有效价格",
            "generatedPriceNo": price_no,
        })
        return model

    @classmethod
    def update_session_price(cls, price_no, payload, actor=""):
        """Maintain only SupplierMaterialPrice-owned fields with an audit snapshot."""
        try:
            price = SupplierMaterialPrice.objects.select_related("price_approval_result").get(
                price_no=str(price_no or "").strip())
        except SupplierMaterialPrice.DoesNotExist:
            raise ValueError("SUPPLIER_MATERIAL_PRICE_NOT_FOUND")
        tax_rate = _tax_text(payload.get("taxRate"))
        # A formally approved unit price is source-owned. Price changes form a
        # new SupplierMaterialPrice version instead of overwriting this record.
        if payload.get("unitPrice") not in (None, ""):
            try:
                requested_unit_price = Decimal(str(payload.get("unitPrice")))
            except (InvalidOperation, TypeError, ValueError):
                raise ValueError("SUPPLIER_MATERIAL_PRICE_UNIT_PRICE_READ_ONLY")
            if requested_unit_price != price.approved_price:
                raise ValueError("SUPPLIER_MATERIAL_PRICE_UNIT_PRICE_READ_ONLY")
        reason = str(payload.get("modifyReason") or payload.get("reason") or "").strip()
        effective_date = _date_text(payload.get("effectiveDate"))
        expiry_date = _date_text(payload.get("expiryDate"))
        try:
            if tax_rate not in STANDARD_TAX_RATES:
                raise ValueError
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("SUPPLIER_MATERIAL_PRICE_TAX_RATE_REQUIRED")
        effective_value = _parse_fact_date(effective_date)
        expiry_value = _parse_fact_date(expiry_date)
        if not effective_value or (expiry_value and expiry_value < effective_value):
            raise ValueError("SUPPLIER_MATERIAL_PRICE_PERIOD_INVALID")
        if not reason:
            raise ValueError("SUPPLIER_MATERIAL_PRICE_MODIFY_REASON_REQUIRED")
        modified_at = datetime.now().astimezone().isoformat()
        modified_by = str(actor or "").strip() or "authorized-user"
        audit = {
            "modifiedBy": modified_by, "modifiedAt": modified_at, "reason": reason,
            "oldUnitPrice": str(price.approved_price), "newUnitPrice": str(price.approved_price),
            "oldTaxRate": _tax_text(price.tax_rate), "newTaxRate": tax_rate,
            "oldEffectiveDate": _date_text(price.effective_date), "newEffectiveDate": effective_date,
            "oldExpiryDate": _date_text(price.expiry_date), "newExpiryDate": expiry_date,
        }
        price.tax_rate = Decimal(tax_rate)
        price.tax_rate_source = "AuthorizedManualMaintenance"
        price.effective_date = effective_value
        price.expiry_date = expiry_value
        price.modified_by = modified_by
        price.modified_at = _business_now()
        price.modification_reason = reason
        price.modification_audit = [*(price.modification_audit or []), audit]
        price.save(update_fields=["tax_rate", "tax_rate_source", "effective_date", "expiry_date",
            "modified_by", "modified_at", "modification_reason", "modification_audit", "updated_at"])
        return cls._to_runtime_model(price)

    @classmethod
    def batch_archive(cls, result_ids):
        ordered_ids = list(dict.fromkeys(str(item or "").strip() for item in (result_ids or []) if str(item or "").strip()))
        if not ordered_ids:
            raise ValueError("PRICE_APPROVAL_RESULT_SELECTION_REQUIRED")
        items = []
        for result_id in ordered_ids:
            result = cls._price_approval_results.get(result_id)
            try:
                if result is None:
                    raise ValueError("PRICE_APPROVAL_RESULT_NOT_FOUND")
                price = cls._archive_approval_result(result)
                items.append({"resultId": result_id, "status": "SUCCESS", "priceNo": price.priceNo, "errorCode": ""})
            except ValueError as exc:
                items.append({"resultId": result_id, "status": "FAILED", "priceNo": "", "errorCode": str(exc)})
        cls._last_batch_archive_result = {
            "requestedCount": len(items),
            "successCount": sum(item["status"] == "SUCCESS" for item in items),
            "failureCount": sum(item["status"] == "FAILED" for item in items),
            "items": items,
        }
        return cls._last_batch_archive_result

    @classmethod
    def archive_price_approval_preparation(cls, preparation_id, payload, *, user=None):
        """Persist an explicit confirmation through PriceApprovalResult, idempotently."""
        if isinstance(payload,dict) and 'action' in payload:
            from procurement.formal_price_confirmation_service import execute_confirmation
            return execute_confirmation(user=user,preparation_id=preparation_id,payload=payload)
        from procurement.preparation_review_service import is_native
        native = PriceApprovalPreparation.objects.select_related('source_comparison').filter(pk=preparation_id).first() if str(preparation_id).isdigit() else None
        if native is not None and is_native(native):
            from procurement.formal_price_confirmation_service import execute_confirmation
            return execute_confirmation(user=user, preparation_id=native.pk, payload=payload)
        from procurement.price_approval_preparation_service import (
            resolve_price_approval_review_result,
        )

        preparation_key = str(preparation_id or "")
        session_preparation = (next((item for item in cls._source_matched_acceptance_preparations()
            if item["id"] == preparation_key), None)
            if preparation_key.startswith("SESSION-PAP-") else None)
        if session_preparation:
            preparation = session_preparation
            preparation_pk = preparation["id"]
            preparation_no = preparation["approvalPrepareNo"]
            preparation_status = preparation["status"]
            review_result = preparation["reviewResult"]
            reviewer = preparation["reviewer"]
            reviewed_at = preparation["reviewedAt"]
            review_opinion = preparation["reviewOpinion"]
            selected = preparation["selectedSupplier"]
            material_lines = preparation["materialLines"]
            evidence_rows = preparation["sourceQuotationEvidence"]
            original_source_type = preparation["sourceType"]
            original_source_object_id = str(preparation["sourceObjectId"])
            original_source_reference = evidence_rows[0].get("sourceFactReference") or ""
            persistent_preparation = None
        else:
            try:
                preparation = PriceApprovalPreparation.objects.get(pk=preparation_id)
            except (PriceApprovalPreparation.DoesNotExist, TypeError, ValueError):
                raise ValueError("PRICE_APPROVAL_PREPARATION_NOT_FOUND")
            preparation_pk = preparation.pk
            preparation_no = preparation.approval_prepare_no
            preparation_status = preparation.status
            review_result = resolve_price_approval_review_result(preparation)
            reviewer = preparation.reviewer
            reviewed_at = preparation.reviewed_at
            review_opinion = preparation.review_opinion
            selected = preparation.selected_supplier if isinstance(preparation.selected_supplier, dict) else {}
            material_lines = [item for item in (preparation.material_lines or []) if isinstance(item, dict)]
            evidence_rows = [item for item in (preparation.source_quotation_evidence or []) if isinstance(item, dict)]
            original_source_type = preparation.fact_origin
            original_source_object_id = str(preparation.source_projection_id or preparation.source_comparison_id or "")
            original_source_reference = (preparation.source_legacy_comparison_no
                or preparation.source_projection_id or preparation.approval_prepare_no)
            persistent_preparation = preparation

            diagnostic = cls.diagnose_price_approval_preparation(preparation)
            if not diagnostic["canArchive"]:
                raise ValueError(diagnostic["blockReasonCode"])

        if preparation_status not in ("completed", "approved"):
            raise ValueError("PRICE_APPROVAL_PREPARATION_COMPLETED_REQUIRED")
        if review_result != "pass":
            raise ValueError("PRICE_APPROVAL_PREPARATION_PASS_REQUIRED")
        if not str(reviewer or "").strip() or not reviewed_at:
            raise ValueError("PRICE_APPROVAL_MANUAL_CONFIRMATION_REQUIRED")
        if not str(review_opinion or "").strip():
            raise ValueError("PRICE_APPROVAL_REVIEW_OPINION_REQUIRED")

        selected_code = _code(selected.get("supplierCode") or selected.get("supplierId"))
        if not selected_code or len(material_lines) != 1:
            raise ValueError("PRICE_APPROVAL_ARCHIVE_SOURCE_INCOMPLETE")
        material_code = _code(material_lines[0].get("materialCode") or material_lines[0].get("materialId"))
        selected_evidence = next((item for item in evidence_rows
            if _code(item.get("supplierCode") or item.get("supplierId")) == selected_code), None)
        evidence_price = str((selected_evidence or {}).get("unitPrice")
            or (selected_evidence or {}).get("quotationAmount") or "").strip()
        evidence_currency = str((selected_evidence or {}).get("currency") or "").strip()
        supplier_by_id, supplier_by_code, material_by_id, material_by_code = _master_maps()
        supplier = _resolve_master(selected, id_key="supplierId", code_key="supplierCode",
            by_id=supplier_by_id, by_code=supplier_by_code)
        material = _resolve_master(material_lines[0], id_key="materialId", code_key="materialCode",
            by_id=material_by_id, by_code=material_by_code)
        if not supplier:
            raise ValueError("SUPPLIER_MAPPING_FAILED")
        if not material:
            raise ValueError("MATERIAL_MAPPING_FAILED")
        if not _positive_price(evidence_price) or not evidence_currency:
            raise ValueError("PRICE_APPROVAL_APPROVED_PRICE_REQUIRED")

        if original_source_type == "SupplierQuotation":
            matches = [row for row in _quotation_runtime_lines()
                if f"SupplierQuotation:{row[0].quotation_no}:line:{row[1] + 1}" == original_source_reference]
            if len(matches) != 1:
                raise ValueError("SUPPLIER_QUOTATION_SOURCE_NOT_FOUND")
            quotation, _, line, quote_supplier, quote_material = matches[0]
            authoritative_currency = str(line.get("currency") or quotation.currency or "").strip()
            if (quote_supplier.pk != supplier.pk or quote_material.pk != material.pk
                    or str(line.get("unitPrice")) != evidence_price
                    or authoritative_currency != evidence_currency):
                raise ValueError("PRICE_APPROVAL_SOURCE_PRICE_MISMATCH")
            tax_rate, tax_rate_source = _quotation_tax(line)
        else:
            tax_rate = _enterprise_procurement_default_tax_rate()
            tax_rate_source = "EnterpriseProcurementDefaultTaxRate"

        confirmed_at = _business_now()
        approved_at = _business_datetime(reviewed_at)
        effective_date = confirmed_at.date()
        result_no = f"PAR-{preparation_no}"
        price_no = f"SMP-{preparation_no}"
        with transaction.atomic():
            result, _ = PriceApprovalResult.objects.get_or_create(
                preparation_identity=str(preparation_pk),
                defaults={
                    "result_no": result_no, "preparation": persistent_preparation,
                    "original_source_type": original_source_type,
                    "original_source_object_id": original_source_object_id,
                    "original_source_reference": original_source_reference,
                    "source_trace": {"preparationNo": preparation_no,
                        "originalSourceType": original_source_type,
                        "originalSourceReference": original_source_reference},
                    "supplier": supplier, "material": material,
                    "approved_price": Decimal(evidence_price), "currency": evidence_currency,
                    "tax_rate": Decimal(tax_rate), "tax_rate_source": tax_rate_source,
                    "approval_conclusion": "pass", "selected_supplier": selected,
                    "approved_by": str(reviewer), "approved_at": approved_at,
                    "confirmed_by": str(reviewer), "confirmed_at": confirmed_at,
                    "review_opinion": str(review_opinion),
                },
            )
            if (result.supplier_id != supplier.pk or result.material_id != material.pk
                    or result.approved_price != Decimal(evidence_price)
                    or result.original_source_type != original_source_type):
                raise ValueError("PRICE_APPROVAL_RESULT_IDEMPOTENCY_CONFLICT")
            price, _ = SupplierMaterialPrice.objects.get_or_create(
                price_approval_result=result,
                defaults={
                    "price_no": price_no, "supplier": supplier, "material": material,
                    "approved_price": result.approved_price, "currency": result.currency,
                    "tax_rate": result.tax_rate, "tax_rate_source": result.tax_rate_source,
                    "effective_date": effective_date, "expiry_date": None, "status": "ACTIVE",
                    "price_source_type": "PriceApprovalResult", "price_source_label": "人工核价确认",
                    "original_source_type": original_source_type,
                    "original_source_reference": original_source_reference,
                    "approved_by": result.approved_by, "approved_at": result.approved_at,
                    "confirmed_by": result.confirmed_by, "confirmed_at": result.confirmed_at,
                },
            )
        return {
            "preparationId": preparation_pk,
            "approvalPrepareNo": preparation_no,
            "resultId": result.result_no,
            "status": "SUCCESS",
            "priceNo": price.price_no,
            "sourceType": "PriceApprovalResult",
            "effectiveDate": price.effective_date.isoformat(),
        }

    @classmethod
    def _persist_native_price_confirmation(cls, *, preparation, proof, actor, confirmed_at, approved_at):
        """Same persistent archive objects; exact frozen native facts, no inferred tax/date."""
        from workflow_runtime.state_transitions import create_business_object_with_initial_state
        from procurement.formal_price_confirmation_service import CONTRACT
        c=proof['commercial'];terms=c['terms']
        result=PriceApprovalResult.objects.create(
            result_no=f'PAR-{preparation.approval_prepare_no}',preparation=preparation,
            preparation_identity=str(preparation.pk),original_source_type=CONTRACT,
            original_source_object_id=str(preparation.source_comparison_id),
            original_source_reference=proof['source']['quotationNo'],source_trace={},
            supplier_id=c['supplierId'],material_id=c['materialId'],approved_price=Decimal(c['unitPrice']),
            currency=c['currency'],tax_rate=Decimal(terms['taxRate']),tax_rate_source='NATIVE_QUOTATION_LINE',
            approval_conclusion='pass',selected_supplier=preparation.selected_supplier,
            approved_by=str(proof['reviewActorId']),approved_at=approved_at,
            confirmed_by=str(actor.pk),confirmed_at=confirmed_at,review_opinion=preparation.review_opinion)
        price=create_business_object_with_initial_state(model=SupplierMaterialPrice,initial_state='ACTIVE',
            price_no=f'SMP-{preparation.approval_prepare_no}',supplier=result.supplier,material=result.material,
            price_approval_result=result,approved_price=result.approved_price,currency=result.currency,
            tax_rate=result.tax_rate,tax_rate_source=result.tax_rate_source,
            effective_date=date.fromisoformat(terms['effectiveDate']),expiry_date=date.fromisoformat(terms['expiryDate']),
            price_source_type='PriceApprovalResult',price_source_label='原生正式人工价格确认',
            original_source_type=CONTRACT,original_source_reference=proof['source']['quotationNo'],
            approved_by=result.approved_by,approved_at=approved_at,confirmed_by=str(actor.pk),confirmed_at=confirmed_at)
        return result,price

    @classmethod
    def batch_archive_price_approval_preparations(cls, items):
        """Archive preparations independently so one invalid row cannot roll back peers."""
        results = []
        for item in items or []:
            preparation_id = item.get("preparationId") if isinstance(item, dict) else None
            try:
                results.append(cls.archive_price_approval_preparation(preparation_id, item))
            except ValueError as exc:
                error_code = str(exc)
                results.append({
                    "preparationId": preparation_id,
                    "status": "FAILED",
                    "priceNo": "",
                    "errorCode": error_code,
                    "errorMessage": _archive_error_message(error_code),
                })
        if not results:
            raise ValueError("PRICE_APPROVAL_PREPARATION_SELECTION_REQUIRED")
        cls._last_preparation_archive_result = {
            "requestedCount": len(results),
            "successCount": sum(item["status"] == "SUCCESS" for item in results),
            "failureCount": sum(item["status"] == "FAILED" for item in results),
            "items": results,
        }
        return cls._last_preparation_archive_result

    @classmethod
    def confirm_quotation(cls, payload):
        """Backward-compatible single confirmation followed by explicit archiving.

        This does not persist a business object and cannot be consumed by the
        purchase-order resolver. The authoritative quote identity and price are
        always re-read from SupplierQuotation; the page only supplies manual
        effective-price attributes and confirmation evidence.
        """
        result = cls.record_approval_result(payload)
        if result["confirmationResult"] != "ACCEPT":
            raise ValueError("PRICE_CONFIRMATION_ACCEPT_REQUIRED")
        return cls._archive_approval_result(result)

    @classmethod
    def facts(cls):
        models = cls.list_runtime_models()
        candidates = cls._migration_candidates()
        rejected = [item for item in candidates if not item["eligible"]]
        return {
            "models": models,
            "formalPriceCount": len(models),
            "migrationCandidateCount": len(candidates),
            "rejectedCandidateCount": len(rejected),
            "migrationCandidates": candidates,
            "migrationStatus": "ISOLATED" if rejected else "NO_CANDIDATES",
            "sessionConfirmedPriceCount": 0,
            "persistedPriceCount": SupplierMaterialPrice.objects.count(),
            "priceApprovalResultCount": PriceApprovalResult.objects.count(),
            "archiveEligibleResultCount": sum(
                item["confirmationResult"] == "ACCEPT" and item["archiveStatus"] == "PENDING_ARCHIVE"
                for item in cls._price_approval_results.values()
            ),
            "priceApprovalResults": [{
                "resultId": item.result_no,
                "preparationId": item.preparation_identity,
                "sourceType": item.original_source_type,
                "sourceReference": item.original_source_reference,
                "supplierCode": item.supplier.code,
                "materialCode": item.material.code,
                "approvedPrice": str(item.approved_price),
                "currency": item.currency,
                "confirmedBy": item.confirmed_by,
                "confirmedAt": item.confirmed_at.isoformat(),
                "persisted": True,
            } for item in PriceApprovalResult.objects.select_related("supplier", "material")],
            "lastBatchArchiveResult": cls._last_batch_archive_result,
            "lastPreparationArchiveResult": cls._last_preparation_archive_result,
            "sessionPersistence": "DATABASE_PERSISTED",
            "enterpriseProcurementDefaultTaxRate": _enterprise_procurement_default_tax_rate(),
            "enterpriseProcurementDefaultTaxRateSource": "django.conf.settings.PCE_ENTERPRISE_PROCUREMENT_DEFAULT_TAX_RATE",
            "standardTaxRateOptions": list(STANDARD_TAX_RATES),
            "taxMaintenanceAudit": list(cls._tax_maintenance_audit),
            "effectiveDateReconciliation": [{
                "priceId": price.price_no,
                "supplier": price.supplier.name,
                "material": price.material.name,
                "originalSourceType": price.original_source_type,
                "priceApprovalResultId": (price.price_approval_result.result_no
                                          if price.price_approval_result_id else ""),
                "priceConfirmedAt": price.confirmed_at.isoformat(),
                "supplierConfirmedAt": "",
                "approvedAt": price.approved_at.isoformat(),
                "oldEffectiveDate": "",
                "newEffectiveDate": price.effective_date.isoformat(),
                "changed": True,
                "reason": ("报价确认时间优先" if price.price_approval_result_id
                           else "直接采购权限控制的人工维护版本"),
            } for price in SupplierMaterialPrice.objects.select_related(
                "supplier", "material", "price_approval_result")],
            "approvalChain": [
                "OriginalPriceFact",
                "PriceApprovalPreparation",
                "PriceApprovalResult",
                "SupplierMaterialPriceRuntime",
            ],
            "allowedSourceTypes": [
                "SupplierQuotation",
                "legacy_verified_fact",
                "development_test_data",
                "MANUAL_MAINTENANCE",
            ],
            "confirmationResults": [
                "ACCEPT_QUOTATION",
                "REJECT_QUOTATION",
                "REQUEST_RENEGOTIATION",
            ],
            "autoGenerationEnabled": False,
            "maintenanceMode": cls.maintenance_mode,
            "referenceChain": list(cls.reference_chain),
            "businessProgressWriteCount": 0,
        }


SUPPLIER_PRICE_FACT_SOURCE_PRIORITY = (
    "SupplierQuotation",
    "SupplierMaterialPrice",
    "PurchaseOrderHistory",
)

SUPPLIER_PRICE_FACT_STATUS_LABELS = {
    "ACTIVE": "有效报价",
    "PENDING_VALIDITY": "待补有效期",
    "HISTORICAL": "历史执行价",
    "TEST_BASE_PRICE": "测试基础价格",
}


def _date_text(value):
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).strip()


def _integer(value, default=0):
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def _decimal_value(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _decimal_text(value, places="0.0001"):
    return format(_decimal_value(value).quantize(Decimal(places), rounding=ROUND_HALF_UP), "f")


def _change_ratio(current, previous):
    current_value = _decimal_value(current)
    previous_value = _decimal_value(previous)
    if previous_value <= 0:
        return None
    return (current_value - previous_value) / previous_value


def _trend_values(ratio):
    if ratio is None:
        return "NO_BASELINE", "无基准"
    if ratio >= Decimal("0.01"):
        return "UP", "上涨"
    if ratio <= Decimal("-0.01"):
        return "DOWN", "下降"
    return "STABLE", "平稳"


def _parse_fact_date(value):
    try:
        return date.fromisoformat(str(value or ""))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class SupplierPriceFactModel:
    priceFactId: str
    supplierId: int
    supplierCode: str
    supplierName: str
    materialId: int
    materialCode: str
    materialName: str
    unitPrice: str
    currency: str
    unit: str
    taxRate: str
    deliveryPeriod: int
    effectiveDate: str
    expiryDate: str
    sourceType: str
    sourceReference: str
    status: str
    statusLabel: str
    sourcePriority: int
    sourceDetailType: str
    isTestBasePrice: bool = False
    source: str = "SupplierPriceFactRuntime"

    @property
    def uniqueness_key(self):
        return (self.supplierId, self.materialId, self.effectiveDate)

    def to_dict(self):
        return asdict(self)


class PriceReviewRuleRuntime:
    """Generate explainable prompts for manual price review; never a decision."""

    runtime_code = "PriceReviewRuleRuntime"
    rule_version = "PRICE-REVIEW-ASSIST-RULES-V1.0"

    @classmethod
    def evaluate(cls, *, quotation, history_reference, supplier_comparison):
        current_price = _decimal_value(quotation.unitPrice)
        latest_price = _decimal_value(history_reference.get("latestPurchasePrice"))
        lowest_price = _decimal_value(history_reference.get("lowestPurchasePrice"))
        deviation = _decimal_value(supplier_comparison.get("deviationRatio"))
        prompts = []
        rule_catalog = [
            {"ruleCode": "QUOTE_ABOVE_LATEST_20", "threshold": "> 20%", "purpose": "价格上涨风险"},
            {"ruleCode": "QUOTE_BELOW_LOWEST_30", "threshold": "< -30%", "purpose": "异常低价"},
            {"ruleCode": "QUOTE_PEER_AVERAGE_DEVIATION_20", "threshold": "绝对偏离 >= 20%", "purpose": "价格偏离"},
            {"ruleCode": "HISTORY_REFERENCE_INSUFFICIENT", "threshold": "历史样本 >= 1", "purpose": "历史数据完整性"},
            {"ruleCode": "SUPPLIER_COMPARISON_INSUFFICIENT", "threshold": "可比供应商 >= 2", "purpose": "供应商比较完整性"},
        ]

        def append_prompt(rule_code, prompt_type, message, actual, threshold, reference):
            prompts.append({
                "promptId": f"PRA-{quotation.priceFactId}-{rule_code}",
                "ruleCode": rule_code,
                "ruleVersion": cls.rule_version,
                "promptType": prompt_type,
                "message": message,
                "actualValue": _decimal_text(actual),
                "threshold": threshold,
                "referenceValue": _decimal_text(reference) if reference is not None else "",
                "severity": "WARNING",
                "requiresHumanConfirmation": True,
                "decision": None,
            })

        if latest_price > 0:
            latest_change = (current_price - latest_price) / latest_price
            if latest_change > Decimal("0.20"):
                append_prompt(
                    "QUOTE_ABOVE_LATEST_20", "PRICE_INCREASE_RISK",
                    "当前报价高于最近采购价20%，请人工核对报价口径与原因。",
                    latest_change, "> 20%", latest_price,
                )
        else:
            append_prompt(
                "HISTORY_REFERENCE_INSUFFICIENT", "DATA_QUALITY",
                "当前报价缺少同币种、同单位的历史采购价格，请人工核对其他价格证据。",
                history_reference.get("historicalPurchaseCount", 0), "历史样本 >= 1", None,
            )
        if lowest_price > 0:
            lowest_change = (current_price - lowest_price) / lowest_price
            if lowest_change < Decimal("-0.30"):
                append_prompt(
                    "QUOTE_BELOW_LOWEST_30", "ABNORMALLY_LOW_PRICE",
                    "当前报价低于历史最低采购价30%，请人工确认质量、税率和交付范围。",
                    lowest_change, "< -30%", lowest_price,
                )
        if supplier_comparison and abs(deviation) >= Decimal("0.20"):
            append_prompt(
                "QUOTE_PEER_AVERAGE_DEVIATION_20", "PEER_PRICE_DEVIATION",
                "当前供应商报价偏离同口径供应商均价20%，请人工确认可比性。",
                deviation, "绝对偏离 >= 20%",
                supplier_comparison.get("comparisonAveragePrice"),
            )
        if not supplier_comparison or supplier_comparison.get("supplierCandidateCount", 0) < 2:
            append_prompt(
                "SUPPLIER_COMPARISON_INSUFFICIENT", "DATA_QUALITY",
                "同口径可比供应商不足2家，价格比较不能作为供应商选择依据。",
                supplier_comparison.get("supplierCandidateCount", 0) if supplier_comparison else 0,
                "可比供应商 >= 2", None,
            )
        return {
            "runtimeCode": cls.runtime_code,
            "ruleVersion": cls.rule_version,
            "promptCount": len(prompts),
            "ruleCatalog": rule_catalog,
            "prompts": prompts,
            "resultType": "ASSISTIVE_PROMPT_ONLY",
            "automaticDecision": False,
            "automaticSupplierSelection": False,
            "automaticPriceModification": False,
            "automaticPurchaseOrderCreation": False,
            "businessProgressWriteCount": 0,
        }


class SupplierPriceFactRuntime:
    """Read-only facts extending the existing supplier price runtime.

    Raw source candidates remain available in ``historyModels``. ``models``
    contains one canonical fact for each governed effective period.
    """

    runtime_code = "SupplierPriceFactRuntime"
    runtime_model_type = "SupplierPriceFactModel"
    runtime_version = "V1.14.2.8.4.27.2.38"
    intelligence_rule_version = "PRICE-INTELLIGENCE-RULES-V1.0"
    source_priority = SUPPLIER_PRICE_FACT_SOURCE_PRIORITY
    intelligence_extension_points = (
        "PRICE_HISTORY_ANALYSIS",
        "PRICE_TREND_ANALYSIS",
        "PRICE_ANOMALY_DETECTION",
        "SUPPLIER_PRICE_COMPARISON",
    )

    @classmethod
    def _quotation_facts(cls):
        facts = []
        for quotation, line_index, line, supplier, material in _quotation_runtime_lines():
            if not _positive_price(line.get("unitPrice")):
                continue
            effective_date = _date_text(
                line.get("effectiveDate")
                or line.get("validFrom")
                or quotation.received_at
                or quotation.created_at
            )
            expiry_date = _date_text(
                line.get("expiryDate")
                or line.get("validTo")
                or line.get("validityDate")
            )
            status = "ACTIVE" if expiry_date else "PENDING_VALIDITY"
            facts.append(SupplierPriceFactModel(
                priceFactId=f"SPF-SQ-{quotation.pk}-{line_index + 1}",
                supplierId=supplier.pk,
                supplierCode=supplier.code,
                supplierName=supplier.name,
                materialId=material.pk,
                materialCode=material.code,
                materialName=material.name,
                unitPrice=str(line.get("unitPrice")),
                currency=str(line.get("currency") or quotation.currency or "").strip(),
                unit=str(line.get("unit") or material.purchase_unit or material.unit or "").strip(),
                taxRate=str(line.get("taxRate") if line.get("taxRate") not in (None, "") else ""),
                deliveryPeriod=_integer(line.get("deliveryPeriod")),
                effectiveDate=effective_date,
                expiryDate=expiry_date,
                sourceType="SupplierQuotation",
                sourceReference=f"SupplierQuotation:{quotation.quotation_no}:line:{line_index + 1}",
                status=status,
                statusLabel=SUPPLIER_PRICE_FACT_STATUS_LABELS[status],
                sourcePriority=1,
                sourceDetailType="SupplierQuotationItem",
            ))
        return facts

    @classmethod
    def _supplier_material_price_facts(cls):
        facts = []
        material_by_id = {
            item.pk: item
            for item in Material.objects.only("id", "unit", "purchase_unit")
        }
        for price in SupplierMaterialPriceRuntime.list_runtime_models():
            if price.factOrigin == "SESSION_CONFIRMED":
                continue
            material = material_by_id.get(price.materialId)
            facts.append(SupplierPriceFactModel(
                priceFactId=f"SPF-SMP-{price.priceId}",
                supplierId=price.supplierId,
                supplierCode=price.supplierCode,
                supplierName=price.supplierName,
                materialId=price.materialId,
                materialCode=price.materialCode,
                materialName=price.materialName,
                unitPrice=price.unitPrice,
                currency=price.currency,
                unit=str((material.purchase_unit or material.unit) if material else "").strip(),
                taxRate=price.taxRate,
                deliveryPeriod=price.deliveryPeriod,
                effectiveDate=price.effectiveDate,
                expiryDate=price.expiryDate,
                sourceType="SupplierMaterialPrice",
                sourceReference=f"SupplierMaterialPrice:{price.priceId}:{price.sourceReference}",
                status="ACTIVE",
                statusLabel=SUPPLIER_PRICE_FACT_STATUS_LABELS["ACTIVE"],
                sourcePriority=2,
                sourceDetailType=price.sourceType,
            ))
        return facts

    @classmethod
    def _purchase_order_history_facts(cls):
        facts = []
        items = PurchaseOrderItem.objects.filter(
            material__isnull=False,
            unit_price__gt=0,
        ).select_related("po", "po__supplier", "material").order_by("po__order_date", "id")
        for item in items:
            supplier = item.po.supplier
            material = item.material
            effective_date = _date_text(item.po.order_date)
            expected_date = item.expected_date or item.po.expected_date
            delivery_period = (
                max((expected_date - item.po.order_date).days, 0)
                if expected_date and item.po.order_date else 0
            )
            facts.append(SupplierPriceFactModel(
                priceFactId=f"SPF-PO-{item.po_id}-{item.pk}",
                supplierId=supplier.pk,
                supplierCode=supplier.code,
                supplierName=supplier.name,
                materialId=material.pk,
                materialCode=material.code,
                materialName=material.name,
                unitPrice=str(item.unit_price),
                currency="UNKNOWN",
                unit=str(material.purchase_unit or material.unit or "").strip(),
                taxRate="",
                deliveryPeriod=delivery_period,
                effectiveDate=effective_date,
                expiryDate=effective_date,
                sourceType="PurchaseOrderHistory",
                sourceReference=f"PurchaseOrder:{item.po.po_no or item.po_id}:item:{item.pk}",
                status="HISTORICAL",
                statusLabel=SUPPLIER_PRICE_FACT_STATUS_LABELS["HISTORICAL"],
                sourcePriority=3,
                sourceDetailType="PurchaseOrderItem",
            ))
        return facts

    @classmethod
    def history_runtime_models(cls):
        return [
            *cls._quotation_facts(),
            *cls._supplier_material_price_facts(),
            *cls._purchase_order_history_facts(),
        ]

    @classmethod
    def list_runtime_models(cls):
        canonical = {}
        for fact in sorted(
            cls.history_runtime_models(),
            key=lambda item: (item.sourcePriority, item.sourceReference, item.priceFactId),
        ):
            canonical.setdefault(fact.uniqueness_key, fact)
        return sorted(
            canonical.values(),
            key=lambda item: (
                item.supplierCode, item.materialCode, item.effectiveDate,
                item.sourcePriority, item.priceFactId,
            ),
        )

    @classmethod
    def _history_analysis(cls, history_models):
        purchase_history = [
            item for item in history_models
            if item.sourceType == "PurchaseOrderHistory"
            and _decimal_value(item.unitPrice) > 0
            and _parse_fact_date(item.effectiveDate)
        ]
        groups = defaultdict(list)
        for item in purchase_history:
            groups[(
                item.supplierId, item.materialId,
                item.currency or "UNKNOWN", item.unit,
            )].append(item)

        analyses = []
        history_rows = []
        for group_key, rows in sorted(groups.items(), key=lambda entry: entry[0]):
            ordered = sorted(rows, key=lambda item: (
                item.effectiveDate, item.sourceReference, item.priceFactId,
            ))
            prices = [_decimal_value(item.unitPrice) for item in ordered]
            first = ordered[0]
            latest = ordered[-1]
            previous = ordered[-2] if len(ordered) > 1 else None
            latest_change = _change_ratio(latest.unitPrice, previous.unitPrice if previous else None)
            overall_change = _change_ratio(latest.unitPrice, first.unitPrice)
            trend_code, trend_label = _trend_values(latest_change)
            analysis_id = (
                f"SPA-{first.supplierCode}-{first.materialCode}-"
                f"{first.currency or 'UNKNOWN'}-{first.unit or 'UNKNOWN'}"
            )
            analyses.append({
                "analysisId": analysis_id,
                "supplierId": first.supplierId,
                "supplierCode": first.supplierCode,
                "supplierName": first.supplierName,
                "materialId": first.materialId,
                "materialCode": first.materialCode,
                "materialName": first.materialName,
                "currency": first.currency or "UNKNOWN",
                "unit": first.unit,
                "sampleCount": len(ordered),
                "lowestPurchasePrice": _decimal_text(min(prices)),
                "latestPurchasePrice": _decimal_text(latest.unitPrice),
                "averagePurchasePrice": _decimal_text(sum(prices) / len(prices)),
                "previousPurchasePrice": _decimal_text(previous.unitPrice) if previous else "",
                "priceChangeRatio": _decimal_text(latest_change) if latest_change is not None else "",
                "overallChangeRatio": _decimal_text(overall_change) if overall_change is not None else "",
                "trendCode": trend_code,
                "trendLabel": trend_label,
                "firstPurchaseDate": first.effectiveDate,
                "latestPurchaseDate": latest.effectiveDate,
                "sourceType": "PurchaseOrderHistory",
                "ruleVersion": cls.intelligence_rule_version,
                "analysisStatus": "AVAILABLE" if len(ordered) >= 2 else "INSUFFICIENT_DATA",
                "analysisStatusLabel": "可分析" if len(ordered) >= 2 else "样本不足",
                "readOnly": True,
            })
            previous_row = None
            for index, item in enumerate(ordered):
                row_change = _change_ratio(
                    item.unitPrice,
                    previous_row.unitPrice if previous_row else None,
                )
                row_trend_code, row_trend_label = _trend_values(row_change)
                history_rows.append({
                    **item.to_dict(),
                    "historySequence": index + 1,
                    "analysisId": analysis_id,
                    "previousPrice": _decimal_text(previous_row.unitPrice) if previous_row else "",
                    "changeRatio": _decimal_text(row_change) if row_change is not None else "",
                    "trendCode": row_trend_code,
                    "trendLabel": row_trend_label,
                    "ruleVersion": cls.intelligence_rule_version,
                    "readOnly": True,
                })
                previous_row = item
        return analyses, history_rows

    @classmethod
    def _supplier_comparisons(cls, history_models):
        latest_by_supplier = {}
        for item in history_models:
            if _decimal_value(item.unitPrice) <= 0 or not _parse_fact_date(item.effectiveDate):
                continue
            key = (
                item.materialId, item.currency or "UNKNOWN", item.unit,
                item.supplierId,
            )
            current = latest_by_supplier.get(key)
            if current is None or (
                item.effectiveDate, -item.sourcePriority, item.sourceReference,
            ) > (
                current.effectiveDate, -current.sourcePriority, current.sourceReference,
            ):
                latest_by_supplier[key] = item

        comparison_groups = defaultdict(list)
        for key, item in latest_by_supplier.items():
            comparison_groups[key[:3]].append(item)

        rows = []
        for group_key, candidates in sorted(comparison_groups.items(), key=lambda entry: entry[0]):
            prices = [_decimal_value(item.unitPrice) for item in candidates]
            average = sum(prices) / len(prices)
            lowest = min(prices)
            for item in sorted(candidates, key=lambda value: (
                _decimal_value(value.unitPrice), value.supplierCode,
            )):
                deviation = (
                    (_decimal_value(item.unitPrice) - average) / average
                    if average > 0 else None
                )
                rows.append({
                    "comparisonId": f"SPC-{item.materialCode}-{item.currency or 'UNKNOWN'}-{item.supplierCode}",
                    "materialId": item.materialId,
                    "materialCode": item.materialCode,
                    "materialName": item.materialName,
                    "supplierId": item.supplierId,
                    "supplierCode": item.supplierCode,
                    "supplierName": item.supplierName,
                    "unitPrice": _decimal_text(item.unitPrice),
                    "currency": item.currency or "UNKNOWN",
                    "unit": item.unit,
                    "effectiveDate": item.effectiveDate,
                    "sourceType": item.sourceType,
                    "sourceReference": item.sourceReference,
                    "supplierCandidateCount": len(candidates),
                    "comparisonAveragePrice": _decimal_text(average),
                    "comparisonLowestPrice": _decimal_text(lowest),
                    "deviationRatio": _decimal_text(deviation) if deviation is not None else "",
                    "isLowestReference": _decimal_value(item.unitPrice) == lowest,
                    "comparisonStatus": "COMPARABLE" if len(candidates) >= 2 else "INSUFFICIENT_DATA",
                    "comparisonStatusLabel": "可比较" if len(candidates) >= 2 else "候选不足",
                    "decision": None,
                    "readOnly": True,
                })
        return rows

    @classmethod
    def _anomaly_analysis(cls, history_analyses, comparison_rows):
        rules = [
            {"ruleCode": "PRICE_INCREASE_20", "name": "异常上涨", "threshold": ">= 20%", "minimumSamples": 2},
            {"ruleCode": "PRICE_DECREASE_20", "name": "异常下降", "threshold": "<= -20%", "minimumSamples": 2},
            {"ruleCode": "PRICE_LOW_DEVIATION_30", "name": "异常低价", "threshold": "<= 同物料均价 -30%", "minimumSamples": 3},
            {"ruleCode": "PRICE_HIGH_DEVIATION_30", "name": "异常高价", "threshold": ">= 同物料均价 +30%", "minimumSamples": 3},
            {"ruleCode": "PRICE_STALE_180_DAYS", "name": "长期无价格更新", "threshold": "> 180天", "minimumSamples": 1},
        ]
        anomalies = []
        latest_dates = [
            _parse_fact_date(item.get("latestPurchaseDate"))
            for item in history_analyses
            if _parse_fact_date(item.get("latestPurchaseDate"))
        ]
        reference_date = max(latest_dates) if latest_dates else None
        for item in history_analyses:
            ratio = _decimal_value(item.get("priceChangeRatio"))
            if item.get("sampleCount", 0) >= 2 and ratio >= Decimal("0.20"):
                anomalies.append(cls._anomaly_row(item, "PRICE_INCREASE_20", "异常上涨", ratio))
            if item.get("sampleCount", 0) >= 2 and ratio <= Decimal("-0.20"):
                anomalies.append(cls._anomaly_row(item, "PRICE_DECREASE_20", "异常下降", ratio))
            latest_date = _parse_fact_date(item.get("latestPurchaseDate"))
            if reference_date and latest_date and reference_date - latest_date > timedelta(days=180):
                anomalies.append(cls._anomaly_row(
                    item, "PRICE_STALE_180_DAYS", "长期无价格更新",
                    None, days_since_update=(reference_date - latest_date).days,
                ))
        for item in comparison_rows:
            if item.get("supplierCandidateCount", 0) < 3:
                continue
            deviation = _decimal_value(item.get("deviationRatio"))
            if deviation <= Decimal("-0.30"):
                anomalies.append(cls._comparison_anomaly_row(item, "PRICE_LOW_DEVIATION_30", "异常低价", deviation))
            if deviation >= Decimal("0.30"):
                anomalies.append(cls._comparison_anomaly_row(item, "PRICE_HIGH_DEVIATION_30", "异常高价", deviation))
        return rules, anomalies, reference_date.isoformat() if reference_date else ""

    @classmethod
    def _anomaly_row(cls, item, rule_code, anomaly_label, ratio, days_since_update=0):
        return {
            "anomalyId": f"SPA-{rule_code}-{item['analysisId']}",
            "ruleCode": rule_code,
            "ruleVersion": cls.intelligence_rule_version,
            "anomalyType": anomaly_label,
            "supplierCode": item["supplierCode"],
            "supplierName": item["supplierName"],
            "materialCode": item["materialCode"],
            "materialName": item["materialName"],
            "currentPrice": item["latestPurchasePrice"],
            "referencePrice": item["previousPurchasePrice"],
            "changeRatio": _decimal_text(ratio) if ratio is not None else "",
            "effectiveDate": item["latestPurchaseDate"],
            "sourceType": "PurchaseOrderHistory",
            "daysSinceUpdate": days_since_update,
            "severity": "WARNING",
            "explanation": "仅作价格提醒，必须人工核对来源与口径。",
            "decision": None,
            "readOnly": True,
        }

    @classmethod
    def _comparison_anomaly_row(cls, item, rule_code, anomaly_label, ratio):
        return {
            "anomalyId": f"SPA-{rule_code}-{item['comparisonId']}",
            "ruleCode": rule_code,
            "ruleVersion": cls.intelligence_rule_version,
            "anomalyType": anomaly_label,
            "supplierCode": item["supplierCode"],
            "supplierName": item["supplierName"],
            "materialCode": item["materialCode"],
            "materialName": item["materialName"],
            "currentPrice": item["unitPrice"],
            "referencePrice": item["comparisonAveragePrice"],
            "changeRatio": _decimal_text(ratio),
            "effectiveDate": item["effectiveDate"],
            "sourceType": item["sourceType"],
            "daysSinceUpdate": 0,
            "severity": "WARNING",
            "explanation": "仅作同物料价格偏离提醒，不构成供应商选择。",
            "decision": None,
            "readOnly": True,
        }

    @classmethod
    def intelligence_analysis(cls, history_models, models, conflicts):
        history_analyses, price_history_rows = cls._history_analysis(history_models)
        comparison_rows = cls._supplier_comparisons(history_models)
        anomaly_rules, anomalies, reference_date = cls._anomaly_analysis(
            history_analyses, comparison_rows,
        )
        source_counts = {
            source_type: sum(item.sourceType == source_type for item in history_models)
            for source_type in cls.source_priority
        }
        quality = {
            "supplierCount": len({item.supplierId for item in history_models}),
            "materialCount": len({item.materialId for item in history_models}),
            "priceFactCount": len(models),
            "historyPriceCount": sum(
                item.sourceType == "PurchaseOrderHistory" for item in history_models
            ),
            "sourceTypes": list(cls.source_priority),
            "sourceCounts": source_counts,
            "missingEffectiveDateCount": sum(not item.effectiveDate for item in history_models),
            "missingExpiryDateCount": sum(not item.expiryDate for item in history_models),
            "duplicatePriceCount": len(conflicts),
            "anomalyPriceCount": len(anomalies),
            "historyAnalysisCount": len(history_analyses),
            "supplierComparisonCount": len(comparison_rows),
            "qualityStatus": "PASS",
        }
        return {
            "quality": quality,
            "historyAnalyses": history_analyses,
            "priceHistoryRows": price_history_rows,
            "supplierComparisons": comparison_rows,
            "anomalyRules": anomaly_rules,
            "anomalies": anomalies,
            "anomalyCount": len(anomalies),
            "analysisReferenceDate": reference_date,
            "ruleVersion": cls.intelligence_rule_version,
            "analysisMode": "READ_ONLY_REFERENCE",
            "automaticSupplierSelection": False,
            "automaticPriceDecision": False,
            "automaticPurchaseOrderCreation": False,
            "businessProgressWriteCount": 0,
        }

    @classmethod
    def purchase_price_review_contexts(cls, history_models, intelligence_analysis):
        relations = MaterialSupplierRelationRuntime.list_runtime_models()
        relation_map = {
            (item.supplierId, item.materialId): item
            for item in relations
        }
        history_map = {
            (
                item["supplierId"], item["materialId"],
                item["currency"], item["unit"],
            ): item
            for item in intelligence_analysis["historyAnalyses"]
        }
        comparison_groups = defaultdict(list)
        for item in intelligence_analysis["supplierComparisons"]:
            comparison_groups[(
                item["materialId"], item["currency"], item["unit"],
            )].append(item)

        contexts = []
        quotations = [item for item in history_models if item.sourceType == "SupplierQuotation"]
        for quotation in quotations:
            comparison_rows = comparison_groups.get((
                quotation.materialId, quotation.currency or "UNKNOWN", quotation.unit,
            ), [])
            current_comparison = next((
                item for item in comparison_rows
                if item["supplierId"] == quotation.supplierId
            ), {})
            history = history_map.get((
                quotation.supplierId, quotation.materialId,
                quotation.currency or "UNKNOWN", quotation.unit,
            ), {})
            relation = relation_map.get((quotation.supplierId, quotation.materialId))
            history_reference = {
                "lowestPurchasePrice": history.get("lowestPurchasePrice", ""),
                "latestPurchasePrice": history.get("latestPurchasePrice", ""),
                "averagePurchasePrice": history.get("averagePurchasePrice", ""),
                "historicalPurchaseCount": history.get("sampleCount", 0),
                "latestPurchaseDate": history.get("latestPurchaseDate", ""),
                "trendCode": history.get("trendCode", "INSUFFICIENT_DATA"),
                "trendLabel": history.get("trendLabel", "样本不足"),
                "analysisStatus": history.get("analysisStatus", "INSUFFICIENT_DATA"),
                "source": "SupplierPriceFactRuntime.intelligenceAnalysis",
            }
            rule_assist = PriceReviewRuleRuntime.evaluate(
                quotation=quotation,
                history_reference=history_reference,
                supplier_comparison=current_comparison,
            )
            contexts.append({
                "reviewContextId": f"PPRC-{quotation.priceFactId}",
                "objectType": "PurchasePriceReviewContext",
                "contextVersion": cls.runtime_version,
                "caseMarker": "TEST_CASE",
                "currentQuotationFact": quotation.to_dict(),
                "historicalPriceReference": history_reference,
                "supplierComparison": {
                    "currentSupplier": current_comparison,
                    "candidates": comparison_rows,
                    "candidateCount": len(comparison_rows),
                    "source": "SupplierPriceFactRuntime.intelligenceAnalysis",
                },
                "supplierPerformance": {
                    "relationCode": getattr(relation, "relationCode", ""),
                    "deliveryPeriod": getattr(relation, "deliveryPeriod", None),
                    "deliveryPeriodLabel": getattr(relation, "deliveryPeriodLabel", "-"),
                    "qualityLevel": getattr(relation, "qualityLevel", "待评估"),
                    "onTimeRate": getattr(relation, "onTimeRate", None),
                    "onTimeRateLabel": getattr(relation, "onTimeRateLabel", "-"),
                    "source": "MaterialSupplierRelationRuntime",
                },
                "ruleAssist": rule_assist,
                "purchasePriceDecisionContext": {
                    "objectType": "PurchasePriceDecisionContext",
                    "decisionStatus": "PENDING_MANUAL_CONFIRMATION",
                    "decisionStatusLabel": "待人工确认",
                    "reviewOpinion": "",
                    "confirmedBy": "",
                    "confirmedAt": "",
                    "confirmationResult": "",
                    "auditMode": "memory_session_only",
                    "persisted": False,
                    "isBusinessDecision": False,
                    "businessStateAdvanced": False,
                    "businessProgressWriteCount": 0,
                },
                "source": "SupplierPriceFactRuntime",
                "automaticPriceDecision": False,
                "automaticSupplierSelection": False,
                "automaticPriceModification": False,
                "automaticPurchaseOrderCreation": False,
                "businessProgressWriteCount": 0,
            })
        return contexts

    @classmethod
    def facts(cls):
        history_models = cls.history_runtime_models()
        models = cls.list_runtime_models()
        canonical_ids = {item.priceFactId for item in models}
        conflicts = [item for item in history_models if item.priceFactId not in canonical_ids]
        source_counts = {
            source_type: sum(item.sourceType == source_type for item in history_models)
            for source_type in cls.source_priority
        }
        intelligence_analysis = cls.intelligence_analysis(history_models, models, conflicts)
        price_review_contexts = cls.purchase_price_review_contexts(
            history_models, intelligence_analysis,
        )
        return {
            "models": models,
            "historyModels": history_models,
            "duplicateEffectivePeriodCandidates": conflicts,
            "priceFactCount": len(models),
            "historyFactCount": len(history_models),
            "duplicateEffectivePeriodCount": len(conflicts),
            "sourcePriority": list(cls.source_priority),
            "sourceCounts": source_counts,
            "intelligenceExtensionPoints": list(cls.intelligence_extension_points),
            "intelligenceAnalysis": intelligence_analysis,
            "purchasePriceReviewContexts": price_review_contexts,
            "purchasePriceReviewContextCount": len(price_review_contexts),
            "autoDecisionEnabled": False,
            "businessProgressWriteCount": 0,
        }


@dataclass(frozen=True)
class MasterDataStatisticsRuntimeModel:
    materialCount: int
    supplierCount: int
    supplierMaterialRelationCount: int
    supplierPriceCount: int
    source: str = "MasterDataStatisticsRuntime"

    def to_dict(self):
        return asdict(self)


class MasterDataStatisticsRuntime:
    runtime_code = "MasterDataStatisticsRuntime"
    version = "V1.14.2.8.4.27.2.30"

    @classmethod
    def facts(cls):
        model = MasterDataStatisticsRuntimeModel(
            materialCount=len(MaterialMasterRuntimeAdapter.list_runtime_models()),
            supplierCount=len(SupplierMasterRuntimeAdapter.list_runtime_models()),
            supplierMaterialRelationCount=len(
                MaterialSupplierRelationRuntime.list_runtime_models()
            ),
            supplierPriceCount=len(SupplierMaterialPriceRuntime.list_runtime_models()),
        )
        return {
            **model.to_dict(),
            "runtimeCode": cls.runtime_code,
            "runtimeVersion": cls.version,
            "countSources": {
                "materialCount": "MaterialMasterRuntimeAdapter",
                "supplierCount": "SupplierMasterRuntimeAdapter",
                "supplierMaterialRelationCount": MaterialSupplierRelationRuntime.runtime_code,
                "supplierPriceCount": SupplierMaterialPriceRuntime.runtime_code,
            },
            "businessProgressWriteCount": 0,
        }
