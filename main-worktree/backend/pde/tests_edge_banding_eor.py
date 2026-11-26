"""SIMULATED_FOR_TEST: governed length facts, resource correction and EOR.

These cases populate only an isolated Django test database. Abstract identifiers
prove that dimensions, mappings and capacities come from formal data.
"""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from masterdata.models import CodeRule, ExternalIdentity, MasterDataWriteRequest, UnitOfMeasure
from system.models import OrganizationOperatingAuditRecord, Process
from workflow_runtime.models import BusinessStateTransition
from . import operation_requirement_service as operation
from . import tests_operation_requirement as fixtures
from . import tests_manufacturing_eor_configuration as manufacturing_fixtures
from .daily_capacity_service import capacity_fact, capacity_source_rules, SOURCE_RULES_CONTRACT
from .engineering_fact_extension_service import EngineeringFactExtensionService, validate_extension_fact, CONTRACT as FACT_CONTRACT
from .manufacturing_configuration_service import ManufacturingConfigurationService, CREATE, RELEASE
from .manufacturing_capacity_scope import capacity_usage_scope_proof
from .manufacturing_resource_configuration_service import ManufacturingResourceConfigurationService
from .manufacturing_rule_configuration import publication_config_validation
from .models import EngineeringCalculationRecord, EngineeringCalculationDetail, EngineeringDerivedFact, EngineeringFactInput, EngineeringOperationRequirement, EngineeringRuleDefinition, ManufacturingMode, StandardCapacity
from .production_foundation_service import ProductionFoundationError


RESOURCE_CONTRACT = 'PCE-MANUFACTURING-RESOURCE-CONFIGURATION-V1'
SCOPE_CONTRACT = 'PCE-MANUFACTURING-CAPACITY-SCOPE-V1'


