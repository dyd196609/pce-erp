from django.test import TestCase
from masterdata.models import Material
from masterdata.serializers import MaterialSerializer
from planning.services import supply_type_for


class MaterialSupplyGovernanceA0Tests(TestCase):
    def payload(self, **overrides):
        payload = {
            "code": "A0-MAT-001",
            "name": "A0供应属性测试物料",
            "unit": "件",
            "material_type": "raw",
            "company_id": 1,
            "is_purchased": True,
            "is_produced": False,
        }
        payload.update(overrides)
        return payload

    def test_purchase_and_production_are_formal_supply_types(self):
        purchase = Material(**self.payload())
        production = Material(**self.payload(
            code="A0-MAT-002", is_purchased=False, is_produced=True,
        ))
        self.assertEqual(purchase.supply_type, "purchase")
        self.assertEqual(production.supply_type, "production")
        self.assertEqual(supply_type_for(purchase), "purchase")
        self.assertEqual(supply_type_for(production), "production")

    def test_legacy_ambiguous_pair_is_pending_not_guessed(self):
        material = Material(**self.payload(
            code="A0-MAT-003", is_purchased=False, is_produced=False,
        ))
        self.assertEqual(material.supply_type, "pending_confirmation")
        self.assertEqual(material.supply_type_display, "待确认")
        self.assertEqual(supply_type_for(material), "ambiguous")

    def test_new_material_cannot_submit_conflicting_supply_flags(self):
        serializer = MaterialSerializer(data=self.payload(is_produced=True))
        self.assertFalse(serializer.is_valid())
        self.assertIn("is_purchased", serializer.errors)
        self.assertIn("is_produced", serializer.errors)

    def test_new_material_may_remain_pending_without_guessing_supply_type(self):
        serializer = MaterialSerializer(data=self.payload(
            is_purchased=False, is_produced=False,
        ))
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_fixed_asset_is_a_legal_material_type(self):
        serializer = MaterialSerializer(data=self.payload(material_type="fixed_asset"))
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_arbitrary_material_type_remains_rejected(self):
        serializer = MaterialSerializer(data=self.payload(material_type="fixed"))
        self.assertFalse(serializer.is_valid())
        self.assertIn("material_type", serializer.errors)

    def test_pending_legacy_record_can_be_resolved_explicitly(self):
        material = Material.objects.create(**self.payload(
            code="A0-MAT-004", is_purchased=False, is_produced=False,
        ))
        serializer = MaterialSerializer(
            material,
            data={"is_purchased": True, "is_produced": False},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        resolved = serializer.save()
        self.assertEqual(resolved.supply_type, "purchase")
