"""Read-only SupplierMaster runtime and business-reference mapping."""

from collections import defaultdict
from dataclasses import asdict, dataclass

from django.db.models import Count


def _mask_phone(value):
    text = str(value or "").strip()
    if len(text) < 7:
        return text
    return f"{text[:3]}****{text[-4:]}"


@dataclass(frozen=True)
class SupplierMasterRuntimeModel:
    supplierId: int
    supplierCode: str
    supplierName: str
    contactName: str
    contactPhone: str
    address: str
    deliveryAddress: str
    category: str
    businessStatus: str
    supplierLevel: str
    performanceLevel: str
    usageCount: int
    usageModules: tuple
    mappingStatus: str
    fieldCompleteness: str
    missingFields: tuple
    duplicateReviewStatus: str = "无需审核"
    settlementReference: str = "SCM供应商结算"
    performanceReference: str = "SCM供应商绩效"

    def to_dict(self):
        value = asdict(self)
        value["usageModules"] = list(self.usageModules)
        value["missingFields"] = list(self.missingFields)
        value["supplierSourceTrace"] = {
            "source": "SupplierMaster",
            "domain": "procurement.Supplier",
            "databaseTable": "supplier",
            "businessKey": self.supplierCode,
        }
        return value


class SupplierBusinessMapping:
    """Strictly map persisted business supplier identities to SupplierMaster."""

    runtime_code = "SupplierBusinessMapping"

    @staticmethod
    def _resolve(*, supplier_id=None, supplier_code="", supplier_name=""):
        from procurement.models import Supplier, SupplierBusinessReferenceMapping

        candidates = None
        if supplier_id not in (None, "") and str(supplier_id).isdigit():
            candidates = Supplier.objects.filter(pk=int(supplier_id))
        if supplier_code:
            by_code = Supplier.objects.filter(code=str(supplier_code).strip())
            if not by_code.exists():
                mapped_ids = SupplierBusinessReferenceMapping.objects.filter(
                    legacy_supplier_code=str(supplier_code).strip(),
                    evidence_status="UNIQUE_CONFIRMED",
                ).values("supplier_id")
                by_code = Supplier.objects.filter(pk__in=mapped_ids)
            candidates = by_code if candidates is None else candidates.filter(pk__in=by_code.values("pk"))
        if supplier_name:
            by_name = Supplier.objects.filter(name=str(supplier_name).strip())
            candidates = by_name if candidates is None else candidates.filter(pk__in=by_name.values("pk"))
        if candidates is None or candidates.count() != 1:
            return None
        return candidates.first()

    @classmethod
    def scan(cls):
        from procurement.models import (
            PriceApproval, PurchaseInquiry, PurchaseOrder, PurchaseRequestItem,
            PriceApprovalPreparation, QuoteComparisonFact, Supplier,
            SupplierBusinessReferenceMapping, SupplierDuplicateReview, SupplierQuotation,
        )

        usage = defaultdict(lambda: {"count": 0, "modules": set()})
        unresolved = []

        def record(module, *, supplier_id=None, supplier_code="", supplier_name="", object_no=""):
            if supplier_id in (None, "") and not supplier_code and not supplier_name:
                return
            supplier = cls._resolve(
                supplier_id=supplier_id, supplier_code=supplier_code,
                supplier_name=supplier_name,
            )
            if supplier is None:
                unresolved.append({
                    "module": module,
                    "supplierId": supplier_id,
                    "supplierCode": supplier_code,
                    "supplierName": supplier_name,
                    "sourceObjectNo": object_no,
                    "reason": "无法唯一映射SupplierMaster",
                })
                return
            usage[supplier.pk]["count"] += 1
            usage[supplier.pk]["modules"].add(module)

        for item in PurchaseRequestItem.objects.select_related("suggested_supplier", "purchase_request"):
            record(
                "PurchaseRequest", supplier_id=item.suggested_supplier_id,
                supplier_code=item.suggested_supplier_code,
                supplier_name=item.suggested_supplier_name,
                object_no=item.purchase_request.request_no,
            )
        for inquiry in PurchaseInquiry.objects.all():
            record("PurchaseInquiry", supplier_code=inquiry.supplier, object_no=inquiry.inquiry_no)
            source = inquiry.quotation if isinstance(inquiry.quotation, dict) else {}
            for candidate in source.get("supplierCandidates", source.get("suppliers", [])) or []:
                if isinstance(candidate, dict):
                    record(
                        "PurchaseInquiry", supplier_id=candidate.get("supplierId"),
                        supplier_code=candidate.get("supplierCode", ""),
                        supplier_name=candidate.get("supplierName", ""),
                        object_no=inquiry.inquiry_no,
                    )
        for quotation in SupplierQuotation.objects.all():
            identity = str(quotation.supplier_id or "").strip()
            record(
                "SupplierQuote", supplier_id=identity if identity.isdigit() else None,
                supplier_code="" if identity.isdigit() else identity,
                supplier_name=quotation.supplier_name,
                object_no=quotation.quotation_no,
            )
        for comparison in QuoteComparisonFact.objects.all():
            for evidence in comparison.supplier_quote_evidence or []:
                if isinstance(evidence, dict):
                    record(
                        "QuoteComparison", supplier_id=evidence.get("supplierId"),
                        supplier_code=evidence.get("supplierCode", ""),
                        supplier_name=evidence.get("supplierName", ""),
                        object_no=comparison.comparison_no,
                    )
        for approval in PriceApproval.objects.all():
            identity = str(approval.supplier or "").strip()
            record(
                "PriceApproval", supplier_id=identity if identity.isdigit() else None,
                supplier_code="" if identity.isdigit() else identity,
                object_no=approval.approval_no,
            )
        for preparation in PriceApprovalPreparation.objects.all():
            for candidate in preparation.supplier_candidates or []:
                if isinstance(candidate, dict):
                    record("PriceApprovalPreparation", supplier_id=candidate.get("supplierId"),
                           supplier_code=candidate.get("supplierCode", ""),
                           supplier_name=candidate.get("supplierName", ""),
                           object_no=preparation.approval_prepare_no)
            selected = preparation.selected_supplier if isinstance(preparation.selected_supplier, dict) else {}
            record("PriceApprovalSelection", supplier_id=selected.get("supplierId"),
                   supplier_code=selected.get("supplierCode", ""),
                   supplier_name=selected.get("supplierName", ""),
                   object_no=preparation.approval_prepare_no)
        for order in PurchaseOrder.objects.select_related("supplier"):
            record(
                "PurchaseOrder", supplier_id=order.supplier_id,
                supplier_code=order.supplier.code,
                supplier_name=order.supplier.name,
                object_no=order.po_no,
            )

        duplicate_codes = list(
            Supplier.objects.values("code").annotate(count=Count("id")).filter(count__gt=1)
        )
        duplicate_names = list(
            Supplier.objects.values("name").annotate(count=Count("id")).filter(count__gt=1)
        )
        duplicate_reviews = list(
            SupplierDuplicateReview.objects.order_by("supplier_code").values(
                "supplier_id", "supplier_code", "supplier_name",
                "duplicate_reason", "status",
            )
        )
        reviewed_supplier_ids = {
            row["supplier_id"] for row in duplicate_reviews
            if row["status"] == SupplierDuplicateReview.STATUS_PENDING
        }
        duplicate_supplier_ids = set(
            Supplier.objects.filter(
                name__in=[row["name"] for row in duplicate_names]
            ).values_list("id", flat=True)
        )
        return {
            "usage": usage,
            "unresolved": unresolved,
            "duplicateCodes": duplicate_codes,
            "duplicateNames": duplicate_names,
            "duplicateReviews": duplicate_reviews,
            "duplicateReviewMissingSupplierIds": sorted(
                duplicate_supplier_ids - reviewed_supplier_ids
            ),
            "explicitMappings": list(SupplierBusinessReferenceMapping.objects.select_related("supplier")
                .values("legacy_supplier_code", "legacy_supplier_name", "supplier_id",
                        "supplier__code", "supplier__name", "evidence_status", "source_version")),
        }


