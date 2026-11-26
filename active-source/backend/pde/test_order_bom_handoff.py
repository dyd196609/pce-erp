"""Isolated no-database tests for the additive read-only handoff contract."""
import ast
import inspect
from pathlib import Path
from types import SimpleNamespace as Obj
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.db import DatabaseError
from rest_framework.test import APIRequestFactory, force_authenticate
from sales.models import SalesOrder
from .order_bom_handoff_service import (
    BUSINESS_CONFIRMATION_STATUSES, HandoffReadError, MATERIAL_PREVIEW_STATUSES,
    MATERIAL_REQUIREMENT_MAPPING_CONTRACT, _mapping_contract, bom_handoff_gate,
    _apply_formal_confirmation_readback, _material_group_signature,
    _source_material_analysis, positive_id, saved_quantity_basis,
    order_bom_handoff, order_business_purpose, validate_record_scope,
)
from .engineering_calculation_service import (
    EngineeringCalculationError,
    OrderEngineeringClosureService,
    _current_version_material_completeness,
    _bom_item_role,
    _bom_requirement_type,
    _bom_supply_type,
)
from .formal_manufacturing_eligibility_service import FormalManufacturingEligibilityService
from .production_foundation_service import (
    EngineeringLifecycleService,
    ProductionFoundationError,
)
from .views import (
    EngineeringLifecycleView,
    OrderEngineeringBomPreviewView,
    ProductBomListView,
    PdeReadOnlyListView,
)
from rest_framework.response import Response


def record_fixture():
    item = Obj(pk=14, sales_order_id=2, sales_order=Obj(company_id=7))
    return Obj(company_id=7, sales_order_item=item, engineering_instance=Obj(pk=9, company_id=7, sales_order_item_id=14, source_record_id=8),
               source_record_id=8, source_record=Obj(company_id=7), trace={"salesOrderItemId": 14, "orderEngineeringInstanceId": 9,
               "sourceReference": {"id": 8}, "baselineReference": {"orderId": 2}})


def development_order():
    return SalesOrder(
        pk=3,
        order_no="SO-DEV",
        acceptance_marker="DEVELOPMENT_ONLY",
        contract_reference="DEV-1",
        delivery_information={
            "developmentOnly": True,
            "developmentContract": {"purpose": "DEVELOPMENT_ONLY"},
        },
    )


def formal_order(*, status="engineering", admission_mode="STANDARD"):
    return SalesOrder(
        pk=4,
        order_no="SO-FORMAL",
        status=status,
        acceptance_marker="",
        contract_reference="FORMAL-1",
        delivery_information={
            "businessPurpose": "FORMAL_SALE",
            "admissionMode": admission_mode,
        },
    )


def handoff_record(*, calculation_id, line_id, instance_id, object_count, covered_count,
                   requirement_count=None, preview=None):
    if requirement_count is None:
        requirement_count = covered_count
    if preview is None and requirement_count:
        preview = {
            "canGenerate": covered_count == object_count,
            "alreadyGenerated": False,
            "firstRealBlocker": None,
            "currentVersionMaterialCompleteness": {
                "complete": covered_count == object_count,
                "notApplicableCategories": ["CORE_MATERIAL", "FILLER"],
            },
        }
    return {
        "calculationId": calculation_id,
        "calculationNo": f"EC-{calculation_id}",
        "lineId": line_id,
        "lineNo": line_id,
        "instanceId": instance_id,
        "instanceNo": f"OEI-{instance_id}",
        "materialRequirementCount": requirement_count,
        "objectCount": object_count,
        "objects": [
            {"formalMaterialRequirementCount": 1 if index < covered_count else 0}
            for index in range(object_count)
        ],
        "formalRequirementPreview": preview,
    }


