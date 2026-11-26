"""Isolated fixed-input proof regression; no production source admission.

Only the existing workbook fixture's synthetic numeric method/reference is
substituted. XLSX normalization, source publication, native main persistence,
completion audits, metadata proof and classified extension remain real. This
class borrows fixture helpers without inheriting or rerunning its old tests.
"""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase

from masterdata.models import UnitOfMeasure
from system.models import Company, OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from . import tests_engineering_workbook_source_version as workbook_fixture
from . import tests_engineering_calculation_continuation as main_fixture
from .engineering_calculation_continuation_service import (
    EngineeringCalculationContinuationService as Continuation,
)
from .engineering_calculation_service import EngineeringCalculationError
from .engineering_fact_extension_service import EngineeringFactExtensionService
from .engineering_fact_metadata import _prepare_origin
from .engineering_workbook_source_service import (
    CONTRACT, WorkbookSourceError, resolve_workbook_source, saved_workbook_input,
)
from .formal_engineering_continuation_service import calculation_input_hash, _hash
from .models import (
    EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringRuleDefinition,
    EngineeringSourceRecord, OrderEngineeringBaseline, OrderEngineeringBaselineItem,
    ProductDesignItem, ProductDesignRevision,
)
from .operation_requirement_service import OperationRequirementError


