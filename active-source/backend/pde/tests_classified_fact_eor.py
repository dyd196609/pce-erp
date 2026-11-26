"""SIMULATED_FOR_TEST: classified facts use real frozen input and real EOR.

All writes occur in Django's isolated test DB. No metadata resolver, source
proof, permission check or business writer is mocked to manufacture a PASS.
Fixture helpers are borrowed without inheriting or rerunning prior TestCases.
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal
import json

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from sales.models import SalesOrderItem, SalesOrderItemEngineeringAttribute
from system.models import Company, User
from . import operation_requirement_service as operation
from . import tests_operation_requirement as original_fixtures
from . import tests_manufacturing_eor_configuration as manufacturing_fixtures
from .engineering_fact_extension_service import (
    CONTRACT as FACT_CONTRACT, EngineeringFactExtensionService, validate_extension_fact,
)
from .engineering_rule_foundation import specification_hash
from .formal_engineering_continuation_service import _baseline_reference, _snapshot_design_input
from .manufacturing_configuration_service import (
    CREATE, RELEASE, CONTRACT as MANUFACTURING_CONTRACT, ManufacturingConfigurationService,
)
from .manufacturing_fact_batch_service import ManufacturingFactBatchService
from .models import (
    CapacityProductType, EngineeringCalculationDetail, EngineeringCalculationRecord, EngineeringDerivedFact,
    EngineeringOperationRequirement, EngineeringRuleDefinition, EngineeringSourceRecord,
    ManufacturingProcessType, OrderEngineeringBaseline, OrderEngineeringBaselineItem,
    OrderEngineeringInstance, ProductCategory, ProductDesignItem, ProductDesignRevision,
)


class ClassifiedFactEorTests(TestCase):
    initial = original_fixtures.OperationRequirementTests.initial
    advance = original_fixtures.OperationRequirementTests.advance
    make_rule = original_fixtures.OperationRequirementTests.make_rule
    make_source_fact = original_fixtures.OperationRequirementTests.make_source_fact
    generate = original_fixtures.OperationRequirementTests.generate
    make_mode = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_mode
    make_capacity = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_capacity
    make_mapping = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_mapping
    grant_configuration_permissions = manufacturing_fixtures.ManufacturingEorConfigurationTests.grant_configuration_permissions

    def setUp(self):
        manufacturing_fixtures.ManufacturingEorConfigurationTests.setUp(self)
        self.old_eor_id = self.generate(rule=self.mapping)["operationRequirementId"]
        self.old_calculation_id = self.source_calc.pk
        self.paint_a = ManufacturingProcessType.objects.create(company=self.company,
            code="SIM-COATING-X17", name="Abstract coating class one")
        self.paint_b = ManufacturingProcessType.objects.create(company=self.company,
            code="SIM-COATING-Y29", name="Abstract coating class two")
        self.source_field = "unrelated_measure_token"
        self.producer = self.make_rule(self.op_area, self.area, self.source_field, output_domain="DERIVED_FACT")
        self.serial = 0
        self.grant_configuration_permissions(CREATE, RELEASE)
        origins = self.build_sources([{
            "item": self.item, "instance": self.instance,
            "rows": [(self.paint_a, "2.50"), (self.paint_a, "1.25"),
                     (self.paint_b, "4.75"), (None, "3.00"), (None, "0.00")],
        }])
        self.source_calc, self.raw_facts = origins[0]
        self.fact_package = self.classification_package()
        self.manufacturing_package = self.eor_package()
        self.preserved = self.source_snapshot()

    def build_sources(self, groups, *, source=None, reference_field="paintProcessTypeId"):
        """Create a confirmed shared baseline and independently frozen origins."""
        source = source or self.source
        self.serial += 1
        baseline = self.initial(OrderEngineeringBaseline, "draft", company=self.company,
            sales_order=self.order, baseline_no=f"SIM-CLASSIFIED-BASE-{self.serial}",
            sequence=self.serial + 1, reason="SIMULATED_FOR_TEST classified input",
            candidate_hash=operation._digest([{"itemId": group["item"].pk,
                "instanceId": group["instance"].pk, "rows": [
                    [reference.pk if reference else None, quantity] for reference, quantity in group["rows"]]}
                for group in groups]), snapshot_hash=operation._digest([]),
            scope_item_count=sum(len(group["rows"]) for group in groups),
            confirmable_item_count=sum(len(group["rows"]) for group in groups),
            blocker_count=0, blocker_summary={}, created_by=self.user)
        selected = []
        for group_no, group in enumerate(groups):
            items = []
            for row_no, (reference, quantity) in enumerate(group["rows"]):
                token = f"{self.serial}-{group_no}-{row_no}"
                attribute = SalesOrderItemEngineeringAttribute.objects.create(
                    sales_order_item=group["item"], sequence=100 + row_no + self.serial * 20,
                    raw_source="SIMULATED_FOR_TEST", raw_sheet="ABSTRACT-SHEET",
                    external_source=token, raw_field="stable_object", raw_value={"token": token},
                    canonical_field="stable_object", normalized_value={"token": token},
                    value_type="json", source_type="ENGINEERING_INPUT", created_by=self.user)
                design = ProductDesignItem.objects.create(company=self.company,
                    sales_order_item=group["item"], source_record=source, source_attribute=attribute,
                    item_no=f"SIM-CLASSIFIED-OBJECT-{token}", item_name="Abstract independent source object",
                    source_version=source.source_version, source_content_hash=source.content_hash,
                    product_category=group["instance"].product_category,
                    physical_quantity=Decimal("37"), physical_uom=self.pcs)
                revision_values = {"paint_process_type": None, "material_process_type": None}
                revision_values["paint_process_type" if reference_field == "paintProcessTypeId"
                                else "material_process_type"] = reference
                revision = ProductDesignRevision.objects.create(design_item=design, revision=1,
                    design_nature="FORMAL", design_length=100, design_width=100,
                    design_thickness=10, design_data={}, created_by=self.user, **revision_values)
                snapshot = {
                    "designItem": {"id": design.pk, "physicalQuantity": "37.000000",
                        "physicalUomId": self.pcs.pk, "physicalUom": self.pcs.code,
                        "productCategoryId": group["instance"].product_category_id,
                        "productDefinitionId": None, "existingDesignData": {
                            "provenance": {"sourceSheet": "ABSTRACT-SHEET", "sourceRow": row_no + 1}}},
                    "source": {"recordId": source.pk, "rawSheet": "ABSTRACT-SHEET"},
                    "revision": {"id": revision.pk, "revision": 1, "designNature": "FORMAL",
                        "designLength": "100.000000", "designWidth": "100.000000",
                        "designThickness": "10.000000", "designUomId": None,
                        "materialId": None, "paintProcessTypeId": revision.paint_process_type_id,
                        "materialProcessTypeId": revision.material_process_type_id,
                        "edgeMethodId": None, "designData": {}},
                }
                item = OrderEngineeringBaselineItem.objects.create(baseline=baseline,
                    design_item=design, design_revision=revision, source_record=source,
                    source_attribute=attribute, source_type="DESIGN_REVISION",
                    item_no_snapshot=design.item_no, item_name_snapshot=design.item_name,
                    design_item_version=design.version, design_revision_no=1,
                    design_nature_snapshot="FORMAL", source_version_snapshot=source.source_version,
                    source_content_hash_snapshot=source.content_hash, content_snapshot=snapshot,
                    content_hash=operation._digest(snapshot), confirmable=True)
                items.append((item, quantity))
            selected.append((group, items))
        complete = list(baseline.items.order_by("design_item__sales_order_item__line_no",
            "source_attribute_id", "design_item_id", "pk"))
        baseline.snapshot_hash = operation._digest([item.content_hash for item in complete])
        baseline.confirmed_by, baseline.confirmed_at = self.user, timezone.now()
        baseline.save(update_fields=("snapshot_hash", "confirmed_by", "confirmed_at"))
        self.advance(baseline, "confirmed")
        output = []
        for group_no, (group, items) in enumerate(selected):
            objects = [{"baselineItemId": item.pk, "designItemId": item.design_item_id,
                "designItemNo": item.item_no_snapshot, "sourceAttributeId": item.source_attribute_id,
                "sourceKey": f"ABSTRACT-SHEET:{index + 1}", "contentHash": item.content_hash,
                "sourceVersion": source.source_version, "sourceContentHash": source.content_hash,
                "input": _snapshot_design_input(item)} for index, (item, _) in enumerate(items)]
            reference = _baseline_reference(baseline, [item for item, _ in items])
            input_hash = operation._digest({"baseline": reference, "objects": objects})
            calculation = self.initial(EngineeringCalculationRecord, "running", company=self.company,
                scope="order_engineering", source_record=source, sales_order_item=group["item"],
                engineering_instance=group["instance"], calculation_no=f"SIM-CLASSIFIED-ORIGIN-{self.serial}-{group_no}",
                rule_set_version="SIM-V1", revision=self.serial + 2,
                input_hash=input_hash, rule_graph_hash=operation._digest([]), result_hash=operation._digest([]),
                trace={"baselineReference": reference, "objectInputSnapshot": objects,
                    "objectInputSnapshotHash": input_hash, "sourceReference": {
                        "id": source.pk, "sourceVersion": source.source_version, "contentHash": source.content_hash}})
            saved_calculation = self.source_calc
            self.source_calc = calculation
            facts = []
            for index, ((item, quantity), envelope) in enumerate(zip(items, objects), 1):
                fact = self.make_source_fact(self.producer, self.area, self.source_field, quantity, index)
                fact.trace.update(baselineId=baseline.pk, baselineItemId=item.pk,
                    baselineContentHash=item.content_hash, designItemId=item.design_item_id,
                    sourceAttributeId=item.source_attribute_id)
                fact.save(update_fields=("trace",))
                detail = fact.source_detail
                detail.input_snapshot["object"] = deepcopy(envelope["input"])
                detail.save(update_fields=("input_snapshot",))
                facts.append(fact)
            for additional in group.get("extraMeasurements", []):
                index = additional["objectIndex"]
                item, _ = items[index]
                fact = self.make_source_fact(additional["producer"], self.area,
                    additional["field"], additional["quantity"], len(facts) + 1)
                fact.trace.update(baselineId=baseline.pk, baselineItemId=item.pk,
                    baselineContentHash=item.content_hash, designItemId=item.design_item_id,
                    sourceAttributeId=item.source_attribute_id)
                fact.save(update_fields=("trace",))
                detail = fact.source_detail
                detail.input_snapshot["object"] = deepcopy(objects[index]["input"])
                detail.save(update_fields=("input_snapshot",))
                facts.append(fact)
            self.source_calc = saved_calculation
            self.finish_source_hashes(calculation, facts)
            self.advance(calculation, "completed")
            output.append((calculation, facts))
        return output

    def finish_source_hashes(self, calculation, facts):
        graph = [{"ruleId": fact.rule_id, "ruleCode": fact.rule.rule_code,
            "ruleVersion": fact.rule.version, "specificationHash": specification_hash(fact.rule.specification)}
            for fact in facts]
        results = [{"factId": fact.pk, "detailId": fact.source_detail_id,
            "canonicalField": fact.canonical_field, "displayName": fact.source_detail.output_name,
            "ruleCode": fact.rule.rule_code, "ruleVersion": fact.rule.version, "value": fact.value} for fact in facts]
        calculation.rule_graph_hash, calculation.result_hash = operation._digest(graph), operation._digest(results)
        calculation.trace.update(ruleGraphSnapshot=graph, resultSnapshot=results, resultHash=calculation.result_hash)
        calculation.started_at = calculation.finished_at = timezone.now()
        calculation.save(update_fields=("rule_graph_hash", "result_hash", "trace", "started_at", "finished_at"))

    def classification_package(self, *, code="SIM-CLASSIFIED-SUM", field=None, producer=None, area_type="VISIBLE_RECORD"):
        producer = producer or self.producer
        specification = {"rulePackage": {"code": code, "version": "V1"},
            "expression": "area_quantity", "inputs": [{"canonicalName": "area_quantity",
                "valueType": "decimal", "unit": self.area.code, "unitDimension": "area",
                "sourceType": "AGGREGATED", "required": True, "unitRequired": True}],
            "outputs": [{"canonicalName": "abstract_grouped_measure", "valueType": "decimal",
                "unit": self.area.code, "unitDimension": "area", "resultDomain": "DERIVED_FACT"}],
            "dependencies": [], "applicability": {}, "decimalPrecision": 28,
            "outputScale": 6, "roundingMode": "ROUND_HALF_UP", "sourceEvidence": {"reference": "SIMULATED_FOR_TEST"},
            "factExtension": {"contractVersion": FACT_CONTRACT, "strategy": "GROUP_SUM",
                "productCategoryIds": [], "outputUomId": self.area.pk,
                "groupKeys": ["CoatingClass", "AreaClass"],
                "metadataBindings": [
                    {"name": "CoatingClass", "sourceType": "FORMAL_OBJECT_REFERENCE",
                        "inputPath": ["paintProcessTypeId"], "referenceModel": "pde.ManufacturingProcessType", "valueField": "code"},
                    {"name": "IndependentIdentity", "sourceType": "FORMAL_OBJECT_REFERENCE",
                        "inputPath": ["paintProcessTypeId"], "referenceModel": "pde.ManufacturingProcessType", "valueField": "id"},
                    {"name": "AreaClass", "sourceType": "CONFIGURATION_VALUE", "value": area_type}],
                "quantityTraceKey": "quantity_copy", "uomTraceKey": "unit_copy", "inputHashTraceKey": "digest_copy",
                "bindings": [{"inputName": "area_quantity", "sourceScope": "ORIGIN",
                    "sourceUomId": self.area.pk, "targetUomId": self.area.pk,
                    "selector": {"canonicalField": field or self.source_field,
                        "producerRuleId": producer.pk, "producerRuleVersion": producer.version,
                        "traceEquals": {"sourceKind": "SIMULATED_FOR_TEST"}}}]}}
        return {"contractVersion": FACT_CONTRACT, "companyId": self.company.pk,
            "rules": [{"ruleCode": code, "ruleName": "Abstract classified sum", "version": "V1",
                "specification": specification}],
            "consolidatedReadback": {"groupKeys": ["CoatingClass", "AreaClass"]}}

    def eor_package(self, *, partitions=None, candidate_policy=True):
        partitions = partitions or [(self.product_type, self.capacity)]
        rules = []
        for product_type, capacity in partitions:
            for process in (self.paint_a, self.paint_b):
                spec = deepcopy(self.mapping.specification)
                spec["expression"] = "declared_input"
                spec["inputs"] = [{"canonicalName": "declared_input", "sourceCanonicalField": "abstract_grouped_measure",
                    "valueType": "decimal", "unit": self.area.code, "unitDimension": "area",
                    "sourceType": "ENGINEERING_DERIVED", "required": True, "unitRequired": True}]
                spec["outputs"][0].update(canonicalName="abstract_required_work", productTypeId=product_type.pk,
                    quantityBasis="SOURCE_SCOPE_TOTAL", basisQuantitySource="SALES_ORDER_ITEM", basisUomSource="SALES_ORDER_ITEM")
                spec["outputs"][0].pop("basisQuantity", None)
                spec["outputs"][0].pop("basisUomId", None)
                spec["manufacturing"]["standardCapacityId"] = capacity.pk
                spec["manufacturing"].pop("modeId", None)
                spec["manufacturing"]["modeCode"] = self.mode.code
                spec["manufacturing"]["sourceSelector"] = {
                    "canonicalField": "abstract_grouped_measure", "producerRuleCode": "SIM-CLASSIFIED-SUM",
                    "producerRuleVersion": "V1", "traceEquals": {
                        "contractVersion": FACT_CONTRACT, "CoatingClass": process.code, "AreaClass": "VISIBLE_RECORD"}}
                if candidate_policy:
                    spec["manufacturing"]["sourceSelector"]["candidatePolicy"] = "MATCH_CONFIGURED_TRACE"
                rules.append({"ruleCode": f"SIM-CLASSIFIED-EOR-{product_type.pk}-{process.pk}",
                    "ruleName": "Abstract classified work mapping", "version": "V1", "specification": spec})
        return {"contractVersion": MANUFACTURING_CONTRACT, "companyId": self.company.pk, "modes": [], "rules": rules}

    def configure(self, package=None):
        return EngineeringFactExtensionService.configure(user=self.user,
            package=package or self.fact_package, reason="SIMULATED_FOR_TEST")["ruleIds"]

    def derive(self, *, rules=None, source=None, key="sim-classified"):
        return EngineeringFactExtensionService.derive(user=self.user,
            source_calculation_id=(source or self.source_calc).pk, rule_ids=rules or self.configure(),
            idempotency_key=key, reason="SIMULATED_FOR_TEST")

    def batch(self, *, sources=None, allow_partial=True, package=None, mapping=None, key="sim-classified-batch"):
        return ManufacturingFactBatchService.execute(user=self.user, fact_package=package or self.fact_package,
            manufacturing_package=mapping or self.manufacturing_package,
            source_calculation_ids=sources or [self.source_calc.pk], request_key=key,
            reason="SIMULATED_FOR_TEST", allow_partial=allow_partial)

    def full_database_snapshot(self):
        result = {}
        with connection.cursor() as cursor:
            for table in connection.introspection.table_names():
                cursor.execute("SELECT * FROM " + connection.ops.quote_name(table))
                rows = sorted(json.dumps(row, sort_keys=True, default=str) for row in cursor.fetchall())
                result[table] = operation._digest(rows)
        return result

    def source_snapshot(self):
        ids = [self.old_calculation_id, self.source_calc.pk]
        return {"calculations": list(EngineeringCalculationRecord.objects.filter(pk__in=ids).order_by("pk").values()),
            "facts": list(EngineeringDerivedFact.objects.filter(calculation_id__in=ids).order_by("pk").values()),
            "details": list(EngineeringCalculationDetail.objects.filter(calculation_id__in=ids).order_by("pk").values()),
            "oldEor": list(EngineeringOperationRequirement.objects.filter(pk=self.old_eor_id).values())}

    def assert_no_write_failure(self, action, code=None):
        before = self.full_database_snapshot()
        with self.assertRaises(operation.OperationRequirementError) as caught:
            action()
        if code:
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.full_database_snapshot(), before)
        return caught.exception.code

    def corrupt_json(self, obj, field, value):
        """Inject historical corruption through SQL only in the test database."""
        with connection.cursor() as cursor:
            cursor.execute("UPDATE " + connection.ops.quote_name(obj._meta.db_table)
                + " SET " + connection.ops.quote_name(field) + "=%s WHERE id=%s",
                (json.dumps(value, ensure_ascii=False), obj.pk))

    def test_same_code_sums_real_source_rows_without_count_multiplication(self):
        result = self.derive()
        facts = list(EngineeringDerivedFact.objects.filter(pk__in=result["factIds"]))
        quantities = {fact.trace["CoatingClass"]: fact.value["decimal"] for fact in facts}
        self.assertEqual(quantities, {self.paint_a.code: "3.750000", self.paint_b.code: "4.750000"})
        a = next(fact for fact in facts if fact.trace["CoatingClass"] == self.paint_a.code)
        self.assertEqual(set(a.inputs.values_list("source_fact_id", flat=True)),
            {self.raw_facts[0].pk, self.raw_facts[1].pk})
        self.assertEqual(self.source_snapshot(), self.preserved)
        self.assertEqual(self.item.quantity, Decimal("5"))
        for link in a.inputs.all():
            proof = link.input_snapshot["metadataProof"]
            self.assertEqual(proof["frozenObjectInput"]["physicalQuantity"], "37.000000")
            self.assertEqual(proof["sourceRecordVersion"], self.source.source_version)
            self.assertEqual(proof["bindings"][0]["referenceSnapshot"]["id"], self.paint_a.pk)

    def test_preview_preserves_missing_positive_and_zero_instead_of_falling_back(self):
        rules = self.configure()
        before = self.full_database_snapshot()
        preview = EngineeringFactExtensionService.preview(user=self.user,
            source_calculation_id=self.source_calc.pk, rule_ids=rules)
        self.assertEqual(preview["groupCount"], 2)
        missing = preview["retainedMissingMetadata"]
        self.assertEqual({row["sourceFactId"] for row in missing}, {fact.pk for fact in self.raw_facts[-2:]})
        self.assertEqual({row["value"]["decimal"] for row in missing}, {"3.00", "0.00"})
        self.assertTrue(self.instance.selected_process_type_id)
        self.assertTrue(all(row["metadataProof"]["frozenObjectInput"]["paintProcessTypeId"] is None for row in missing))
        self.assertEqual(self.full_database_snapshot(), before)

    def test_all_missing_derive_is_zero_write_and_keeps_zero_failure(self):
        origin, raw = self.build_sources([{"item": self.item, "instance": self.instance,
            "rows": [(None, "9.00"), (None, "0.00")]}])[0]
        rules = self.configure()
        before = self.full_database_snapshot()
        result = self.derive(source=origin, rules=rules, key="missing-only")
        self.assertIsNone(result["calculationId"])
        self.assertEqual(result["factIds"], [])
        self.assertEqual({row["sourceFactId"] for row in result["retainedMissingMetadata"]}, {fact.pk for fact in raw})
        self.assertEqual((result["businessWriteCount"], result["auditWriteCount"]), (0, 0))
        self.assertEqual(self.full_database_snapshot(), before)

    def test_aliases_metadata_and_input_links_are_saved_and_hash_verified(self):
        result = self.derive()
        calc = EngineeringCalculationRecord.objects.get(pk=result["calculationId"])
        for fact in EngineeringDerivedFact.objects.filter(pk__in=result["factIds"]):
            proof = validate_extension_fact(calc, fact)
            self.assertEqual(proof["baseEngineeringCalculationId"], self.source_calc.pk)
            self.assertEqual(fact.trace["quantity_copy"], fact.value["decimal"])
            self.assertEqual(fact.trace["unit_copy"], self.area.code)
            self.assertEqual(fact.trace["digest_copy"], fact.trace["inputHash"])
            self.assertEqual(fact.trace["inputHash"], operation._digest(fact.source_detail.input_snapshot))
            for link in fact.inputs.all():
                self.assertEqual(link.source_hash, operation._digest(link.input_snapshot))
                self.assertEqual(link.input_snapshot["metadata"]["CoatingClass"], fact.trace["CoatingClass"])

    def test_other_area_type_with_same_unit_remains_separate(self):
        producer = self.make_rule(self.op_area, self.area, "different_record", output_domain="DERIVED_FACT")
        origin, _ = self.build_sources([{"item": self.item, "instance": self.instance,
            "rows": [(self.paint_a, "2.50"), (self.paint_a, "1.25"), (self.paint_b, "4.75")],
            "extraMeasurements": [{"objectIndex": 0, "producer": producer,
                "field": "different_record", "quantity": "17.0"}]}])[0]
        package = deepcopy(self.fact_package)
        package["rules"].extend(self.classification_package(code="SIM-OTHER-AREA",
            field="different_record", producer=producer, area_type="OTHER_RECORD")["rules"])
        result = self.derive(source=origin, rules=self.configure(package))
        values = {(fact.trace["CoatingClass"], fact.trace["AreaClass"]): fact.value["decimal"]
            for fact in EngineeringDerivedFact.objects.filter(pk__in=result["factIds"])}
        self.assertEqual(values[(self.paint_a.code, "VISIBLE_RECORD")], "3.750000")
        self.assertEqual(values[(self.paint_a.code, "OTHER_RECORD")], "17.000000")
        self.assertEqual(len(values), 3)

    def test_configured_formal_reference_and_alias_names_are_generic(self):
        origin, _ = self.build_sources([{"item": self.item, "instance": self.instance,
            "rows": [(self.paint_b, "6.125")]}], reference_field="materialProcessTypeId")[0]
        package = self.classification_package(code="SIM-RENAMED-CLASSIFICATION", area_type="CUSTOM_AREA_TOKEN")
        config = package["rules"][0]["specification"]["factExtension"]
        config["groupKeys"] = ["formal_code_token", "different_area_label"]
        for binding in config["metadataBindings"]:
            binding["name"] = {"CoatingClass": "formal_code_token", "AreaClass": "different_area_label",
                "IndependentIdentity": "formal_fk_token"}[binding["name"]]
            if binding["sourceType"] == "FORMAL_OBJECT_REFERENCE":
                binding["inputPath"] = ["materialProcessTypeId"]
        result = self.derive(source=origin, rules=self.configure(package), key="renamed-contract")
        fact = EngineeringDerivedFact.objects.get(pk=result["factIds"][0])
        self.assertEqual(fact.trace["formal_code_token"], self.paint_b.code)
        self.assertEqual(fact.trace["different_area_label"], "CUSTOM_AREA_TOKEN")
        self.assertEqual(fact.value, {"decimal": "6.125000"})
        self.assertNotIn("PaintingProcessCode", fact.trace)

    def test_partial_default_rolls_back_rule_publication_and_all_data(self):
        self.assert_no_write_failure(lambda: self.batch(allow_partial=False), "CLASSIFIED_METADATA_REQUIRED")

    def test_partial_batch_generates_native_eor_and_keeps_original_results(self):
        result = self.batch()
        self.assertEqual(result["coverageStatus"], "PARTIAL")
        self.assertEqual(len(result["retainedMissingMetadata"]), 2)
        generated = result["runs"][0]["generation"]
        self.assertEqual(generated["blockers"], [])
        ids = [row["id"] for row in generated["requirements"]]
        requirements = EngineeringOperationRequirement.objects.filter(pk__in=ids)
        self.assertEqual(requirements.count(), 2)
        self.assertEqual(sorted(requirements.values_list("workload_quantity", flat=True)), [Decimal("3.75"), Decimal("4.75")])
        self.assertTrue(all(req.uom_id == self.area.pk and len(req.input_hash) == len(req.source_hash) == 64 for req in requirements))
        for requirement in requirements:
            operation._validate_requirement(requirement, self.company.pk)
            self.assertEqual(requirement.audit_record.actor_id, self.user.pk)
        self.assertEqual(self.source_snapshot(), self.preserved)
        self.assertEqual((result["productionPlanWriteCount"], result["apsWriteCount"]), (0, 0))

    def test_same_batch_key_replay_is_zero_write_across_every_test_table(self):
        first = self.batch()
        before = self.full_database_snapshot()
        again = self.batch()
        self.assertEqual(first["consolidatedFacts"], again["consolidatedFacts"])
        self.assertEqual(self.full_database_snapshot(), before)
        self.assertTrue(again["runs"][0]["derivation"]["idempotent"])
        self.assertEqual(again["runs"][0]["generation"]["businessWriteCount"], 0)
        self.assertEqual(again["runs"][0]["generation"]["auditWriteCount"], 0)

    def test_readback_sums_same_code_across_origins_but_keeps_resource_partitions(self):
        category = ProductCategory.objects.create(company=self.company, code="SIM-OTHER-CATEGORY", name="Unrelated category")
        kind = self.kind
        item = SalesOrderItem.objects.create(sales_order=self.order, line_no=2, material=self.material,
            quantity=9, uom=self.pcs, required_date=date.today(), engineering_mode="ORDER_ENGINEERED")
        instance = self.initial(OrderEngineeringInstance, "draft", company=self.company,
            instance_no="SIM-SECOND-PARTITION", sales_order_item=item, source_record=self.source,
            product_category=category, selected_process_type=kind)
        self.advance(instance, "source_confirmed")
        self.advance(instance, "calculated")
        product_type = CapacityProductType.objects.create(company=self.company, code="SIM-SECOND-PCT",
            name="Second partition", product_category=category, manufacturing_process_type=kind)
        capacity = self.make_capacity(self.op_area, self.area, "SIM-SECOND-CAPACITY", product_type=product_type)
        origins = self.build_sources([
            {"item": self.item, "instance": self.instance, "rows": [(self.paint_a, "0.75")]},
            {"item": item, "instance": instance, "rows": [(self.paint_a, "6.00")]},
        ])
        result = self.batch(sources=[calc.pk for calc, _ in origins], allow_partial=False,
            mapping=self.eor_package(partitions=[(self.product_type, self.capacity), (product_type, capacity)]))
        groups = result["consolidatedFacts"]["groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(Decimal(groups[0]["quantity"]), Decimal("6.75"))
        self.assertEqual(len(groups[0]["partitions"]), 2)
        requirements = EngineeringOperationRequirement.objects.exclude(pk=self.old_eor_id)
        self.assertEqual(set(requirements.values_list("standard_capacity_id", flat=True)), {self.capacity.pk, capacity.pk})
        self.assertEqual(set(requirements.values_list("source_calculation__sales_order_item_id", flat=True)), {self.item.pk, item.pk})

    def test_consolidated_readback_never_merges_distinct_source_versions_or_baselines(self):
        first = self.derive()
        source = self.initial(EngineeringSourceRecord, "draft", company=self.company,
            source_no="SIM-SECOND-SOURCE", source_name="New independent revision", source_type="manual_confirmed",
            source_version="V99", source_payload={"revision": 99}, content_hash=operation._digest({"revision": 99}))
        self.advance(source, "confirmed")
        item = SalesOrderItem.objects.create(sales_order=self.order, line_no=2, material=self.material,
            quantity=9, uom=self.pcs, required_date=date.today(), engineering_mode="ORDER_ENGINEERED")
        instance = self.initial(OrderEngineeringInstance, "draft", company=self.company,
            instance_no="SIM-NEW-VERSION", sales_order_item=item, source_record=source,
            product_category=self.category, selected_process_type=self.kind)
        self.advance(instance, "source_confirmed")
        self.advance(instance, "calculated")
        origin, _ = self.build_sources([{"item": item, "instance": instance,
            "rows": [(self.paint_a, "10")]}], source=source)[0]
        second = self.derive(source=origin, key="second-source-version")
        result = ManufacturingFactBatchService.consolidated_readback(user=self.user,
            calculation_ids=[first["calculationId"], second["calculationId"]], group_keys=["CoatingClass", "AreaClass"])
        a = [row for row in result["groups"] if row["group"]["CoatingClass"] == self.paint_a.code]
        self.assertEqual(len(a), 2)
        self.assertEqual({row["sourceRecordVersion"] for row in a}, {self.source.source_version, "V99"})
        self.assertEqual(len({row["baselineId"] for row in a}), 2)

    def test_duplicate_upstream_fact_in_readback_is_rejected(self):
        first = self.derive()
        rules = self.configure(self.classification_package(code="SIM-DUPLICATE-SUM"))
        second = self.derive(rules=rules, key="duplicate-source-contract")
        self.assert_no_write_failure(lambda: ManufacturingFactBatchService.consolidated_readback(user=self.user,
            calculation_ids=[first["calculationId"], second["calculationId"]],
            group_keys=["CoatingClass", "AreaClass"]), "CLASSIFIED_FACT_DUPLICATE_SOURCE")

    def test_readback_permission_and_duplicate_scope_are_checked(self):
        result = self.derive()
        user = User.objects.create_user(username="sim_classified_without_authority", company_id=self.company.pk)
        self.assert_no_write_failure(lambda: ManufacturingFactBatchService.consolidated_readback(user=user,
            calculation_ids=[result["calculationId"]], group_keys=["CoatingClass", "AreaClass"]), "PERMISSION_DENIED")
        self.assert_no_write_failure(lambda: ManufacturingFactBatchService.consolidated_readback(user=self.user,
            calculation_ids=[result["calculationId"], result["calculationId"]],
            group_keys=["CoatingClass", "AreaClass"]), "CLASSIFIED_READBACK_SCOPE_INVALID")

    def test_old_rule_outside_batch_whitelist_never_generates_or_blocks(self):
        result = self.derive()
        fact = EngineeringDerivedFact.objects.get(pk=result["factIds"][0])
        legacy = self.make_mapping(fact, self.op_area, self.area, mode=self.mode,
            capacity=self.capacity, dynamic_source_basis=True)
        batch = self.batch()
        self.assertEqual(len(batch["runs"][0]["generation"]["requirements"]), 2)
        self.assertFalse(EngineeringOperationRequirement.objects.filter(source_detail__rule=legacy).exists())

    def test_candidate_trace_mismatch_skips_opt_in_but_legacy_reports_blocker(self):
        result = self.derive()
        for policy in (True, False):
            package = self.eor_package(candidate_policy=policy)
            package["rules"] = package["rules"][:1]
            package["rules"][0]["ruleCode"] = f"SIM-CANDIDATE-{policy}"
            selector = package["rules"][0]["specification"]["manufacturing"]["sourceSelector"]
            selector.pop("producerRuleCode")
            selector["producerRuleId"] = EngineeringRuleDefinition.objects.get(rule_code="SIM-CLASSIFIED-SUM").pk
            selector["traceEquals"]["CoatingClass"] = "SIM-UNMATCHED-CODE"
            rules = ManufacturingConfigurationService.configure(user=self.user, package=package,
                reason="SIMULATED_FOR_TEST")["rules"]
            generated = ManufacturingConfigurationService.generate_for_calculation(user=self.user,
                source_calculation_id=result["calculationId"], request_key=f"candidate-{policy}",
                reason="SIMULATED_FOR_TEST", rule_ids=[row["id"] for row in rules])
            self.assertEqual(generated["requirements"], [])
            if policy:
                self.assertEqual([row["code"] for row in generated["blockers"]], ["MANUFACTURING_INPUT_MAPPING_MISSING"])
                self.assertTrue(all("sourceFactId" not in row for row in generated["blockers"]))
            else:
                self.assertTrue(generated["blockers"])
                self.assertTrue(all("sourceFactId" in row for row in generated["blockers"]))

    def test_unknown_candidate_policy_is_rejected_before_writes(self):
        package = deepcopy(self.manufacturing_package)
        package["rules"][0]["specification"]["manufacturing"]["sourceSelector"]["candidatePolicy"] = "IGNORE_PROOF"
        self.assert_no_write_failure(lambda: self.batch(mapping=package), "MANUFACTURING_CONFIG_INVALID")

    def test_cross_company_formal_reference_is_fail_closed(self):
        foreign = Company.objects.create(code="SIM-FOREIGN-CLASS", name="Another company")
        self.paint_a.company = foreign
        self.paint_a.save(update_fields=("company",))
        rules = self.configure()
        self.assert_no_write_failure(lambda: self.derive(rules=rules), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_inactive_formal_reference_is_retained_and_never_classified(self):
        self.paint_a.is_active = False
        self.paint_a.save(update_fields=("is_active",))
        preview = EngineeringFactExtensionService.preview(user=self.user,
            source_calculation_id=self.source_calc.pk, rule_ids=self.configure())
        self.assertEqual(preview["groupCount"], 1)
        reasons = [field["reasonCode"] for row in preview["retainedMissingMetadata"] for field in row["missingFields"]]
        self.assertIn("FORMAL_REFERENCE_INACTIVE", reasons)

    def test_selected_area_with_wrong_unit_is_rejected_without_omission(self):
        fact = self.raw_facts[0]
        with connection.cursor() as cursor:
            cursor.execute("UPDATE pde_engineering_derived_fact SET uom_id=%s WHERE id=%s", (self.pcs.pk, fact.pk))
            cursor.execute("UPDATE pde_engineering_calculation_detail SET uom_id=%s WHERE id=%s", (self.pcs.pk, fact.source_detail_id))
        rules = self.configure()
        self.assert_no_write_failure(lambda: self.derive(rules=rules), "FACT_UOM_MISMATCH")

    def test_original_hashes_and_frozen_snapshots_are_independently_verified(self):
        rules = self.configure()
        original_trace = deepcopy(self.source_calc.trace)
        cases = ("objectInputSnapshotHash", "resultHash", "ruleGraphSnapshot", "resultSnapshot")
        for key in cases:
            with self.subTest(key=key):
                trace = deepcopy(original_trace)
                trace[key] = "f" * 64 if key.endswith("Hash") else [{"tampered": True}]
                self.corrupt_json(self.source_calc, "trace", trace)
                self.assert_no_write_failure(lambda: self.derive(rules=rules), "FACT_METADATA_SOURCE_UNPROVEN")
                self.corrupt_json(self.source_calc, "trace", original_trace)

    def test_baseline_content_tamper_does_not_pass_even_with_fact_trace_unchanged(self):
        fact = self.raw_facts[0]
        item = OrderEngineeringBaselineItem.objects.get(pk=fact.trace["baselineItemId"])
        content = deepcopy(item.content_snapshot)
        content["revision"]["paintProcessTypeId"] = self.paint_b.pk
        self.corrupt_json(item, "content_snapshot", content)
        rules = self.configure()
        self.assert_no_write_failure(lambda: self.derive(rules=rules), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_original_detail_object_cannot_supply_a_different_formal_reference(self):
        detail = self.raw_facts[0].source_detail
        snapshot = deepcopy(detail.input_snapshot)
        snapshot["object"]["paintProcessTypeId"] = self.paint_b.pk
        self.corrupt_json(detail, "input_snapshot", snapshot)
        rules = self.configure()
        self.assert_no_write_failure(lambda: self.derive(rules=rules), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_derived_metadata_aliases_and_input_proofs_reject_corruption(self):
        result = self.derive()
        calc = EngineeringCalculationRecord.objects.get(pk=result["calculationId"])
        fact = EngineeringDerivedFact.objects.get(pk=result["factIds"][0])
        original = deepcopy(fact.trace)
        for field in ("CoatingClass", "AreaClass", "quantity_copy", "unit_copy", "digest_copy", "inputHash", "metadata"):
            with self.subTest(field=field):
                trace = deepcopy(original)
                trace[field] = {"changed": True} if field == "metadata" else "changed"
                self.corrupt_json(fact, "trace", trace)
                self.assert_no_write_failure(lambda: validate_extension_fact(calc, fact))
                self.corrupt_json(fact, "trace", original)
                fact.refresh_from_db()
        link = fact.inputs.first()
        snapshot = deepcopy(link.input_snapshot)
        old_id = snapshot["metadataProof"]["frozenObjectInput"]["paintProcessTypeId"]
        snapshot["metadataProof"]["frozenObjectInput"]["paintProcessTypeId"] = (
            self.paint_b.pk if old_id != self.paint_b.pk else self.paint_a.pk)
        self.corrupt_json(link, "input_snapshot", snapshot)
        self.assert_no_write_failure(lambda: validate_extension_fact(calc, fact))

    def test_metadata_config_cannot_overwrite_provenance_or_load_arbitrary_models(self):
        for field, value in (("name", "outputHash"), ("referenceModel", "system.User")):
            with self.subTest(field=field):
                package = deepcopy(self.fact_package)
                package["rules"][0]["specification"]["factExtension"]["metadataBindings"][0][field] = value
                self.assert_no_write_failure(lambda: self.configure(package), "FACT_METADATA_CONFIG_INVALID")

    def test_invalid_batch_scopes_and_readback_group_contracts_are_zero_write(self):
        self.assert_no_write_failure(lambda: self.batch(sources=[self.source_calc.pk, self.source_calc.pk]), "CLASSIFIED_BATCH_SCOPE_INVALID")
        result = self.derive()
        self.assert_no_write_failure(lambda: ManufacturingFactBatchService.consolidated_readback(user=self.user,
            calculation_ids=[result["calculationId"]], group_keys=["CoatingClass"]), "CLASSIFIED_READBACK_SCOPE_INVALID")

    def test_non_fk_integer_input_cannot_be_configured_as_a_formal_reference(self):
        for path in (["sourceRow"], ["sourceAttributeId"], ["designItemId"]):
            with self.subTest(path=path):
                package = deepcopy(self.fact_package)
                package["rules"][0]["specification"]["factExtension"]["metadataBindings"][0]["inputPath"] = path
                self.assert_no_write_failure(lambda: self.configure(package), "FACT_METADATA_CONFIG_INVALID")

    def test_boolean_identity_and_nonfinite_json_never_equal_formal_metadata(self):
        from .manufacturing_rule_configuration import _trace_matches
        self.assertFalse(_trace_matches({"identity": True}, {"identity": 1}))
        self.assertFalse(_trace_matches({"quantity": float("nan")}, {"quantity": float("nan")}))
        self.assertFalse(_trace_matches({"quantity": float("inf")}, {"quantity": float("inf")}))
        origin, _ = self.build_sources([{"item": self.item, "instance": self.instance,
            "rows": [(self.kind, "8.0")]}])[0]
        result = self.derive(source=origin, key="strict-scalar-identity")
        fact = EngineeringDerivedFact.objects.get(pk=result["factIds"][0])
        calc = fact.calculation
        trace = deepcopy(fact.trace)
        trace["IndependentIdentity"] = True
        trace["metadata"]["IndependentIdentity"] = True
        self.corrupt_json(fact, "trace", trace)
        self.assert_no_write_failure(lambda: validate_extension_fact(calc, fact))

    def test_later_design_revision_does_not_replace_frozen_classification(self):
        item = OrderEngineeringBaselineItem.objects.get(pk=self.raw_facts[0].trace["baselineItemId"])
        ProductDesignRevision.objects.create(design_item=item.design_item, revision=2,
            design_nature="FORMAL", paint_process_type=self.paint_b, design_data={}, created_by=self.user)
        result = self.derive()
        a = EngineeringDerivedFact.objects.get(pk__in=result["factIds"], trace__CoatingClass=self.paint_a.code)
        self.assertEqual(a.value, {"decimal": "3.750000"})
        self.assertIn(item.design_revision_id, [link.input_snapshot["metadataProof"]["designRevisionId"] for link in a.inputs.all()])

    def test_frozen_revision_identity_mismatch_is_rejected(self):
        item = OrderEngineeringBaselineItem.objects.get(pk=self.raw_facts[0].trace["baselineItemId"])
        content = deepcopy(item.content_snapshot)
        content["revision"]["id"] = item.design_revision_id + 1000
        self.corrupt_json(item, "content_snapshot", content)
        rules = self.configure()
        self.assert_no_write_failure(lambda: self.derive(rules=rules), "FACT_METADATA_SOURCE_UNPROVEN")

    def test_partial_mapping_keeps_unconsumed_classified_area_in_summary(self):
        origin, _ = self.build_sources([{"item": self.item, "instance": self.instance,
            "rows": [(self.paint_a, "2.50"), (self.paint_a, "1.25"), (self.paint_b, "4.75")]}])[0]
        mapping = deepcopy(self.manufacturing_package)
        mapping["rules"] = mapping["rules"][:1]
        result = self.batch(sources=[origin.pk], mapping=mapping)
        self.assertEqual(result["retainedMissingMetadata"], [])
        self.assertEqual(result["coverageStatus"], "PARTIAL")
        self.assertEqual(len(result["runs"][0]["generation"]["requirements"]), 1)
        self.assertEqual(len(result["retainedUnmappedFacts"]), 1)
        gap = result["retainedUnmappedFacts"][0]
        self.assertEqual(gap["group"]["CoatingClass"], self.paint_b.code)
        self.assertEqual(Decimal(gap["quantity"]), Decimal("4.75"))
        self.assertEqual(gap["reasonCode"], "MANUFACTURING_INPUT_MAPPING_MISSING")
        summary = {row["group"]["CoatingClass"]: Decimal(row["quantity"])
            for row in result["consolidatedFacts"]["groups"]}
        self.assertEqual(summary, {self.paint_a.code: Decimal("3.75"), self.paint_b.code: Decimal("4.75")})

    def test_missing_mapping_rolls_back_complete_mode_even_with_some_eor_results(self):
        origin, _ = self.build_sources([{"item": self.item, "instance": self.instance,
            "rows": [(self.paint_a, "3.75"), (self.paint_b, "4.75")]}])[0]
        mapping = deepcopy(self.manufacturing_package)
        mapping["rules"] = mapping["rules"][:1]
        self.assert_no_write_failure(lambda: self.batch(sources=[origin.pk],
            mapping=mapping, allow_partial=False), "CLASSIFIED_EOR_MAPPING_REQUIRED")

    def test_no_matching_mapping_keeps_typed_facts_without_claiming_complete(self):
        origin, raw = self.build_sources([{"item": self.item, "instance": self.instance,
            "rows": [(self.paint_a, "3.75"), (self.paint_b, "4.75")]}])[0]
        mapping = deepcopy(self.manufacturing_package)
        mapping["rules"] = mapping["rules"][:1]
        mapping["rules"][0]["specification"]["manufacturing"]["sourceSelector"]["traceEquals"]["CoatingClass"] = "UNMAPPED-TOKEN"
        result = self.batch(sources=[origin.pk], mapping=mapping)
        self.assertEqual(result["coverageStatus"], "PARTIAL")
        self.assertEqual(result["retainedMissingMetadata"], [])
        self.assertEqual(result["runs"][0]["generation"]["requirements"], [])
        self.assertEqual(len(result["retainedUnmappedFacts"]), 2)
        self.assertEqual(len(result["consolidatedFacts"]["groups"]), 2)
        self.assertEqual(EngineeringOperationRequirement.objects.count(), 1)
        self.assertEqual(set(result["consolidatedFacts"]["groups"][0]["sourceFactIds"]
            + result["consolidatedFacts"]["groups"][1]["sourceFactIds"]), {fact.pk for fact in raw})

    def test_allow_partial_does_not_tolerate_resource_unit_errors(self):
        self.capacity.uom = self.pcs
        self.capacity.save(update_fields=("uom",))
        self.assert_no_write_failure(lambda: self.batch(allow_partial=True), "MANUFACTURING_UOM_MISMATCH")
