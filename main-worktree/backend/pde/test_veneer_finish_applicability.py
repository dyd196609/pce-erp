"""Focused regression matrix for generic VENEER_FINISH applicability."""

import inspect
from types import SimpleNamespace as Obj

from django.test import SimpleTestCase

from .engineering_calculation_service import (
    _current_version_material_completeness,
    _veneer_finish_applicability,
)
from .material_role_applicability import (
    APPLICABLE,
    NOT_APPLICABLE,
    UNRESOLVED,
    resolve_material_role_applicability,
)


def requirement(design_item_id, role, *, pk=None, material_id=None, quantity=None):
    return Obj(
        pk=pk,
        trace={"designItemId": design_item_id, "structureRole": role},
        order_specification={},
        source_detail_id=None,
        material_id=material_id,
        net_quantity=quantity,
        calculated_quantity=quantity,
        uom_id=1 if quantity is not None else None,
    )


def completeness(*, inputs, requirements, results=None):
    snapshots = [
        {"designItemId": design_item_id, "designItemNo": f"DES-{design_item_id}", "input": value}
        for design_item_id, value in sorted(inputs.items())
    ]
    return _current_version_material_completeness(
        Obj(trace={"objectInputSnapshot": snapshots, "resultSnapshot": results or []}),
        requirements,
    )


def saved_evidence(**buckets):
    return {"materialRoleApplicability": {"VENEER_FINISH": buckets}}