class HandoffContractTests(TestCase):
    def test_target_preview_error_is_not_reported_as_ready(self):
        row = handoff_record(calculation_id=42, line_id=8, instance_id=7,
                             object_count=1, covered_count=1, requirement_count=2)
        row["formalRequirementPreview"] = None
        row["formalRequirementPreviewError"] = {
            "code": "INCOMPATIBLE_MATERIAL_REQUIREMENTS", "message": "incompatible specifications",
        }
        result = self._gate([row], target=42)
        self.assertEqual(result["code"], "INCOMPATIBLE_MATERIAL_REQUIREMENTS")
        self.assertFalse(result["canGenerate"])
        self.assertEqual(result["coverageStatus"], "BLOCKED")
        self.assertEqual(result["targetCoverageGate"], "PASS")

    def _gate(self, records, *, target=None, order=None, bom_count=0, version_count=0, item_count=0):
        bom_versions = MagicMock()
        bom_versions.count.return_value = version_count
        with (
            patch("pde.order_bom_handoff_service.ProductBOM.objects.filter") as product_boms,
            patch("pde.order_bom_handoff_service.BOMVersion.objects.filter") as versions,
            patch("pde.order_bom_handoff_service.BOMItem.objects.filter") as items,
        ):
            product_boms.return_value.count.return_value = bom_count
            versions.return_value.distinct.return_value = bom_versions
            items.return_value.count.return_value = item_count
            return bom_handoff_gate(
                records=records,
                selected_order=order or formal_order(),
                company_id=1,
                target_calculation_id=target,
            )

    def test_material_requirement_values_map_to_canonical_bom_contract(self):
        self.assertEqual(_bom_item_role("MAIN_MATERIAL"), "material")
        self.assertEqual(_bom_item_role("MAIN_PANEL_WITH_TRIM"), "material")
        self.assertEqual(_bom_requirement_type("MANUFACTURING"), "manufacturing")
        self.assertEqual(_bom_supply_type("PRODUCTION"), "MAKE")

    def test_unknown_material_requirement_contract_fails_closed(self):
        with self.assertRaises(EngineeringCalculationError) as caught:
            _bom_supply_type("UNCONTROLLED_VALUE")
        self.assertEqual(caught.exception.code, "UNSUPPORTED_BOM_SUPPLY_TYPE_MAPPING")

    def test_business_purpose_comes_from_persisted_development_order_evidence(self):
        order = development_order()
        purpose = order_business_purpose(order)
        self.assertEqual(purpose["code"], "DEVELOPMENT_VALIDATION")
        self.assertEqual(purpose["statusLabel"], "开发验证订单")
        self.assertIn("仅允许草稿和只读验证", purpose["boundary"])
        self.assertEqual(purpose["evidence"]["contractPurpose"], "DEVELOPMENT_ONLY")

    def test_formal_sale_is_eligible_only_with_explicit_persisted_evidence(self):
        order = SalesOrder(
            pk=4, order_no="SO-FORMAL", acceptance_marker="",
            contract_reference="FORMAL-1",
            delivery_information={"businessPurpose": "FORMAL_SALE"},
        )
        result = FormalManufacturingEligibilityService.resolve(order)
        self.assertEqual(result["businessPurposeCode"], "FORMAL_SALE")
        self.assertTrue(result["formalManufacturingEligible"])
        self.assertEqual(result["decisionCode"], "FORMAL_MANUFACTURING_ELIGIBLE")

    def test_unknown_conflict_and_broken_trace_fail_closed(self):
        unknown = FormalManufacturingEligibilityService.resolve(SalesOrder(
            pk=None, order_no="SO-UNKNOWN", acceptance_marker="",
            contract_reference="", delivery_information={},
        ))
        self.assertEqual(unknown["businessPurposeCode"], "UNKNOWN")
        self.assertFalse(unknown["formalManufacturingEligible"])
        conflict = FormalManufacturingEligibilityService.resolve(SalesOrder(
            pk=None, order_no="SO-CONFLICT", acceptance_marker="DEVELOPMENT_ONLY",
            contract_reference="", delivery_information={"businessPurpose": "FORMAL_SALE"},
        ))
        self.assertEqual(conflict["decisionCode"], "BUSINESS_PURPOSE_EVIDENCE_CONFLICT")
        self.assertFalse(conflict["formalManufacturingEligible"])
        broken = FormalManufacturingEligibilityService.resolve(Obj(pk=99))
        self.assertEqual(broken["decisionCode"], "FORMAL_MANUFACTURING_ORDER_TRACE_BROKEN")
        self.assertFalse(broken["orderTraceUnique"])

    def test_server_gate_keeps_preview_operable_and_generation_disabled(self):
        records = [handoff_record(
            calculation_id=index, line_id=index, instance_id=index,
            object_count=1, covered_count=0,
        ) for index in range(1, 5)]
        gate = self._gate(records, target=1, order=development_order())
        self.assertEqual(gate["code"], "FORMAL_ENGINEERING_MATERIAL_REQUIREMENT_REQUIRED")
        self.assertEqual(gate["formalEngineeringMaterialRequirementCount"], 0)
        self.assertEqual(gate["productBomCount"], 0)
        self.assertTrue(gate["canPreview"])
        self.assertFalse(gate["canGenerate"])
        self.assertEqual(gate["businessWriteSideEffectCount"], 0)

    def test_server_gate_exposes_partial_preview_without_marking_order_complete(self):
        records = [
            handoff_record(calculation_id=3, line_id=3, instance_id=2, object_count=5, covered_count=5),
            handoff_record(calculation_id=4, line_id=4, instance_id=3, object_count=2, covered_count=2),
            handoff_record(calculation_id=5, line_id=5, instance_id=4, object_count=30, covered_count=0),
            handoff_record(calculation_id=6, line_id=6, instance_id=5, object_count=34, covered_count=0),
        ]
        gate = self._gate(records, target=3, order=development_order())
        self.assertEqual(gate["code"], "BOM_TARGET_READY")
        self.assertEqual(gate["formalEngineeringMaterialRequirementCount"], 5)
        self.assertEqual(gate["formalRequirementObjectCount"], 7)
        self.assertEqual(gate["orderScope"]["totalCoveredCount"], 7)
        self.assertEqual(gate["orderScope"]["totalDesignItemCount"], 71)
        self.assertEqual(gate["remainingObjectCount"], 64)
        self.assertEqual(gate["previewReadyCalculationCount"], 2)
        self.assertEqual(gate["blockedCalculationCount"], 2)
        self.assertFalse(gate["orderCoverageComplete"])
        self.assertTrue(gate["developmentValidationDraftSupported"])
        self.assertFalse(gate["formalManufacturingEligible"])
        self.assertEqual(gate["formalManufacturingDecisionCode"], "DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN")
        self.assertIn("generate_bom", gate["generationDisabledReason"])

    def test_target_five_of_five_passes_even_when_order_is_seven_of_seventy_one(self):
        records = [
            handoff_record(calculation_id=3, line_id=3, instance_id=2, object_count=5, covered_count=5),
            handoff_record(calculation_id=4, line_id=4, instance_id=3, object_count=66, covered_count=2),
        ]
        gate = self._gate(records, target=3)
        self.assertEqual(gate["targetScope"]["coveredDesignItemCount"], 5)
        self.assertEqual(gate["targetCoverageGate"], "PASS")
        self.assertEqual(gate["orderScope"]["coverageStatus"], "PARTIAL")
        self.assertEqual(gate["orderScope"]["gateRole"], "INFORMATIONAL")
        self.assertTrue(gate["canGenerate"])

    def test_target_missing_one_requirement_fails_closed(self):
        record = handoff_record(calculation_id=3, line_id=3, instance_id=2, object_count=5, covered_count=4)
        gate = self._gate([record], target=3)
        self.assertEqual(gate["code"], "TARGET_BOM_REQUIREMENT_COVERAGE_INCOMPLETE")
        self.assertEqual(gate["targetScope"]["coverageGate"], "FAIL")
        self.assertFalse(gate["canGenerate"])

    def test_other_line_requirements_do_not_cover_target(self):
        records = [
            handoff_record(calculation_id=3, line_id=3, instance_id=2, object_count=5, covered_count=4),
            handoff_record(calculation_id=4, line_id=4, instance_id=3, object_count=1, covered_count=1),
        ]
        gate = self._gate(records, target=3)
        self.assertEqual(gate["targetScope"]["coveredDesignItemCount"], 4)
        self.assertEqual(gate["code"], "TARGET_BOM_REQUIREMENT_COVERAGE_INCOMPLETE")

    def test_other_oei_requirements_do_not_cover_target(self):
        records = [
            handoff_record(calculation_id=3, line_id=3, instance_id=2, object_count=2, covered_count=1),
            handoff_record(calculation_id=4, line_id=3, instance_id=99, object_count=1, covered_count=1),
        ]
        gate = self._gate(records, target=3)
        self.assertEqual(gate["targetScope"]["orderEngineeringInstanceId"], 2)
        self.assertEqual(gate["targetScope"]["coveredDesignItemCount"], 1)

    def test_other_calculation_requirements_do_not_cover_target(self):
        records = [
            handoff_record(calculation_id=3, line_id=3, instance_id=2, object_count=2, covered_count=1),
            handoff_record(calculation_id=33, line_id=3, instance_id=2, object_count=1, covered_count=1),
        ]
        gate = self._gate(records, target=3)
        self.assertEqual(gate["targetScope"]["calculationId"], 3)
        self.assertEqual(gate["targetScope"]["coveredDesignItemCount"], 1)

    def test_order_progress_remains_seven_of_seventy_one(self):
        records = [
            handoff_record(calculation_id=3, line_id=3, instance_id=2, object_count=5, covered_count=5),
            handoff_record(calculation_id=4, line_id=4, instance_id=3, object_count=66, covered_count=2),
        ]
        gate = self._gate(records, target=3)
        self.assertEqual(
            (gate["orderScope"]["totalCoveredCount"], gate["orderScope"]["totalDesignItemCount"]),
            (7, 71),
        )
        self.assertFalse(gate["orderScope"]["hardBlocker"])

    def test_legacy_and_standard_admission_use_identical_target_scope(self):
        record = handoff_record(calculation_id=3, line_id=3, instance_id=2, object_count=5, covered_count=5)
        legacy = self._gate([record], target=3, order=formal_order(admission_mode="LEGACY_ADOPTION"))
        standard = self._gate([record], target=3, order=formal_order(admission_mode="STANDARD"))
        self.assertEqual(legacy["targetScope"], standard["targetScope"])
        self.assertEqual(legacy["targetCoverageGate"], standard["targetCoverageGate"])

    def test_existing_two_boms_remain_visible_without_becoming_target_coverage(self):
        record = handoff_record(calculation_id=3, line_id=3, instance_id=2, object_count=5, covered_count=5)
        gate = self._gate([record], target=3, bom_count=2, version_count=2, item_count=2)
        self.assertEqual((gate["productBomCount"], gate["bomVersionCount"], gate["bomItemCount"]), (2, 2, 2))
        self.assertEqual(gate["targetScope"]["coveredDesignItemCount"], 5)

    def test_duplicate_bom_fails_closed_without_duplicate_creation(self):
        preview = {
            "canGenerate": False,
            "alreadyGenerated": True,
            "firstRealBlocker": None,
            "currentVersionMaterialCompleteness": {"complete": True},
        }
        record = handoff_record(
            calculation_id=3, line_id=3, instance_id=2, object_count=5,
            covered_count=5, preview=preview,
        )
        gate = self._gate([record], target=3)
        self.assertEqual(gate["code"], "BOM_ALREADY_GENERATED")
        self.assertFalse(gate["canGenerate"])

    def test_internal_current_version_na_categories_do_not_block(self):
        record = handoff_record(calculation_id=3, line_id=3, instance_id=2, object_count=1, covered_count=1)
        gate = self._gate([record], target=3)
        self.assertTrue(gate["canGenerate"])
        self.assertIn("CORE_MATERIAL", gate["currentVersionMaterialCompleteness"]["notApplicableCategories"])

    def test_applicable_missing_material_is_the_only_first_real_blocker(self):
        blocker = {
            "code": "CASING_MATERIAL_REQUIREMENT_MISSING",
            "statusLabel": "门套材料Requirement尚未形成",
            "message": "保存事实证明适用，但没有正式Requirement。",
        }
        preview = {
            "canGenerate": False,
            "alreadyGenerated": False,
            "firstRealBlocker": blocker,
            "currentVersionMaterialCompleteness": {"complete": False, "firstRealBlocker": blocker},
        }
        record = handoff_record(
            calculation_id=3, line_id=3, instance_id=2, object_count=5,
            covered_count=5, preview=preview,
        )
        gate = self._gate([record], target=3)
        self.assertEqual(gate["missingConditions"], [blocker])
        self.assertEqual(gate["firstRealBlocker"]["code"], "CASING_MATERIAL_REQUIREMENT_MISSING")

    def test_cancelled_order_is_generically_isolated(self):
        record = handoff_record(calculation_id=3, line_id=3, instance_id=2, object_count=1, covered_count=1)
        gate = self._gate([record], target=3, order=formal_order(status="cancelled"))
        self.assertEqual(gate["code"], "CANCELLED_ORDER_BOM_ISOLATED")
        self.assertFalse(gate["canGenerate"])

    def test_standard_two_line_order_first_complete_line_is_not_blocked_by_second(self):
        records = [
            handoff_record(calculation_id=101, line_id=1, instance_id=201, object_count=2, covered_count=2),
            handoff_record(calculation_id=102, line_id=2, instance_id=202, object_count=3, covered_count=0),
        ]
        gate = self._gate(records, target=101, order=formal_order(admission_mode="STANDARD"))
        self.assertEqual(gate["targetCoverageGate"], "PASS")
        self.assertTrue(gate["canGenerate"])
        self.assertEqual(gate["orderScope"]["coverageStatus"], "PARTIAL")

    def test_object_aware_completeness_stops_at_casing_after_surface_panel(self):
        snapshots = [{"designItemId": value, "designItemNo": f"DES-{value}", "input": {}} for value in (1, 2)]
        results = [
            {"designItemId": value, "canonicalField": code}
            for value in (1, 2) for code in ("R", "S", "U", "N", "O", "P", "Q", "X", "Z")
        ]
        requirements = [Obj(
            trace={"designItemId": value, "structureRole": "DOOR_LEAF_SURFACE_PANEL"},
            order_specification={}, source_detail_id=None,
        ) for value in (1, 2)]
        completeness = _current_version_material_completeness(
            Obj(trace={"objectInputSnapshot": snapshots, "resultSnapshot": results}), requirements,
        )
        self.assertEqual(completeness["coveredDesignItemCount"], 2)
        self.assertEqual(completeness["evaluatedCategories"][0]["status"], "COMPLETE")
        self.assertEqual(completeness["firstRealBlocker"]["code"], "CASING_MATERIAL_REQUIREMENT_MISSING")

    def test_zero_door_leaf_dimensions_do_not_require_surface_panel(self):
        snapshots = [{"designItemId": 1, "designItemNo": "DES-1", "input": {}}]
        results = [
            {"designItemId": 1, "canonicalField": code, "value": {"decimal": value}}
            for code, value in (("R", "0"), ("S", "0"), ("U", "1"), ("N", "2000"),
                                ("O", "900"), ("P", "120"), ("Q", "1"), ("X", "0.5"))
        ]
        requirements = [Obj(
            trace={"designItemId": 1, "structureRole": "MAIN_PANEL_WITH_TRIM"},
            order_specification={
                "structureRole": "MAIN_PANEL_WITH_TRIM",
                "separateEdgeMaterial": False,
            },
            source_detail_id=None,
        )]
        completeness = _current_version_material_completeness(
            Obj(trace={"objectInputSnapshot": snapshots, "resultSnapshot": results}), requirements,
        )
        self.assertNotIn(
            "DOOR_LEAF_SURFACE_PANEL_REQUIREMENT_MISSING",
            [row.get("code") for row in completeness["evaluatedCategories"]],
        )
        self.assertIsNone(completeness["firstRealBlocker"])

    def test_main_panel_with_trim_covers_casing_and_explicitly_non_separate_edge(self):
        snapshots = [{"designItemId": 1, "designItemNo": "DES-1", "input": {}}]
        results = [
            {"designItemId": 1, "canonicalField": code}
            for code in ("N", "O", "P", "Q", "X", "AT", "AU", "AV", "AW", "AX", "AY", "Z")
        ]
        requirements = [Obj(
            trace={"designItemId": 1, "structureRole": "MAIN_PANEL_WITH_TRIM"},
            order_specification={
                "structureRole": "MAIN_PANEL_WITH_TRIM",
                "separateEdgeMaterial": False,
            },
            source_detail_id=None,
        )]
        completeness = _current_version_material_completeness(
            Obj(trace={"objectInputSnapshot": snapshots, "resultSnapshot": results}), requirements,
        )
        by_code = {row["code"]: row for row in completeness["evaluatedCategories"]}
        self.assertEqual(by_code["CASING_MATERIAL"]["status"], "COMPLETE")
        self.assertEqual(by_code["CASING_TRIM"]["status"], "COMPLETE")
        self.assertNotIn("EDGE_BANDING", by_code)
        self.assertIsNone(completeness["firstRealBlocker"])

    def test_scope_service_contains_no_order_or_admission_special_case(self):
        source = inspect.getsource(bom_handoff_gate) + inspect.getsource(order_bom_handoff)
        self.assertNotIn("SO202609180003", source)
        self.assertNotIn("admissionMode", source)

    def test_shared_guard_blocks_bom_and_manufacturing_output_formal_states(self):
        denied = {
            "formalManufacturingEligible": False,
            "decisionCode": "DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN",
            "message": FormalManufacturingEligibilityService.DEVELOPMENT_MESSAGE,
        }
        with patch.object(FormalManufacturingEligibilityService, "resolve", return_value=denied) as resolve:
            for entity, instance, target in (
                ("bom-versions", Obj(bom_scope="order_specific"), "reviewed"),
                ("bom-versions", Obj(bom_scope="order_specific"), "released"),
                ("manufacturing-outputs", Obj(definition_mode="order_specific"), "engineering_review"),
                ("manufacturing-outputs", Obj(definition_mode="order_specific"), "released_to_manufacturing"),
            ):
                with self.assertRaises(ProductionFoundationError) as caught:
                    EngineeringLifecycleService._formal_manufacturing_eligibility(entity, instance, target)
                self.assertEqual(caught.exception.code, denied["decisionCode"])
        self.assertEqual(resolve.call_count, 4)

    def test_standard_manufacturing_definitions_keep_original_lifecycle(self):
        with patch.object(FormalManufacturingEligibilityService, "resolve") as resolve:
            self.assertIsNone(EngineeringLifecycleService._formal_manufacturing_eligibility(
                "bom-versions", Obj(bom_scope="standard"), "reviewed",
            ))
            self.assertIsNone(EngineeringLifecycleService._formal_manufacturing_eligibility(
                "manufacturing-outputs", Obj(definition_mode="standard"), "engineering_review",
            ))
        resolve.assert_not_called()

    def test_lifecycle_api_reports_business_eligibility_as_http_409(self):
        request = APIRequestFactory().post(
            "/api/pde/a1-engineering/bom-versions/7/transition/",
            {"targetStatus": "reviewed"},
            format="json",
        )
        user = Obj(is_authenticated=True, company_id=7)
        force_authenticate(request, user=user)
        with patch.object(
            EngineeringLifecycleService,
            "transition",
            side_effect=ProductionFoundationError(
                "DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN",
                FormalManufacturingEligibilityService.DEVELOPMENT_MESSAGE,
            ),
        ):
            response = EngineeringLifecycleView.as_view()(request, entity="bom-versions", object_id=7)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "DEVELOPMENT_VALIDATION_FORMAL_MANUFACTURING_FORBIDDEN")

    def test_mapping_contract_is_schema_free_and_complete(self):
        required = {
            "applicabilityScope", "sourceFactCode", "materialId", "outputUom",
            "quantityBasis", "quantityExpression", "quantitySource", "salesItemMultiplier",
            "scrapRate", "itemRole", "requirementType", "supplyType", "orderSpecification",
            "rounding", "precision", "sourceRuleVersion", "effectiveScope",
            "mappingVersion", "auditIdentity",
        }
        self.assertEqual(set(MATERIAL_REQUIREMENT_MAPPING_CONTRACT["requiredFields"]), required)
        self.assertFalse(MATERIAL_REQUIREMENT_MAPPING_CONTRACT["schemaChangeRequired"])
        self.assertEqual(MATERIAL_REQUIREMENT_MAPPING_CONTRACT["quantityBasisValues"], ["PER_SALES_ITEM_UNIT", "ORDER_TOTAL"])
        self.assertIn("不做", MATERIAL_REQUIREMENT_MAPPING_CONTRACT["uomPolicy"])
        self.assertEqual(len(MATERIAL_PREVIEW_STATUSES), 8)
        self.assertIn("CONFIRMED", MATERIAL_PREVIEW_STATUSES)
        self.assertEqual(BUSINESS_CONFIRMATION_STATUSES, (
            "CONFIRMED", "READY_FOR_BUSINESS_CONFIRMATION", "MATERIAL_IDENTITY_REQUIRED",
            "QUANTITY_RULE_REQUIRED", "UOM_DEFINITION_REQUIRED", "BUSINESS_FACT_REQUIRED",
        ))

    def test_business_group_signature_uses_business_facts_not_material_id(self):
        context = {
            "product": "房门", "component": "单开门", "materialText": "", "sourceSpecification": "",
            "finishOrColor": "柚木直纹，封闭/LC-M045", "processConfiguration": "QSFB/FM",
            "paintProcess": "清水封闭", "edgeMethod": "四边", "visibleCondition": "双",
            "hardware": "", "glass": "",
        }
        facts = [{"canonicalField": "W", "unit": "m2"}]
        missing = {"sourceMaterialCode": "QSFB4601001", "businessContext": context, "facts": facts, "material": None}
        bound = {**missing, "material": {"id": 130}}
        self.assertEqual(_material_group_signature(missing), _material_group_signature(bound))
        other = {**missing, "businessContext": {**context, "component": "单面套"}}
        self.assertNotEqual(_material_group_signature(missing), _material_group_signature(other))

    def test_formal_requirement_readback_projects_confirmed_mapping_and_external_identity_without_writes(self):
        external_identity = {"id": 51, "externalId": "SOURCE|CODE:QSFB4601001"}
        requirement = {
            "id": 28, "mappingNo": "I4-MRC-001", "mappingRuleId": 40,
            "materialId": 130, "materialCode": "MAT202608000048",
            "materialName": "清水封闭实木多层板",
            "material": {"id": 130, "code": "MAT202608000048", "name": "清水封闭实木多层板", "specification": "清水封闭"},
            "sourceFactId": 102, "netQuantity": "0.856800", "uom": "m2",
            "quantityBasis": "ORDER_TOTAL", "salesItemMultiplier": "NOT_APPLIED",
            "itemRole": "MAIN_PANEL_WITH_TRIM", "requirementType": "manufacturing",
            "supplyType": "MAKE", "scrapRate": None,
            "responsibilitySource": "工程/BOM承接确认",
            "sourceExternalIdentity": external_identity,
        }
        records = [{
            "lineId": 4, "lineNo": 2, "orderQuantity": "3.0000", "orderUomCode": "套",
            "objects": [{
                "id": 6, "objectNo": "SO202609180003-DES-02-SRC-0008",
                "objectName": "单面套", "sourceKey": "房门单:14",
                "businessContext": {}, "formalMaterialRequirements": [requirement],
                "facts": [{
                    "factId": 102, "detailId": 102, "canonicalField": "X",
                    "displayName": "门套净面积", "valueText": "0.856800", "unit": "m2",
                    "sourcePath": "baseline.items[77].results[X]", "quantityBasis": {},
                }],
            }],
        }]
        mappings = [{
            "id": 40, "mappingNo": "I4-MRC-001", "mappingVersion": "V1",
            "materialId": 130, "contractStatus": "READY",
            "applicabilityScope": {"designItemNo": "SO202609180003-DES-02-SRC-0008"},
            "sourceExternalIdentity": external_identity,
        }]
        package = {
            "objectCount": 1, "groups": [], "mappingCards": [], "mappingChecklist": [],
        }

        result = _apply_formal_confirmation_readback(package, records, mappings)

        self.assertEqual(result["confirmedMappingCount"], 1)
        self.assertEqual(result["confirmedRequirementCount"], 1)
        self.assertEqual(result["mappingReadbackCount"], 1)
        self.assertEqual(result["requirementReadbackCount"], 1)
        self.assertEqual(result["mappingWriteCount"], 0)
        self.assertEqual(result["requirementWriteCount"], 0)
        self.assertEqual(result["databaseBusinessWriteCount"], 0)
        card = result["mappingCards"][0]
        self.assertEqual(card["currentStatus"], "CONFIRMED")
        self.assertEqual(card["confirmedMapping"]["id"], 40)
        self.assertEqual(card["formalRequirement"]["id"], 28)
        self.assertEqual(card["material"]["id"], 130)
        self.assertEqual(card["sourceExternalIdentity"]["id"], 51)

    def test_r1_mapping_requires_saved_fact_and_explicit_multiplier(self):
        rule = Obj(
            pk=9, rule_code="MR-MAP", version="V1", rule_kind="mapping", effective_from=None, effective_to=None,
            specification={
                "applicability": {"productCategoryId": 2},
                "outputs": [{
                    "resultDomain": "MATERIAL_REQUIREMENT", "materialId": 7, "outputUom": "m2",
                    "sourceFactCode": "net_area", "quantitySource": {"type": "SAVED_DERIVED_FACT", "sourceFactCode": "net_area"},
                    "quantityBasis": "ORDER_TOTAL", "quantityExpression": "SOURCE_FACT_VALUE",
                    "salesItemMultiplier": "NONE", "scrapRate": None, "itemRole": "component",
                    "requirementType": "manufacturing", "supplyType": "BUY", "orderSpecification": {},
                    "sourceRuleVersion": "AREA@V1",
                }],
                "decimalPrecision": 20, "outputScale": 6, "roundingMode": "ROUND_HALF_UP",
                "auditIdentity": {"authorizationReference": "USER_INSTRUCTION:TEST"},
            },
        )
        contract = _mapping_contract(rule)
        self.assertEqual(contract["contractStatus"], "READY")
        self.assertEqual(contract["missingConditions"], [])
        rule.specification["outputs"][0]["quantityExpression"] = "net_area * 2"
        self.assertEqual(_mapping_contract(rule)["contractStatus"], "INCOMPLETE")

    def test_unmatched_source_code_is_not_fuzzy_bound(self):
        analysis = _source_material_analysis({
            "sourceMaterialCode": "BTKF2601001", "sourceMaterialMasterMatch": {"status": "NO_MATCH"},
            "material": None,
        }, {})
        self.assertEqual(analysis["category"], "NON_PURE_MATERIAL_CODE")
        self.assertEqual(analysis["exactFormalMaterialCandidates"], [])
        self.assertIn("不做名称", analysis["matchingPolicy"])

    def test_scope_valid(self):
        validate_record_scope(record_fixture(), 7)

    def test_cross_company_refused(self):
        record = record_fixture(); record.engineering_instance.company_id = 8
        with self.assertRaises(HandoffReadError): validate_record_scope(record, 7)

    def test_cross_line_refused(self):
        record = record_fixture(); record.engineering_instance.sales_order_item_id = 88
        with self.assertRaises(HandoffReadError): validate_record_scope(record, 7)

    def test_source_and_baseline_context_refused(self):
        for name, value in [("sourceReference", {"id": 77}), ("baselineReference", {"orderId": 77})]:
            record = record_fixture(); record.trace[name] = value
            with self.assertRaises(HandoffReadError): validate_record_scope(record, 7)

    def test_invalid_context_never_guessed(self):
        for value in ("0", "-1", "abc", "3.1", []):
            with self.assertRaises(HandoffReadError): positive_id(value)
        self.assertIsNone(positive_id("")); self.assertEqual(positive_id("12"), 12)

    def test_quantity_is_described_never_recalculated(self):
        inputs = [{"key": "M", "name": "原始数量", "value": "2.5", "unit": "组"}]
        detail = Obj(expression_snapshot="J * K * M / 1000000", input_snapshot={"ruleInputs": inputs})
        basis = saved_quantity_basis(detail)
        self.assertEqual(basis["inputs"], inputs)
        self.assertIn("2.5", basis["quantityDependencyLabel"])
        self.assertNotIn("calculatedQuantity", basis)

    def test_geometry_does_not_invent_quantity(self):
        basis = saved_quantity_basis(Obj(expression_snapshot="J - 10", input_snapshot={"ruleInputs": [{"key": "M", "name": "数量", "value": "5"}]}))
        self.assertEqual(basis["inputs"], [])

    def test_service_has_no_writes_evaluation_or_numbering(self):
        source = Path(__file__).with_name("order_bom_handoff_service.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertFalse(calls & {"save", "create", "update", "delete", "bulk_create", "get_or_create", "generate_bom", "execute", "next_code"})
        self.assertIn("candidateQuantity=None", source)
        self.assertIn("scrapRate=None", source)

    def test_original_list_is_unchanged_without_opt_in(self):
        request = APIRequestFactory().get("/api/pde/product-boms/")
        force_authenticate(request, user=Obj(is_authenticated=True, company_id=7))
        with patch.object(PdeReadOnlyListView, "get", return_value=Response({"rows": ["existing"]})) as original:
            response = ProductBomListView.as_view()(request)
        self.assertEqual(response.data, {"rows": ["existing"]}); original.assert_called_once()

    def test_existing_preview_api_returns_business_gate_instead_of_http_500(self):
        request = APIRequestFactory().get("/api/pde/a1-engineering/calculations/3/bom-preview/")
        user = Obj(is_authenticated=True, company_id=7)
        force_authenticate(request, user=user)
        with patch.object(
            OrderEngineeringClosureService,
            "preview_bom",
            side_effect=EngineeringCalculationError(
                "MATERIAL_REQUIREMENT_REQUIRED",
                "该核算没有形成物料需求，不能生成空BOM草稿。",
            ),
        ) as preview:
            response = OrderEngineeringBomPreviewView.as_view()(request, calculation_id=3)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "MATERIAL_REQUIREMENT_REQUIRED")
        self.assertIn("不能生成空BOM草稿", response.data["message"])
        preview.assert_called_once_with(user=user, calculation_id=3)

    def test_permission_denial_does_not_remove_original_bom_list(self):
        request = APIRequestFactory().get("/api/pde/product-boms/?handoff=1")
        force_authenticate(request, user=Obj(is_authenticated=True, company_id=7))
        surfaces = {key: {} for key in ("apiFacts", "pageFacts", "diagnosticFacts", "strictFacts", "acceptanceFacts")}
        with patch("pde.order_bom_handoff_service.order_bom_handoff", side_effect=EngineeringCalculationError("PERMISSION_DENIED", "无核算查看权")), patch.object(PdeReadOnlyListView, "get", return_value=Response({"rows": ["existing"], **surfaces})):
            response = ProductBomListView.as_view()(request)
        self.assertEqual(response.data["rows"], ["existing"])
        self.assertNotIn("handoff", response.data)
        self.assertEqual(response.data["handoffReadFailure"]["errorCode"], "PERMISSION_DENIED")

    def test_read_failure_is_not_empty_success(self):
        request = APIRequestFactory().get("/api/pde/product-boms/?handoff=1")
        force_authenticate(request, user=Obj(is_authenticated=True, company_id=7))
        with patch("pde.order_bom_handoff_service.order_bom_handoff", side_effect=DatabaseError("offline")):
            response = ProductBomListView.as_view()(request)
        self.assertEqual(response.status_code, 503)
        self.assertIsNone(response.data["recordCount"])
        self.assertNotIn("handoff", response.data)
