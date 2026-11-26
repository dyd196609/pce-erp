"""Canonical read-only MaterialSupplierRelation projection from persisted facts."""

from dataclasses import asdict, dataclass, replace

from procurement.models import (
    PriceApproval,
    PriceApprovalPreparation,
    PurchaseInquiry,
    PurchaseOrder,
    PurchaseRequestItem,
    QuoteComparisonFact,
    Supplier,
    SupplierQuotation,
)

from .models import Material, SupplierMaterialPrice


SOURCE_PRIORITY = {
    "SupplierRecommendation": 1,
    "PriceApproval": 2,
    "ManualPriceMaintenance": 2,
    "QuoteComparison": 3,
    "SupplierQuotation": 3,
    "PurchaseOrder": 4,
}
ALL_SOURCE_MODULES = (
    "PurchaseRequest",
    "PurchaseInquiry",
    "SupplierQuotation",
    "QuoteComparison",
    "PriceApproval",
    "ManualPriceMaintenance",
    "SupplierRecommendation",
    "PurchaseOrderGate",
    "PurchaseOrder",
)


def _text(value):
    return str(value or "").strip()


def _positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _percentage(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if 0 <= result <= 100 else None


@dataclass(frozen=True)
class MaterialSupplierRelation:
    relationCode: str
    materialId: int
    materialCode: str
    materialName: str
    materialDisplay: str
    supplierId: int
    supplierCode: str
    supplierName: str
    supplierDisplay: str
    isMainSupplier: bool
    isMainSupplierLabel: str
    priority: int
    deliveryPeriod: object
    deliveryPeriodLabel: str
    deliveryPeriodSource: str
    qualityLevel: str
    onTimeRate: object
    onTimeRateLabel: str
    status: str
    statusLabel: str
    sourceReference: str
    sourceModules: tuple
    businessUsageCount: int
    quoteCount: int
    recommendationCount: int
    purchaseOrderReferenceCount: int
    source: str = "MaterialSupplierRelationRuntime"

    def to_dict(self):
        payload = asdict(self)
        payload["sourceModules"] = list(self.sourceModules)
        return payload


class MaterialSupplierUsageMatrix:
    """Scan persisted procurement facts without changing any business object."""

    def __init__(self):
        self.materials = list(Material.objects.only("id", "code", "name"))
        self.suppliers = list(Supplier.objects.only("id", "code", "name"))
        self.material_by_id = {str(item.pk): item for item in self.materials}
        self.material_by_code = {item.code: item for item in self.materials}
        self.supplier_by_id = {str(item.pk): item for item in self.suppliers}
        self.supplier_by_code = {item.code: item for item in self.suppliers}
        self.valid = {}
        self.unresolved = []
        self.source_summary = {module: 0 for module in ALL_SOURCE_MODULES}

    def _resolve(self, *, code, identity, by_code, by_id):
        code_value = _text(code)
        identity_value = _text(identity)
        code_match = by_code.get(code_value) if code_value else None
        id_match = by_id.get(identity_value) if identity_value else None
        if code_value and code_match is None:
            return None, f"业务编码未严格匹配主数据：{code_value}"
        if identity_value and identity_value.isdigit() and id_match is None:
            return None, f"业务主键未匹配主数据：{identity_value}"
        if code_match and id_match and code_match.pk != id_match.pk:
            return None, "业务编码与业务主键指向不同主数据"
        resolved = code_match or id_match
        if resolved is None:
            return None, "缺少可验证的正式编码或主键"
        return resolved, ""

    def add(
        self, *, module, reference, material_code="", material_id=None,
        material_name="", supplier_code="", supplier_id=None,
        supplier_name="", delivery_period=None, explicit_main=False,
        quality_level="", on_time_rate=None,
    ):
        self.source_summary[module] = self.source_summary.get(module, 0) + 1
        material, material_reason = self._resolve(
            code=material_code, identity=material_id,
            by_code=self.material_by_code, by_id=self.material_by_id,
        )
        supplier, supplier_reason = self._resolve(
            code=supplier_code, identity=supplier_id,
            by_code=self.supplier_by_code, by_id=self.supplier_by_id,
        )
        if material is None or supplier is None:
            self.unresolved.append({
                "materialCode": _text(material_code),
                "materialName": _text(material_name),
                "supplierCode": _text(supplier_code),
                "supplierName": _text(supplier_name),
                "sourceModule": module,
                "sourceReference": reference,
                "mappingStatus": "待人工确认",
                "reason": material_reason or supplier_reason,
            })
            return
        key = (material.code, supplier.code)
        row = self.valid.setdefault(key, {
            "material": material,
            "supplier": supplier,
            "sources": [],
            "quoteCount": 0,
            "recommendationCount": 0,
            "purchaseOrderReferenceCount": 0,
        })
        source = {
            "module": module,
            "reference": reference,
            "priority": SOURCE_PRIORITY.get(module),
            "deliveryPeriod": _positive_int(delivery_period),
            "explicitMain": bool(explicit_main),
            "qualityLevel": _text(quality_level),
            "onTimeRate": _percentage(on_time_rate),
        }
        row["sources"].append(source)
        if module == "SupplierQuotation":
            row["quoteCount"] += 1
        if module == "SupplierRecommendation":
            row["recommendationCount"] += 1
        if module == "PurchaseOrder":
            row["purchaseOrderReferenceCount"] += 1

    def _scan_purchase_requests(self):
        for item in PurchaseRequestItem.objects.select_related(
            "material", "suggested_supplier", "purchase_request"
        ):
            if not (item.suggested_supplier_id or item.suggested_supplier_code):
                continue
            self.add(
                module="PurchaseRequest",
                reference=f"PurchaseRequest:{item.purchase_request.request_no}:line:{item.line_no}",
                material_id=item.material_id,
                material_code=item.material_code,
                material_name=item.material_name,
                supplier_id=item.suggested_supplier_id,
                supplier_code=item.suggested_supplier_code,
                supplier_name=item.suggested_supplier_name,
            )

    def _scan_inquiries(self):
        for inquiry in PurchaseInquiry.objects.select_related("source_purchase_request"):
            supplier_code = _text(inquiry.supplier)
            if not supplier_code:
                continue
            for item in inquiry.source_purchase_request.request_items.all():
                self.add(
                    module="PurchaseInquiry",
                    reference=f"PurchaseInquiry:{inquiry.inquiry_no}:request-line:{item.line_no}",
                    material_id=item.material_id,
                    material_code=item.material_code,
                    material_name=item.material_name,
                    supplier_code=supplier_code,
                )

    def _scan_quotations(self):
        for quotation in SupplierQuotation.objects.filter(
            quotation_status__in=("saved", "submitted", "received")
        ).select_related("source_inquiry"):
            supplier_identity = _text(quotation.supplier_id)
            supplier_id = supplier_identity if supplier_identity.isdigit() else None
            supplier_code = "" if supplier_id else supplier_identity
            for index, line in enumerate(quotation.items or []):
                if not isinstance(line, dict):
                    continue
                line_supplier_id = line.get("supplierId")
                line_supplier_code = line.get("supplierCode")
                self.add(
                    module="SupplierQuotation",
                    reference=f"SupplierQuotation:{quotation.quotation_no}:line:{index + 1}",
                    material_id=line.get("materialId"),
                    material_code=line.get("materialCode"),
                    material_name=line.get("materialName"),
                    supplier_id=line_supplier_id or supplier_id,
                    supplier_code=line_supplier_code or supplier_code,
                    supplier_name=quotation.supplier_name,
                    delivery_period=line.get("deliveryPeriod"),
                    quality_level=line.get("qualityLevel"),
                    on_time_rate=line.get("onTimeRate"),
                )

    def _scan_comparisons(self):
        explicit_keys = (
            "selectedSupplierCode", "recommendedSupplierCode", "winnerSupplierCode"
        )
        for comparison in QuoteComparisonFact.objects.all():
            result = comparison.comparison_result if isinstance(comparison.comparison_result, dict) else {}
            explicit_code = next((_text(result.get(key)) for key in explicit_keys if result.get(key)), "")
            for index, evidence in enumerate(comparison.supplier_quote_evidence or []):
                if not isinstance(evidence, dict):
                    continue
                identity = _text(evidence.get("supplierId"))
                identity_id = identity if identity.isdigit() else None
                identity_code = _text(evidence.get("supplierCode")) or (
                    "" if identity_id else identity
                )
                self.add(
                    module="QuoteComparison",
                    reference=f"QuoteComparison:{comparison.comparison_no}:supplier:{index + 1}",
                    material_code=comparison.material_code,
                    material_name=comparison.material_name,
                    supplier_id=identity_id,
                    supplier_code=identity_code,
                    supplier_name=evidence.get("supplierName"),
                    explicit_main=bool(explicit_code and explicit_code == identity_code),
                    delivery_period=evidence.get("deliveryPeriod"),
                    quality_level=evidence.get("qualityLevel"),
                    on_time_rate=evidence.get("onTimeRate"),
                )

    def _scan_price_approvals(self):
        for preparation in PriceApprovalPreparation.objects.filter(
            status="completed", review_result="pass"
        ):
            selected = preparation.selected_supplier if isinstance(preparation.selected_supplier, dict) else {}
            supplier_code = _text(selected.get("supplierCode"))
            supplier_id = selected.get("supplierId")
            for index, line in enumerate(preparation.material_lines or []):
                if not isinstance(line, dict):
                    continue
                self.add(
                    module="PriceApproval",
                    reference=f"PriceApproval:{preparation.approval_prepare_no}:line:{index + 1}",
                    material_id=line.get("materialId"),
                    material_code=line.get("materialCode"),
                    material_name=line.get("materialName"),
                    supplier_id=supplier_id,
                    supplier_code=supplier_code,
                    supplier_name=selected.get("supplierName"),
                    explicit_main=True,
                    delivery_period=selected.get("deliveryPeriod"),
                    quality_level=selected.get("qualityLevel"),
                    on_time_rate=selected.get("onTimeRate"),
                )
        for approval in PriceApproval.objects.filter(status="approved"):
            supplier_identity = _text(approval.supplier)
            supplier_id = supplier_identity if supplier_identity.isdigit() else None
            supplier_code = "" if supplier_id else supplier_identity
            for index, line in enumerate(approval.items or []):
                if not isinstance(line, dict):
                    continue
                self.add(
                    module="PriceApproval",
                    reference=f"PriceApproval:{approval.approval_no}:line:{index + 1}",
                    material_id=line.get("materialId"),
                    material_code=line.get("materialCode"),
                    material_name=line.get("materialName"),
                    supplier_id=supplier_id,
                    supplier_code=supplier_code,
                    explicit_main=True,
                    delivery_period=line.get("deliveryPeriod"),
                )

        # SupplierMaterialPrice is the governed persisted result of price approval.
        # Historical approval flows may not retain a separately scannable
        # PriceApproval row, so the approved result remains formal relation evidence.
        for price in SupplierMaterialPrice.objects.select_related(
            "supplier", "material", "price_approval_result"
        ):
            if price.price_approval_result_id:
                if price.price_approval_result.approval_conclusion != "pass":
                    continue
                self.add(
                    module="PriceApproval",
                    reference=(f"SupplierMaterialPrice:{price.price_no}:"
                               f"PriceApprovalResult:{price.price_approval_result_id}"),
                    material_id=price.material_id,
                    material_code=price.material.code,
                    material_name=price.material.name,
                    supplier_id=price.supplier_id,
                    supplier_code=price.supplier.code,
                    supplier_name=price.supplier.name,
                    explicit_main=True,
                )
                continue
            if price.price_source_type != "MANUAL_MAINTENANCE":
                continue
            audit_rows = price.modification_audit if isinstance(price.modification_audit, list) else []
            relation_audit = next((
                row for row in audit_rows
                if isinstance(row, dict)
                and row.get("relationConfirmed") is True
                and row.get("relationCode") == f"MSR|{price.material.code}|{price.supplier.code}"
            ), None)
            if relation_audit:
                self.add(
                    module="ManualPriceMaintenance",
                    reference=f"SupplierMaterialPrice:{price.price_no}:ManualRelationConfirmation",
                    material_id=price.material_id,
                    material_code=price.material.code,
                    material_name=price.material.name,
                    supplier_id=price.supplier_id,
                    supplier_code=price.supplier.code,
                    supplier_name=price.supplier.name,
                )

    def _scan_purchase_orders(self):
        for order in PurchaseOrder.objects.select_related("supplier").prefetch_related("items__material"):
            for index, item in enumerate(order.items.all()):
                if item.material_id is None:
                    continue
                self.add(
                    module="PurchaseOrder",
                    reference=f"PurchaseOrder:{order.po_no}:line:{index + 1}",
                    material_id=item.material_id,
                    material_code=item.material.code,
                    material_name=item.material.name,
                    supplier_id=order.supplier_id,
                    supplier_code=order.supplier.code,
                    supplier_name=order.supplier.name,
                )

    def scan(self):
        self._scan_purchase_requests()
        self._scan_inquiries()
        self._scan_quotations()
        self._scan_comparisons()
        self._scan_price_approvals()
        self._scan_purchase_orders()
        return self

    def matrix_rows(self):
        rows = []
        for (_material_code, _supplier_code), value in sorted(self.valid.items()):
            modules = sorted({item["module"] for item in value["sources"]})
            eligible = any(item["priority"] is not None for item in value["sources"])
            rows.append({
                "materialCode": value["material"].code,
                "materialName": value["material"].name,
                "supplierCode": value["supplier"].code,
                "supplierName": value["supplier"].name,
                "sourceModules": modules,
                "sourceModule": " / ".join(modules),
                "businessUsageCount": len(value["sources"]),
                "quoteCount": value["quoteCount"],
                "recommendationCount": value["recommendationCount"],
                "purchaseOrderReferenceCount": value["purchaseOrderReferenceCount"],
                "mappingStatus": "已映射" if eligible else "待人工确认",
            })
        return rows

    def relation_models(self):
        models = []
        for (material_code, supplier_code), value in sorted(self.valid.items()):
            eligible = [item for item in value["sources"] if item["priority"] is not None]
            if not eligible:
                continue
            eligible.sort(key=lambda item: (item["priority"], item["reference"]))
            primary = eligible[0]
            delivery_source = next(
                (item for item in eligible
                 if item["module"] == "SupplierQuotation" and item["deliveryPeriod"]),
                None,
            )
            quality_source = next((item for item in eligible if item["qualityLevel"]), None)
            on_time_source = next((item for item in eligible if item["onTimeRate"] is not None), None)
            material = value["material"]
            supplier = value["supplier"]
            is_main = any(item["explicitMain"] for item in eligible)
            delivery_period = delivery_source["deliveryPeriod"] if delivery_source else None
            on_time_rate = on_time_source["onTimeRate"] if on_time_source else None
            models.append(MaterialSupplierRelation(
                relationCode=f"MSR|{material_code}|{supplier_code}",
                materialId=material.pk,
                materialCode=material.code,
                materialName=material.name,
                materialDisplay=f"{material.code} / {material.name}",
                supplierId=supplier.pk,
                supplierCode=supplier.code,
                supplierName=supplier.name,
                supplierDisplay=f"{supplier.code} / {supplier.name}",
                isMainSupplier=is_main,
                isMainSupplierLabel="是" if is_main else "否",
                priority=primary["priority"],
                deliveryPeriod=delivery_period,
                deliveryPeriodLabel=f"{delivery_period} 天" if delivery_period else "-",
                deliveryPeriodSource=delivery_source["reference"] if delivery_source else "",
                qualityLevel=quality_source["qualityLevel"] if quality_source else "待评估",
                onTimeRate=on_time_rate,
                onTimeRateLabel=f"{on_time_rate:g}%" if on_time_rate is not None else "-",
                status="enabled",
                statusLabel="启用",
                sourceReference=primary["reference"],
                sourceModules=tuple(sorted({item["module"] for item in value["sources"]})),
                businessUsageCount=len(value["sources"]),
                quoteCount=value["quoteCount"],
                recommendationCount=value["recommendationCount"],
                purchaseOrderReferenceCount=value["purchaseOrderReferenceCount"],
            ))
        return models


class MaterialSupplierRelationRuntime:
    runtime_code = "MaterialSupplierRelationRuntime"
    runtime_version = "V1.14.2.8.4.27.2.46-Batch2.2-R5.1"
    _session_delivery_periods = {}

    @classmethod
    def facts(cls):
        matrix = MaterialSupplierUsageMatrix().scan()
        models = [
            replace(
                model,
                deliveryPeriod=cls._session_delivery_periods[model.relationCode],
                deliveryPeriodLabel=f"{cls._session_delivery_periods[model.relationCode]} 天",
                deliveryPeriodSource=f"MaterialSupplierRelationManual:{model.relationCode}",
            ) if model.relationCode in cls._session_delivery_periods else model
            for model in matrix.relation_models()
        ]
        matrix_rows = matrix.matrix_rows()
        relation_keys = [(item.materialCode, item.supplierCode) for item in models]
        return {
            "runtimeCode": cls.runtime_code,
            "runtimeVersion": cls.runtime_version,
            "models": models,
            "usageMatrix": matrix_rows,
            "unresolvedMappings": matrix.unresolved,
            "sourceSummary": matrix.source_summary,
            "relationCount": len(models),
            "usageMatrixCount": len(matrix_rows),
            "duplicateRelationCount": len(relation_keys) - len(set(relation_keys)),
            "businessProgressWriteCount": 0,
            "sessionMaintenanceCount": len(cls._session_delivery_periods),
            "sessionPersistence": "SERVER_MEMORY_ONLY",
        }

    @classmethod
    def list_runtime_models(cls):
        return cls.facts()["models"]

    @classmethod
    def update_delivery_period(cls, relation_code, payload):
        relation_code = str(relation_code or "").strip()
        try:
            delivery_period = int(payload.get("deliveryPeriod"))
        except (TypeError, ValueError):
            raise ValueError("MATERIAL_SUPPLIER_DELIVERY_PERIOD_REQUIRED")
        if delivery_period <= 0:
            raise ValueError("MATERIAL_SUPPLIER_DELIVERY_PERIOD_REQUIRED")
        if not any(item.relationCode == relation_code for item in cls.facts()["models"]):
            raise ValueError("MATERIAL_SUPPLIER_RELATION_NOT_FOUND")
        cls._session_delivery_periods[relation_code] = delivery_period
        return next(item for item in cls.facts()["models"] if item.relationCode == relation_code)


MaterialSupplierRelationRuntimeModel = MaterialSupplierRelation