class VeneerFinishApplicabilityTests(SimpleTestCase):
    def test_01_appearance_only_is_not_applicable(self):
        result = resolve_material_role_applicability(
            role_code="VENEER_FINISH",
            appearance_evidence=[{"status": "PRESENT", "value": "柚木直纹"}],
        )
        self.assertEqual(result["status"], NOT_APPLICABLE)
        self.assertEqual(result["reasonCode"], "APPEARANCE_PROCESS_ONLY_NO_INDEPENDENT_MATERIAL")

    def test_02_process_only_is_not_applicable(self):
        result = resolve_material_role_applicability(
            role_code="VENEER_FINISH",
            process_evidence=[{"status": "PRESENT", "value": "清水封闭"}],
        )
        self.assertEqual(result["status"], NOT_APPLICABLE)

    def test_03_appearance_and_process_remain_not_applicable(self):
        result = resolve_material_role_applicability(
            role_code="VENEER_FINISH",
            appearance_evidence=[{"status": "PRESENT"}],
            process_evidence=[{"status": "PRESENT"}],
        )
        self.assertEqual(result["status"], NOT_APPLICABLE)

    def test_04_explicit_configuration_role_is_applicable(self):
        result = resolve_material_role_applicability(
            role_code="VENEER_FINISH",
            configuration_evidence=[{"status": "CONFIRMED", "roleCode": "VENEER_FINISH"}],
        )
        self.assertEqual(result["status"], APPLICABLE)
        self.assertEqual(result["reasonCode"], "EXPLICIT_ORDER_PRODUCT_CONFIGURATION_ROLE")

    def test_05_explicit_template_role_is_applicable(self):
        result = resolve_material_role_applicability(
            role_code="VENEER_FINISH",
            template_evidence=[{"status": "CONFIRMED", "roleCode": "VENEER_FINISH"}],
        )
        self.assertEqual(result["status"], APPLICABLE)
        self.assertEqual(result["reasonCode"], "EXPLICIT_PRODUCT_TEMPLATE_STRUCTURE_ROLE")

    def test_06_independent_material_and_quantity_are_applicable(self):
        result = resolve_material_role_applicability(
            role_code="VENEER_FINISH",
            material_evidence=[{"status": "CONFIRMED", "materialId": 901}],
            quantity_evidence=[{"status": "CONFIRMED", "quantity": "2.5", "uomCode": "M2"}],
        )
        self.assertEqual(result["status"], APPLICABLE)
        self.assertEqual(result["reasonCode"], "INDEPENDENT_MATERIAL_IDENTITY_AND_QUANTITY")

    def test_07_partial_material_identity_is_unresolved(self):
        result = resolve_material_role_applicability(
            role_code="VENEER_FINISH",
            material_evidence=[{"status": "CONFIRMED", "materialId": 901}],
        )
        self.assertEqual(result["status"], UNRESOLVED)
        self.assertEqual(result["reasonCode"], "INDEPENDENT_MATERIAL_IDENTITY_QUANTITY_INCOMPLETE")

    def test_08_ambiguous_configuration_is_unresolved(self):
        result = resolve_material_role_applicability(
            role_code="VENEER_FINISH",
            configuration_evidence=[{"status": "AMBIGUOUS", "roleCode": "VENEER_FINISH"}],
        )
        self.assertEqual(result["status"], UNRESOLVED)

    def test_09_conflicting_positive_and_negative_evidence_is_unresolved(self):
        result = resolve_material_role_applicability(
            role_code="VENEER_FINISH",
            configuration_evidence=[{"status": "CONFIRMED"}],
            template_evidence=[{"status": "NOT_APPLICABLE"}],
        )
        self.assertEqual(result["status"], UNRESOLVED)
        self.assertEqual(result["reasonCode"], "CONFLICTING_APPLICABILITY_EVIDENCE")

    def test_10_applicable_without_requirement_is_blocked(self):
        result = completeness(
            inputs={1: saved_evidence(
                configurationEvidence=[{"status": "CONFIRMED", "roleCode": "VENEER_FINISH"}],
            )},
            requirements=[requirement(1, "OTHER_MATERIAL")],
        )
        self.assertEqual(result["firstRealBlocker"]["code"], "VENEER_FINISH_REQUIREMENT_MISSING")

    def test_11_applicable_with_requirement_is_complete(self):
        result = completeness(
            inputs={1: {}},
            requirements=[requirement(1, "VENEER_FINISH", pk=11, material_id=901, quantity="1.2")],
        )
        veneer = next(row for row in result["evaluatedCategories"] if row["code"] == "VENEER_FINISH")
        self.assertEqual(veneer["status"], "COMPLETE")
        self.assertIsNone(result["firstRealBlocker"])

    def test_12_not_applicable_without_requirement_passes(self):
        requirements = [requirement(1, "OTHER_MATERIAL")]
        result = completeness(
            inputs={1: {"finishOrColor": "柚木直纹"}},
            requirements=requirements,
        )
        veneer = next(row for row in result["evaluatedCategories"] if row["code"] == "VENEER_FINISH")
        self.assertEqual(veneer["status"], "NOT_APPLICABLE")
        self.assertIn("VENEER_FINISH", result["notApplicableCategories"])
        self.assertIsNone(result["firstRealBlocker"])

    def test_13_unresolved_applicability_blocks_closure(self):
        result = completeness(
            inputs={1: saved_evidence(materialEvidence=[{"status": "CONFIRMED", "materialId": 901}])},
            requirements=[requirement(1, "OTHER_MATERIAL")],
        )
        self.assertEqual(result["firstRealBlocker"]["code"], "APPLICABILITY_UNRESOLVED")

    def test_14_five_appearance_process_objects_are_all_not_applicable(self):
        inputs = {
            value: {"finishOrColor": "柚木直纹，封闭/LC-M045", "paintProcess": "清水封闭"}
            for value in range(1, 6)
        }
        fact_codes = ("R", "S", "U", "N", "O", "P", "Q", "X", "AT", "Z")
        results = [
            {"designItemId": value, "canonicalField": code}
            for value in inputs for code in fact_codes
        ]
        requirements = [
            requirement(value, role)
            for value in inputs
            for role in (
                "DOOR_LEAF_SURFACE_PANEL", "CASING_MATERIAL", "CASING_TRIM", "EDGE_BANDING",
            )
        ]
        result = completeness(inputs=inputs, requirements=requirements, results=results)
        veneer = next(row for row in result["evaluatedCategories"] if row["code"] == "VENEER_FINISH")
        self.assertEqual(
            (
                veneer["applicableDesignItemCount"],
                veneer["notApplicableDesignItemCount"],
                veneer["requirementDesignItemCount"],
                veneer["status"],
            ),
            (0, 5, 0, "NOT_APPLICABLE"),
        )
        self.assertIsNone(result["firstRealBlocker"])

    def test_15_not_applicable_resolution_does_not_add_requirement(self):
        requirements = [requirement(1, "OTHER_MATERIAL")]
        before = tuple(requirements)
        completeness(inputs={1: {"finishOrColor": "柚木直纹"}}, requirements=requirements)
        self.assertEqual(tuple(requirements), before)

    def test_16_existing_material_id_does_not_create_duplicate_veneer_requirement(self):
        requirements = [requirement(1, "OTHER_MATERIAL", material_id=130, quantity="1")]
        before = len(requirements)
        result = completeness(
            inputs={1: {"finishOrColor": "LC-M045"}}, requirements=requirements,
        )
        self.assertEqual(len(requirements), before)
        veneer = next(row for row in result["evaluatedCategories"] if row["code"] == "VENEER_FINISH")
        self.assertEqual(veneer["requirementDesignItemCount"], 0)

    def test_17_appearance_code_is_never_material_identity(self):
        resolution = _veneer_finish_applicability(
            {"designItemId": 1, "input": {"finishOrColor": "LC-M045"}},
            [],
        )
        self.assertEqual(resolution["status"], NOT_APPLICABLE)
        self.assertEqual(resolution["materialEvidence"], [])
        self.assertEqual(len(resolution["appearanceEvidence"]), 1)

    def test_18_non_current_positive_scenario_requires_requirement(self):
        result = completeness(
            inputs={88: saved_evidence(
                ruleEvidence=[{"status": "CONFIRMED", "ruleCode": "GENERIC-VENEER-RULE"}],
            )},
            requirements=[requirement(88, "OTHER_MATERIAL")],
        )
        self.assertEqual(result["firstRealBlocker"]["code"], "VENEER_FINISH_REQUIREMENT_MISSING")

    def test_19_output_exposes_required_evidence_partitions(self):
        result = resolve_material_role_applicability(role_code="VENEER_FINISH")
        self.assertTrue({
            "materialEvidence", "templateEvidence", "configurationEvidence",
            "appearanceEvidence", "processEvidence", "quantityEvidence",
        }.issubset(result))

    def test_20_current_four_complete_roles_do_not_regress(self):
        fact_codes = ("R", "S", "U", "N", "O", "P", "Q", "X", "AT", "Z")
        results = [{"designItemId": 1, "canonicalField": code} for code in fact_codes]
        requirements = [
            requirement(1, role)
            for role in (
                "DOOR_LEAF_SURFACE_PANEL", "CASING_MATERIAL", "CASING_TRIM", "EDGE_BANDING",
            )
        ]
        result = completeness(
            inputs={1: {"finishOrColor": "仅外观", "paintProcess": "仅工艺"}},
            requirements=requirements,
            results=results,
        )
        statuses = {
            row["code"]: row["status"] for row in result["evaluatedCategories"][:4]
        }
        self.assertEqual(statuses, {
            "DOOR_LEAF_SURFACE_PANEL": "COMPLETE",
            "CASING_MATERIAL": "COMPLETE",
            "CASING_TRIM": "COMPLETE",
            "EDGE_BANDING": "COMPLETE",
        })

    def test_21_production_logic_has_no_formal_order_or_item_hardcoding(self):
        source = inspect.getsource(_veneer_finish_applicability)
        self.assertNotIn("SO202609180003", source)
        self.assertNotIn("LC-M045", source)
        self.assertNotIn("material_id == 130", source)
