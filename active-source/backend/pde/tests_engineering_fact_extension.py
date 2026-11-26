"""SIMULATED_FOR_TEST: incremental facts and Cutting EOR use formal authorities.

Only an isolated Django test database is populated. Abstract selectors and
nonstandard conversion data prove that no field, product or order name drives
the runtime. Original calculation rows and previously generated EOR are retained.
"""

from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from masterdata.models import UnitOfMeasure
from system.models import Company, OrganizationOperatingAuditRecord, User
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import record_projected_business_transition
from . import operation_requirement_service as operation
from . import tests_operation_requirement as fixtures
from . import tests_manufacturing_eor_configuration as manufacturing_fixtures
from .engineering_fact_extension_service import (
    CONTRACT, EngineeringFactExtensionService, validate_extension_fact,
)
from .manufacturing_configuration_service import CREATE, RELEASE
from .production_foundation_service import _snapshot
from .models import (
    EngineeringCalculationRecord, EngineeringCalculationDetail, EngineeringDerivedFact,
    EngineeringFactInput, EngineeringOperationRequirement, EngineeringRuleDefinition,
)


class EngineeringFactExtensionTests(TestCase):
    initial = fixtures.OperationRequirementTests.initial
    advance = fixtures.OperationRequirementTests.advance
    make_rule = fixtures.OperationRequirementTests.make_rule
    make_source_fact = fixtures.OperationRequirementTests.make_source_fact
    generate = fixtures.OperationRequirementTests.generate
    make_mode = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_mode
    make_capacity = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_capacity
    make_mapping = manufacturing_fixtures.ManufacturingEorConfigurationTests.make_mapping
    grant_configuration_permissions = manufacturing_fixtures.ManufacturingEorConfigurationTests.grant_configuration_permissions

    def setUp(self):
        manufacturing_fixtures.ManufacturingEorConfigurationTests.setUp(self)
        self.old_eor = self.generate(rule=self.mapping)["operationRequirementId"]
        self.old_calculation = self.source_calc
        self.metres = UnitOfMeasure.objects.create(company_id=self.company.pk,
            code="SIM-LENGTH", name="Abstract base length", dimension="length")
        self.millimetres = UnitOfMeasure.objects.create(company_id=self.company.pk,
            code="SIM-SMALL-LENGTH", name="Abstract source length", dimension="length",
            conversion_base=self.metres, conversion_factor=Decimal("0.001"))
        self.source_calc = self.initial(EngineeringCalculationRecord, "running",
            company=self.company, scope="order_engineering", source_record=self.source,
            sales_order_item=self.item, engineering_instance=self.instance,
            calculation_no="SIM-INCREMENTAL-ORIGIN", rule_set_version="SIM-V1", revision=2,
            input_hash=fixtures.digest("input"), rule_graph_hash=fixtures.digest("graph"),
            result_hash=fixtures.digest("result"), trace={"sourceKind": "SIMULATED_FOR_TEST"})
        producers = {}
        for name, unit in (("abstract_height", self.millimetres),
                           ("abstract_width", self.millimetres), ("abstract_quantity", self.pcs)):
            producers[name] = self.make_rule(self.op_area, unit, name, output_domain="DERIVED_FACT")
        self.input_facts = []
        for group, values in enumerate((("2000", "800", "2"), ("1000", "500", "1")), 1):
            for name, value in zip(producers, values):
                unit = self.pcs if name == "abstract_quantity" else self.millimetres
                fact = self.make_source_fact(producers[name], unit, name, value, len(self.input_facts) + 1)
                fact.trace.update(baselineItemId=group, designItemId=group, sourceAttributeId=group)
                fact.save(update_fields=("trace",))
                self.input_facts.append(fact)
        self.existing_area = self.make_source_fact(self.fact_area.rule, self.area, "source_area", "20", 7)
        self.source_calc.started_at = self.source_calc.finished_at = timezone.now()
        self.source_calc.save(update_fields=("started_at", "finished_at"))
        self.advance(self.source_calc, "completed")
        self.producers = producers
        self.grant_configuration_permissions(CREATE, RELEASE)
        self.package = self.make_package()
        self.rule_ids = EngineeringFactExtensionService.configure(user=self.user,
            package=self.package, reason="SIMULATED_FOR_TEST")['ruleIds']
        self.preserved = self.preservation_snapshot()

    def binding(self, input_name, field, producer, source_unit, target_unit, *, scope="ORIGIN"):
        return {"inputName": input_name, "sourceScope": scope,
            "sourceUomId": source_unit.pk, "targetUomId": target_unit.pk,
            "productCategoryIds": [self.category.pk],
            "selector": {"canonicalField": field, "producerRuleId": producer.pk,
                "producerRuleVersion": producer.version,
                "traceEquals": {"sourceKind": "SIMULATED_FOR_TEST"}}}

    def spec(self, inputs, output, expression, config):
        return {"description": "SIMULATED_FOR_TEST generic fact definition",
            "rulePackage": {"code": "SIM.FACT", "version": "V1"}, "expression": expression,
            "inputs": inputs, "outputs": [{"canonicalName": output, "valueType": "decimal",
                "unit": self.area.code, "unitDimension": "area", "resultDomain": "DERIVED_FACT"}],
            "dependencies": [], "applicability": {"scope": "fact_extension"},
            "decimalPrecision": 28, "outputScale": 6, "roundingMode": "ROUND_HALF_UP",
            "priority": 1, "sourceEvidence": {"reference": "SIMULATED_FOR_TEST"},
            "factExtension": {"contractVersion": CONTRACT,
                "productCategoryIds": [self.category.pk], "outputUomId": self.area.pk, **config}}

    def make_package(self):
        inputs = [{"canonicalName": name, "valueType": "decimal", "unit": unit.code,
            "unitDimension": dimension, "sourceType": "ENGINEERING_DERIVED",
            "required": True, "unitRequired": True}
            for name, unit, dimension in (("height", self.metres, "length"),
                ("width", self.metres, "length"), ("quantity", self.pcs, "dimensionless"))]
        bindings = [self.binding(name, field, self.producers[field], source, target)
            for name, field, source, target in (("height", "abstract_height", self.millimetres, self.metres),
                ("width", "abstract_width", self.millimetres, self.metres),
                ("quantity", "abstract_quantity", self.pcs, self.pcs))]
        object_spec = self.spec(inputs, "abstract_panel_area", "height * width * quantity",
            {"strategy": "OBJECT_FORMULA", "groupKeys": ["baselineItemId", "designItemId", "sourceAttributeId"],
             "anchorInput": "quantity", "requirePositiveInputGroups": True, "bindings": bindings})
        sum_binding = {"inputName": "area_quantity", "sourceScope": "EXTENSION",
            "sourceUomId": self.area.pk, "targetUomId": self.area.pk,
            "selector": {"canonicalField": "abstract_panel_area",
                "producerRuleCode": "SIM-FACT-OBJECT", "producerRuleVersion": "V1",
                "traceEquals": {"contractVersion": CONTRACT}}}
        sum_spec = self.spec([{"canonicalName": "area_quantity", "valueType": "decimal",
            "unit": self.area.code, "unitDimension": "area", "sourceType": "AGGREGATED",
            "required": True, "unitRequired": True}], "abstract_board_summary", "area_quantity",
            {"strategy": "SCOPE_SUM", "bindings": [
                self.binding("area_quantity", "source_area", self.existing_area.rule, self.area, self.area),
                sum_binding]})
        return {"contractVersion": CONTRACT, "companyId": self.company.pk, "rules": [
            {"ruleCode": "SIM-FACT-OBJECT", "ruleName": "Abstract object formula", "version": "V1", "specification": object_spec},
            {"ruleCode": "SIM-FACT-SUM", "ruleName": "Abstract scope sum", "version": "V1", "specification": sum_spec}]}

    def derive(self, *, key="sim-fact-request", rules=None, user=None, source=None, **extra):
        return EngineeringFactExtensionService.derive(user=user or self.user,
            source_calculation_id=(source or self.source_calc).pk,
            rule_ids=self.rule_ids if rules is None else rules, idempotency_key=key,
            reason="SIMULATED_FOR_TEST", **extra)

    def snapshot(self):
        return {model._meta.label: list(model.objects.order_by("pk").values()) for model in (
            EngineeringCalculationRecord, EngineeringCalculationDetail, EngineeringDerivedFact,
            EngineeringFactInput, EngineeringOperationRequirement, EngineeringRuleDefinition,
            OrganizationOperatingAuditRecord, BusinessStateTransition)}

    def preservation_snapshot(self):
        return {"eor": list(EngineeringOperationRequirement.objects.filter(pk=self.old_eor).values()),
            "source": list(EngineeringCalculationRecord.objects.filter(pk__in=[self.old_calculation.pk, self.source_calc.pk]).values()),
            "facts": list(EngineeringDerivedFact.objects.filter(calculation_id__in=[self.old_calculation.pk, self.source_calc.pk]).order_by("pk").values()),
            "details": list(EngineeringCalculationDetail.objects.filter(calculation_id__in=[self.old_calculation.pk, self.source_calc.pk]).order_by("pk").values())}

    def result(self, **kwargs):
        result = self.derive(**kwargs)
        calculation = EngineeringCalculationRecord.objects.get(pk=result["calculationId"])
        facts = list(calculation.derived_facts.order_by("sequence"))
        return result, calculation, facts

    def assert_blocked(self, action=None, code=None):
        before = self.snapshot()
        with self.assertRaises(operation.OperationRequirementError) as caught:
            (action or self.derive)()
        if code:
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.snapshot(), before)
        return caught.exception.code

    def test_server_formula_and_summary_preserve_original_rows_and_latest_scope(self):
        with patch("pde.engineering_calculation_service.EngineeringCalculationService.execute",
                   side_effect=AssertionError("Original calculation must not be executed")):
            result, calc, facts = self.result()
        self.assertEqual((calc.scope, calc.origin_calculation_id, calc.supersedes_id),
            ("fact_extension", self.source_calc.pk, None))
        self.assertEqual([Decimal(f.value['decimal']) for f in facts],
            [Decimal("3.2"), Decimal("0.5"), Decimal("23.7")])
        self.assertEqual([f.uom_id for f in facts], [self.area.pk] * 3)
        self.assertEqual([f.inputs.count() for f in facts], [3, 3, 3])
        self.assertEqual(set(facts[-1].inputs.values_list("source_fact_id", flat=True)),
            {self.existing_area.pk, facts[0].pk, facts[1].pk})
        for fact in facts:
            self.assertEqual(len(fact.trace['outputHash']), 64)
            self.assertTrue(fact.trace['calculatedAt'])
            self.assertEqual(fact.source_detail.rule_version, "V1")
            for link in fact.inputs.all():
                self.assertEqual(link.source_hash, operation._digest(link.input_snapshot))
        proof = validate_extension_fact(calc, facts[-1])
        self.assertEqual(proof['baseEngineeringCalculationId'], self.source_calc.pk)
        latest = EngineeringCalculationRecord.objects.filter(sales_order_item=self.item,
            scope="order_engineering").order_by("-revision", "-pk").first()
        self.assertEqual(latest.pk, self.source_calc.pk)
        self.assertEqual(self.preservation_snapshot(), self.preserved)
        self.assertGreater(result['businessWriteCount'], 0)
        operation._validate_requirement(EngineeringOperationRequirement.objects.get(pk=self.old_eor), self.company.pk)

    def test_conversion_uses_formal_uom_data_and_keeps_basis_total_once(self):
        self.millimetres.conversion_factor = Decimal("0.002")
        self.millimetres.save(update_fields=("conversion_factor",))
        _, _, facts = self.result()
        self.assertEqual([Decimal(f.value['decimal']) for f in facts],
            [Decimal("12.8"), Decimal("2"), Decimal("34.8")])
        normalized = facts[0].inputs.get(input_name="height").input_snapshot['normalization']
        self.assertEqual(Decimal(normalized['appliedFactor']), Decimal("0.002"))
        self.assertEqual(normalized['conversionBaseId'], self.metres.pk)
        self.assertEqual(self.preservation_snapshot(), self.preserved)

    def test_summary_produces_real_eor_with_manufacturing_mode_and_lineage(self):
        _, calc, facts = self.result()
        summary = facts[-1]
        mapping = self.make_mapping(summary, self.op_area, self.area,
            mode=self.mode, capacity=self.capacity, dynamic_source_basis=True,
            manufacturing_overrides={"sourceSelector": {"canonicalField": summary.canonical_field,
                "producerRuleId": summary.rule_id, "producerRuleVersion": "V1",
                "traceEquals": {"contractVersion": CONTRACT}}})
        result = operation.OperationRequirementService.generate(user=self.user,
            source_calculation_id=calc.pk, source_fact_id=summary.pk, rule_id=mapping.pk,
            idempotency_key="sim-summary-eor", reason="SIMULATED_FOR_TEST")
        req = EngineeringOperationRequirement.objects.get(pk=result['operationRequirementId'])
        self.assertEqual((req.workload_quantity, req.uom_id), (Decimal("23.7"), self.area.pk))
        self.assertEqual((req.manufacturing_mode_id, req.work_center_id, req.standard_capacity_id),
            (self.mode.pk, self.center.pk, self.capacity.pk))
        self.assertEqual((req.source_calculation_id, req.source_fact_id), (calc.pk, summary.pk))
        self.assertEqual(req.source_detail.rule_version, "V1")
        operation._validate_requirement(req, self.company.pk)
        before = self.snapshot()
        repeated = operation.OperationRequirementService.generate(user=self.user,
            source_calculation_id=calc.pk, source_fact_id=summary.pk, rule_id=mapping.pk,
            idempotency_key="sim-summary-eor", reason="SIMULATED_FOR_TEST")
        self.assertEqual(repeated['operationRequirementId'], req.pk)
        self.assertEqual(repeated['businessWriteCount'], 0)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.preservation_snapshot(), self.preserved)

    def test_request_replay_is_zero_write_and_new_alias_is_bound_once(self):
        first = self.derive()
        before = self.snapshot()
        for key in ("sim-fact-request",):
            repeated = self.derive(key=key)
            self.assertEqual(repeated['calculationId'], first['calculationId'])
            self.assertEqual(repeated['factIds'], first['factIds'])
            self.assertEqual((repeated['businessWriteCount'], repeated['auditWriteCount']), (0, 0))
            self.assertEqual(self.snapshot(), before)
        alias = self.derive(key="sim-fact-alias")
        self.assertEqual(alias['calculationId'], first['calculationId'])
        self.assertEqual((alias['businessWriteCount'], alias['auditWriteCount']), (0, 1))
        self.assertEqual(EngineeringCalculationRecord.objects.filter(scope='fact_extension').count(), 1)
        before = self.snapshot()
        repeated = self.derive(key="sim-fact-alias")
        self.assertEqual((repeated['businessWriteCount'], repeated['auditWriteCount']), (0, 0))
        self.assertEqual(self.snapshot(), before)
        self.assert_blocked(lambda: self.derive(key="sim-fact-alias", rules=[self.rule_ids[0]]), "IDEMPOTENCY_CONFLICT")

    def test_same_key_different_rule_graph_is_rejected(self):
        self.derive()
        self.assert_blocked(lambda: self.derive(rules=[self.rule_ids[0]]), "IDEMPOTENCY_CONFLICT")

    def test_missing_dimension_is_rejected_and_transaction_remains_empty(self):
        self.advance(self.input_facts[0], "superseded")
        self.assert_blocked(code="SOURCE_FACT_MISMATCH")

    def test_missing_engineering_object_lineage_is_rejected(self):
        self.input_facts[2].trace.pop('sourceAttributeId')
        self.input_facts[2].save(update_fields=("trace",))
        self.assert_blocked(code="FACT_SOURCE_GROUP_MISSING")

    def test_positive_dimensions_cannot_be_omitted_when_formal_count_is_missing(self):
        package = deepcopy(self.package)
        package['rules'][0]['ruleCode'] = "SIM-FACT-MISSING-COUNT"
        package['rules'][1]['ruleCode'] = "SIM-FACT-MISSING-COUNT-SUM"
        package['rules'][0]['specification']['factExtension']['bindings'][2]['selector']['canonicalField'] = "unavailable_quantity"
        package['rules'][1]['specification']['factExtension']['bindings'][1]['selector']['producerRuleCode'] = "SIM-FACT-MISSING-COUNT"
        ids = EngineeringFactExtensionService.configure(user=self.user,
            package=package, reason="SIMULATED_FOR_TEST")['ruleIds']
        self.assert_blocked(lambda: self.derive(rules=ids), "FACT_INPUT_MISSING")

    def test_mismatched_group_cannot_mix_two_engineering_objects(self):
        self.input_facts[0].trace['baselineItemId'] = 999
        self.input_facts[0].save(update_fields=("trace",))
        self.assert_blocked(code="FACT_INPUT_MISSING")

    def test_duplicate_object_input_is_rejected(self):
        original = self.input_facts[0]
        duplicate = self.make_source_fact(original.rule, original.uom,
            original.canonical_field, original.value['decimal'], 8)
        duplicate.trace.update(baselineItemId=1, designItemId=1, sourceAttributeId=1)
        duplicate.save(update_fields=("trace",))
        self.assert_blocked(code="FACT_INPUT_MISSING")

    def test_negative_input_is_rejected(self):
        self.input_facts[0].value = {"decimal": "-1"}
        self.input_facts[0].source_detail.output_value = {"decimal": "-1"}
        self.input_facts[0].source_detail.save(update_fields=("output_value",))
        self.input_facts[0].save(update_fields=("value",))
        self.assert_blocked(code="FACT_INPUT_INVALID")

    def test_missing_formal_unit_conversion_is_rejected(self):
        self.millimetres.conversion_base = None
        self.millimetres.conversion_factor = 1
        self.millimetres.save(update_fields=("conversion_base", "conversion_factor"))
        self.assert_blocked(code="FACT_UOM_MISMATCH")

    def test_missing_rule_and_reversed_dependency_order_are_rejected(self):
        self.assert_blocked(lambda: self.derive(rules=[999999]), "FACT_RULE_NOT_RELEASED")
        self.assert_blocked(lambda: self.derive(rules=list(reversed(self.rule_ids))))

    def test_unpublished_rule_and_foreign_company_source_are_rejected(self):
        rule = EngineeringRuleDefinition.objects.get(pk=self.rule_ids[0])
        self.advance(rule, "obsolete")
        self.assert_blocked(code="FACT_RULE_NOT_RELEASED")
        foreign = Company.objects.create(code="SIM-FACT-FOREIGN", name="SIMULATED_FOR_TEST foreign company")
        # Simulated corrupt scope is isolated; runtime must reject it without writes.
        EngineeringCalculationRecord.objects.filter(pk=self.source_calc.pk).update(company_id=foreign.pk)
        self.assert_blocked(code="SOURCE_CALCULATION_MISSING")

    def test_frontend_computed_values_are_not_accepted(self):
        before = self.snapshot()
        for payload in ({"door_panel_net_area": "999"}, {"input_values": {"height": "999"}},
                        {"output_quantity": "999"}):
            with self.assertRaises(TypeError):
                self.derive(**payload)
        self.assertEqual(self.snapshot(), before)

    def test_input_links_are_immutable_and_hash_validated(self):
        _, _, facts = self.result()
        link = facts[0].inputs.first()
        before = self.snapshot()
        with self.assertRaises(ValidationError):
            link.save()
        with self.assertRaises(ValidationError):
            link.delete()
        with self.assertRaises(ValidationError):
            EngineeringFactInput.objects.filter(pk=link.pk).update(input_name="changed")
        with self.assertRaises(ValidationError):
            EngineeringFactInput.objects.filter(pk=link.pk).delete()
        self.assertEqual(self.snapshot(), before)
        candidate = EngineeringFactInput(fact=facts[-1], source_fact=self.existing_area,
            input_name="other", sequence=10, source_hash="0" * 64, input_snapshot={"sourceFactId": self.existing_area.pk})
        with self.assertRaises(ValidationError):
            candidate.save()

    def test_incremental_schema_requires_fixed_origin_and_prohibits_superseding(self):
        _, calc, _ = self.result()
        calc.origin_calculation = None
        with self.assertRaises(ValidationError):
            calc.clean()
        calc.origin_calculation = self.source_calc
        calc.supersedes = self.source_calc
        with self.assertRaises(ValidationError):
            calc.clean()
        original = deepcopy(self.source_calc)
        original.origin_calculation = self.old_calculation
        with self.assertRaises(ValidationError):
            original.clean()

    def test_current_uom_data_drift_invalidates_saved_extension_proof(self):
        _, calc, facts = self.result()
        self.millimetres.conversion_factor = Decimal("0.002")
        self.millimetres.save(update_fields=("conversion_factor",))
        before = self.snapshot()
        with self.assertRaises(operation.OperationRequirementError) as caught:
            validate_extension_fact(calc, facts[-1])
        self.assertEqual(caught.exception.code, "FACT_EXTENSION_HASH_MISMATCH")
        self.assertEqual(self.snapshot(), before)

    def test_configuration_replay_is_zero_write_and_cannot_overwrite_version(self):
        before = self.snapshot()
        repeated = EngineeringFactExtensionService.configure(user=self.user,
            package=self.package, reason="SIMULATED_FOR_TEST")
        self.assertEqual(repeated['ruleIds'], self.rule_ids)
        self.assertEqual(self.snapshot(), before)
        modified = deepcopy(self.package)
        modified['rules'][0]['specification']['expression'] += " * 2"
        self.assert_blocked(lambda: EngineeringFactExtensionService.configure(user=self.user,
            package=modified, reason="SIMULATED_FOR_TEST"), "FACT_RULE_VERSION_CONFLICT")

    def test_rule_configuration_and_derivation_require_official_permissions(self):
        denied = User.objects.create_user(username="sim_fact_permission_denied", company_id=self.company.pk)
        self.assert_blocked(lambda: EngineeringFactExtensionService.configure(user=denied,
            package=self.package, reason="SIMULATED_FOR_TEST"), "PERMISSION_DENIED")
        self.assert_blocked(lambda: self.derive(user=denied), "PERMISSION_DENIED")

    def test_wrong_output_unit_and_duplicate_sum_sources_do_not_publish(self):
        package = deepcopy(self.package)
        package['rules'][0]['ruleCode'] += "-BAD-UNIT"
        package['rules'][0]['specification']['factExtension']['outputUomId'] = self.pcs.pk
        self.assert_blocked(lambda: EngineeringFactExtensionService.configure(user=self.user,
            package=package, reason="SIMULATED_FOR_TEST"), "FACT_UOM_MISMATCH")
        package = deepcopy(self.package)
        package['rules'][1]['ruleCode'] += "-DUPLICATE"
        bindings = package['rules'][1]['specification']['factExtension']['bindings']
        bindings.append(deepcopy(bindings[0]))
        ids = EngineeringFactExtensionService.configure(user=self.user,
            package=package, reason="SIMULATED_FOR_TEST")['ruleIds']
        self.assert_blocked(lambda: self.derive(rules=ids), "FACT_INPUT_AMBIGUOUS")

    def test_configuration_failure_rolls_back_new_rule_history_and_audits(self):
        package = deepcopy(self.package)
        package['rules'][0]['ruleCode'] = "SIM-FACT-NEW-OBJECT"
        package['rules'][1]['ruleCode'] = "SIM-FACT-NEW-SUM"
        config = package['rules'][1]['specification']['factExtension']
        config['bindings'][1]['selector']['producerRuleCode'] = "SIM-FACT-NEW-OBJECT"
        config['outputUomId'] = self.pcs.pk
        self.assert_blocked(lambda: EngineeringFactExtensionService.configure(user=self.user,
            package=package, reason="SIMULATED_FOR_TEST"), "FACT_UOM_MISMATCH")
        self.assertFalse(EngineeringRuleDefinition.objects.filter(rule_code="SIM-FACT-NEW-OBJECT").exists())

    def test_zero_quantity_retains_zero_engineering_fact_and_sums_positive_areas(self):
        quantity = self.input_facts[2]
        quantity.value = {"decimal": "0"}
        quantity.source_detail.output_value = quantity.value
        quantity.source_detail.save(update_fields=("output_value",))
        quantity.save(update_fields=("value",))
        _, calc, facts = self.result()
        self.assertEqual([Decimal(f.value['decimal']) for f in facts],
            [Decimal("0"), Decimal("0.5"), Decimal("20.5")])
        validate_extension_fact(calc, facts[-1])

    def test_persisted_calculation_detail_and_fact_states_have_real_audit_records(self):
        _, calc, facts = self.result()
        objects = [(calc, ("running", "completed"))]
        for fact in facts:
            objects.extend(((fact, ("active",)), (fact.source_detail, ("running", "succeeded"))))
        for obj, states in objects:
            history = list(BusinessStateTransition.objects.filter(
                object_type=type(obj).__name__, object_id=str(obj.pk)).order_by("version"))
            self.assertEqual(tuple(row.target_state for row in history), states)
            for transition in history:
                audit = OrganizationOperatingAuditRecord.objects.get(
                    pk=transition.audit_reference.split(':')[-1])
                self.assertEqual((audit.target_type, audit.target_id, audit.actor_id),
                    (type(obj).__name__, obj.pk, self.user.pk))

    def test_missing_calculation_audit_blocks_incremental_fact_proof(self):
        _, calc, facts = self.result()
        OrganizationOperatingAuditRecord.objects.filter(
            target_type='EngineeringCalculationRecord', target_id=calc.pk).delete()
        self.assert_blocked(lambda: validate_extension_fact(calc, facts[-1]),
            "FACT_EXTENSION_AUDIT_MISSING")

    def test_tampered_input_source_fk_blocks_incremental_fact_proof(self):
        _, calc, facts = self.result()
        link = facts[0].inputs.get(input_name='height')
        # Direct corruption is confined to the isolated test DB to challenge readback.
        table = connection.ops.quote_name(EngineeringFactInput._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f'UPDATE {table} SET source_fact_id = %s WHERE id = %s',
                [self.existing_area.pk, link.pk])
        self.assert_blocked(lambda: validate_extension_fact(calc, facts[-1]),
            "FACT_EXTENSION_UNPROVEN")

    def test_tampered_input_hash_blocks_incremental_fact_proof(self):
        _, calc, facts = self.result()
        link = facts[0].inputs.get(input_name='height')
        # Persisted evidence damage must fail even when all output numbers still match.
        table = connection.ops.quote_name(EngineeringFactInput._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f'UPDATE {table} SET source_hash = %s WHERE id = %s',
                ['0' * 64, link.pk])
        self.assert_blocked(lambda: validate_extension_fact(calc, facts[-1]),
            "FACT_EXTENSION_UNPROVEN")

    def test_selected_summary_source_with_wrong_unit_is_blocked_without_omission(self):
        other_area = UnitOfMeasure.objects.create(company_id=self.company.pk,
            code='SIM-OTHER-AREA', name='Abstract other area unit', dimension='area')
        package = deepcopy(self.package)
        package['rules'][1]['ruleCode'] = 'SIM-FACT-SUM-WRONG-SOURCE-UNIT'
        package['rules'][1]['specification']['factExtension']['bindings'][0]['sourceUomId'] = other_area.pk
        ids = EngineeringFactExtensionService.configure(user=self.user,
            package=package, reason='SIMULATED_FOR_TEST')['ruleIds']
        self.assert_blocked(lambda: self.derive(rules=ids), "FACT_UOM_MISMATCH")

    def test_publication_rejects_target_unit_differing_from_arithmetic_input_contract(self):
        package = deepcopy(self.package)
        package['rules'][0]['ruleCode'] = 'SIM-FACT-WRONG-ARITHMETIC-UNIT'
        package['rules'][0]['specification']['factExtension']['bindings'][0]['targetUomId'] = self.millimetres.pk
        self.assert_blocked(lambda: EngineeringFactExtensionService.configure(user=self.user,
            package=package, reason='SIMULATED_FOR_TEST'), 'FACT_UOM_MISMATCH')
        self.assertFalse(EngineeringRuleDefinition.objects.filter(
            rule_code='SIM-FACT-WRONG-ARITHMETIC-UNIT').exists())

    def test_extra_contradictory_state_history_blocks_fact_proof(self):
        _, calc, facts = self.result()
        fact = facts[0]
        # A uniform-service projection is injected only as an isolated fault fixture.
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code=operation.EXECUTE, actor=self.user, organization=self.company,
            target_type=type(fact).__name__, target_id=fact.pk, target_label=str(fact.pk),
            reason='SIMULATED_FOR_TEST contradictory extra state history',
            before_snapshot={'state': _snapshot(fact)}, after_snapshot={'state': _snapshot(fact)})
        record_projected_business_transition(object_type=type(fact).__name__, object_id=fact.pk,
            source_state='active', target_state='active', action_code=operation.EXECUTE,
            operator=self.user, reason=audit.reason,
            audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',
            allowed_transitions=(('active', 'active'),))
        self.assert_blocked(lambda: validate_extension_fact(calc, facts[-1]),
            'FACT_EXTENSION_AUDIT_MISSING')

    def test_calculation_time_tampering_blocks_fact_proof(self):
        _, calc, facts = self.result()
        fact = facts[0]
        fact.trace['calculatedAt'] = '1900-01-01T00:00:00+00:00'
        fact.save(update_fields=('trace',))
        self.assert_blocked(lambda: validate_extension_fact(calc, facts[-1]),
            'FACT_EXTENSION_AUDIT_MISSING')
