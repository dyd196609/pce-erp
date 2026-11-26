"""SIMULATED_FOR_TEST: frozen full codes, object facts and real painting EOR.

Only Django's guarded isolated test DB is populated. Frozen provenance,
permissions, business state transitions and the native writers are not mocked.
Small representative fixtures are not the customer's 69-object result.
"""
from copy import deepcopy
from decimal import Decimal
import json

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from sales.models import SalesOrderItem, SalesOrderItemEngineeringAttribute
from system.models import User
from . import operation_requirement_service as operation
from . import tests_operation_requirement as original
from . import tests_manufacturing_eor_configuration as manufacturing
from . import tests_classified_fact_eor as classified
from .engineering_fact_extension_service import EngineeringFactExtensionService, validate_extension_fact
from .engineering_rule_foundation import specification_hash
from .formal_engineering_continuation_service import _baseline_reference, _snapshot_design_input
from .manufacturing_configuration_service import CREATE, RELEASE, ManufacturingConfigurationService
from .manufacturing_fact_batch_service import ManufacturingFactBatchService
from .models import (
    EngineeringCalculationRecord, EngineeringCalculationDetail, EngineeringDerivedFact,
    EngineeringOperationRequirement, EngineeringRuleDefinition, EngineeringSourceRecord,
    ManufacturingProcessType, OrderEngineeringBaseline, OrderEngineeringBaselineItem,
    OrderEngineeringInstance, ProductDesignItem, ProductDesignRevision,
)


