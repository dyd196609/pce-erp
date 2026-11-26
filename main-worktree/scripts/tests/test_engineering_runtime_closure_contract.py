from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.engineering_runtime_closure_contract import (
    CURRENT_REQUIREMENT_ACTION,
    CURRENT_REQUIREMENT_SERVICE,
    LEGACY_REQUIREMENT_ACTION,
    LEGACY_REQUIREMENT_SERVICE,
    assess_database_gate,
    assess_purpose_contract,
    assess_requirement_contract,
)


def purpose_facts(order_no="ORDER-OTHER"):
    before = {"businessPurpose": "DEVELOPMENT_VALIDATION", "orderVersion": 1}
    after = {"businessPurpose": "FORMAL_SALE", "orderVersion": 2}
    protected = {"orderNo": order_no, "itemCount": 2}
    return {
        "orderId": 700,
        "orderNo": order_no,
        "companyId": 9,
        "orderVersion": 2,
        "currentPurpose": "FORMAL_SALE",
        "correctionActionCount": 1,
        "correctionAction": {
            "actionCode": "sales.order.correct_business_identity",
            "auditActionCode": "sales.order.correct_business_identity",
            "auditTargetId": 700,
            "actorId": 20,
            "auditActorId": 20,
            "idempotencyKey": "purpose-key",
            "requestId": "purpose-request",
            "auditRecordId": 80,
            "auditId": 80,
            "audit": {
                "beforeIdentity": before,
                "afterIdentity": after,
                "protectedIdentityBefore": protected,
                "protectedIdentityAfter": deepcopy(protected),
                "actor": {
                    "isSuperuser": False,
                    "isActive": True,
                    "employeeId": 4,
                    "employeeStatus": "active",
                },
                "authorization": {
                    "allowed": True,
                    "actionCode": "sales.order.update",
                    "organizationId": "9",
                },
                "workflowResponsibility": {
                    "businessActionCode": "sales.order.update",
                    "responsibilityCode": "RESP_SALES_ORDER",
                },
                "orderWriteCount": 1,
                "businessStateTransitionCount": 0,
                "downstreamWriteCount": 0,
                "reason": "authorized correction",
            },
        },
    }


def requirement_row(order_no, row_id, mapping_id, *, legacy=False, line_no=1):
    quantity = str(row_id + 1)
    action = LEGACY_REQUIREMENT_ACTION if legacy else CURRENT_REQUIREMENT_ACTION
    service = LEGACY_REQUIREMENT_SERVICE if legacy else CURRENT_REQUIREMENT_SERVICE
    after = {
        "requirementId": row_id,
        "sourceDetailId": row_id + 1000,
        "calculationReexecuted": False,
    }
    if legacy:
        after.update({
            "mappingRuleId": mapping_id,
            "materialId": row_id + 2000,
            "netQuantity": quantity,
            "uom": "m",
        })
    else:
        after.update({
            "bomGenerated": False,
            "request": {
                "mappingRuleId": mapping_id,
                "calculationId": line_no + 100,
                "materialId": row_id + 2000,
                "quantity": quantity,
                "uom": "m",
                "authorizationReference": f"USER_INSTRUCTION:{order_no}:{row_id}",
            },
        })
    row = {
        "id": row_id,
        "companyId": 9,
        "salesOrderId": 700,
        "lineNo": line_no,
        "calculationId": line_no + 100,
        "sourceDetailCalculationId": line_no + 100,
        "sourceDetailId": row_id + 1000,
        "materialId": row_id + 2000,
        "calculatedQuantity": quantity,
        "netQuantity": quantity,
        "uomCode": "m",
        "uomSymbol": "m",
        "trace": {
            "serviceCode": service,
            "mappingRuleId": mapping_id,
            "mappingSpecificationHash": f"hash-{mapping_id}",
            "sourceDetailId": row_id + 1000,
            "calculationReexecuted": False,
            "authorizationReference": f"USER_INSTRUCTION:{order_no}:{row_id}",
        },
        "mapping": {
            "id": mapping_id,
            "ruleCode": f"MRM.{order_no}.MAP-{mapping_id}",
            "status": "released",
            "companyId": 9,
            "specificationHash": f"hash-{mapping_id}",
        },
        "audit": {
            "count": 1,
            "targetId": row_id,
            "actionCode": action,
            "reason": f"USER_INSTRUCTION:{order_no}:{row_id}",
            "authorizationAllowed": True,
            "actor": {
                "isSuperuser": False,
                "isActive": True,
                "employeeId": 4,
                "employeeStatus": "active",
            },
            "after": after,
        },
        "writeRequestCount": 0 if legacy else 1,
        "externalIdentityCount": 0 if legacy else 1,
        "bomSourceLinkCount": 1 if legacy else 0,
        "bomSourceLinks": [],
    }
    if legacy:
        attach_bom_link(row)
    return row


