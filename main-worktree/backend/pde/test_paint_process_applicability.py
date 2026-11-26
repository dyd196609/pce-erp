"""Regression matrix for PAINT_PROCESS process/routing/capacity/material separation."""

import inspect
from types import SimpleNamespace as Obj

from django.test import SimpleTestCase

from .engineering_calculation_service import _current_version_material_completeness
from .paint_process_applicability import (
    APPLICABLE,
    BLOCKED,
    DEFERRED,
    INCOMPLETE,
    MATERIAL_BOM_GENERATION_STAGE,
    NOT_APPLICABLE,
    READY,
    UNRESOLVED,
    resolve_capacity_readiness,
    resolve_capacity_stage_gate,
    resolve_paint_material_applicability,
    resolve_process_applicability,
)


def requirement(design_item_id, role, *, pk=1, material_id=100, quantity="1", uom_id=1):
    return Obj(
        pk=pk,
        material_id=material_id,
        net_quantity=quantity,
        calculated_quantity=quantity,
        uom_id=uom_id,
        source_detail_id=None,
        order_specification={"structureRole": role},
        trace={"designItemId": design_item_id, "structureRole": role},
    )


def formal_context(*, capacity_complete=False, code="GENERIC/ROUTE"):
    operations = [{
        "sequence": 1,
        "operationCode": "OP-GENERIC",
        "operationName": "通用工序",
        "workshopId": 1,
        "workCenterId": 1 if capacity_complete else None,
        "quantityDriver": "AREA" if capacity_complete else None,
        "standardHours": "1.0000" if capacity_complete else None,
        "capacityFactIds": [1] if capacity_complete else [],
    }]
    return {
        "process": {"status": "CONFIRMED", "code": "GENERIC", "name": "通用表面工艺"},
        "routing": {
            "status": READY,
            "routingId": 1,
            "routingCode": code,
            "routingVersionId": 1,
            "operationCount": 1,
        },
        "capacity": {
            "status": READY if capacity_complete else INCOMPLETE,
            "complete": capacity_complete,
            "stepCount": 1,
            "stepsWithWorkshop": 1,
            "stepsWithWorkCenter": 1 if capacity_complete else 0,
            "stepsWithWorkloadDriver": 1 if capacity_complete else 0,
            "stepsWithStandardTime": 1 if capacity_complete else 0,
            "stepsWithCapacityFact": 1 if capacity_complete else 0,
            "stepsWithReadyCapacityFact": 1 if capacity_complete else 0,
            "standardCapacityFactCount": 1 if capacity_complete else 0,
            "operationRequirementCount": 1 if capacity_complete else 0,
        },
        "operations": operations,
        "sourceByObject": {},
    }


def complete_requirements(ids):
    rows = []
    pk = 1
    for design_item_id in ids:
        for role in (
            "DOOR_LEAF_SURFACE_PANEL", "DOOR_CASING_MATERIAL",
            "CASING_TRIM", "EDGE_BANDING", "EDGE_BANDING",
        ):
            rows.append(requirement(design_item_id, role, pk=pk))
            pk += 1
    return rows


def completeness(
    *, ids=(1,), context=None, input_overrides=None, requirements=None,
    workflow_stage=MATERIAL_BOM_GENERATION_STAGE,
):
    context = context or formal_context()
    overrides = input_overrides or {}
    snapshots = []
    results = []
    for design_item_id in ids:
        values = {
            "paintProcess": "通用表面工艺",
            "processConfigurationCode": context["routing"].get("routingCode"),
        }
        values.update(overrides.get(design_item_id, {}))
        snapshots.append({
            "designItemId": design_item_id,
            "designItemNo": f"DES-{design_item_id}",
            "input": values,
        })
        results.extend({"designItemId": design_item_id, "canonicalField": code}
                       for code in ("R", "S", "U", "N", "O", "P", "Q", "X",
                                    "AT", "AU", "AV", "AW", "AX", "AY", "Z", "AA"))
    calculation = Obj(trace={
        "objectInputSnapshot": snapshots,
        "resultSnapshot": results,
        "paintProcessClosureFacts": context,
    })
    return _current_version_material_completeness(
        calculation,
        requirements if requirements is not None else complete_requirements(ids),
        workflow_stage=workflow_stage,
    )