class PaintingFullCodeEorTests(TestCase):
    initial = original.OperationRequirementTests.initial
    advance = original.OperationRequirementTests.advance
    make_rule = original.OperationRequirementTests.make_rule
    make_source_fact = original.OperationRequirementTests.make_source_fact
    generate = original.OperationRequirementTests.generate
    make_mode = manufacturing.ManufacturingEorConfigurationTests.make_mode
    make_capacity = manufacturing.ManufacturingEorConfigurationTests.make_capacity
    make_mapping = manufacturing.ManufacturingEorConfigurationTests.make_mapping
    grant_configuration_permissions = manufacturing.ManufacturingEorConfigurationTests.grant_configuration_permissions
    finish_source_hashes = classified.ClassifiedFactEorTests.finish_source_hashes
    full_database_snapshot = classified.ClassifiedFactEorTests.full_database_snapshot
    corrupt_json = classified.ClassifiedFactEorTests.corrupt_json
    classification_package = classified.ClassifiedFactEorTests.classification_package

    def setUp(self):
        manufacturing.ManufacturingEorConfigurationTests.setUp(self)
        self.old_initial_calculation = self.source_calc
        self.old_initial_eor = self.generate(rule=self.mapping)["operationRequirementId"]
        self.paint_a = ManufacturingProcessType.objects.create(company=self.company,
            code="SIM-INDEPENDENT-X17", name="Independent historical classification")
        self.paint_b = ManufacturingProcessType.objects.create(company=self.company,
            code="SIM-INDEPENDENT-Y29", name="Another independent classification")
        self.source_field = "opaque_visible_measure_X17"
        self.producer = self.make_rule(self.op_area, self.area, self.source_field, output_domain="DERIVED_FACT")
        self.grant_configuration_permissions(CREATE, RELEASE)
        self.serial = 0
        self.source_calc, self.raw_facts = self.build_full_origin([
            ("QSFB/FM", "2.50", None), ("QSFB/FM", "1.25", None),
            ("BTKF/GT", "4.75", None), ("BTKF/GT", "0", None),
            ("BTKF/GT", "0", None), ("BTKF/SM", "1.86", None),
            ("BTKF/GT", "0.0624", self.paint_a), ("BTKF/SM", "1.86", self.paint_a),
        ])
        self.old_paint_rules, self.old_paint_eors = [], []
        for index, fact in enumerate(self.raw_facts[-2:]):
            rule = self.make_mapping(fact, self.op_area, self.area,
                mode=self.mode, capacity=self.capacity, dynamic_source_basis=True)
            self.old_paint_rules.append(rule.pk)
            self.old_paint_eors.append(self.generate(fact=fact, rule=rule,
                key=f"sim-full-old-paint-{index}")["operationRequirementId"])
        self.fact_package = self.make_full_package()
        self.rule_ids = self.configure()
        self.manufacturing_package = self.make_eor_package()
        self.mapping_ids = self.configure_eor()
        self.preserved = self.protected_snapshot()

    def build_full_origin(self, recipe, *, edit_snapshot=None, edit_raw=None):
        """Create genuine confirmed source/baseline envelopes before completion."""
        self.serial += 1
        raw_rows = []
        for index, (code, quantity, _) in enumerate(recipe, 10):
            raw = {"id": f"SIM-FULL-SOURCE-{self.serial}-{index}", "sourceSheet": "SIM-FROZEN-SHEET",
                "sourceRow": index, "routingProcessCode": code, "quantity": "37",
                "unit": self.pcs.code, "sourceEvidence": {"C": {
                    "cell": f"SIM-FROZEN-SHEET!C{index}", "value": code, "formula": None,
                    "sourceValueType": "来源原始值"}}}
            if edit_raw:
                edit_raw(raw, index - 10)
            raw_rows.append(raw)
        payload = {"sourceKind": "SIMULATED_FOR_TEST", "engineeringRows": deepcopy(raw_rows)}
        source = self.initial(EngineeringSourceRecord, "draft", company=self.company,
            source_no=f"SIM-FULL-SOURCE-{self.serial}", source_name="Simulated frozen full-code source",
            source_type="manual_confirmed", source_version=f"SIM-FULL-V{self.serial}",
            source_payload=payload, content_hash=operation._digest(payload))
        self.advance(source, "confirmed")
        item = SalesOrderItem.objects.create(sales_order=self.order, line_no=10 + self.serial,
            material=self.material, quantity=37, uom=self.pcs, required_date=self.item.required_date,
            engineering_mode="ORDER_ENGINEERED", customer_product_name="Unrelated source caption")
        instance = self.initial(OrderEngineeringInstance, "draft", company=self.company,
            instance_no=f"SIM-FULL-INSTANCE-{self.serial}", sales_order_item=item,
            product_category=self.category, selected_process_type=self.kind, source_record=source)
        self.advance(instance, "source_confirmed")
        self.advance(instance, "calculated")
        baseline = self.initial(OrderEngineeringBaseline, "draft", company=self.company,
            sales_order=self.order, baseline_no=f"SIM-FULL-BASE-{self.serial}", sequence=self.serial + 2,
            reason="SIMULATED_FOR_TEST", candidate_hash=operation._digest(payload),
            snapshot_hash=operation._digest([]), scope_item_count=len(recipe),
            confirmable_item_count=len(recipe), blocker_count=0, blocker_summary={}, created_by=self.user)
        selected = []
        for index, ((code, quantity, reference), raw) in enumerate(zip(recipe, raw_rows), 10):
            attribute = SalesOrderItemEngineeringAttribute.objects.create(sales_order_item=item,
                sequence=index, raw_source="SIMULATED_FOR_TEST", raw_sheet=raw["sourceSheet"],
                external_source=raw["id"], raw_field="source_line_identity", raw_value=deepcopy(raw),
                canonical_field="external_source_line_identity", normalized_value=raw["id"],
                value_type="code", source_type="ENGINEERING_INPUT", created_by=self.user)
            existing = {"routingProcessCode": code, "provenance": {
                "sourceSheet": raw["sourceSheet"], "sourceRow": raw["sourceRow"]}}
            design = ProductDesignItem.objects.create(company=self.company, sales_order_item=item,
                source_record=source, source_attribute=attribute, item_no=raw["id"],
                item_name="Unrelated component label", source_version=source.source_version,
                source_content_hash=source.content_hash, product_category=self.category,
                physical_quantity=37, physical_uom=self.pcs)
            revision = ProductDesignRevision.objects.create(design_item=design, revision=1,
                design_nature="FORMAL", design_length=100, design_width=100, design_thickness=10,
                paint_process_type=reference, design_data={}, created_by=self.user)
            snapshot = {"designItem": {"id": design.pk, "physicalQuantity": "37.000000",
                "physicalUomId": self.pcs.pk, "physicalUom": self.pcs.code,
                "productCategoryId": self.category.pk, "productDefinitionId": None,
                "existingDesignData": existing}, "source": {"recordId": source.pk,
                "rawSheet": raw["sourceSheet"], "rawValue": deepcopy(raw)},
                "revision": {"id": revision.pk, "revision": 1, "designNature": "FORMAL",
                    "designLength": "100.000000", "designWidth": "100.000000",
                    "designThickness": "10.000000", "designUomId": None,
                    "materialId": None, "paintProcessTypeId": revision.paint_process_type_id,
                    "materialProcessTypeId": None, "edgeMethodId": None, "designData": {}}}
            if edit_snapshot:
                edit_snapshot(snapshot, index - 10)
            frozen = OrderEngineeringBaselineItem.objects.create(baseline=baseline,
                design_item=design, design_revision=revision, source_record=source,
                source_attribute=attribute, source_type="DESIGN_REVISION", item_no_snapshot=design.item_no,
                item_name_snapshot=design.item_name, design_item_version=design.version,
                design_revision_no=1, design_nature_snapshot="FORMAL",
                source_version_snapshot=source.source_version, source_content_hash_snapshot=source.content_hash,
                content_snapshot=snapshot, content_hash=operation._digest(snapshot), confirmable=True)
            selected.append((frozen, quantity))
        baseline.snapshot_hash = operation._digest([row.content_hash for row, _ in selected])
        baseline.confirmed_by, baseline.confirmed_at = self.user, timezone.now()
        baseline.save(update_fields=("snapshot_hash", "confirmed_by", "confirmed_at"))
        self.advance(baseline, "confirmed")
        objects = [{"baselineItemId": row.pk, "designItemId": row.design_item_id,
            "designItemNo": row.item_no_snapshot, "sourceAttributeId": row.source_attribute_id,
            "sourceKey": f"SIM-FROZEN-SHEET:{index}", "contentHash": row.content_hash,
            "sourceVersion": source.source_version, "sourceContentHash": source.content_hash,
            "input": _snapshot_design_input(row)} for index, (row, _) in enumerate(selected, 10)]
        reference = _baseline_reference(baseline, [row for row, _ in selected])
        input_hash = operation._digest({"baseline": reference, "objects": objects})
        calc = self.initial(EngineeringCalculationRecord, "running", company=self.company,
            scope="order_engineering", source_record=source, sales_order_item=item, engineering_instance=instance,
            calculation_no=f"SIM-FULL-ORIGIN-{self.serial}", rule_set_version="SIM-V1", revision=self.serial + 2,
            input_hash=input_hash, rule_graph_hash=operation._digest([]), result_hash=operation._digest([]),
            trace={"baselineReference": reference, "objectInputSnapshot": objects,
                "objectInputSnapshotHash": input_hash, "sourceReference": {"id": source.pk,
                    "sourceVersion": source.source_version, "contentHash": source.content_hash}})
        saved = self.source_calc
        self.source_calc = calc
        facts = []
        for index, ((frozen, quantity), envelope) in enumerate(zip(selected, objects), 1):
            fact = self.make_source_fact(self.producer, self.area, self.source_field, quantity, index)
            fact.trace.update(baselineId=baseline.pk, baselineItemId=frozen.pk,
                baselineContentHash=frozen.content_hash, designItemId=frozen.design_item_id,
                sourceAttributeId=frozen.source_attribute_id, resultScope="original")
            fact.save(update_fields=("trace",))
            detail = fact.source_detail
            detail.input_snapshot["object"] = deepcopy(envelope["input"])
            detail.save(update_fields=("input_snapshot",))
            facts.append(fact)
        self.finish_source_hashes(calc, facts)
        self.advance(calc, "completed")
        self.source_calc = saved
        return calc, facts

    def make_full_package(self):
        package = self.classification_package(code="SIM-FULL-CODE-AREA")
        row = package["rules"][0]
        row["version"] = row["specification"]["rulePackage"]["version"] = "V2"
        row["specification"]["outputs"][0]["canonicalName"] = "PaintingProcessAreaQuantity"
        config = row["specification"]["factExtension"]
        config["objectInputConditions"] = [{"inputPath": ["paintProcessTypeId"], "operator": "IS_NULL"}]
        config["metadataBindings"] = [
            {"name": "ProductPaintingProcessCode", "sourceType": "FORMAL_FROZEN_VALUE", "inputPath": ["routingProcessCode"]},
            {"name": "AreaType", "sourceType": "CONFIGURATION_VALUE", "value": "VISIBLE_AREA"},
        ] + [{"name": name, "sourceType": "FORMAL_SOURCE_IDENTITY", "valueField": name}
             for name in ("designItemId", "baselineItemId", "sourceAttributeId")]
        config["groupKeys"] = ["ProductPaintingProcessCode", "AreaType", "designItemId", "baselineItemId", "sourceAttributeId"]
        config.update(quantityTraceKey="AreaQuantity", uomTraceKey="UOM", inputHashTraceKey="InputHash")
        config["bindings"][0]["selector"]["traceEquals"] = {"resultScope": "original"}
        package["consolidatedReadback"]["groupKeys"] = deepcopy(config["groupKeys"])
        return package

    def make_eor_package(self):
        rows = []
        for code in ("QSFB/FM", "BTKF/GT", "BTKF/SM"):
            spec = deepcopy(self.mapping.specification)
            spec["expression"] = "declared_area"
            spec["inputs"] = [{"canonicalName": "declared_area", "sourceCanonicalField": "PaintingProcessAreaQuantity",
                "sourceType": "ENGINEERING_DERIVED", "valueType": "decimal", "unit": self.area.code,
                "unitDimension": "area", "required": True, "unitRequired": True}]
            output = spec["outputs"][0]
            output.pop("basisQuantity", None)
            output.pop("basisUomId", None)
            output.update(canonicalName="sim_full_paint_demand", quantityBasis="SOURCE_SCOPE_TOTAL",
                basisQuantitySource="SALES_ORDER_ITEM", basisUomSource="SALES_ORDER_ITEM")
            config = spec["manufacturing"]
            config.pop("modeId", None)
            config.update(modeCode=self.mode.code, modeVersion=self.mode.version)
            config["sourceSelector"] = {"canonicalField": "PaintingProcessAreaQuantity",
                "producerRuleCode": "SIM-FULL-CODE-AREA", "producerRuleVersion": "V2",
                "traceEquals": {"ProductPaintingProcessCode": code, "AreaType": "VISIBLE_AREA"},
                "candidatePolicy": "MATCH_CONFIGURED_TRACE", "objectTraceKeys": [
                    "baseEngineeringCalculationId", "designItemId", "baselineItemId", "sourceAttributeId", "InputHash"]}
            rows.append({"ruleCode": "SIM-FULL-EOR-" + code.replace("/", "-"),
                "ruleName": "Simulated configured full code", "version": "V2", "specification": spec})
        return {"contractVersion": "PCE-MANUFACTURING-EOR-RULE-V1", "companyId": self.company.pk,
            "modes": [], "rules": rows}

    def configure(self, package=None, user=None):
        return EngineeringFactExtensionService.configure(user=user or self.user,
            package=package or self.fact_package, reason="SIMULATED_FOR_TEST")["ruleIds"]

    def configure_eor(self, package=None):
        package = deepcopy(package or self.manufacturing_package)
        for row in package["rules"]:
            selector = row["specification"]["manufacturing"]["sourceSelector"]
            selector.pop("producerRuleCode", None)
            selector["producerRuleId"] = self.rule_ids[0]
        return [row["id"] for row in ManufacturingConfigurationService.configure(user=self.user,
            package=package, reason="SIMULATED_FOR_TEST")["rules"]]

    def derive(self, *, source=None, key="sim-full-code", rules=None, user=None):
        return EngineeringFactExtensionService.derive(user=user or self.user,
            source_calculation_id=(source or self.source_calc).pk, rule_ids=rules or self.rule_ids,
            idempotency_key=key, reason="SIMULATED_FOR_TEST")

    def pipeline(self, *, source=None, key="sim-full-code", mapping=None, rules=None):
        return ManufacturingFactBatchService.execute(user=self.user, fact_package=self.fact_package,
            manufacturing_package=mapping or self.manufacturing_package,
            source_calculation_ids=[(source or self.source_calc).pk], request_key=key,
            reason="SIMULATED_FOR_TEST", allow_partial=False)

    def protected_snapshot(self):
        calculations = [self.old_initial_calculation.pk, self.source_calc.pk]
        return {"calcs": list(EngineeringCalculationRecord.objects.filter(pk__in=calculations).order_by("pk").values()),
            "facts": list(EngineeringDerivedFact.objects.filter(calculation_id__in=calculations).order_by("pk").values()),
            "details": list(EngineeringCalculationDetail.objects.filter(calculation_id__in=calculations).order_by("pk").values()),
            "rules": list(EngineeringRuleDefinition.objects.filter(pk__in=self.old_paint_rules).order_by("pk").values()),
            "eors": list(EngineeringOperationRequirement.objects.filter(pk__in=[self.old_initial_eor,
                *self.old_paint_eors]).order_by("pk").values())}

    def no_write_failure(self, action, code=None):
        before = self.full_database_snapshot()
        with self.assertRaises(operation.OperationRequirementError) as caught:
            action()
        if code:
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.full_database_snapshot(), before)
        return caught.exception.code

    def rejected_configuration(self, edit):
        package = deepcopy(self.fact_package)
        edit(package["rules"][0]["specification"]["factExtension"])
        self.no_write_failure(lambda: self.configure(package), "FACT_METADATA_CONFIG_INVALID")

    def test_three_complete_codes_keep_slashes_and_independent_object_facts(self):
        result = self.derive()
        facts = list(EngineeringDerivedFact.objects.filter(pk__in=result["factIds"]))
        self.assertEqual(len(facts), 6)
        self.assertEqual({f.trace["ProductPaintingProcessCode"] for f in facts}, {"QSFB/FM", "BTKF/GT", "BTKF/SM"})
        self.assertEqual(len({f.trace["designItemId"] for f in facts}), 6)
        self.assertEqual(sum(Decimal(f.value["decimal"]) for f in facts), Decimal("10.36"))
        self.assertEqual(self.protected_snapshot(), self.preserved)

    def test_each_input_proves_original_fact_object_version_hash_and_cell(self):
        result = self.derive()
        calc = EngineeringCalculationRecord.objects.get(pk=result["calculationId"])
        for fact in EngineeringDerivedFact.objects.filter(pk__in=result["factIds"]):
            validate_extension_fact(calc, fact)
            self.assertEqual(fact.inputs.count(), 1)
            link = fact.inputs.get()
            proof = link.input_snapshot["metadataProof"]
            self.assertEqual(proof["designItemId"], fact.trace["designItemId"])
            self.assertEqual(proof["sourceRecordVersion"], self.source_calc.source_record.source_version)
            self.assertEqual(proof["sourceRecordHash"], self.source_calc.source_record.content_hash)
            self.assertEqual(link.source_hash, operation._digest(link.input_snapshot))
            self.assertEqual(fact.trace["InputHash"], operation._digest(fact.source_detail.input_snapshot))
            binding = proof["bindings"][0]
            self.assertIn(fact.trace["ProductPaintingProcessCode"], json.dumps(binding, ensure_ascii=False))
            self.assertIn("!C", json.dumps(binding, ensure_ascii=False))

    def test_conditions_exclude_two_previously_classified_objects_without_mutation(self):
        preview = EngineeringFactExtensionService.preview(user=self.user,
            source_calculation_id=self.source_calc.pk, rule_ids=self.rule_ids)
        self.assertEqual({r["sourceFactId"] for r in preview["excludedInputs"]}, {f.pk for f in self.raw_facts[-2:]})
        result = self.derive()
        linked = set(EngineeringDerivedFact.objects.filter(pk__in=result["factIds"])
            .values_list("inputs__source_fact_id", flat=True))
        self.assertEqual(linked, {f.pk for f in self.raw_facts[:-2]})
        self.assertEqual(self.protected_snapshot(), self.preserved)

    def test_two_zero_objects_keep_typed_facts_and_source_links_without_zero_eor(self):
        result = self.pipeline()
        generated = result["runs"][0]["generation"]
        self.assertEqual(len(generated["requirements"]), 4)
        self.assertEqual(len(generated["retainedZeroFacts"]), 2)
        zeros = EngineeringDerivedFact.objects.filter(pk__in=result["runs"][0]["derivation"]["factIds"],
            value__decimal="0.000000")
        self.assertEqual(zeros.count(), 2)
        self.assertEqual(set(zeros.values_list("inputs__source_fact_id", flat=True)), {f.pk for f in self.raw_facts[3:5]})
        self.assertEqual(result["coverageStatus"], "COMPLETE")

    def test_source_area_is_dynamic_and_sales_basis_thirty_seven_does_not_multiply(self):
        origin, _ = self.build_full_origin([("QSFB/FM", "17.123456", None)])
        result = self.pipeline(source=origin, key="sim-dynamic-area")
        self.assertEqual(result["runs"][0]["generation"]["requirements"][0]["workloadQuantity"], "17.123456")
        self.assertEqual(origin.sales_order_item.quantity, Decimal("37"))

    def test_native_eors_reference_version_mode_resources_object_and_actual_audit(self):
        result = self.pipeline()
        for row in result["runs"][0]["generation"]["requirements"]:
            req = EngineeringOperationRequirement.objects.get(pk=row["id"])
            operation._validate_requirement(req, self.company.pk)
            self.assertEqual(req.uom_id, self.area.pk)
            self.assertEqual(req.standard_capacity_id, self.capacity.pk)
            self.assertEqual(req.audit_record.actor_id, self.user.pk)
            self.assertEqual(req.source_detail.rule_version, "V2")
            self.assertEqual(len(req.source_hash), len(req.input_hash))
            self.assertEqual(len(req.input_hash), 64)
            self.assertEqual(req.source_fact.inputs.count(), 1)
        self.assertEqual(self.protected_snapshot(), self.preserved)

    def test_preview_and_same_request_replay_are_zero_write_for_every_test_table(self):
        before = self.full_database_snapshot()
        EngineeringFactExtensionService.preview(user=self.user,
            source_calculation_id=self.source_calc.pk, rule_ids=self.rule_ids)
        self.assertEqual(self.full_database_snapshot(), before)
        first = self.pipeline()
        after = self.full_database_snapshot()
        second = self.pipeline()
        self.assertEqual(self.full_database_snapshot(), after)
        self.assertEqual(first["consolidatedFacts"], second["consolidatedFacts"])
        self.assertEqual(second["runs"][0]["generation"]["businessWriteCount"], 0)
        self.assertEqual(second["runs"][0]["generation"]["auditWriteCount"], 0)

    def test_old_rules_outside_new_whitelist_do_not_create_duplicate_eors(self):
        self.pipeline()
        self.assertEqual(set(EngineeringOperationRequirement.objects.filter(source_detail__rule_id__in=self.old_paint_rules)
            .values_list("pk", flat=True)), set(self.old_paint_eors))
        self.assertEqual(self.protected_snapshot(), self.preserved)

    def test_configuration_replay_cannot_overwrite_an_existing_version(self):
        before = self.full_database_snapshot()
        self.assertEqual(self.configure(), self.rule_ids)
        self.assertEqual(self.full_database_snapshot(), before)
        package = deepcopy(self.fact_package)
        package["rules"][0]["specification"]["sourceEvidence"]["reference"] = "Changed historical semantic"
        self.no_write_failure(lambda: self.configure(package))

    def test_legacy_default_contract_keeps_shape_and_three_hash_serializations(self):
        legacy = self.classification_package(code="SIM-LEGACY-FK")
        rules = self.configure(legacy)
        preview = EngineeringFactExtensionService.preview(user=self.user,
            source_calculation_id=self.source_calc.pk, rule_ids=rules)
        plan = preview["plan"]
        self.assertNotIn("excludedInputs", plan)
        self.assertNotIn("excludedInputs", preview)
        inputs = {"source": plan["source"], "graph": plan["graph"],
            "inputs": [c["sources"] for c in plan["contexts"]],
            "retainedMissingMetadata": plan["retainedMissingMetadata"]}
        self.assertEqual(plan["inputHash"], operation._digest(inputs))
        self.assertEqual(plan["ruleGraphHash"], operation._digest(plan["graph"]))
        self.assertEqual(plan["resultHash"], operation._digest({"contexts": plan["contexts"],
            "retainedMissingMetadata": plan["retainedMissingMetadata"]}))
        for context in plan["contexts"]:
            for source in context["sources"]:
                self.assertNotIn("objectInputConditions", source["metadataProof"])

    def test_unknown_frozen_path_and_arbitrary_source_identity_are_rejected(self):
        self.rejected_configuration(lambda c: c["metadataBindings"][0].update(inputPath=["finishOrColor"]))
        self.rejected_configuration(lambda c: c["metadataBindings"][2].update(valueField="salesOrderNumber"))

    def test_provenance_collisions_and_all_configuration_constants_are_rejected(self):
        self.rejected_configuration(lambda c: c["metadataBindings"][0].update(name="outputHash"))
        self.rejected_configuration(lambda c: c["metadataBindings"][0].update(name="AreaQuantity"))
        def constants(config):
            config["metadataBindings"] = [{"name": "OnlyCode", "sourceType": "CONFIGURATION_VALUE", "value": "QSFB/FM"}]
            config["groupKeys"] = ["OnlyCode"]
        self.rejected_configuration(constants)

    def test_condition_operator_unknown_path_and_malformed_contract_are_rejected(self):
        for condition in ({"inputPath": ["sourceRow"], "operator": "IS_NULL"},
                {"inputPath": ["paintProcessTypeId"], "operator": "DEFAULT"},
                {"inputPath": ["paintProcessTypeId"], "operator": "IS_NULL", "value": None}):
            with self.subTest(condition=condition):
                self.rejected_configuration(lambda c: c.update(objectInputConditions=[condition]))

    def test_missing_condition_key_is_not_treated_as_null(self):
        trace = deepcopy(self.source_calc.trace)
        trace["objectInputSnapshot"][0]["input"].pop("paintProcessTypeId")
        self.corrupt_json(self.source_calc, "trace", trace)
        self.no_write_failure(lambda: self.derive(), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_missing_frozen_revision_fk_key_is_not_defaulted_to_null(self):
        origin, _ = self.build_full_origin([("QSFB/FM", "1", None)],
            edit_snapshot=lambda s, _: s["revision"].pop("paintProcessTypeId"))
        self.assertIsNone(origin.trace["objectInputSnapshot"][0]["input"]["paintProcessTypeId"])
        self.no_write_failure(lambda: self.derive(source=origin), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_non_text_and_untrimmed_full_codes_are_not_valid_business_identity(self):
        for code in (True, 17, " QSFB/FM "):
            with self.subTest(code=code):
                origin, _ = self.build_full_origin([(code, "1", None)])
                self.no_write_failure(lambda: self.derive(source=origin), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_all_zero_source_objects_retain_classification_without_positive_eor(self):
        origin, raw = self.build_full_origin([("BTKF/GT", "0", None), ("BTKF/GT", "0", None)])
        result = self.pipeline(source=origin, key="sim-full-zero-only")
        run = result["runs"][0]
        self.assertEqual(len(run["derivation"]["factIds"]), 2)
        self.assertEqual(run["generation"]["requirements"], [])
        self.assertEqual(run["generation"]["blockers"], [])
        self.assertEqual(len(run["generation"]["retainedZeroFacts"]), 2)
        self.assertEqual(set(EngineeringDerivedFact.objects.filter(pk__in=run["derivation"]["factIds"])
            .values_list("inputs__source_fact_id", flat=True)), {fact.pk for fact in raw})
        self.assertEqual(result["coverageStatus"], "COMPLETE")

    def test_boolean_formal_identity_is_rejected(self):
        fact = self.raw_facts[0]
        trace = deepcopy(fact.trace)
        trace["designItemId"] = True
        self.corrupt_json(fact, "trace", trace)
        self.no_write_failure(lambda: self.derive(), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_full_code_c_evidence_cannot_disagree_with_frozen_object(self):
        origin, _ = self.build_full_origin([("QSFB/FM", "1", None)],
            edit_snapshot=lambda s, _: s["source"]["rawValue"]["sourceEvidence"]["C"].update(value="BTKF/GT"))
        self.no_write_failure(lambda: self.derive(source=origin), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_wrong_source_cell_and_missing_c_proof_are_rejected(self):
        for edit in (lambda s, _: s["source"]["rawValue"]["sourceEvidence"]["C"].update(cell="OTHER!C10"),
                lambda s, _: s["source"]["rawValue"]["sourceEvidence"].pop("C")):
            origin, _ = self.build_full_origin([("QSFB/FM", "1", None)], edit_snapshot=edit)
            self.no_write_failure(lambda: self.derive(source=origin), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_empty_code_is_retained_as_missing_even_for_zero_and_complete_batch_rolls_back(self):
        origin, raw = self.build_full_origin([("", "1", None), ("", "0", None)])
        before = self.full_database_snapshot()
        preview = EngineeringFactExtensionService.preview(user=self.user,
            source_calculation_id=origin.pk, rule_ids=self.rule_ids)
        self.assertEqual({r["sourceFactId"] for r in preview["retainedMissingMetadata"]}, {f.pk for f in raw})
        self.assertEqual(preview["groupCount"], 0)
        self.assertEqual(self.full_database_snapshot(), before)
        self.no_write_failure(lambda: self.pipeline(source=origin), "CLASSIFIED_METADATA_REQUIRED")

    def test_original_detail_and_baseline_hash_tampering_are_fail_closed(self):
        detail = self.raw_facts[0].source_detail
        saved = deepcopy(detail.input_snapshot)
        changed = deepcopy(saved)
        changed["object"]["routingProcessCode"] = "BTKF/GT"
        self.corrupt_json(detail, "input_snapshot", changed)
        self.no_write_failure(lambda: self.derive(), "FACT_METADATA_SOURCE_UNPROVEN")
        self.corrupt_json(detail, "input_snapshot", saved)
        item = OrderEngineeringBaselineItem.objects.get(pk=self.raw_facts[0].trace["baselineItemId"])
        content = deepcopy(item.content_snapshot)
        content["designItem"]["existingDesignData"]["routingProcessCode"] = "BTKF/GT"
        self.corrupt_json(item, "content_snapshot", content)
        self.no_write_failure(lambda: self.derive(), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_source_version_drift_and_later_design_revision_do_not_replace_frozen_code(self):
        item = OrderEngineeringBaselineItem.objects.get(pk=self.raw_facts[0].trace["baselineItemId"])
        ProductDesignRevision.objects.create(design_item=item.design_item, revision=2, design_nature="FORMAL",
            paint_process_type=self.paint_b, design_data={"routingProcessCode": "BTKF/SM"}, created_by=self.user)
        result = self.derive()
        fact = EngineeringDerivedFact.objects.get(pk__in=result["factIds"], trace__designItemId=item.design_item_id)
        self.assertEqual(fact.trace["ProductPaintingProcessCode"], "QSFB/FM")
        trace = deepcopy(self.source_calc.trace)
        trace["sourceReference"]["sourceVersion"] = "OTHER-VERSION"
        self.corrupt_json(self.source_calc, "trace", trace)
        self.no_write_failure(lambda: self.derive(key="sim-changed-version"), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_saved_full_code_metadata_or_input_proof_corruption_is_rejected(self):
        result = self.derive()
        fact = EngineeringDerivedFact.objects.get(pk=result["factIds"][0])
        calc = fact.calculation
        trace = deepcopy(fact.trace)
        trace["ProductPaintingProcessCode"] = "QSFB"
        self.corrupt_json(fact, "trace", trace)
        fact.refresh_from_db()
        self.no_write_failure(lambda: validate_extension_fact(calc, fact))

    def test_missing_full_code_mapping_rolls_back_the_whole_batch(self):
        package = deepcopy(self.manufacturing_package)
        package["rules"] = package["rules"][:1]
        self.no_write_failure(lambda: self.pipeline(mapping=package), "CLASSIFIED_EOR_MAPPING_REQUIRED")

    def test_fact_and_eor_units_are_validated_without_fixed_conversion(self):
        package = deepcopy(self.fact_package)
        package["rules"][0]["specification"]["factExtension"]["bindings"][0]["targetUomId"] = self.pcs.pk
        self.no_write_failure(lambda: self.configure(package), "FACT_UOM_MISMATCH")
        self.capacity.uom = self.pcs
        self.capacity.save(update_fields=("uom",))
        self.no_write_failure(lambda: self.pipeline())

    def test_execution_and_publication_permissions_remain_real_and_fail_before_writes(self):
        user = User.objects.create_user(username="sim_full_code_without_authority", company_id=self.company.pk)
        self.no_write_failure(lambda: self.derive(user=user), "PERMISSION_DENIED")
        self.no_write_failure(lambda: self.configure(user=user), "PERMISSION_DENIED")

    def test_unpublished_new_rule_and_wrong_source_producer_version_are_rejected(self):
        package = deepcopy(self.fact_package)
        package["rules"][0]["specification"]["factExtension"]["bindings"][0]["selector"]["producerRuleVersion"] = "V99"
        self.no_write_failure(lambda: self.configure(package), "FACT_RULE_NOT_RELEASED")
        with connection.cursor() as cursor:
            cursor.execute("UPDATE pde_engineering_rule_definition SET status='draft' WHERE id=%s", (self.rule_ids[0],))
        self.no_write_failure(lambda: self.derive(), "FACT_RULE_NOT_RELEASED")