def attach_bom_link(row, *, version_id=None):
    version_id = version_id or row["calculationId"] + 5000
    row["bomSourceLinks"] = [{
        "id": row["id"] + 8000,
        "requirementId": row["id"],
        "bomItemId": row["id"] + 7000,
        "bomVersionId": version_id,
        "sourceCalculationId": row["calculationId"],
        "materialId": row["materialId"],
        "uomCode": row["uomCode"],
        "bomItemQuantity": row["netQuantity"],
        "contributedQuantity": row["netQuantity"],
    }]
    row["bomSourceLinkCount"] = 1


def requirement_facts(order_no="ORDER-OTHER", *, current=1, legacy=1):
    rows = []
    for index in range(legacy):
        rows.append(requirement_row(order_no, 100 + index, 500 + index, legacy=True, line_no=3 + index))
    for index in range(current):
        rows.append(requirement_row(order_no, 200 + index, 600 + index, line_no=1))
    return {
        "scopeType": "SALES_ORDER",
        "orderId": 700,
        "orderNo": order_no,
        "companyId": 9,
        "requirements": rows,
        "releasedMappingRuleIds": [row["trace"]["mappingRuleId"] for row in rows],
    }


class PurposeContractTests(unittest.TestCase):
    def test_01_authorized_formal_purpose_passes(self):
        self.assertEqual(assess_purpose_contract(purpose_facts()), [])

    def test_02_illegal_purpose_drift_is_blocked(self):
        facts = purpose_facts()
        facts["currentPurpose"] = "SYSTEM_TEST"
        self.assertTrue(assess_purpose_contract(facts))

    def test_03_missing_correction_is_blocked(self):
        facts = purpose_facts()
        facts["correctionActionCount"] = 0
        facts["correctionAction"] = {}
        self.assertTrue(assess_purpose_contract(facts))

    def test_04_forged_after_value_is_blocked(self):
        facts = purpose_facts()
        facts["correctionAction"]["audit"]["afterIdentity"]["businessPurpose"] = "SYSTEM_TEST"
        self.assertTrue(assess_purpose_contract(facts))


