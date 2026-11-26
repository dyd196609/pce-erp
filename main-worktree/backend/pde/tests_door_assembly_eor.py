"""SIMULATED_FOR_TEST: semantic quantity facts and real assembly EOR.

Only an isolated Django test DB is populated. Source, permission, state-machine,
hash and EOR services are real. Fixture helpers are borrowed, not test classes.
"""
from copy import deepcopy
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
import tempfile

from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from masterdata.models import UnitOfMeasure
from sales.models import SalesOrderItem
from system.models import Process, User
from . import operation_requirement_service as operation
from . import tests_operation_requirement as original
from . import tests_manufacturing_eor_configuration as manufacturing
from . import tests_classified_fact_eor as classified
from .engineering_fact_extension_service import (
    CONTRACT, EngineeringFactExtensionService, validate_extension_fact,
)
from .manufacturing_configuration_service import (
    CREATE, RELEASE, ManufacturingConfigurationService,
)
from .models import (
    EngineeringCalculationRecord, EngineeringCalculationDetail, EngineeringDerivedFact,
    EngineeringOperationRequirement, EngineeringRuleDefinition, OrderEngineeringInstance,
    WorkCenterOperationCapability,
)


class DoorAssemblyEorTests(TestCase):
    initial = original.OperationRequirementTests.initial
    advance = original.OperationRequirementTests.advance
    make_rule = original.OperationRequirementTests.make_rule
    make_source_fact = original.OperationRequirementTests.make_source_fact
    generate = original.OperationRequirementTests.generate
    make_mode = manufacturing.ManufacturingEorConfigurationTests.make_mode
    make_capacity = manufacturing.ManufacturingEorConfigurationTests.make_capacity
    make_mapping = manufacturing.ManufacturingEorConfigurationTests.make_mapping
    grant_configuration_permissions = manufacturing.ManufacturingEorConfigurationTests.grant_configuration_permissions
    build_sources = classified.ClassifiedFactEorTests.build_sources
    finish_source_hashes = classified.ClassifiedFactEorTests.finish_source_hashes
    full_database_snapshot = classified.ClassifiedFactEorTests.full_database_snapshot

    def setUp(self):
        manufacturing.ManufacturingEorConfigurationTests.setUp(self)
        self.item.quantity = Decimal("37")
        self.item.save(update_fields=("quantity",))
        self.old_eor_id = self.generate(rule=self.mapping)["operationRequirementId"]
        self.old_calculation_id = self.source_calc.pk
        self.leaves = UnitOfMeasure.objects.create(company_id=self.company.pk,
            code="SIM-RAW-COUNT", name="Abstract source counting unit", dimension="count")
        self.sets = UnitOfMeasure.objects.create(company_id=self.company.pk,
            code="SIM-SET-COUNT", name="Abstract assembly counting unit", dimension="count")
        self.assembly = Process.objects.create(company=self.company, code="SIM-ASSEMBLY-X17",
            name="Abstract configured operation", calculation_basis="count", calculation_uom=self.sets,
            standard_hours=Decimal("999"))
        WorkCenterOperationCapability.objects.create(work_center=self.center,
            operation=self.assembly, assignment_role="primary", is_active=True)
        self.set_mode = self.make_mode(self.sets, "SIM-COUNT-MODE")
        self.set_capacity = self.make_capacity(self.assembly, self.sets, "SIM-COUNT-CAP", quantity=12)
        self.source_field, self.serial = "opaque_quantity_X17", 0
        self.producer = self.make_rule(self.assembly, self.leaves, self.source_field,
            output_domain="DERIVED_FACT")
        casing_item = SalesOrderItem.objects.create(sales_order=self.order, line_no=2,
            material=self.material, quantity=3, uom=self.sets, required_date=self.item.required_date,
            engineering_mode="ORDER_ENGINEERED")
        casing_instance = self.initial(OrderEngineeringInstance, "draft", company=self.company,
            instance_no="SIM-CASING-INDEPENDENT", sales_order_item=casing_item,
            product_category=self.category, selected_process_type=self.kind, source_record=self.source)
        self.advance(casing_instance, "source_confirmed")
        self.advance(casing_instance, "calculated")
        actual_area = self.area
        self.area = self.leaves
        origins = self.build_sources([
            {"item": self.item, "instance": self.instance, "rows": [(None, "1")] * 5},
            {"item": casing_item, "instance": casing_instance, "rows": [(None, "1")] * 3},
        ])
        self.area = actual_area
        self.source_calc, self.raw_facts = origins[0]
        self.casing_calculation, self.casing_facts = origins[1]
        for fact in self.raw_facts + self.casing_facts:
            fact.trace["resultScope"] = "original"
            fact.save(update_fields=("trace",))
        for fact in self.casing_facts:
            fact.uom = self.sets
            fact.save(update_fields=("uom",))
            fact.source_detail.uom = self.sets
            fact.source_detail.save(update_fields=("uom",))
        self.grant_configuration_permissions(CREATE, RELEASE)
        self.fact_package = self.make_fact_package()
        self.rule_ids = self.configure()
        self.manufacturing_package = self.make_eor_package()
        self.mapping_id = self.configure_eor()[0]
        self.preserved = self.source_snapshot()

    def make_fact_package(self):
        rules = []
        for index, (code, input_name, output, unit, scope) in enumerate((
            ("SIM-SEMANTIC-SET", "declared_quantity", "DoorSetQuantity", self.leaves, "ORIGIN"),
            ("SIM-SEMANTIC-ASSEMBLY", "declared_sets", "DoorAssemblyQuantity", self.sets, "EXTENSION"),
        )):
            producer = ({"producerRuleId": self.producer.pk} if not index else
                {"producerRuleCode": "SIM-SEMANTIC-SET"})
            selector = {"canonicalField": self.source_field if not index else "DoorSetQuantity",
                "producerRuleVersion": "V1", **producer,
                "traceEquals": {"resultScope": "original"} if not index else {"contractVersion": CONTRACT}}
            spec = {"rulePackage": {"code": "SIM-SEMANTIC-QUANTITY", "version": "V1"},
                "expression": input_name, "inputs": [{"canonicalName": input_name,
                    "valueType": "decimal", "unit": unit.code, "unitDimension": "count",
                    "sourceType": "ENGINEERING_DERIVED", "required": True, "unitRequired": True}],
                "outputs": [{"canonicalName": output, "valueType": "decimal", "unit": self.sets.code,
                    "unitDimension": "count", "resultDomain": "DERIVED_FACT"}], "dependencies": [],
                "applicability": {"scope": "fact_extension"}, "decimalPrecision": 28,
                "outputScale": 6, "roundingMode": "ROUND_HALF_UP",
                "sourceEvidence": {"reference": "SIMULATED_FOR_TEST versioned complete-set semantic confirmation"},
                "factExtension": {"contractVersion": CONTRACT, "strategy": "OBJECT_FORMULA",
                    "inheritGroupIdentity": True, "productCategoryIds": [self.category.pk],
                    "outputUomId": self.sets.pk, "anchorInput": input_name,
                    "groupKeys": ["baselineItemId", "designItemId", "sourceAttributeId"],
                    "bindings": [{"inputName": input_name, "sourceScope": scope,
                        "sourceUomId": unit.pk, "targetUomId": unit.pk, "selectByUom": True,
                        "productCategoryIds": [self.category.pk], "selector": selector}]}}
            rules.append({"ruleCode": code, "ruleName": "Abstract declared count interpretation",
                "version": "V1", "specification": spec})
        return {"contractVersion": CONTRACT, "companyId": self.company.pk, "rules": rules}

    def make_eor_package(self):
        spec = deepcopy(self.mapping.specification)
        spec["expression"] = "declared_source_sets"
        spec["inputs"] = [{"canonicalName": "declared_source_sets", "sourceCanonicalField": "DoorAssemblyQuantity",
            "valueType": "decimal", "unit": self.sets.code, "unitDimension": "count",
            "sourceType": "ENGINEERING_DERIVED", "required": True, "unitRequired": True}]
        output = spec["outputs"][0]
        output.pop("basisQuantity", None); output.pop("basisUomId", None)
        output.update(canonicalName="abstract_assembly_demand", unit=self.sets.code, unitDimension="count",
            uomId=self.sets.pk, operationId=self.assembly.pk, quantityBasis="SOURCE_SCOPE_TOTAL",
            basisQuantitySource="SALES_ORDER_ITEM", basisUomSource="SALES_ORDER_ITEM")
        spec["manufacturing"].update(modeCode=self.set_mode.code, modeVersion="V1",
            standardCapacityId=self.set_capacity.pk)
        spec["manufacturing"].pop("modeId", None)
        spec["manufacturing"]["sourceSelector"] = {"canonicalField": "DoorAssemblyQuantity",
            "producerRuleId": self.rule_ids[1], "producerRuleVersion": "V1",
            "traceEquals": {"contractVersion": CONTRACT}, "candidatePolicy": "MATCH_CONFIGURED_TRACE",
            "objectTraceKeys": ["baseEngineeringCalculationId", "outputKey"]}
        return {"contractVersion": "PCE-MANUFACTURING-EOR-RULE-V1", "companyId": self.company.pk,
            "modes": [], "rules": [{"ruleCode": "SIM-DECLARED-ASSEMBLY-EOR", "ruleName": "Abstract quantity EOR",
                "version": "V1", "specification": spec}]}

    def configure(self, package=None, user=None):
        return EngineeringFactExtensionService.configure(user=user or self.user,
            package=package or self.fact_package, reason="SIMULATED_FOR_TEST")["ruleIds"]

    def configure_eor(self, package=None):
        result = ManufacturingConfigurationService.configure(user=self.user,
            package=package or self.manufacturing_package, reason="SIMULATED_FOR_TEST")
        return [row["id"] for row in result["rules"]]

    def derive(self, *, key="sim-door", source=None, rules=None, user=None):
        return EngineeringFactExtensionService.derive(user=user or self.user,
            source_calculation_id=(source or self.source_calc).pk, rule_ids=rules or self.rule_ids,
            idempotency_key=key, reason="SIMULATED_FOR_TEST")

    def run_pipeline(self, key="sim-door"):
        result = self.derive(key=key)
        generation = ManufacturingConfigurationService.generate_for_calculation(user=self.user,
            source_calculation_id=result["calculationId"], request_key=key,
            reason="SIMULATED_FOR_TEST", rule_ids=[self.mapping_id])
        self.assertEqual(generation["blockers"], [])
        return result, generation

    def source_snapshot(self):
        ids = [self.old_calculation_id, self.source_calc.pk, self.casing_calculation.pk]
        return {"calculations": list(EngineeringCalculationRecord.objects.filter(pk__in=ids).order_by("pk").values()),
            "facts": list(EngineeringDerivedFact.objects.filter(calculation_id__in=ids).order_by("pk").values()),
            "details": list(EngineeringCalculationDetail.objects.filter(calculation_id__in=ids).order_by("pk").values()),
            "oldEor": list(EngineeringOperationRequirement.objects.filter(pk=self.old_eor_id).values())}

    def no_write_failure(self, action, code=None):
        before = self.full_database_snapshot()
        with self.assertRaises(operation.OperationRequirementError) as caught:
            action()
        if code:
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.full_database_snapshot(), before)

    def rejected_package(self, edit):
        package = deepcopy(self.fact_package)
        edit(package["rules"][0]["specification"]["factExtension"])
        self.no_write_failure(lambda: self.configure(package))

    def command(self, *, key="sim-command", apply=True):
        paths = []
        try:
            for package in (self.fact_package, self.manufacturing_package):
                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as file:
                    json.dump(package, file); paths.append(file.name)
            output = StringIO()
            call_command("generate_incremental_fact_eor", fact_file=paths[0], manufacturing_file=paths[1],
                actor=self.user.pk, reason="SIMULATED_FOR_TEST", apply=apply,
                source_calculation=[self.source_calc.pk], request_key=key, stdout=output)
            return json.loads(output.getvalue())
        finally:
            for path in paths:
                Path(path).unlink(missing_ok=True)

    def test_pipeline_creates_ten_facts_and_five_real_set_eors(self):
        result, generated = self.run_pipeline()
        facts = list(EngineeringDerivedFact.objects.filter(pk__in=result["factIds"]))
        self.assertEqual(CounterFields(facts), {"DoorSetQuantity": 5, "DoorAssemblyQuantity": 5})
        self.assertEqual(len(generated["requirements"]), 5)
        self.assertEqual(sum(Decimal(row["workloadQuantity"]) for row in generated["requirements"]), Decimal("5"))
        self.assertTrue(all(row["uomId"] == self.sets.pk for row in generated["requirements"]))
        self.assertEqual(self.source_snapshot(), self.preserved)

    def test_each_output_keeps_one_source_object_and_two_stage_fact_links(self):
        result, generated = self.run_pipeline()
        calc = EngineeringCalculationRecord.objects.get(pk=result["calculationId"])
        facts = list(calc.derived_facts.order_by("sequence"))
        raw_ids = {fact.pk for fact in self.raw_facts}
        for fact in facts:
            validate_extension_fact(calc, fact)
            self.assertEqual(set(fact.trace["group"]), {"baselineItemId", "designItemId", "sourceAttributeId"})
            self.assertNotIn("baselineItemId", fact.trace)  # opt-in changes only the in-memory extension pool
            link = fact.inputs.get()
            self.assertEqual(link.source_hash, operation._digest(link.input_snapshot))
            if fact.canonical_field == "DoorSetQuantity":
                self.assertIn(link.source_fact_id, raw_ids)
            else:
                self.assertEqual(link.source_fact.canonical_field, "DoorSetQuantity")
                self.assertEqual(link.source_fact.trace["group"], fact.trace["group"])
                self.assertIn(link.source_fact.inputs.get().source_fact_id, raw_ids)
        for row in generated["requirements"]:
            requirement = EngineeringOperationRequirement.objects.get(pk=row["id"])
            self.assertEqual(requirement.source_fact.canonical_field, "DoorAssemblyQuantity")
            operation._validate_requirement(requirement, self.company.pk)

    def test_independent_casing_set_unit_is_excluded_without_business_writes(self):
        self.no_write_failure(lambda: self.derive(source=self.casing_calculation), "FACT_INPUT_MISSING")
        self.assertEqual(self.source_snapshot(), self.preserved)

    def test_quantity_is_dynamic_and_never_a_fixed_five(self):
        actual_area = self.area
        self.area = self.leaves
        origin, facts = self.build_sources([{"item": self.item, "instance": self.instance,
            "rows": [(None, quantity) for quantity in ("2", "3", "1", "7", "4")]}])[0]
        self.area = actual_area
        for fact in facts:
            fact.trace["resultScope"] = "original"
            fact.save(update_fields=("trace",))
        result = self.derive(source=origin, key="sim-dynamic-revision")
        generated = ManufacturingConfigurationService.generate_for_calculation(user=self.user,
            source_calculation_id=result["calculationId"], request_key="sim-dynamic-revision",
            reason="SIMULATED_FOR_TEST", rule_ids=[self.mapping_id])
        self.assertEqual(generated["blockers"], [])
        self.assertEqual(sum(Decimal(row["workloadQuantity"]) for row in generated["requirements"]), Decimal("17"))
        self.assertEqual(self.source_snapshot(), self.preserved)

    def test_sales_basis_thirty_seven_does_not_multiply_source_demand(self):
        _, generated = self.run_pipeline()
        self.assertEqual(self.item.quantity, Decimal("37"))
        for row in generated["requirements"]:
            self.assertEqual(Decimal(row["workloadQuantity"]), 1)
            self.assertEqual(Decimal(row["basisQuantity"]), 37)
            self.assertEqual(row["quantityBasis"], "SOURCE_SCOPE_TOTAL")

    def test_semantic_output_does_not_create_a_leaf_to_set_unit_conversion(self):
        result = self.derive()
        for fact in EngineeringDerivedFact.objects.filter(pk__in=result["factIds"], canonical_field="DoorSetQuantity"):
            normalization = fact.inputs.get().input_snapshot["normalization"]
            self.assertEqual(normalization["sourceUomId"], self.leaves.pk)
            self.assertEqual(normalization["targetUomId"], self.leaves.pk)
            self.assertEqual(Decimal(normalization["appliedFactor"]), 1)
            self.assertEqual(fact.uom_id, self.sets.pk)
        self.leaves.refresh_from_db()
        self.assertIsNone(self.leaves.conversion_base_id)

    def test_preview_and_replay_are_zero_writes_across_all_tables(self):
        before = self.full_database_snapshot()
        preview = EngineeringFactExtensionService.preview(user=self.user,
            source_calculation_id=self.source_calc.pk, rule_ids=self.rule_ids)
        self.assertEqual(preview["groupCount"], 10)
        self.assertEqual(self.full_database_snapshot(), before)
        first, generated = self.run_pipeline()
        before = self.full_database_snapshot()
        repeated, replay = self.run_pipeline()
        self.assertEqual(first["factIds"], repeated["factIds"])
        self.assertEqual((repeated["businessWriteCount"], repeated["auditWriteCount"]), (0, 0))
        self.assertEqual((replay["businessWriteCount"], replay["auditWriteCount"]), (0, 0))
        self.assertEqual([row["id"] for row in replay["requirements"]], [row["id"] for row in generated["requirements"]])
        self.assertEqual(self.full_database_snapshot(), before)

    def test_configuration_replay_does_not_republish_or_overwrite(self):
        before = self.full_database_snapshot()
        self.assertEqual(self.configure(), self.rule_ids)
        self.assertEqual(self.configure_eor(), [self.mapping_id])
        self.assertEqual(self.full_database_snapshot(), before)
        package = deepcopy(self.fact_package)
        package["rules"][0]["specification"]["expression"] = "declared_quantity * 2"
        self.no_write_failure(lambda: self.configure(package), "FACT_RULE_VERSION_CONFLICT")

    def test_missing_inheritance_cannot_mix_or_flatten_objects_implicitly(self):
        package = deepcopy(self.fact_package)
        package["rules"][0]["ruleCode"] = "SIM-NO-INHERIT"
        package["rules"][1]["ruleCode"] = "SIM-NO-INHERIT-SECOND"
        package["rules"][0]["specification"]["factExtension"].pop("inheritGroupIdentity")
        package["rules"][1]["specification"]["factExtension"]["bindings"][0]["selector"]["producerRuleCode"] = "SIM-NO-INHERIT"
        ids = self.configure(package)
        self.no_write_failure(lambda: self.derive(rules=ids), "FACT_SOURCE_GROUP_MISSING")

    def test_legacy_absent_flag_preserves_plan_shape_and_hash_serialization(self):
        package = deepcopy(self.fact_package)
        package["rules"] = package["rules"][:1]
        package["rules"][0]["ruleCode"] = "SIM-LEGACY-OBJECT"
        package["rules"][0]["specification"]["factExtension"].pop("inheritGroupIdentity")
        ids = self.configure(package)
        plan = EngineeringFactExtensionService.preview(user=self.user,
            source_calculation_id=self.source_calc.pk, rule_ids=ids)["plan"]
        self.assertEqual(plan["inputHash"], operation._digest({"source": plan["source"], "graph": plan["graph"],
            "inputs": [context["sources"] for context in plan["contexts"]]}))
        self.assertEqual(plan["ruleGraphHash"], operation._digest(plan["graph"]))
        self.assertEqual(plan["resultHash"], operation._digest(plan["contexts"]))
        self.assertTrue(all(set(context) == {"outputKey", "ruleId", "ruleVersion", "specificationHash",
            "group", "inputs", "sources", "result", "uomId"} for context in plan["contexts"]))

    def test_flag_requires_exact_boolean_configuration(self):
        for invalid in (1, 0, "true", None):
            with self.subTest(invalid=invalid):
                self.rejected_package(lambda config: config.update(inheritGroupIdentity=invalid))

    def test_inheritance_cannot_be_enabled_for_scope_sum(self):
        self.rejected_package(lambda config: config.update(strategy="SCOPE_SUM"))

    def test_inheritance_group_keys_reject_duplicates_and_empty_tokens(self):
        for keys in (["designItemId", "designItemId"], [""], [" designItemId"], [True], []):
            with self.subTest(keys=keys):
                self.rejected_package(lambda config: config.update(groupKeys=keys))

    def test_inheritance_rejects_reserved_source_and_trace_key_collisions(self):
        for key in ("contractVersion", "sourceFactId", "outputKey", "inputHash", "sourcePath", "normalization"):
            with self.subTest(key=key):
                self.rejected_package(lambda config: config.update(groupKeys=[key]))

    def test_inheritance_rejects_metadata_alias_key_collisions(self):
        self.rejected_package(lambda config: config.update(quantityTraceKey="designItemId"))
        self.rejected_package(lambda config: config.update(metadataBindings=[{"name": "baselineItemId"}]))

    def test_group_identity_rejects_non_scalar_boolean_or_empty_values_before_writes(self):
        fact = self.raw_facts[0]
        original_trace = deepcopy(fact.trace)
        for invalid in (True, False, {}, [], 1.0, "", " padded ", 0):
            with self.subTest(invalid=invalid):
                fact.trace = {**original_trace, "baselineItemId": invalid}
                fact.save(update_fields=("trace",))
                self.no_write_failure(self.derive, "FACT_SOURCE_GROUP_MISSING")

    def test_missing_object_identity_and_duplicate_anchor_are_blocked(self):
        fact = self.raw_facts[0]
        original_trace = deepcopy(fact.trace)
        fact.trace.pop("sourceAttributeId"); fact.save(update_fields=("trace",))
        self.no_write_failure(self.derive, "FACT_SOURCE_GROUP_MISSING")
        fact.trace = original_trace; fact.save(update_fields=("trace",))
        second = self.raw_facts[1]
        second.trace.update({key: original_trace[key] for key in ("baselineItemId", "designItemId", "sourceAttributeId")})
        second.save(update_fields=("trace",))
        self.no_write_failure(self.derive, "FACT_INPUT_AMBIGUOUS")

    def test_wrong_producer_version_and_unpublished_producer_are_blocked(self):
        package = deepcopy(self.fact_package)
        package["rules"][0]["specification"]["factExtension"]["bindings"][0]["selector"]["producerRuleVersion"] = "V99"
        self.no_write_failure(lambda: self.configure(package), "FACT_RULE_NOT_RELEASED")
        self.advance(self.producer, "draft")
        self.no_write_failure(self.derive, "FACT_RULE_NOT_RELEASED")

    def test_unpublished_fact_rule_and_unauthorized_executor_are_blocked(self):
        rule = EngineeringRuleDefinition.objects.get(pk=self.rule_ids[0])
        self.advance(rule, "draft")
        self.no_write_failure(self.derive, "FACT_RULE_NOT_RELEASED")
        unauthorized = User.objects.create_user(username="sim_no_door_rights", company_id=self.company.pk)
        self.no_write_failure(lambda: self.derive(user=unauthorized))

    def test_unauthorized_rule_publication_has_no_side_effects(self):
        unauthorized = User.objects.create_user(username="sim_no_publish_rights", company_id=self.company.pk)
        self.no_write_failure(lambda: self.configure(user=unauthorized))

    def test_area_input_or_output_contract_cannot_replace_set_quantity(self):
        self.rejected_package(lambda config: config.update(outputUomId=self.area.pk))
        self.rejected_package(lambda config: config["bindings"][0].update(sourceUomId=self.area.pk))

    def test_count_units_are_checked_when_unit_selection_is_not_declared(self):
        package = deepcopy(self.fact_package)
        package["rules"][0]["ruleCode"] = "SIM-STRICT-SOURCE-UNIT"
        package["rules"][1]["ruleCode"] = "SIM-STRICT-SOURCE-UNIT-SECOND"
        package["rules"][0]["specification"]["factExtension"]["bindings"][0]["selectByUom"] = False
        package["rules"][1]["specification"]["factExtension"]["bindings"][0]["selector"]["producerRuleCode"] = "SIM-STRICT-SOURCE-UNIT"
        ids = self.configure(package)
        self.no_write_failure(lambda: self.derive(rules=ids, source=self.casing_calculation), "FACT_UOM_MISMATCH")

    def test_real_eor_has_published_version_resources_hashes_and_actual_audit_actor(self):
        _, generated = self.run_pipeline()
        for row in generated["requirements"]:
            requirement = EngineeringOperationRequirement.objects.get(pk=row["id"])
            self.assertEqual((requirement.manufacturing_mode_id, requirement.work_center_id, requirement.standard_capacity_id),
                (self.set_mode.pk, self.center.pk, self.set_capacity.pk))
            self.assertEqual(requirement.source_detail.rule_version, "V1")
            self.assertEqual(requirement.audit_record.actor_id, self.user.pk)
            self.assertEqual((len(requirement.source_hash), len(requirement.input_hash)), (64, 64))
            operation._validate_requirement(requirement, self.company.pk)
        self.assertEqual((self.set_capacity.uom_id, self.set_capacity.time_basis, self.set_capacity.time_basis_quantity),
            (self.sets.pk, "day", 1))

    def test_standard_capacity_area_unit_or_unknown_capacity_blocks_new_eor(self):
        result = self.derive()
        fact = EngineeringDerivedFact.objects.get(pk=result["factIds"][-1])
        for overrides in ({"uom": self.area}, {"quantity": None, "measurement_status": "not_determinable"}):
            for key, value in overrides.items():
                setattr(self.set_capacity, key, value)
            self.set_capacity.save(update_fields=tuple(overrides))
            self.no_write_failure(lambda: operation.OperationRequirementService.generate(user=self.user,
                source_calculation_id=result["calculationId"], source_fact_id=fact.pk, rule_id=self.mapping_id,
                idempotency_key="invalid-set-capacity", reason="SIMULATED_FOR_TEST"))
            self.set_capacity.uom, self.set_capacity.quantity = self.sets, Decimal("12")
            self.set_capacity.measurement_status = "measured"
            self.set_capacity.save(update_fields=("uom", "quantity", "measurement_status"))

    def test_command_whitelist_generates_only_newly_selected_mapping_and_replays_zero(self):
        unrelated = deepcopy(self.manufacturing_package)
        unrelated["rules"][0]["ruleCode"] = "SIM-UNSELECTED-BUT-VALID-EOR"
        extra_id = self.configure_eor(unrelated)[0]
        before_count = EngineeringOperationRequirement.objects.count()
        first = self.command()
        self.assertEqual(len(first["runs"][0]["generation"]["requirements"]), 5)
        self.assertEqual(EngineeringOperationRequirement.objects.count(), before_count + 5)
        self.assertEqual(EngineeringOperationRequirement.objects.filter(source_detail__rule_id=extra_id).count(), 0)
        before = self.full_database_snapshot()
        second = self.command()
        self.assertEqual(second["runs"][0]["generation"]["businessWriteCount"], 0)
        self.assertEqual(second["runs"][0]["derivation"]["auditWriteCount"], 0)
        self.assertEqual(self.full_database_snapshot(), before)
        self.assertEqual(self.source_snapshot(), self.preserved)

    def test_command_inspection_is_zero_write(self):
        before = self.full_database_snapshot()
        result = self.command(apply=False)
        self.assertEqual((result["factRuleCount"], result["manufacturingRuleCount"]), (2, 1))
        self.assertEqual(self.full_database_snapshot(), before)

    def test_persisted_group_corruption_fails_provenance_revalidation(self):
        result = self.derive()
        fact = EngineeringDerivedFact.objects.get(pk=result["factIds"][-1])
        trace = deepcopy(fact.trace); trace["group"]["designItemId"] += 1000
        with connection.cursor() as cursor:
            cursor.execute("UPDATE " + connection.ops.quote_name(fact._meta.db_table) + " SET trace=%s WHERE id=%s",
                (json.dumps(trace), fact.pk))
        self.no_write_failure(lambda: operation.OperationRequirementService.generate(user=self.user,
            source_calculation_id=result["calculationId"], source_fact_id=fact.pk, rule_id=self.mapping_id,
            idempotency_key="corrupt-identity", reason="SIMULATED_FOR_TEST"))


def CounterFields(facts):
    from collections import Counter
    return dict(Counter(fact.canonical_field for fact in facts))