class SupplierMasterRuntimeAdapter:
    runtime_model_type = "SupplierMasterRuntimeModel"
    runtime_adapter_code = "SupplierMasterRuntimeAdapter"
    database_table = "supplier"

    @classmethod
    def list_runtime_models(cls):
        from procurement.models import Supplier

        mapping = SupplierBusinessMapping.scan()
        rows = []
        for supplier in Supplier.objects.order_by("code", "id"):
            missing = []
            if not str(supplier.contact_person or "").strip() or supplier.contact_person == "未维护":
                missing.append("联系人")
            if not str(supplier.contact_phone or "").strip() or supplier.contact_phone == "未维护":
                missing.append("联系电话")
            if not str(supplier.address or "").strip() or supplier.address == "未维护":
                missing.append("地址")
            if (
                not str(supplier.delivery_address or "").strip()
                or supplier.delivery_address == "未维护"
            ):
                missing.append("送货地址")
            if not str(supplier.category or "").strip() or supplier.category == "未分类":
                missing.append("分类")
            business = mapping["usage"].get(supplier.pk, {"count": 0, "modules": set()})
            duplicate_review = next(
                (
                    row for row in mapping["duplicateReviews"]
                    if row["supplier_id"] == supplier.pk
                ),
                None,
            )
            rows.append(SupplierMasterRuntimeModel(
                supplierId=supplier.pk,
                supplierCode=supplier.code,
                supplierName=supplier.name,
                contactName=supplier.contact_person or "未维护",
                contactPhone=_mask_phone(supplier.contact_phone) or "未维护",
                address=supplier.address or "未维护",
                deliveryAddress=supplier.delivery_address or "未维护",
                category=supplier.category,
                businessStatus="启用" if supplier.is_active else "停用",
                supplierLevel=supplier.credit_rating,
                performanceLevel=supplier.credit_rating,
                usageCount=business["count"],
                usageModules=tuple(sorted(business["modules"])),
                mappingStatus="已映射" if business["count"] else "未被测试业务引用",
                fieldCompleteness="完整" if not missing else "待补全",
                missingFields=tuple(missing),
                duplicateReviewStatus=(
                    duplicate_review["status"] if duplicate_review else "无需审核"
                ),
            ))
        return rows

    @classmethod
    def facts(cls):
        mapping = SupplierBusinessMapping.scan()
        models = cls.list_runtime_models()
        return {
            "models": models,
            "businessUsageCount": sum(item.usageCount for item in models),
            "mappedSupplierCount": sum(1 for item in models if item.usageCount > 0),
            "unresolved": mapping["unresolved"],
            "duplicateCodes": mapping["duplicateCodes"],
            "duplicateNames": mapping["duplicateNames"],
            "duplicateReviews": mapping["duplicateReviews"],
            "duplicateReviewMissingSupplierIds": mapping["duplicateReviewMissingSupplierIds"],
            "fieldIncompleteCount": sum(1 for item in models if item.fieldCompleteness != "完整"),
            "supplierFieldCompleteGate": (
                "PASS" if all(item.fieldCompleteness == "完整" for item in models) else "FAIL"
            ),
            "supplierDuplicateReviewGate": (
                "PASS" if not mapping["duplicateReviewMissingSupplierIds"] else "FAIL"
            ),
            "supplierDeliveryAddressGate": (
                "PASS" if all(item.deliveryAddress != "未维护" for item in models) else "FAIL"
            ),
        }
