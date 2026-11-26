"""Contract-level regression tests for the generic saved-fact handoff."""

from decimal import Decimal
from types import SimpleNamespace as Obj

from django.test import SimpleTestCase

from .saved_fact_material_requirement_service import (
    SavedFactInputBinding,
    SavedFactMaterialRequirementContract,
    build_mapping_specification,
    evaluate_contract_formula,
)


def _contract(**overrides):
    values = {
        "mapping_no": "MRC-TEST",
        "mapping_rule_code": "MRM.TEST.CASING",
        "mapping_version": "V1",
        "rule_name": "CASING_FRAME_LENGTH",
        "order_no": "SO-TEST",
        "calculation_id": 1,
        "design_item_no": "DES-TEST",
        "material_id": 9,
        "material_code": "MAT-TEST",
        "output_uom_code": "m",
        "output_name": "casing_frame_length",
        "expression": "(2*N+O)*Q/1000",
        "inputs": (
            SavedFactInputBinding("N", "N", "mm", "length"),
            SavedFactInputBinding("O", "O", "mm", "length"),
            SavedFactInputBinding(
                "Q", "Q", None, None, unit_required=False, integer_required=True,
            ),
        ),
        "primary_source_fact_code": "N",
        "expected_quantity": Decimal("4.990000"),
        "authorization_reference": "TEST-AUTHORIZATION",
        "idempotency_key": "TEST-CASING",
        "purpose_code": "DOOR_CASING_MATERIAL",
        "output_unit_dimension": "length",
        "require_design_material_reference": False,
    }
    values.update(overrides)
    return SavedFactMaterialRequirementContract(**values)


def _fact(pk, code, value, *, uom=None):
    return Obj(
        pk=pk,
        rule_id=None,
        rule=None,
        source_detail_id=pk,
        source_path=f"facts[{code}]",
        value={"decimal": value},
        uom_id=1 if uom else None,
        uom=Obj(code=uom) if uom else None,
        calculation_id=1,
        calculation=Obj(result_hash="HASH", sales_order_item_id=2),
    )


class SavedFactMaterialRequirementContractTests(SimpleTestCase):
    def test_stock_piece_conversion_requires_both_saved_cut_lengths(self):
        from .saved_fact_material_requirement_service import _validate_input_values, SavedFactMaterialRequirementError
        contract = _contract(order_specification={"inputAssertions": [
            {"variable": "N", "equals": "2440", "uom": "mm"},
            {"variable": "O", "equals": "2440", "uom": "mm"},
        ]})
        values = {"N": {"value": "2440", "unit": "mm"},
                  "O": {"value": "2440", "unit": "mm"}, "Q": {"value": "15"}}
        _validate_input_values(contract, values)
        values["O"]["value"] = "2400"
        with self.assertRaises(SavedFactMaterialRequirementError) as caught:
            _validate_input_values(contract, values)
        self.assertEqual(caught.exception.code, "SAVED_FACT_ASSERTION_MISMATCH")

    def test_casing_formula_uses_length_dimension_and_no_order_multiplier(self):
        contract = _contract()
        facts = {
            "N": _fact(1, "N", "2035", uom="mm"),
            "O": _fact(2, "O", "920", uom="mm"),
            "Q": _fact(3, "Q", "1"),
        }
        spec = build_mapping_specification(
            contract,
            resolved_facts=facts,
            material=Obj(pk=9, code="MAT-TEST", specification="30×40 mm"),
            order_specification={"structureRole": "DOOR_CASING_MATERIAL"},
        )
        quantity = evaluate_contract_formula(
            contract,
            mapping_specification=spec,
            input_values={
                "N": {"value": "2035", "unit": "mm", "unitDimension": "length"},
                "O": {"value": "920", "unit": "mm", "unitDimension": "length"},
                "Q": {"value": "1", "unitDimension": None},
            },
        )
        self.assertEqual(spec["outputs"][0]["unitDimension"], "length")
        self.assertEqual(spec["outputs"][0]["salesItemMultiplier"], "NONE")
        self.assertEqual(quantity, Decimal("4.990000"))

    def test_existing_area_contract_defaults_remain_unchanged(self):
        contract = _contract(
            expression="R*S*U/1000000",
            inputs=(
                SavedFactInputBinding("R", "R", "mm", "length"),
                SavedFactInputBinding("S", "S", "mm", "length"),
                SavedFactInputBinding(
                    "U", "U", None, None, unit_required=False, integer_required=True,
                ),
            ),
            primary_source_fact_code="R",
            expected_quantity=Decimal("1.000000"),
            output_uom_code="m2",
            output_unit_dimension="area",
            require_design_material_reference=True,
        )
        self.assertEqual(contract.output_unit_dimension, "area")
        self.assertTrue(contract.require_design_material_reference)
        self.assertIsNone(contract.source_external_identity_id)
        self.assertFalse(
            contract.allow_missing_design_revision_when_source_identity_confirmed
        )

    def test_material_area_fact_marks_x_as_quantity_basis(self):
        contract = _contract(
            expression="X",
            inputs=(SavedFactInputBinding("X", "X", "m2", "area"),),
            primary_source_fact_code="X",
            expected_quantity=Decimal("0.856800"),
            output_uom_code="m2",
            output_unit_dimension="area",
            scrap_rate=None,
            source_external_identity_id=51,
            allow_missing_design_revision_when_source_identity_confirmed=True,
        )
        facts = {"X": _fact(102, "X", "0.856800", uom="m2")}
        spec = build_mapping_specification(
            contract,
            resolved_facts=facts,
            material=Obj(pk=130, code="MAT202608000048", specification="清水封闭"),
            order_specification={
                "structureRole": "MAIN_PANEL_WITH_CONFIRMED_TRIM_SCOPE",
                "sourceExternalIdentity": {"id": 51, "mappingStatus": "MATCH"},
            },
        )
        quantity = evaluate_contract_formula(
            contract,
            mapping_specification=spec,
            input_values={"X": {"value": "0.856800", "unit": "m2", "unitDimension": "area"}},
        )
        self.assertEqual(quantity, Decimal("0.856800"))
        self.assertEqual(
            spec["sourceEvidence"]["materialSourceExternalIdentity"]["id"], 51
        )

