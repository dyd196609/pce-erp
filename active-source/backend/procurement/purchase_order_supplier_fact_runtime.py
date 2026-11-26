"""Compatibility facade for the V24 purchase-order supplier fact runtime."""

from .supplier_material_fact_resolver import (
    SupplierMaterialFact as PurchaseOrderSupplierFact,
    SupplierMaterialFactResolver,
)


class PurchaseOrderSupplierFactRuntime(SupplierMaterialFactResolver):
    runtime_code = "PurchaseOrderSupplierFactRuntime"