class EngineeringCalculationInputContractTests(TestCase):
    _adopt = workbook_fixture.EngineeringWorkbookSourceVersionTests._adopt
    args = workbook_fixture.EngineeringWorkbookSourceVersionTests.args
    numeric_fixture = workbook_fixture.EngineeringWorkbookSourceVersionTests.numeric_fixture
    make_blob = workbook_fixture.EngineeringWorkbookSourceVersionTests.make_blob
    publish_rule = workbook_fixture.EngineeringWorkbookSourceVersionTests.publish_rule
    save_source = workbook_fixture.EngineeringWorkbookSourceVersionTests.save_source

    @classmethod
    def setUpTestData(cls):
        workbook_fixture.EngineeringWorkbookSourceVersionTests.setUpTestData.__func__(cls)

    def setUp(self):
        workbook_fixture.EngineeringWorkbookSourceVersionTests.setUp(self)

    def main(self, *, workbook=True):
        arguments = self.args()
        if workbook:
            self.workbook_source = self.save_source()
            arguments['workbook_source_record_id'] = self.workbook_source.pk
        candidate = Continuation.preview(**arguments)
        self.assertTrue(candidate['ready'], candidate)
        result = Continuation.execute(**arguments,
            expected_context_hash=candidate['expectedContextHash'],
            continuation_basis_hash=candidate['continuationBasisHash'],
            idempotency_key='isolated-fixed-input-main', reason='isolated fixed input proof')
        return EngineeringCalculationRecord.objects.get(pk=result['newCalculationId'])

    def metadata_rejected(self, calculation, *, cause=None):
        with self.assertRaises(OperationRequirementError) as caught:
            _prepare_origin(calculation)
        self.assertEqual(caught.exception.code, 'FACT_METADATA_SOURCE_UNPROVEN')
        if cause:
            self.assertEqual(caught.exception.details.get('cause'), cause)

    def completion(self, calculation):
        state = BusinessStateTransition.objects.get(object_type='EngineeringCalculationRecord',
            object_id=calculation.pk, action_code='production.engineering.calculation.execute',
            target_state='completed')
        return state, OrganizationOperatingAuditRecord.objects.get(
            pk=int(state.audit_reference.split(':')[-1]))

    def classified_rule(self, calculation):
        fact = calculation.derived_facts.select_related('source_detail').first()
        spec = {'rulePackage': {'code': 'ISOLATED-FIXED-INPUT-CLASSIFICATION', 'version': 'V1'},
            'inputs': [{'canonicalName': 'quantity', 'valueType': 'decimal', 'unit': self.uom.code,
                'unitDimension': 'count', 'sourceType': 'AGGREGATED', 'required': True, 'unitRequired': True}],
            'outputs': [{'canonicalName': 'FixedObjectQuantity', 'valueType': 'decimal',
                'resultDomain': 'DERIVED_FACT', 'unit': self.uom.code, 'unitDimension': 'count'}],
            'expression': 'quantity', 'dependencies': [], 'applicability': {},
            'decimalPrecision': 28, 'outputScale': 6, 'roundingMode': 'ROUND_HALF_UP',
            'sourceEvidence': {'reference': 'isolated fixed input and unit proof'},
            'factExtension': {'contractVersion': 'PCE-ENGINEERING-FACT-EXTENSION-V1',
                'strategy': 'GROUP_SUM', 'outputUomId': self.uom.pk,
                'groupKeys': ['designItemId', 'baselineItemId'],
                'metadataBindings': [{'name': key, 'sourceType': 'FORMAL_SOURCE_IDENTITY',
                    'valueField': key} for key in ('designItemId', 'baselineItemId')],
                'bindings': [{'inputName': 'quantity', 'sourceScope': 'ORIGIN',
                    'sourceUomId': self.uom.pk, 'targetUomId': self.uom.pk,
                    'selector': {'canonicalField': fact.canonical_field,
                        'producerRuleId': fact.rule_id, 'producerRuleVersion': fact.source_detail.rule_version,
                        'traceEquals': {'resultScope': fact.trace['resultScope']}}}]}}
        result = EngineeringFactExtensionService.configure(user=self.actor,
            package={'contractVersion': 'PCE-ENGINEERING-FACT-EXTENSION-V1',
                'companyId': self.company.pk, 'rules': [{'ruleCode': 'ISOLATED-FIXED-INPUT-CLASSIFICATION',
                    'ruleName': 'Isolated fixed object quantity', 'version': 'V1', 'specification': spec}]},
            reason='isolated native classification')
        return result['ruleIds']

    def test_01_native_workbook_main_uses_the_same_hash_as_fixed_metadata_reader(self):
        calculation = self.main(); trace = calculation.trace
        reference, objects = trace['baselineReference'], trace['objectInputSnapshot']
        self.assertEqual(calculation.input_hash, calculation_input_hash(reference, objects,
            workbook_source=trace['workbookSource']))
        self.assertNotEqual(calculation.input_hash, calculation_input_hash(reference, objects))
        before = main_fixture.EngineeringCalculationContinuationTests.counts(self)
        with patch('pde.engineering_workbook_source_service.normalize_source_payload', create=True,
                side_effect=AssertionError('saved read must not normalize current input')), \
             patch('pde.engineering_workbook_source_service._read_blob',
                side_effect=AssertionError('saved read must not reopen XLSX')):
            context = _prepare_origin(calculation)
        self.assertEqual(context['baseline'].pk, self.new_baseline_id)
        self.assertEqual(context['inputHash'], calculation.input_hash)
        self.assertEqual(set(context['byItem']), {row['baselineItemId'] for row in objects})
        self.assertEqual(before, main_fixture.EngineeringCalculationContinuationTests.counts(self))

    def test_02_native_legacy_main_preserves_exact_old_hash_and_old_metadata_gate(self):
        calculation = self.main(workbook=False); trace = calculation.trace
        legacy = _hash({'baseline': trace['baselineReference'], 'objects': trace['objectInputSnapshot']})
        self.assertEqual(calculation.input_hash, legacy)
        self.assertEqual(calculation_input_hash(trace['baselineReference'], trace['objectInputSnapshot']), legacy)
        self.assertEqual(saved_workbook_input(calculation, trace['baselineReference'], trace['objectInputSnapshot']), {})
        self.assertEqual(_prepare_origin(calculation)['inputHash'], legacy)
        # A genuinely old input format is not forced to acquire a new audit chain.
        BusinessStateTransition.objects.filter(object_type='EngineeringCalculationRecord',
            object_id=calculation.pk, target_state='completed').delete()
        self.assertEqual(_prepare_origin(calculation)['inputHash'], legacy)

    def test_03_present_null_empty_or_unknown_workbook_contract_cannot_fall_back(self):
        for proof in (None, {}, [], {'contractVersion': 'UNKNOWN-WORKBOOK-V99'}):
            with self.subTest(proof=proof), self.assertRaises(EngineeringCalculationError) as caught:
                calculation_input_hash({'id': 1}, [{'id': 2}], workbook_source=proof)
            self.assertEqual(caught.exception.code, 'CALCULATION_INPUT_CONTRACT_UNPROVEN')

    def test_04_saved_proof_markers_and_exact_contract_are_required(self):
        calculation = self.main(); original = deepcopy(calculation.trace)
        for mutate in (
            lambda trace: trace.update(workbookSource=None),
            lambda trace: trace['workbookSource'].update(contractVersion='UNKNOWN-WORKBOOK-V99'),
            lambda trace: trace.update(workbookSourceRecordId=self.workbook_source.pk + 1000),
            lambda trace: trace['idempotencyPayload'].pop('workbookSource'),
        ):
            with self.subTest(mutation=mutate), transaction.atomic():
                calculation.trace = deepcopy(original); mutate(calculation.trace)
                EngineeringCalculationRecord.objects.filter(pk=calculation.pk).update(trace=calculation.trace)
                self.metadata_rejected(calculation, cause='WORKBOOK_INPUT_COMPLETION_UNPROVEN')
                transaction.set_rollback(True)
        calculation.refresh_from_db()

    def test_05_deleting_proof_and_rehashing_as_legacy_is_rejected_even_without_transition(self):
        calculation = self.main(); state, audit = self.completion(calculation)
        original_trace = deepcopy(calculation.trace)
        for change in ('linked', 'deleted', 'wrong_action'):
            with self.subTest(completion=change), transaction.atomic():
                trace = deepcopy(original_trace)
                trace.pop('workbookSource'); trace.pop('workbookSourceRecordId')
                trace['idempotencyPayload'].pop('workbookSource')
                legacy_hash = calculation_input_hash(trace['baselineReference'], trace['objectInputSnapshot'])
                trace['objectInputSnapshotHash'] = legacy_hash
                EngineeringCalculationRecord.objects.filter(pk=calculation.pk).update(trace=trace, input_hash=legacy_hash)
                if change == 'deleted':
                    BusinessStateTransition.objects.filter(pk=state.pk).delete()
                elif change == 'wrong_action':
                    BusinessStateTransition.objects.filter(pk=state.pk).update(action_code='isolated.wrong.action')
                calculation.refresh_from_db()
                self.metadata_rejected(calculation, cause='WORKBOOK_INPUT_COMPLETION_UNPROVEN')
                self.assertTrue(OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).exists())
                transaction.set_rollback(True)
        calculation.refresh_from_db()

    def test_06_external_registration_changes_do_not_replace_fixed_proof_but_company_stays_bound(self):
        calculation = self.main(); source = self.workbook_source
        other_company = Company.objects.create(code='OTHER-INPUT-CONTRACT', name='Other isolated company')
        mutations = (
            ('source-version', lambda: EngineeringSourceRecord.objects.filter(pk=source.pk).update(source_version='V99')),
            ('source-company', lambda: EngineeringSourceRecord.objects.filter(pk=source.pk).update(company=other_company)),
            ('source-hash', lambda: EngineeringSourceRecord.objects.filter(pk=source.pk).update(content_hash='f' * 64)),
            ('mapping-version', lambda: EngineeringRuleDefinition.objects.filter(pk=self.rule.pk).update(version='V99')),
        )
        for label, mutate in mutations:
            with self.subTest(mutation=label), transaction.atomic():
                mutate()
                if label == 'source-company':
                    self.metadata_rejected(calculation)
                else:
                    self.assertEqual(_prepare_origin(calculation)['inputHash'], calculation.input_hash)
                transaction.set_rollback(True)

    def test_07_fixed_source_mapping_snapshot_and_publication_audit_remain_mandatory(self):
        calculation = self.main(); source = self.workbook_source
        for label in ('source-scope', 'source-quantity', 'source-unit', 'mapping-field', 'mapping-audit'):
            with self.subTest(mutation=label), transaction.atomic():
                if label.startswith('source-'):
                    payload = deepcopy(source.source_payload)
                    if label == 'source-scope':
                        payload['normalization']['sourceScope']['objects'][0]['designItemId'] += 1000
                    elif label == 'source-quantity':
                        payload['normalization']['rows'][0]['canonicalInputs']['J']['value'] = '999'
                    else:
                        payload['normalization']['rows'][0]['canonicalInputs']['Z']['unit'] = 'm2'
                    EngineeringSourceRecord.objects.filter(pk=source.pk).update(source_payload=payload)
                elif label == 'mapping-field':
                    spec = deepcopy(self.rule.specification)
                    spec['sourceFormatMapping']['sheets'][0]['fields'][1]['rawField'] = 'ZZ'
                    EngineeringRuleDefinition.objects.filter(pk=self.rule.pk).update(specification=spec)
                else:
                    state = BusinessStateTransition.objects.filter(object_type='EngineeringRuleDefinition',
                        object_id=self.rule.pk, target_state='released').get()
                    OrganizationOperatingAuditRecord.objects.filter(pk=int(state.audit_reference.split(':')[-1])).update(
                        after_snapshot={'state': {'status': 'released'}})
                if label == 'mapping-audit':
                    self.metadata_rejected(calculation)
                else:
                    # Current import registration is not the historical input.
                    self.assertEqual(_prepare_origin(calculation)['inputHash'], calculation.input_hash)
                    proof = calculation.trace['workbookSource']
                    audit_id = proof['mappingPublication' if label == 'mapping-field' else 'sourceConfirmation']['auditIds'][-1]
                    audit = OrganizationOperatingAuditRecord.objects.get(pk=audit_id)
                    after = deepcopy(audit.after_snapshot)
                    if label == 'mapping-field':
                        after['state']['specification'] = spec
                    else:
                        after['state']['source_payload'] = payload
                    OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).update(after_snapshot=after)
                    self.metadata_rejected(calculation)
                transaction.set_rollback(True)

    def test_08_fixed_objects_baseline_and_quantity_are_not_relaxed(self):
        calculation = self.main(); original = deepcopy(calculation.trace)
        for label in ('quantity', 'unit', 'object', 'baseline', 'object-omitted'):
            with self.subTest(mutation=label), transaction.atomic():
                trace = deepcopy(original)
                if label == 'quantity':
                    trace['objectInputSnapshot'][0]['input']['physicalQuantity'] = '999'
                elif label == 'unit':
                    trace['objectInputSnapshot'][0]['input']['physicalUomId'] += 1000
                elif label == 'object':
                    trace['objectInputSnapshot'][0]['designItemId'] += 1000
                elif label == 'baseline':
                    trace['baselineReference']['snapshotHash'] = '0' * 64
                else:
                    trace['objectInputSnapshot'].pop()
                trace['objectInputSnapshotHash'] = calculation_input_hash(trace['baselineReference'],
                    trace['objectInputSnapshot'], workbook_source=trace['workbookSource'])
                EngineeringCalculationRecord.objects.filter(pk=calculation.pk).update(
                    trace=trace, input_hash=trace['objectInputSnapshotHash'])
                calculation.refresh_from_db(); self.metadata_rejected(calculation)
                transaction.set_rollback(True)
        calculation.refresh_from_db()

    def test_09_fixed_baseline_content_and_header_hash_cannot_be_mutated(self):
        calculation = self.main()
        item = OrderEngineeringBaselineItem.objects.filter(baseline_id=self.new_baseline_id,
            design_item__sales_order_item=self.items[0]).first()
        with transaction.atomic():
            changed = deepcopy(item.content_snapshot); changed['designItem']['physicalQuantity'] = '999'
            OrderEngineeringBaselineItem.objects.filter(pk=item.pk).update(content_snapshot=changed)
            self.metadata_rejected(calculation); transaction.set_rollback(True)
        with transaction.atomic():
            OrderEngineeringBaseline.objects.filter(pk=self.new_baseline_id).update(snapshot_hash='0' * 64)
            self.metadata_rejected(calculation); transaction.set_rollback(True)

    def test_10_future_design_changes_do_not_revoke_saved_history_or_grant_current_execution(self):
        calculation = self.main(); before = _prepare_origin(calculation)
        ProductDesignItem.objects.filter(pk=self.design_items[0].pk).update(version=999)
        ProductDesignRevision.objects.create(design_item=self.design_items[0], revision=99,
            design_nature='FORMAL', design_length=444, design_width=555,
            material=self.material, created_by=self.actor)
        after = _prepare_origin(calculation)
        self.assertEqual(before['inputHash'], after['inputHash'])
        self.assertEqual(set(before['byItem']), set(after['byItem']))
        with self.assertRaises(WorkbookSourceError) as caught:
            resolve_workbook_source(self.workbook_source.pk, company_id=self.company.pk)
        self.assertEqual(caught.exception.code, 'WORKBOOK_OBJECT_SCOPE_MISMATCH')

    def test_11_native_classified_extension_reads_the_original_quantity_and_unit(self):
        calculation = self.main(); rule_ids = self.classified_rule(calculation)
        originals = {fact.pk: fact.value for fact in calculation.derived_facts.all()}
        before = main_fixture.EngineeringCalculationContinuationTests.counts(self)
        preview = EngineeringFactExtensionService.preview(user=self.actor,
            source_calculation_id=calculation.pk, rule_ids=rule_ids)
        self.assertEqual(preview['groupCount'], calculation.derived_facts.count())
        for context in preview['plan']['contexts']:
            self.assertEqual(context['uomId'], self.uom.pk)
            self.assertEqual(Decimal(context['result']['value']), Decimal('2'))
            self.assertEqual(len(context['sources']), 1)
            source = context['sources'][0]['source']
            self.assertEqual(source['value'], originals[source['sourceFactId']])
        self.assertEqual(before, main_fixture.EngineeringCalculationContinuationTests.counts(self))

    def test_12_native_classified_extension_still_rejects_quantity_or_unit_tampering(self):
        calculation = self.main(); rule_ids = self.classified_rule(calculation)
        fact = calculation.derived_facts.select_related('source_detail').first()
        other = UnitOfMeasure.objects.create(company_id=self.company.pk, code='OTHER-COUNT',
            name='Another count unit', dimension='count')
        for label, expected_code in (
            ('fact-only-quantity', 'SOURCE_OUTPUT_DOMAIN_UNPROVEN'),
            ('fact-and-detail-unit', 'FACT_UOM_MISMATCH'),
        ):
            with self.subTest(mutation=label), transaction.atomic():
                if label == 'fact-only-quantity':
                    EngineeringDerivedFact.objects.filter(pk=fact.pk).update(value={'decimal': '999'})
                else:
                    EngineeringDerivedFact.objects.filter(pk=fact.pk).update(uom=other)
                    type(fact.source_detail).objects.filter(pk=fact.source_detail_id).update(uom=other)
                with self.assertRaises(OperationRequirementError) as caught:
                    EngineeringFactExtensionService.preview(user=self.actor,
                        source_calculation_id=calculation.pk, rule_ids=rule_ids)
                self.assertEqual(caught.exception.code, expected_code)
                transaction.set_rollback(True)

    def test_13_native_workbook_classification_commits_proven_inputs_and_replays_without_writes(self):
        from .engineering_fact_extension_service import validate_extension_fact
        from .models import EngineeringFactInput
        from .operation_requirement_service import _digest

        origin = self.main(); rule_ids = self.classified_rule(origin)
        arguments = {'user': self.actor, 'source_calculation_id': origin.pk,
            'rule_ids': rule_ids, 'idempotency_key': 'isolated-workbook-classification-commit',
            'reason': 'isolated native workbook input proof roundtrip'}
        preview = EngineeringFactExtensionService.preview(user=self.actor,
            source_calculation_id=origin.pk, rule_ids=rule_ids)
        result = EngineeringFactExtensionService.derive(**arguments)
        self.assertIs(result['idempotent'], False)
        self.assertGreater(result['businessWriteCount'], 0)
        self.assertGreater(result['auditWriteCount'], 0)

        # Reload every object and call the native validator without a shared
        # read cache; the derive return itself is not the readback authority.
        saved = EngineeringCalculationRecord.objects.get(pk=result['calculationId'])
        facts = list(saved.derived_facts.order_by('sequence', 'pk'))
        self.assertEqual(saved.scope, 'fact_extension')
        self.assertEqual(saved.status, 'completed')
        self.assertEqual(saved.origin_calculation_id, origin.pk)
        self.assertEqual([fact.pk for fact in facts], result['factIds'])
        self.assertEqual(len(facts), preview['groupCount'])
        self.assertEqual(saved.input_hash, preview['plan']['inputHash'])
        self.assertEqual(saved.result_hash, preview['plan']['resultHash'])
        original_values = {fact.pk: fact.value for fact in origin.derived_facts.all()}
        for fact in facts:
            proof = validate_extension_fact(saved, fact)
            self.assertEqual(proof['baseEngineeringCalculationId'], origin.pk)
            self.assertEqual(proof['originInputHash'], origin.input_hash)
            self.assertEqual(proof['originResultHash'], origin.result_hash)
            self.assertEqual(proof['inputHash'], saved.input_hash)
            self.assertEqual(proof['resultHash'], saved.result_hash)
            self.assertEqual(fact.uom_id, self.uom.pk)
            self.assertEqual(Decimal(fact.value['decimal']), Decimal('2'))
            links = list(EngineeringFactInput.objects.filter(fact_id=fact.pk)
                .select_related('source_fact').order_by('sequence', 'pk'))
            self.assertEqual(len(links), 1)
            link = links[0]
            self.assertEqual(link.source_fact.calculation_id, origin.pk)
            self.assertEqual(link.input_snapshot['source']['value'], original_values[link.source_fact_id])
            self.assertEqual(link.source_hash, _digest(link.input_snapshot))
            self.assertEqual(link.input_snapshot['metadataProof']['sourceCalculationId'], origin.pk)

        before = main_fixture.EngineeringCalculationContinuationTests.counts(self)
        input_count = EngineeringFactInput.objects.count()
        replay = EngineeringFactExtensionService.derive(**arguments)
        self.assertIs(replay['idempotent'], True)
        self.assertEqual(replay['calculationId'], saved.pk)
        self.assertEqual(replay['factIds'], result['factIds'])
        self.assertEqual(replay['businessWriteCount'], 0)
        self.assertEqual(replay['auditWriteCount'], 0)
        self.assertEqual(before, main_fixture.EngineeringCalculationContinuationTests.counts(self))
        self.assertEqual(input_count, EngineeringFactInput.objects.count())

    def test_14_legacy_audit_marker_search_is_exact_and_uses_one_existence_statement(self):
        calculation = self.main(workbook=False)
        state, _ = self.completion(calculation)
        BusinessStateTransition.objects.filter(pk=state.pk).delete()
        action = 'production.engineering.calculation.execute'
        self.assertNotEqual(self.calculations[0].pk, calculation.pk)
        for target_type, target_id, action_code in (
            ('EngineeringCalculationRecord', self.calculations[0].pk, action),
            ('EngineeringSourceRecord', self.source.pk, action),
            ('EngineeringCalculationRecord', calculation.pk, 'isolated.unrelated.action'),
        ):
            # Persisted isolated counterexamples, never successful proof stubs.
            OrganizationOperatingAuditRecord.objects.create(organization=self.company, actor=self.actor,
                action_code=action_code, target_type=target_type, target_id=target_id,
                target_label='isolated unrelated workbook marker', reason='isolated audit identity regression',
                before_snapshot={}, after_snapshot={'state': {'trace': {'workbookSource': None}}})
        trace = calculation.trace
        reference, objects = trace['baselineReference'], trace['objectInputSnapshot']
        # One transition lookup plus one audit existence statement; no Python
        # materialization followed by a second, potentially newer SQL snapshot.
        with self.assertNumQueries(2):
            self.assertEqual(saved_workbook_input(calculation, reference, objects), {})
        other = Company.objects.create(code='OTHER-AUDIT-ANCHOR', name='Other isolated audit company')
        OrganizationOperatingAuditRecord.objects.create(organization=other, actor=self.actor,
            action_code=action, target_type='EngineeringCalculationRecord', target_id=calculation.pk,
            target_label='isolated corrupted same-object anchor', reason='isolated anti-downgrade regression',
            before_snapshot={}, after_snapshot={'state': {'trace': {'workbookSourceRecordId': None}}})
        # A malformed same-object anchor cannot disappear through an added
        # company filter or a truthiness check on its null marker value.
        with self.assertRaises(WorkbookSourceError) as caught:
            saved_workbook_input(calculation, reference, objects)
        self.assertEqual(caught.exception.code, 'WORKBOOK_INPUT_COMPLETION_UNPROVEN')
