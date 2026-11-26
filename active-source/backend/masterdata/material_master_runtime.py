"""Canonical, read-only MaterialMaster runtime projection.

The adapter owns the only conversion from ``masterdata.Material`` to a page or
business-reference model.  It never writes business or master-data records.
"""

from dataclasses import asdict, dataclass

from django.db.models import Q

from .models import Material


MATERIAL_TYPE_LABELS = {
    **dict(Material.MATERIAL_TYPES),
    # Read compatibility before the A0 data migration is applied.
    "fixed": "固定资产",
}


@dataclass(frozen=True)
class MaterialRuntimeModel:
    runtimeModelType: str
    runtimeAdapterCode: str
    id: int
    materialCode: str
    materialName: str
    specification: str
    unit: str
    category: str
    type: str
    materialType: str
    status: str
    businessStatus: str
    isPurchased: bool
    isProduced: bool
    supplyType: str
    supplyTypeLabel: str
    supplyTypePending: bool
    updatedAt: str
    materialSourceTrace: dict

    def to_dict(self):
        return asdict(self)

    def to_reference_dict(self):
        """Compatibility aliases for governed selectors; facts stay identical."""
        payload = self.to_dict()
        payload.update({
            "code": self.materialCode,
            "name": self.materialName,
            "purchaseAttribute": "可采购" if self.isPurchased else "不可采购",
        })
        return payload


class MaterialMasterRuntimeAdapter:
    runtime_model_type = "MaterialRuntimeModel"
    runtime_adapter_code = "MaterialMasterRuntimeAdapter"
    database_table = Material._meta.db_table

    @classmethod
    def queryset(cls, query="", *, business_eligible=True):
        queryset = Material.objects.select_related("category").order_by("code", "id")
        if business_eligible:
            queryset = queryset.filter(is_active=True, is_purchased=True)
        query = str(query or "").strip()
        if query:
            queryset = queryset.filter(
                Q(code__icontains=query)
                | Q(name__icontains=query)
                | Q(specification__icontains=query)
            )
        return queryset

    @classmethod
    def to_runtime_model(cls, material):
        material_type = MATERIAL_TYPE_LABELS.get(material.material_type, material.material_type)
        return MaterialRuntimeModel(
            runtimeModelType=cls.runtime_model_type,
            runtimeAdapterCode=cls.runtime_adapter_code,
            id=material.pk,
            materialCode=material.code,
            materialName=material.name,
            specification=material.specification or "",
            unit=material.purchase_unit or material.unit or "",
            category=material.category.name if material.category else "",
            type=material_type,
            materialType=material_type,
            status="enabled" if material.is_active else "disabled",
            businessStatus="启用" if material.is_active else "停用",
            isPurchased=bool(material.is_purchased),
            isProduced=bool(material.is_produced),
            supplyType=material.supply_type,
            supplyTypeLabel=material.supply_type_display,
            supplyTypePending=material.supply_type == "pending_confirmation",
            updatedAt=material.updated_at.isoformat() if material.updated_at else "",
            materialSourceTrace={
                "materialCode": material.code,
                "source": "MaterialMaster",
                "database": cls.database_table,
                "maintenanceEntry": "企业基础数据 → 物料数据",
            },
        )

    @classmethod
    def list_runtime_models(cls, query="", *, business_eligible=True, limit=None):
        queryset = cls.queryset(query, business_eligible=business_eligible)
        if limit is not None:
            queryset = queryset[:limit]
        return [cls.to_runtime_model(material) for material in queryset]
