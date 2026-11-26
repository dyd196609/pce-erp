from types import SimpleNamespace

from django.test import SimpleTestCase

from .models import SalesOrder
from .order_business_purpose_service import (
    LEGACY_MAPPING,
    PERSISTED_FACT,
    order_business_purpose_facts,
    resolve_order_business_purpose,
)


class SalesOrderBusinessPurposeFoundationTests(SimpleTestCase):
    def test_minimum_business_purpose_enum_is_exact(self):
        self.assertEqual(
            set(SalesOrder.BusinessPurpose.values),
            {"FORMAL_SALE", "DEVELOPMENT_VALIDATION", "SYSTEM_TEST"},
        )

    def test_persisted_business_purpose_is_the_formal_fact(self):
        order = SimpleNamespace(
            business_purpose="FORMAL_SALE",
            acceptance_marker="DEVELOPMENT_ONLY",
        )

        result = resolve_order_business_purpose(order)

        self.assertEqual(result.business_purpose, "FORMAL_SALE")
        self.assertEqual(result.fact_source, PERSISTED_FACT)
        self.assertTrue(result.is_persisted)
        self.assertFalse(result.is_legacy_mapping)
        self.assertFalse(result.admission_enforcement_enabled)

    def test_development_marker_is_read_only_legacy_mapping(self):
        order = SimpleNamespace(
            business_purpose=None,
            acceptance_marker="DEVELOPMENT_ONLY",
        )

        result = order_business_purpose_facts(order)

        self.assertEqual(result["businessPurpose"], "DEVELOPMENT_VALIDATION")
        self.assertEqual(result["factSource"], LEGACY_MAPPING)
        self.assertFalse(result["isPersisted"])
        self.assertTrue(result["isLegacyMapping"])
        self.assertFalse(result["admissionEnforcementEnabled"])

    def test_other_acceptance_marker_maps_to_system_test(self):
        result = resolve_order_business_purpose(SimpleNamespace(
            business_purpose=None,
            acceptance_marker="AUTOMATED_REGRESSION_FIXTURE",
        ))

        self.assertEqual(result.business_purpose, "SYSTEM_TEST")
        self.assertEqual(result.fact_source, LEGACY_MAPPING)

    def test_unmarked_legacy_order_maps_to_formal_sale_without_persistence(self):
        result = resolve_order_business_purpose(SimpleNamespace(
            business_purpose=None,
            acceptance_marker="",
        ))

        self.assertEqual(result.business_purpose, "FORMAL_SALE")
        self.assertEqual(result.fact_source, LEGACY_MAPPING)
        self.assertFalse(result.is_persisted)

    def test_invalid_persisted_value_fails_closed(self):
        with self.assertRaisesMessage(ValueError, "Unsupported SalesOrder business purpose"):
            resolve_order_business_purpose(SimpleNamespace(
                business_purpose="UNKNOWN",
                acceptance_marker="",
            ))