class PaintProcessApplicabilityTests(SimpleTestCase):
    def test_01_formal_process_only_proves_process_applicability(self):
        row = resolve_process_applicability(process_fact={"status": "CONFIRMED"})
        self.assertEqual(row["status"], APPLICABLE)

    def test_02_process_without_recipe_makes_material_not_applicable(self):
        row = resolve_paint_material_applicability()
        self.assertEqual(row["status"], NOT_APPLICABLE)

    def test_03_valid_material_recipe_consumption_is_applicable(self):
        row = resolve_paint_material_applicability(
            material_evidence=[{"status": "CONFIRMED", "materialId": 9}],
            recipe_evidence=[{"status": "CONFIRMED", "recipeId": 8}],
            consumption_evidence=[{
                "status": "CONFIRMED", "quantity": "1.2", "uomId": 7,
            }],
        )
        self.assertEqual(row["status"], APPLICABLE)

    def test_04_partial_recipe_is_unresolved(self):
        row = resolve_paint_material_applicability(
            recipe_evidence=[{"status": "CONFIRMED", "recipeId": 8}],
        )
        self.assertEqual(row["status"], UNRESOLVED)

    def test_05_recipe_without_material_is_unresolved(self):
        row = resolve_paint_material_applicability(
            recipe_evidence=[{"status": "CONFIRMED", "recipeId": 8}],
            consumption_evidence=[{
                "status": "CONFIRMED", "formula": "AREA*0.1", "uomCode": "KG",
            }],
        )
        self.assertEqual(row["status"], UNRESOLVED)

    def test_06_complete_capacity_is_ready(self):
        row = resolve_capacity_readiness(
            process_status=APPLICABLE, routing_status=READY,
            capacity_fact={"status": READY, "complete": True},
        )
        self.assertEqual(row["status"], READY)

    def test_07_partial_capacity_is_incomplete(self):
        row = resolve_capacity_readiness(
            process_status=APPLICABLE, routing_status=READY,
            capacity_fact={"status": INCOMPLETE, "complete": False},
        )
        self.assertEqual(row["status"], INCOMPLETE)

    def test_08_no_formal_process_or_route_is_not_applicable(self):
        row = resolve_process_applicability()
        self.assertEqual(row["status"], NOT_APPLICABLE)

    def test_09_resolver_does_not_create_or_guess_material(self):
        materials = []
        resolve_paint_material_applicability(material_evidence=materials)
        self.assertEqual(materials, [])

    def test_10_capacity_never_creates_material_requirement(self):
        requirements = complete_requirements((1,))
        before = tuple(requirements)
        completeness(context=formal_context(capacity_complete=True), requirements=requirements)
        self.assertEqual(tuple(requirements), before)

    def test_11_current_five_are_process_routing_ready_material_na_capacity_deferred(self):
        result = completeness(ids=(1, 2, 3, 4, 5), context=formal_context())
        by_code = {row["code"]: row for row in result["evaluatedCategories"]}
        self.assertEqual(by_code["PAINT_PROCESS"]["status"], APPLICABLE)
        self.assertEqual(by_code["PAINT_PROCESS_ROUTING"]["status"], READY)
        self.assertEqual(by_code["PAINT_PROCESS_CAPACITY"]["status"], DEFERRED)
        self.assertEqual(by_code["PAINT_PROCESS_CAPACITY"]["actualCapacityReadiness"], INCOMPLETE)
        self.assertFalse(by_code["PAINT_PROCESS_CAPACITY"]["capacityRequiredForCurrentStage"])
        self.assertTrue(
            by_code["PAINT_PROCESS_CAPACITY"]["capacityRequiredForLaterManufacturingStage"]
        )
        self.assertEqual(by_code["PAINT_PROCESS_MATERIAL"]["status"], NOT_APPLICABLE)
        self.assertIsNone(result["firstRealBlocker"])
        self.assertTrue(result["complete"])
        self.assertEqual(len(by_code["PAINT_PROCESS"]["applicabilityByObject"]), 5)

    def test_12_closure_does_not_multiply_order_quantity(self):
        requirements = complete_requirements((1, 2, 3, 4, 5))
        before = [row.net_quantity for row in requirements]
        completeness(ids=(1, 2, 3, 4, 5), requirements=requirements)
        self.assertEqual([row.net_quantity for row in requirements], before)

    def test_13_veneer_finish_remains_not_applicable(self):
        result = completeness()
        veneer = next(row for row in result["evaluatedCategories"] if row["code"] == "VENEER_FINISH")
        self.assertEqual(veneer["status"], NOT_APPLICABLE)

    def test_14_existing_twenty_five_requirements_are_unchanged(self):
        requirements = complete_requirements((1, 2, 3, 4, 5))
        before = [(row.pk, row.trace.copy()) for row in requirements]
        completeness(ids=(1, 2, 3, 4, 5), requirements=requirements)
        self.assertEqual([(row.pk, row.trace) for row in requirements], before)
        self.assertEqual(len(requirements), 25)

    def test_15_completeness_path_has_no_save_or_create_call(self):
        source = inspect.getsource(_current_version_material_completeness)
        self.assertNotIn(".save(", source)
        self.assertNotIn(".create(", source)

    def test_16_production_logic_has_no_current_order_or_process_hardcode(self):
        source = inspect.getsource(_current_version_material_completeness)
        self.assertNotIn("SO202609180003", source)
        self.assertNotIn("QSFB/FM", source)
        self.assertNotIn("QSFB4601001", source)
        self.assertNotIn("LC-M045", source)

    def test_17_other_process_can_have_positive_material_facts(self):
        evidence = {
            "materialRoleApplicability": {
                "PAINT_PROCESS_MATERIAL": {
                    "materialEvidence": [{"status": "CONFIRMED", "materialId": 500}],
                    "recipeEvidence": [{"status": "CONFIRMED", "recipeId": 600}],
                    "consumptionEvidence": [{
                        "status": "CONFIRMED", "formula": "AREA*0.2", "uomId": 2,
                    }],
                },
            },
        }
        result = completeness(
            context=formal_context(capacity_complete=True, code="OTHER/PROCESS"),
            input_overrides={1: evidence},
        )
        paint_material = next(
            row for row in result["evaluatedCategories"]
            if row["code"] == "PAINT_PROCESS_MATERIAL"
        )
        self.assertEqual(paint_material["status"], "MISSING_REQUIREMENT")
        self.assertEqual(result["firstRealBlocker"]["code"], "PAINT_PROCESS_MATERIAL_REQUIREMENT_MISSING")

    def test_18_other_process_can_have_positive_capacity_facts(self):
        result = completeness(context=formal_context(capacity_complete=True, code="OTHER/PROCESS"))
        capacity = next(
            row for row in result["evaluatedCategories"]
            if row["code"] == "PAINT_PROCESS_CAPACITY"
        )
        self.assertEqual(capacity["status"], READY)
        self.assertIsNone(result["firstRealBlocker"])

    def test_19_full_scan_exposes_routing_and_deferred_capacity(self):
        result = completeness()
        codes = [row["roleOrRequirementType"] for row in result["fullBomReadinessScan"]]
        self.assertIn("PAINT_PROCESS_ROUTING", codes)
        self.assertIn("PAINT_PROCESS_CAPACITY", codes)
        self.assertIn("PAINT_PROCESS_MATERIAL", codes)
        capacity = next(row for row in result["fullBomReadinessScan"]
                        if row["roleOrRequirementType"] == "PAINT_PROCESS_CAPACITY")
        self.assertEqual(capacity["status"], DEFERRED)
        self.assertTrue(capacity["currentStageSatisfied"])
        self.assertFalse(capacity["needsHumanFact"])
        material = next(row for row in result["fullBomReadinessScan"]
                        if row["roleOrRequirementType"] == "PAINT_PROCESS_MATERIAL")
        self.assertEqual(material["status"], NOT_APPLICABLE)

    def test_20_routing_code_conflict_blocks_without_guessing(self):
        result = completeness(
            context=formal_context(code="FORMAL/ROUTE"),
            input_overrides={1: {"processConfigurationCode": "OTHER/ROUTE"}},
        )
        self.assertEqual(result["firstRealBlocker"]["code"], "PAINT_PROCESS_ROUTING_FACT_MISSING")
        self.assertEqual(result["firstRealBlocker"]["category"], "PAINT_PROCESS_ROUTING")

    def test_21_capacity_planning_requires_incomplete_capacity(self):
        result = completeness(workflow_stage="CAPACITY_PLANNING")
        by_code = {row["code"]: row for row in result["evaluatedCategories"]}
        self.assertEqual(by_code["PAINT_PROCESS_CAPACITY"]["status"], BLOCKED)
        self.assertTrue(by_code["PAINT_PROCESS_CAPACITY"]["capacityRequiredForCurrentStage"])
        self.assertEqual(result["firstRealBlocker"]["code"], "PAINT_PROCESS_CAPACITY_FACT_MISSING")

    def test_22_missing_work_center_is_not_ready(self):
        fact = formal_context(capacity_complete=True)["capacity"]
        fact["stepsWithWorkCenter"] = 0
        row = resolve_capacity_readiness(
            process_status=APPLICABLE, routing_status=READY, capacity_fact=fact,
        )
        self.assertEqual(row["status"], INCOMPLETE)
        self.assertIn("WORK_CENTER", row["missingDimensions"])

    def test_23_missing_standard_time_is_not_ready(self):
        fact = formal_context(capacity_complete=True)["capacity"]
        fact["stepsWithStandardTime"] = 0
        row = resolve_capacity_readiness(
            process_status=APPLICABLE, routing_status=READY, capacity_fact=fact,
        )
        self.assertEqual(row["status"], INCOMPLETE)
        self.assertIn("STANDARD_TIME", row["missingDimensions"])

    def test_24_missing_standard_capacity_is_not_ready(self):
        fact = formal_context(capacity_complete=True)["capacity"]
        fact["stepsWithReadyCapacityFact"] = 0
        fact["standardCapacityFactCount"] = 0
        row = resolve_capacity_readiness(
            process_status=APPLICABLE, routing_status=READY, capacity_fact=fact,
        )
        self.assertEqual(row["status"], INCOMPLETE)
        self.assertIn("STANDARD_CAPACITY", row["missingDimensions"])

    def test_25_unknown_stage_fails_closed_for_capacity(self):
        readiness = resolve_capacity_readiness(
            process_status=APPLICABLE, routing_status=READY,
            capacity_fact=formal_context()["capacity"],
        )
        gate = resolve_capacity_stage_gate(
            process_status=APPLICABLE,
            routing_status=READY,
            capacity_readiness=readiness,
            workflow_stage="UNREGISTERED_LATER_STAGE",
        )
        self.assertEqual(gate["status"], BLOCKED)
        self.assertTrue(gate["capacityRequiredForCurrentStage"])

    def test_26_other_process_uses_same_stage_policy(self):
        bom_result = completeness(
            context=formal_context(code="ANOTHER/PROCESS"),
            workflow_stage=MATERIAL_BOM_GENERATION_STAGE,
        )
        planning_result = completeness(
            context=formal_context(code="ANOTHER/PROCESS"),
            workflow_stage="PRODUCTION_PLANNING",
        )
        bom_capacity = next(row for row in bom_result["evaluatedCategories"]
                            if row["code"] == "PAINT_PROCESS_CAPACITY")
        planning_capacity = next(row for row in planning_result["evaluatedCategories"]
                                 if row["code"] == "PAINT_PROCESS_CAPACITY")
        self.assertEqual(bom_capacity["status"], DEFERRED)
        self.assertEqual(planning_capacity["status"], BLOCKED)
