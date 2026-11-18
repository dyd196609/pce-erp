from django.test import SimpleTestCase

from procurement.models import Warehouse, WarehouseLocation

from .production_foundation_service import ENTITY_CONFIG


class FoundationEntryUnificationPreA18Tests(SimpleTestCase):
    def test_warehouse_and_location_reuse_formal_service_boundary(self):
        self.assertEqual(
            ENTITY_CONFIG["warehouses"],
            (Warehouse, "production.master_data.location.maintain"),
        )
        self.assertEqual(
            ENTITY_CONFIG["warehouse-locations"],
            (WarehouseLocation, "production.master_data.location.maintain"),
        )

    def test_lot_batch_remains_distinct_from_warehouse_master_data(self):
        self.assertIn("inventory-lots", ENTITY_CONFIG)
        self.assertIsNot(
            ENTITY_CONFIG["inventory-lots"][0],
            ENTITY_CONFIG["warehouses"][0],
        )

    def test_core_objects_have_one_formal_service_mapping_each(self):
        entities = [
            "materials", "units", "product-categories", "products",
            "product-versions", "workshops", "work-centers", "operations",
            "equipment", "standard-capacities", "boms", "bom-versions",
            "bom-items", "bom-substitutes", "routings", "routing-versions",
            "routing-steps", "engineering-documents",
            "engineering-document-versions", "manufacturing-outputs",
            "warehouses", "warehouse-locations",
        ]
        self.assertEqual(len(entities), len(set(entities)))
        for entity in entities:
            self.assertIn(entity, ENTITY_CONFIG)