class EdgeBandingEorTests(TestCase):
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
        self.metres = UnitOfMeasure.objects.create(company_id=self.company.pk,
            code='SIM-LENGTH-BASE', name='Abstract length', dimension='length')
        self.edge_process = Process.objects.create(company=self.company, code='SIM-LENGTH-OP',
            name='Abstract measured operation', workshop=self.workshop, work_center=self.center,
            calculation_basis='area', calculation_uom=self.area)
        self.legacy_manifest = {'contractVersion': SOURCE_RULES_CONTRACT,
            'sourceSha256': 'a1' * 32, 'productTypeCode': self.product_type.code,
            'effectiveDate': self.capacity.effective_from.isoformat(),
            'applicableOperationIds': [self.op_area.pk],
            'nonApplicableOperationIds': [self.edge_process.pk],
            'auxiliaryOperationIds': [self.op_area.pk],
            'preparationDays': '0.1', 'transferDays': '0.1',
            'businessFactReference': 'SIMULATED_FOR_TEST preserved source contract'}
        self.capacity.quantity = Decimal(0)
        self.capacity.measurement_status = 'zero_capacity'
        self.capacity.preparation_days = self.capacity.transfer_days = Decimal('0.1')
        self.capacity.conditions = {'sourceSha256': 'a1' * 32,
            'sourceProductTypeCode': self.product_type.code, 'apsSourceRules': deepcopy(self.legacy_manifest)}
        self.capacity.save()
        self.old_source = self.source_calc
        self.old_eor = self.generate(rule=self.mapping, key='SIM-OLD-GENERATE')['operationRequirementId']
        self.length_mode = self.make_mode(self.metres, 'SIM-LENGTH-MODE')
        self.source_calc = self.initial(EngineeringCalculationRecord, 'running', company=self.company,
            scope='order_engineering', source_record=self.source, sales_order_item=self.item,
            engineering_instance=self.instance, calculation_no='SIM-LENGTH-ORIGIN', revision=2,
            rule_set_version='SIM-V1', input_hash=fixtures.digest('length inputs'),
            rule_graph_hash=fixtures.digest('length graph'), result_hash=fixtures.digest('length result'),
            trace={'sourceKind': 'SIMULATED_FOR_TEST'})
        self.length_producer = self.make_rule(self.edge_process, self.metres,
            'abstract_length_input', output_domain='DERIVED_FACT')
        self.length_facts = [self.make_source_fact(self.length_producer, self.metres,
            'abstract_length_input', value, i) for i, value in enumerate(('1.764000', '6.250000', '0.000000'), 1)]
        for i, fact in enumerate(self.length_facts, 1):
            fact.trace['abstractObjectId'] = i
            fact.save(update_fields=('trace',))
        self.source_calc.started_at = self.source_calc.finished_at = timezone.now()
        self.source_calc.save(update_fields=('started_at', 'finished_at'))
        self.advance(self.source_calc, 'completed')
        self.grant_configuration_permissions(CREATE, RELEASE, 'production.master_data.resource.maintain',
            'production.master_data.capacity.maintain', 'production.master_data.create')
        self.scope = {'contractVersion': SCOPE_CONTRACT, 'usageScope': 'ENGINEERING_EOR_ONLY',
            'version': 'V2', 'businessFactReference': 'SIMULATED_FOR_TEST explicit manufacturing configuration',
            'sourceFingerprint': 'b2' * 32}
        self.resource_package = self.make_resource_package()
        self.preserved = self.preservation_snapshot()

    def make_resource_package(self, *, quantity='500', key='sim-length-capacity', code='SIM-LENGTH-CAP'):
        return {'contractVersion': RESOURCE_CONTRACT, 'companyId': self.company.pk,
            'businessReason': 'SIMULATED_FOR_TEST stable business evidence',
            'operationCorrections': [{'objectId': self.edge_process.pk, 'requestKey': 'SIM-UNIT-CORRECTION',
                'expected': {'calculation_basis': 'area', 'calculation_uom_id': self.area.pk},
                'values': {'calculation_basis': 'length', 'calculation_uom_id': self.metres.pk}}],
            'capacities': [{'payload': {'company_id': self.company.pk, 'code': code,
                'name': 'SIMULATED_FOR_TEST governed daily length', 'resource_scope': 'work_center',
                'work_center_id': self.center.pk, 'operation_id': self.edge_process.pk,
                'product_type_id': self.product_type.pk, 'measurement_status': 'measured',
                'quantity': quantity, 'uom_id': self.metres.pk, 'time_basis': 'day',
                'time_basis_quantity': '1', 'time_unit': 'DAY',
                'effective_from': self.capacity.effective_from.isoformat(),
                'conditions': {'capacityUsageScope': deepcopy(self.scope)}, 'is_active': True},
                'requestKey': key, 'sourceIdentity': {'sourceSystem': 'PCE', 'sourceType': 'FORMAL_CONFIG',
                    'sourceObjectType': 'SIMULATED_FOR_TEST_RESOURCE_PACKAGE', 'externalId': code,
                    'sourceFingerprint': self.scope['sourceFingerprint'],
                    'auditMetadata': {'capacityUsageScope': deepcopy(self.scope)}}}]}

    def configure_resources(self, package=None, user=None):
        result = ManufacturingResourceConfigurationService.configure(user=user or self.user,
            package=package or self.resource_package, reason='SIMULATED_FOR_TEST authorized correction')
        return result, StandardCapacity.objects.get(code=(package or self.resource_package)['capacities'][0]['payload']['code'])

    def length_rule(self, capacity, fact=None, *, version='V2', expected_scope=None):
        fact = fact or self.length_facts[0]
        rule = self.make_mapping(fact, self.edge_process, self.metres, mode=self.length_mode,
            capacity=capacity, release=False, dynamic_source_basis=True)
        rule.version = version
        rule.specification['rulePackage']['version'] = version
        rule.specification['expression'] = 'EdgeBandingLength'
        rule.specification['inputs'][0]['canonicalName'] = 'EdgeBandingLength'
        rule.specification['manufacturing']['sourceSelector']['objectTraceKeys'] = ['abstractObjectId']
        rule.specification['manufacturing']['capacityUsageScope'] = deepcopy(expected_scope or self.scope)
        rule.save(update_fields=('version', 'specification'))
        self.advance(rule, 'reviewed')
        self.advance(rule, 'released')
        return rule

    def preservation_snapshot(self):
        return {'eor': list(EngineeringOperationRequirement.objects.filter(pk=self.old_eor).values()),
            'source': list(EngineeringCalculationRecord.objects.filter(pk__in=[self.old_source.pk, self.source_calc.pk]).order_by('pk').values()),
            'facts': list(EngineeringDerivedFact.objects.filter(calculation_id__in=[self.old_source.pk, self.source_calc.pk]).order_by('pk').values()),
            'details': list(EngineeringCalculationDetail.objects.filter(calculation_id__in=[self.old_source.pk, self.source_calc.pk]).order_by('pk').values()),
            'rule': list(EngineeringRuleDefinition.objects.filter(pk=self.mapping.pk).values()),
            'legacyCapacity': list(StandardCapacity.objects.filter(pk=self.capacity.pk).values())}

    def all_snapshot(self):
        return {m.__name__: list(m.objects.order_by('pk').values()) for m in (
            Process, StandardCapacity, EngineeringCalculationRecord, EngineeringCalculationDetail,
            EngineeringDerivedFact, EngineeringFactInput, EngineeringOperationRequirement,
            EngineeringRuleDefinition, ManufacturingMode, OrganizationOperatingAuditRecord,
            BusinessStateTransition, ExternalIdentity, MasterDataWriteRequest, CodeRule)}

    def assert_preserved(self):
        self.assertEqual(self.preservation_snapshot(), self.preserved)
        operation._validate_requirement(EngineeringOperationRequirement.objects.get(pk=self.old_eor), self.company.pk)
        source_rules = capacity_source_rules(self.product_type, company_id=self.company.pk, on_date=operation._today())
        self.assertEqual(source_rules['status'], 'VALID', source_rules)
        self.assertEqual(source_rules['manifest'], self.legacy_manifest)

    def assert_resource_blocked(self, package=None, user=None):
        before = self.all_snapshot()
        with self.assertRaises((operation.OperationRequirementError, ProductionFoundationError)):
            self.configure_resources(package, user)
        self.assertEqual(self.all_snapshot(), before)

    def fact_package(self, *, unit=None):
        unit = unit or self.metres
        spec = {'rulePackage': {'code': 'SIM-LENGTH-FACTS', 'version': 'V2'},
            'inputs': [{'canonicalName': 'net_quantity', 'valueType': 'decimal', 'unit': unit.code,
                'unitDimension': unit.dimension, 'sourceType': 'AGGREGATED', 'required': True, 'unitRequired': True}],
            'outputs': [{'canonicalName': 'EdgeBandingLength', 'valueType': 'decimal', 'unit': unit.code,
                'unitDimension': unit.dimension, 'resultDomain': 'DERIVED_FACT'}],
            'expression': 'net_quantity', 'dependencies': [], 'applicability': {},
            'decimalPrecision': 28, 'outputScale': 6, 'roundingMode': 'ROUND_HALF_UP',
            'sourceEvidence': {'reference': 'SIMULATED_FOR_TEST formal length input'},
            'factExtension': {'contractVersion': FACT_CONTRACT, 'strategy': 'SCOPE_SUM',
                'outputUomId': unit.pk, 'bindings': [{'inputName': 'net_quantity', 'sourceScope': 'ORIGIN',
                    'sourceUomId': unit.pk, 'targetUomId': unit.pk,
                    'selector': {'canonicalField': 'abstract_length_input', 'producerRuleId': self.length_producer.pk,
                        'producerRuleVersion': self.length_producer.version,
                        'traceEquals': {'sourceKind': 'SIMULATED_FOR_TEST'}}}]}}
        return {'contractVersion': FACT_CONTRACT, 'companyId': self.company.pk,
            'rules': [{'ruleCode': 'SIM-NET-LENGTH', 'ruleName': 'Abstract summed length', 'version': 'V2', 'specification': spec}]}

    def test_schema_reuses_existing_formal_fact_input_and_eor_tables(self):
        tables = connection.introspection.table_names()
        self.assertIn(EngineeringFactInput._meta.db_table, tables)
        self.assertIn(EngineeringOperationRequirement._meta.db_table, tables)
        self.assertTrue(EngineeringOperationRequirement._meta.get_field('uom').remote_field)
        self.assertEqual(EngineeringFactInput._meta.get_field('source_fact').remote_field.model, EngineeringDerivedFact)

    def test_formal_resource_correction_has_original_area_in_actual_audit(self):
        self.configure_resources()
        self.edge_process.refresh_from_db()
        self.assertEqual((self.edge_process.calculation_basis, self.edge_process.calculation_uom_id), ('length', self.metres.pk))
        audit = OrganizationOperatingAuditRecord.objects.filter(target_type='Process', target_id=self.edge_process.pk,
            action_code='production.master_data.resource.maintain').get()
        self.assertEqual(audit.before_snapshot['state']['calculation_uom_id'], self.area.pk)
        self.assertEqual(audit.after_snapshot['state']['calculation_uom_id'], self.metres.pk)
        self.assert_preserved()

    def test_configure_same_request_is_zero_write(self):
        self.configure_resources()
        before = self.all_snapshot()
        self.configure_resources()
        self.assertEqual(self.all_snapshot(), before)

    def test_data_capacity_supports_700_without_runtime_500_constant(self):
        _, cap = self.configure_resources(self.make_resource_package(quantity='700'))
        self.assertEqual(cap.quantity, Decimal('700'))
        req = self.generate(fact=self.length_facts[0], rule=self.length_rule(cap))
        saved = EngineeringOperationRequirement.objects.get(pk=req['operationRequirementId'])
        self.assertEqual(saved.workload_quantity, Decimal('1.764'))
        self.assertEqual(saved.calculation.trace['sourceSnapshot']['manufacturing']['standardCapacity']['quantity'], '700.000000')

    def test_length_alias_generates_v2_exact_quantity_and_formal_trace(self):
        _, cap = self.configure_resources()
        rule = self.length_rule(cap)
        with patch('pde.engineering_calculation_service.EngineeringCalculationService.execute',
                   side_effect=AssertionError('Original engineering calculation cannot run')):
            result = self.generate(fact=self.length_facts[0], rule=rule)
        req = EngineeringOperationRequirement.objects.get(pk=result['operationRequirementId'])
        self.assertEqual((req.workload_quantity, req.uom_id, req.source_detail.rule_version), (Decimal('1.764'), self.metres.pk, 'V2'))
        self.assertEqual((req.source_calculation_id, req.source_fact_id, req.operation_id),
            (self.source_calc.pk, self.length_facts[0].pk, self.edge_process.pk))
        self.assertEqual(req.manufacturing_mode_id, self.length_mode.pk)
        self.assertEqual((len(req.source_hash), len(req.input_hash), len(req.calculation.rule_graph_hash)), (64, 64, 64))
        mfg = req.calculation.trace['sourceSnapshot']['manufacturing']
        self.assertFalse(mfg['unitConversionApplied'])
        self.assertEqual(mfg['selectedSource']['sourceEngineeringObject'], {'abstractObjectId': 1})
        self.assertFalse(mfg['standardCapacity']['independentApsSchedulingAllowed'])
        self.assertTrue(capacity_usage_scope_proof(cap))
        operation._validate_requirement(req, self.company.pk)
        self.assert_preserved()

    def test_eor_repeat_keeps_all_rows_and_audits_unchanged(self):
        _, cap = self.configure_resources()
        rule = self.length_rule(cap)
        self.generate(fact=self.length_facts[0], rule=rule)
        before = self.all_snapshot()
        result = self.generate(fact=self.length_facts[0], rule=rule)
        self.assertEqual(result['businessWriteCount'], 0)
        self.assertEqual(result['auditWriteCount'], 0)
        self.assertEqual(self.all_snapshot(), before)

    def test_only_requested_rules_generate_and_zero_length_is_retained(self):
        _, cap = self.configure_resources()
        rule = self.length_rule(cap)
        result = ManufacturingConfigurationService.generate_for_calculation(user=self.user,
            source_calculation_id=self.source_calc.pk, request_key='SIM-SELECTED-RULES',
            reason='SIMULATED_FOR_TEST', rule_ids=[rule.pk])
        self.assertEqual(result['blockers'], [])
        self.assertEqual(len(result['requirements']), 2)
        self.assertEqual(len(result['retainedZeroFacts']), 1)
        self.assertEqual(sum(Decimal(r['workloadQuantity']) for r in result['requirements']), Decimal('8.014'))
        self.assert_preserved()

    def test_server_fact_sum_preserves_fractional_identity_and_input_lineage(self):
        rule_ids = EngineeringFactExtensionService.configure(user=self.user, package=self.fact_package(), reason='SIMULATED_FOR_TEST')['ruleIds']
        with patch('pde.engineering_calculation_service.EngineeringCalculationService.execute',
                   side_effect=AssertionError('No engineering rerun')):
            result = EngineeringFactExtensionService.derive(user=self.user, source_calculation_id=self.source_calc.pk,
                rule_ids=rule_ids, idempotency_key='SIM-LENGTH-FACT', reason='SIMULATED_FOR_TEST')
        calc = EngineeringCalculationRecord.objects.get(pk=result['calculationId'])
        fact = calc.derived_facts.get()
        self.assertEqual((fact.value, fact.uom_id), ({'decimal': '8.014000'}, self.metres.pk))
        self.assertEqual(set(fact.inputs.values_list('source_fact_id', flat=True)), {f.pk for f in self.length_facts})
        for link in fact.inputs.all():
            self.assertEqual(link.input_snapshot['normalization']['appliedFactor'], '1')
            self.assertEqual(link.source_hash, operation._digest(link.input_snapshot))
        validate_extension_fact(calc, fact)
        before = self.all_snapshot()
        EngineeringFactExtensionService.derive(user=self.user, source_calculation_id=self.source_calc.pk,
            rule_ids=rule_ids, idempotency_key='SIM-LENGTH-FACT', reason='SIMULATED_FOR_TEST')
        self.assertEqual(self.all_snapshot(), before)
        self.assert_preserved()

    def test_area_cannot_be_silently_accepted_as_a_length_fact(self):
        rule_ids = EngineeringFactExtensionService.configure(user=self.user, package=self.fact_package(unit=self.area), reason='SIMULATED_FOR_TEST')['ruleIds']
        before = self.all_snapshot()
        with self.assertRaises(operation.OperationRequirementError) as caught:
            EngineeringFactExtensionService.derive(user=self.user, source_calculation_id=self.source_calc.pk,
                rule_ids=rule_ids, idempotency_key='SIM-WRONG-UOM', reason='SIMULATED_FOR_TEST')
        self.assertEqual(caught.exception.code, 'FACT_UOM_MISMATCH')
        self.assertEqual(self.all_snapshot(), before)

    def test_resource_correction_whitelist_rejects_unrelated_field(self):
        package = deepcopy(self.resource_package)
        package['operationCorrections'][0]['values']['name'] = 'Unauthorized renaming'
        self.assert_resource_blocked(package)

    def test_resource_correction_must_match_preexisting_expected_values(self):
        package = deepcopy(self.resource_package)
        package['operationCorrections'][0]['expected']['calculation_uom_id'] = self.metres.pk
        self.assert_resource_blocked(package)

    def test_missing_permission_rolls_back_every_resource_write(self):
        user = type(self.user).objects.create_user(username='sim_length_unauthorized', company_id=self.company.pk)
        self.assert_resource_blocked(user=user)

    def test_invalid_daily_basis_rolls_back_process_correction(self):
        package = deepcopy(self.resource_package)
        package['capacities'][0]['payload']['time_basis'] = 'hour'
        self.assert_resource_blocked(package)

    def test_wrong_capacity_unit_rolls_back_process_correction(self):
        package = deepcopy(self.resource_package)
        package['capacities'][0]['payload']['uom_id'] = self.area.pk
        self.assert_resource_blocked(package)

    def test_forged_scope_without_committed_ledger_fails_closed(self):
        forged = self.make_capacity(self.edge_process, self.metres, 'SIM-FORGED-SCOPE',
            conditions={'capacityUsageScope': deepcopy(self.scope)})
        with self.assertRaises(operation.OperationRequirementError) as caught:
            capacity_usage_scope_proof(forged)
        self.assertEqual(caught.exception.code, 'MANUFACTURING_CAPACITY_SCOPE_INVALID')
        result = capacity_source_rules(self.product_type, company_id=self.company.pk, on_date=operation._today())
        self.assertEqual(result['status'], 'INVALID')

    def test_mixed_aps_and_eor_scope_is_rejected(self):
        package = deepcopy(self.resource_package)
        package['capacities'][0]['payload']['conditions']['apsSourceRules'] = deepcopy(self.legacy_manifest)
        self.assert_resource_blocked(package)

    def test_source_identity_scope_mismatch_is_rejected(self):
        package = deepcopy(self.resource_package)
        package['capacities'][0]['sourceIdentity']['auditMetadata']['capacityUsageScope']['version'] = 'V3'
        self.assert_resource_blocked(package)

    def test_capacity_replay_payload_conflict_cannot_overwrite_history(self):
        self.configure_resources()
        package = deepcopy(self.resource_package)
        package['capacities'][0]['payload']['quantity'] = '700'
        self.assert_resource_blocked(package)

    def test_new_request_key_cannot_alias_existing_source_identity_with_changed_capacity(self):
        _, cap = self.configure_resources()
        proof = capacity_usage_scope_proof(cap)
        identity = ExternalIdentity.objects.get(pk=proof['sourceIdentityId'])
        self.assertEqual(identity.mapping_status, ExternalIdentity.MappingStatus.MATCH)
        package = deepcopy(self.resource_package)
        package['capacities'][0]['requestKey'] = 'SIM-SAME-SOURCE-CHANGED-ALIAS'
        package['capacities'][0]['payload']['quantity'] = '700'
        before = self.all_snapshot()
        with self.assertRaises(operation.OperationRequirementError) as caught:
            self.configure_resources(package)
        self.assertEqual(caught.exception.code, 'RESOURCE_CAPACITY_PAYLOAD_CONFLICT')
        self.assertEqual(self.all_snapshot(), before)
        cap.refresh_from_db()
        self.assertEqual(cap.quantity, Decimal('500'))
        self.assertFalse(MasterDataWriteRequest.objects.filter(idempotency_key='SIM-SAME-SOURCE-CHANGED-ALIAS').exists())
        self.assert_preserved()

    def test_scope_detects_actual_capacity_tamper(self):
        _, cap = self.configure_resources()
        cap.quantity = Decimal('700')
        cap.save(update_fields=('quantity',))
        with self.assertRaises(operation.OperationRequirementError) as caught:
            capacity_usage_scope_proof(cap)
        self.assertEqual(caught.exception.code, 'MANUFACTURING_CAPACITY_SCOPE_INVALID')

    def test_scope_requires_actual_creation_audit(self):
        _, cap = self.configure_resources()
        proof = capacity_usage_scope_proof(cap)
        OrganizationOperatingAuditRecord.objects.filter(pk=proof['auditId']).delete()
        with self.assertRaises(operation.OperationRequirementError) as caught:
            capacity_usage_scope_proof(cap)
        self.assertEqual(caught.exception.code, 'MANUFACTURING_CAPACITY_SCOPE_INVALID')

    def test_eor_only_capacity_does_not_open_aps_availability(self):
        _, cap = self.configure_resources()
        self.assertTrue(capacity_usage_scope_proof(cap))
        before = self.all_snapshot()
        fact = capacity_fact(cap, operation._today())
        self.assertFalse(fact['available'])
        self.assertEqual(fact['quantity'], '500.000000')
        self.assertEqual(fact['uomId'], self.metres.pk)
        self.assertEqual(self.all_snapshot(), before)

    def test_new_published_v2_rule_preserves_original_v1_and_replays_zero_write(self):
        _, cap = self.configure_resources()
        candidate = self.length_rule(cap)
        spec = deepcopy(candidate.specification)
        config = spec['manufacturing']
        config.pop('modeId')
        config['modeCode'] = self.length_mode.code
        package = {'contractVersion': 'PCE-MANUFACTURING-EOR-RULE-V1', 'companyId': self.company.pk,
            'modes': [], 'rules': [{'ruleCode': self.mapping.rule_code,
                'ruleName': 'SIMULATED_FOR_TEST revised length rule', 'version': 'V2', 'specification': spec}]}
        result = ManufacturingConfigurationService.configure(user=self.user, package=package, reason='SIMULATED_FOR_TEST')
        rule = EngineeringRuleDefinition.objects.get(pk=result['rules'][0]['id'])
        self.assertEqual((rule.rule_code, rule.version, rule.status), (self.mapping.rule_code, 'V2', 'released'))
        result = self.generate(fact=self.length_facts[0], rule=rule)
        self.assertEqual(result['operationRequirement']['ruleVersion'], 'V2')
        before = self.all_snapshot()
        ManufacturingConfigurationService.configure(user=self.user, package=package, reason='SIMULATED_FOR_TEST replay')
        self.assertEqual(self.all_snapshot(), before)
        self.assert_preserved()

    def test_scope_requires_complete_committed_write_result(self):
        _, cap = self.configure_resources()
        proof = capacity_usage_scope_proof(cap)
        ledger = MasterDataWriteRequest.objects.get(pk=proof['writeRequestId'])
        ledger.result = {'row': {'id': cap.pk}}
        ledger.save(update_fields=('result',))
        with self.assertRaises(operation.OperationRequirementError) as caught:
            capacity_usage_scope_proof(cap)
        self.assertEqual(caught.exception.code, 'MANUFACTURING_CAPACITY_SCOPE_INVALID')

    def test_rule_scope_expectation_blocks_removed_capacity_scope_downgrade(self):
        _, cap = self.configure_resources()
        rule = self.length_rule(cap)
        cap.conditions = {}
        cap.save(update_fields=('conditions',))
        self.assertIsNone(capacity_usage_scope_proof(cap))
        before = self.all_snapshot()
        with self.assertRaises(operation.OperationRequirementError) as publication_error:
            publication_config_validation(rule, require_released=True)
        self.assertEqual(publication_error.exception.code, 'MANUFACTURING_CAPACITY_SCOPE_INVALID')
        readiness = operation.OperationRequirementService.generate_readiness(user=self.user,
            source_calculation_id=self.source_calc.pk, source_fact_id=self.length_facts[0].pk, rule_id=rule.pk)
        self.assertFalse(readiness['ready'])
        self.assertEqual(readiness['blockers'][0]['code'], 'MANUFACTURING_CAPACITY_SCOPE_INVALID')
        with self.assertRaises(operation.OperationRequirementError):
            self.generate(fact=self.length_facts[0], rule=rule)
        self.assertEqual(self.all_snapshot(), before)

    def test_rule_scope_requires_exact_capacity_scope_version(self):
        _, cap = self.configure_resources()
        expected = {**self.scope, 'version': 'V3'}
        rule = self.length_rule(cap, expected_scope=expected)
        before = self.all_snapshot()
        readiness = operation.OperationRequirementService.generate_readiness(user=self.user,
            source_calculation_id=self.source_calc.pk, source_fact_id=self.length_facts[0].pk, rule_id=rule.pk)
        self.assertFalse(readiness['ready'])
        self.assertEqual(readiness['blockers'][0]['code'], 'MANUFACTURING_CAPACITY_SCOPE_INVALID')
        self.assertEqual(self.all_snapshot(), before)

    def test_declared_scope_with_invalid_fingerprint_rolls_back(self):
        package = deepcopy(self.resource_package)
        package['capacities'][0]['payload']['conditions']['capacityUsageScope']['sourceFingerprint'] = 'invalid'
        self.assert_resource_blocked(package)

    def test_existing_eor_blocks_remeasurement_of_its_process(self):
        package = deepcopy(self.resource_package)
        package['operationCorrections'][0]['objectId'] = self.op_area.pk
        self.assert_resource_blocked(package)
        self.assert_preserved()

    def test_requested_rule_scope_rejects_missing_published_rule_before_writes(self):
        before = self.all_snapshot()
        with self.assertRaises(operation.OperationRequirementError):
            ManufacturingConfigurationService.generate_for_calculation(user=self.user,
                source_calculation_id=self.source_calc.pk, request_key='SIM-MISSING-RULE',
                reason='SIMULATED_FOR_TEST', rule_ids=[999999])
        self.assertEqual(self.all_snapshot(), before)

    def test_exact_object_trace_cannot_be_replaced_by_boolean(self):
        _, cap = self.configure_resources()
        rule = self.length_rule(cap)
        fact = self.length_facts[0]
        fact.trace['abstractObjectId'] = True
        fact.save(update_fields=('trace',))
        before = self.all_snapshot()
        with self.assertRaises(operation.OperationRequirementError):
            self.generate(fact=fact, rule=rule)
        self.assertEqual(self.all_snapshot(), before)

    def test_schema_change_and_foreign_key_errors_are_absent(self):
        _, cap = self.configure_resources()
        self.generate(fact=self.length_facts[0], rule=self.length_rule(cap))
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA foreign_key_check')
            self.assertEqual(cursor.fetchall(), [])
        self.assert_preserved()
