from dataclasses import replace
from unittest.mock import patch

from django.test import SimpleTestCase

from masterdata.material_supplier_relation_runtime import (
    MaterialSupplierRelation,
    MaterialSupplierRelationRuntime,
)


class MaterialSupplierRelationMaintenanceTests(SimpleTestCase):
    def setUp(self):
        MaterialSupplierRelationRuntime._session_delivery_periods = {}

    def test_only_delivery_period_changes_in_session(self):
        original = MaterialSupplierRelation(
            relationCode="MSR|MAT-1|SUP-1",
            materialId=1, materialCode="MAT-1", materialName="物料1", materialDisplay="MAT-1 / 物料1",
            supplierId=1, supplierCode="SUP-1", supplierName="供应商1", supplierDisplay="SUP-1 / 供应商1",
            isMainSupplier=False, isMainSupplierLabel="否", priority=3,
            deliveryPeriod=None, deliveryPeriodLabel="-", deliveryPeriodSource="",
            qualityLevel="待评估", onTimeRate=None, onTimeRateLabel="-",
            status="enabled", statusLabel="启用", sourceReference="SupplierQuotation:SQ-1",
            sourceModules=("SupplierQuotation",), businessUsageCount=1,
            quoteCount=1, recommendationCount=0, purchaseOrderReferenceCount=0,
        )

        def facts():
            days = MaterialSupplierRelationRuntime._session_delivery_periods.get(original.relationCode)
            model = replace(original, deliveryPeriod=days, deliveryPeriodLabel=f"{days} 天") if days else original
            return {"models": [model]}

        with patch.object(MaterialSupplierRelationRuntime, "facts", side_effect=facts):
            updated = MaterialSupplierRelationRuntime.update_delivery_period(original.relationCode, {"deliveryPeriod": 12})

        self.assertEqual(updated.deliveryPeriod, 12)
        self.assertEqual(updated.materialCode, original.materialCode)
        self.assertEqual(updated.supplierCode, original.supplierCode)
        self.assertEqual(updated.sourceReference, original.sourceReference)
