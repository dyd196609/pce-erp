"""No-database contract tests for the authorized R1 handoff service."""

from pathlib import Path
from types import SimpleNamespace as Obj
from unittest import TestCase

from .engineering_rule_foundation import validate_specification
from .r1_material_requirement_handoff_service import (
    AUTHORIZATION_REFERENCE,
    AUTHORIZED_SO202609180003_REPRESENTATIVES,
    MAPPING_CONTRACT_CODE,
    SERVICE_CODE,
    _mapping_specification,
)


class R1MaterialRequirementHandoffContractTests(TestCase):
    def test_authorized_scope_contains_only_two_representatives(self):
        rows = AUTHORIZED_SO202609180003_REPRESENTATIVES
        self.assertEqual([row.mapping_no for row in rows], ["MRC-003", "MRC-004"])
        self.assertEqual([row.material_id for row in rows], [117, 140])
        self.assertEqual([row.expected_saved_value for row in rows], ["0.031200", "1.860000"])
        self.assertTrue(all(row.source_fact_code == "S" for row in rows))
        self.assertTrue(all(row.output_uom == "m2" for row in rows))
        self.assertTrue(all(row.quantity_basis == "PER_SALES_ITEM_UNIT" for row in rows))
        self.assertTrue(all(row.sales_item_multiplier == "APPLY_ONCE" for row in rows))

    def test_mapping_specification_preserves_saved_fact_and_audit_identity(self):
        approval = AUTHORIZED_SO202609180003_REPRESENTATIVES[0]
        fact = Obj(
            pk=158,
            source_detail_id=158,
            source_path="baseline.items[83].results[S]",
            calculation_id=5,
            calculation=Obj(result_hash="HASH"),
            source_detail=Obj(rule_code="APPROVED_SOURCE_NET", rule_version="V1"),
            trace={"ruleCode": "APPROVED_SOURCE_NET", "ruleVersion": "V1"},
        )
        material = Obj(pk=117, code="MAT202608000035", specification="白胚擦色清水开放")
        spec = _mapping_specification(approval, fact=fact, material=material)
        self.assertIs(validate_specification(spec), spec)
        self.assertEqual(spec["contractCode"], MAPPING_CONTRACT_CODE)
        self.assertEqual(spec["expression"], "source_fact_value")
        self.assertEqual(spec["outputs"][0]["quantityExpression"], "SOURCE_FACT_VALUE")
        self.assertEqual(spec["outputs"][0]["quantitySource"]["sourceFactId"], 158)
        self.assertEqual(spec["outputs"][0]["scrapRate"], None)
        self.assertEqual(spec["auditIdentity"]["authorizationReference"], AUTHORIZATION_REFERENCE)

    def test_service_source_forbids_recalculation_and_bom_generation(self):
        source = Path(__file__).with_name("r1_material_requirement_handoff_service.py").read_text(encoding="utf-8")
        self.assertIn("calculationReexecuted\": False", source)
        self.assertIn("bomGenerated\": False", source)
        self.assertNotIn("EngineeringCalculationService.execute", source)
        self.assertNotIn("OrderEngineeringClosureService.generate_bom", source)
        self.assertIn(SERVICE_CODE, source)