class RequirementContractTests(unittest.TestCase):
    def test_05_current_order_contract_passes_without_fixed_count(self):
        facts = requirement_facts("SO202609180003", current=25, legacy=2)
        self.assertEqual(assess_requirement_contract(facts), [])

    def test_06_legitimate_requirement_addition_passes(self):
        facts = requirement_facts(current=1, legacy=0)
        new_row = requirement_row(facts["orderNo"], 901, 9901)
        facts["requirements"].append(new_row)
        facts["releasedMappingRuleIds"].append(9901)
        self.assertEqual(assess_requirement_contract(facts), [])

    def test_07_requirement_deletion_is_blocked_by_released_mapping(self):
        facts = requirement_facts(current=2, legacy=0)
        facts["requirements"].pop()
        self.assertIn(
            "released order mapping and material requirement sets differ",
            assess_requirement_contract(facts),
        )

    def test_08_requirement_tamper_is_blocked_by_creation_audit(self):
        facts = requirement_facts(current=1, legacy=0)
        facts["requirements"][0]["netQuantity"] = "999"
        self.assertTrue(assess_requirement_contract(facts))

    def test_09_duplicate_mapping_consumption_is_blocked(self):
        facts = requirement_facts(current=2, legacy=0)
        facts["requirements"][1]["trace"]["mappingRuleId"] = facts["requirements"][0]["trace"]["mappingRuleId"]
        self.assertTrue(assess_requirement_contract(facts))

    def test_10_historical_line_source_link_is_protected(self):
        facts = requirement_facts(current=0, legacy=2)
        facts["requirements"][0]["bomSourceLinkCount"] = 0
        facts["requirements"][0]["bomSourceLinks"] = []
        self.assertTrue(assess_requirement_contract(facts))

    def test_11_other_order_uses_its_own_scope(self):
        facts = requirement_facts("SO-ANOTHER-ORDER", current=2, legacy=0)
        self.assertEqual(assess_requirement_contract(facts), [])

    def test_12_primary_key_ceiling_is_not_a_count_contract(self):
        facts = requirement_facts(current=0, legacy=0)
        rows = [
            requirement_row(facts["orderNo"], 5, 7001),
            requirement_row(facts["orderNo"], 5000, 7002),
        ]
        facts["requirements"] = rows
        facts["releasedMappingRuleIds"] = [7001, 7002]
        self.assertEqual(assess_requirement_contract(facts), [])

    def test_13_scope_must_be_explicit(self):
        facts = requirement_facts(current=1, legacy=0)
        facts["scopeType"] = "GLOBAL"
        self.assertTrue(assess_requirement_contract(facts))

    def test_14_source_detail_scope_mismatch_is_blocked(self):
        facts = requirement_facts(current=1, legacy=0)
        facts["requirements"][0]["sourceDetailCalculationId"] += 1
        self.assertTrue(assess_requirement_contract(facts))

    def test_15_uom_code_is_authoritative_when_symbol_is_typographic(self):
        facts = requirement_facts(current=1, legacy=0)
        row = facts["requirements"][0]
        row["uomCode"] = "m2"
        row["uomSymbol"] = "m²"
        row["audit"]["after"]["request"]["uom"] = "m2"
        self.assertEqual(assess_requirement_contract(facts), [])

    def test_16_complete_generated_requirement_set_passes(self):
        facts = requirement_facts(current=3, legacy=0)
        for row in facts["requirements"]:
            attach_bom_link(row, version_id=9001)
        self.assertEqual(assess_requirement_contract(facts), [])

    def test_17_generated_source_material_or_quantity_mismatch_is_blocked(self):
        facts = requirement_facts(current=2, legacy=0)
        for row in facts["requirements"]:
            attach_bom_link(row, version_id=9001)
        facts["requirements"][0]["bomSourceLinks"][0]["materialId"] += 1
        facts["requirements"][1]["bomSourceLinks"][0]["contributedQuantity"] = "999"
        risks = assess_requirement_contract(facts)
        self.assertTrue(any("another material" in risk for risk in risks))
        self.assertTrue(any("contribution differs" in risk for risk in risks))

    def test_18_partial_generation_is_blocked(self):
        facts = requirement_facts(current=2, legacy=0)
        attach_bom_link(facts["requirements"][0], version_id=9001)
        self.assertTrue(any(
            "partially generated" in risk for risk in assess_requirement_contract(facts)
        ))

    def test_19_multiple_versions_or_links_are_blocked(self):
        facts = requirement_facts(current=2, legacy=0)
        attach_bom_link(facts["requirements"][0], version_id=9001)
        attach_bom_link(facts["requirements"][1], version_id=9002)
        duplicate = deepcopy(facts["requirements"][0]["bomSourceLinks"][0])
        duplicate["id"] += 1
        facts["requirements"][0]["bomSourceLinks"].append(duplicate)
        facts["requirements"][0]["bomSourceLinkCount"] = 2
        risks = assess_requirement_contract(facts)
        self.assertTrue(any("multiple generated BOM items" in risk for risk in risks))
        self.assertTrue(any("multiple BOM versions" in risk for risk in risks))


class DatabaseContractTests(unittest.TestCase):
    def test_20_database_gate_passes_when_read_only_and_unchanged(self):
        facts = {
            "queryOnly": 1,
            "integrityCheck": "ok",
            "foreignKeyCheck": [],
            "shaBefore": "same",
            "shaAfter": "same",
            "countsBefore": {"requirements": 3},
            "countsAfter": {"requirements": 3},
        }
        self.assertEqual(assess_database_gate(facts), [])

    def test_21_database_hash_or_count_drift_is_blocked(self):
        facts = {
            "queryOnly": 1,
            "integrityCheck": "ok",
            "foreignKeyCheck": [],
            "shaBefore": "before",
            "shaAfter": "after",
            "countsBefore": {"requirements": 3},
            "countsAfter": {"requirements": 4},
        }
        self.assertTrue(assess_database_gate(facts))


if __name__ == "__main__":
    unittest.main()
