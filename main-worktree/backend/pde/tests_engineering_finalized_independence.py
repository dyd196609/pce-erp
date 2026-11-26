"""Isolated native finalized consumption, with no formal DB or file admission.

The borrowed fixture substitutes only its synthetic numeric method/reference.
Source publication, main completion, extension persistence and audit/state
proofs are native. No production workbook is read by this test module.
"""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import json
from unittest.mock import patch

from django.db import connection, transaction
from django.test import TestCase
from masterdata.models import UnitOfMeasure
from system.models import Company, OrganizationOperatingAuditRecord, User
from workflow_runtime.models import BusinessStateTransition

from .tests_engineering_calculation_input_contract import EngineeringCalculationInputContractTests as Fixture
from .engineering_fact_extension_service import EngineeringFactExtensionService, validate_extension_fact
from .engineering_fact_metadata import _prepare_origin
from .engineering_workbook_source_service import resolve_workbook_source, WorkbookSourceError
from .formal_engineering_continuation_service import calculation_input_hash
from .models import (EngineeringCalculationRecord, EngineeringDerivedFact, EngineeringFactInput,
    EngineeringRuleDefinition, EngineeringSourceRecord, OrderEngineeringBaselineItem, ProductDesignItem)
from .operation_requirement_service import OperationRequirementError, _digest


class EngineeringFinalizedIndependenceTests(TestCase):
    _adopt = Fixture._adopt
    args = Fixture.args
    numeric_fixture = Fixture.numeric_fixture
    make_blob = Fixture.make_blob
    publish_rule = Fixture.publish_rule
    save_source = Fixture.save_source
    main = Fixture.main
    completion = Fixture.completion
    classified_rule = Fixture.classified_rule

    @classmethod
    def setUpTestData(cls):
        Fixture.setUpTestData.__func__(cls)

    def setUp(self):
        Fixture.setUp(self)

    @contextmanager
    def no_import_or_replay(self):
        with ExitStack() as stack:
            for name in ('_reference', '_adapter_reference_proof', '_blob_path', '_read_blob',
                    '_root', 'validate_workbook_mapping', 'normalize_workbook_payload'):
                stack.enter_context(patch('pde.engineering_workbook_source_service.' + name,
                    side_effect=AssertionError('finalized consumption invoked external/import dependency: ' + name)))
            stack.enter_context(patch('pde.formal_engineering_continuation_service._snapshot_design_input',
                side_effect=AssertionError('finalized consumption replayed importer fields')))
            stack.enter_context(patch('pde.engineering_fact_extension_service._plan',
                side_effect=AssertionError('finalized consumption replayed derivation')))
            stack.enter_context(patch('pde.engineering_fact_extension_service.evaluate_specification',
                side_effect=AssertionError('finalized consumption re-evaluated expression')))
            stack.enter_context(patch('pde.engineering_fact_extension_service.resolve_metadata',
                side_effect=AssertionError('finalized consumption reclassified inputs')))
            yield

    def extension(self, *, workbook=True):
        main = self.main(workbook=workbook)
        result = EngineeringFactExtensionService.derive(user=self.actor,
            source_calculation_id=main.pk, rule_ids=self.classified_rule(main),
            idempotency_key='isolated-finalized-extension', reason='isolated finalized read contract')
        origin = EngineeringCalculationRecord.objects.get(pk=result['calculationId'])
        return main, origin, origin.derived_facts.order_by('sequence').first()

    def assert_rejected(self, call):
        with self.assertRaises(OperationRequirementError):
            call()

    def test_01_completed_workbook_ignores_file_storage_adapter_and_current_mapping_metadata(self):
        main = self.main(); before = _prepare_origin(main)
        EngineeringSourceRecord.objects.filter(pk=self.workbook_source.pk).update(
            source_version='EXTERNAL-MOVED', content_hash='f' * 64,
            source_payload={'rawContent': {'storageKey': 'removed.xlsx'}, 'externalFormat': 'CHANGED'})
        EngineeringRuleDefinition.objects.filter(pk=self.rule.pk).update(
            version='EXTERNAL-VERSION-CHANGED', specification={'externalFormat': 'CHANGED'})
        with self.no_import_or_replay():
            after = _prepare_origin(EngineeringCalculationRecord.objects.get(pk=main.pk))
        self.assertEqual(after['inputHash'], before['inputHash'])
        self.assertEqual(set(after['byItem']), set(before['byItem']))

    def test_02_internal_object_source_version_remains_a_business_consistency_gate(self):
        main = self.main()
        EngineeringSourceRecord.objects.filter(pk=main.source_record_id).update(
            source_version='EXTERNAL-V99', content_hash='e' * 64, source_payload={'externalPath': 'unavailable'})
        with self.no_import_or_replay():
            self.assert_rejected(lambda: _prepare_origin(EngineeringCalculationRecord.objects.get(pk=main.pk)))

    def test_03_new_source_resolution_keeps_current_file_and_mapping_admission(self):
        main = self.main()
        with patch('pde.engineering_workbook_source_service._read_blob',
                side_effect=WorkbookSourceError('WORKBOOK_BLOB_MISSING', 'isolated missing workbook')):
            with self.assertRaises(WorkbookSourceError):
                resolve_workbook_source(self.workbook_source.pk, company_id=self.company.pk)
        with self.no_import_or_replay():
            self.assertEqual(_prepare_origin(main)['inputHash'], main.input_hash)

    def test_04_saved_extension_uses_frozen_plan_and_returns_identical_original_proof(self):
        main, origin, fact = self.extension()
        before = validate_extension_fact(origin, fact)
        EngineeringSourceRecord.objects.filter(pk=self.workbook_source.pk).update(
            source_version='EXTERNAL-V99', content_hash='e' * 64)
        with self.no_import_or_replay():
            after = validate_extension_fact(EngineeringCalculationRecord.objects.get(pk=origin.pk),
                EngineeringDerivedFact.objects.get(pk=fact.pk))
        self.assertEqual(before, after)
        self.assertEqual(set(before), {'contractVersion', 'baseEngineeringCalculationId',
            'originInputHash', 'originResultHash', 'inputHash',
            'resultHash', 'sourceRecordId', 'sourceRecordVersion'})

    def test_05_legacy_main_keeps_its_original_hash_without_a_workbook_contract(self):
        main, origin, fact = self.extension(workbook=False)
        trace = main.trace
        self.assertEqual(main.input_hash, calculation_input_hash(trace['baselineReference'], trace['objectInputSnapshot']))
        before = validate_extension_fact(origin, fact)
        with self.no_import_or_replay():
            self.assertEqual(validate_extension_fact(origin, fact), before)

    def test_06_publication_audit_scope_unit_or_object_corruption_is_still_rejected(self):
        main = self.main()
        proof = main.trace['workbookSource']
        for label in ('company', 'source-object', 'source-unit', 'mapping-proof', 'authorization'):
            with self.subTest(mutation=label), transaction.atomic():
                if label == 'company':
                    other = Company.objects.create(code='OTHER-FINALIZED', name='Other isolated company')
                    EngineeringSourceRecord.objects.filter(pk=self.workbook_source.pk).update(company_id=other.pk)
                else:
                    audit_id = proof['mappingPublication' if label == 'mapping-proof' else 'sourceConfirmation']['auditIds'][-1]
                    audit = OrganizationOperatingAuditRecord.objects.get(pk=audit_id)
                    after = deepcopy(audit.after_snapshot)
                    if label == 'source-object':
                        after['state']['source_payload']['normalization']['sourceScope']['objects'][0]['designItemId'] += 1000
                    elif label == 'source-unit':
                        after['state']['source_payload']['normalization']['rows'][0]['canonicalInputs']['Z']['unit'] = 'm2'
                    elif label == 'mapping-proof':
                        after['state']['specification']['sourceFormatMapping']['sheets'][0]['fields'][0]['rawField'] = 'ZZ'
                    else:
                        after['authorization']['allowed'] = False
                    OrganizationOperatingAuditRecord.objects.filter(pk=audit_id).update(after_snapshot=after)
                self.assert_rejected(lambda: _prepare_origin(main))
                transaction.set_rollback(True)

    def test_07_proof_removal_cannot_downgrade_a_native_workbook_main_to_legacy(self):
        main = self.main(); state, _ = self.completion(main)
        trace = deepcopy(main.trace)
        trace.pop('workbookSource'); trace.pop('workbookSourceRecordId'); trace['idempotencyPayload'].pop('workbookSource')
        legacy = calculation_input_hash(trace['baselineReference'], trace['objectInputSnapshot'])
        trace['objectInputSnapshotHash'] = legacy
        EngineeringCalculationRecord.objects.filter(pk=main.pk).update(trace=trace, input_hash=legacy)
        BusinessStateTransition.objects.filter(pk=state.pk).delete()
        self.assert_rejected(lambda: _prepare_origin(EngineeringCalculationRecord.objects.get(pk=main.pk)))

    def test_08_internal_baseline_quantity_and_linked_object_are_not_external_metadata(self):
        main = self.main()
        item = OrderEngineeringBaselineItem.objects.filter(baseline_id=self.new_baseline_id,
            design_item__sales_order_item=self.items[0]).first()
        for label in ('quantity', 'object', 'hash'):
            with self.subTest(mutation=label), transaction.atomic():
                values = {}
                if label == 'quantity':
                    snapshot = deepcopy(item.content_snapshot); snapshot['designItem']['physicalQuantity'] = '999'
                    values['content_snapshot'] = snapshot
                elif label == 'object':
                    values['source_attribute_id'] = self.design_items[1].source_attribute_id
                else:
                    values['content_hash'] = '0' * 64
                OrderEngineeringBaselineItem.objects.filter(pk=item.pk).update(**values)
                self.assert_rejected(lambda: _prepare_origin(main)); transaction.set_rollback(True)

    def test_09_current_design_changes_leave_fixed_history_intact(self):
        main, origin, fact = self.extension()
        before = validate_extension_fact(origin, fact)
        ProductDesignItem.objects.filter(pk=self.design_items[0].pk).update(version=999)
        with self.no_import_or_replay():
            self.assertEqual(validate_extension_fact(origin, fact), before)

    def test_10_saved_fact_detail_input_link_and_upstream_values_remain_guarded(self):
        main, origin, fact = self.extension()
        link = EngineeringFactInput.objects.filter(fact=fact).first()
        for label in ('fact', 'detail', 'link-hash', 'link-snapshot', 'upstream'):
            with self.subTest(mutation=label), transaction.atomic():
                if label == 'fact':
                    EngineeringDerivedFact.objects.filter(pk=fact.pk).update(value={'decimal': '999'})
                elif label == 'detail':
                    type(fact.source_detail).objects.filter(pk=fact.source_detail_id).update(output_value={'decimal': '999'})
                elif label == 'link-hash':
                    table = connection.ops.quote_name(EngineeringFactInput._meta.db_table)
                    with connection.cursor() as cursor:
                        cursor.execute(f'UPDATE {table} SET source_hash = %s WHERE id = %s', ['0' * 64, link.pk])
                elif label == 'link-snapshot':
                    changed = deepcopy(link.input_snapshot); changed['normalizedValue'] = '999'
                    table = connection.ops.quote_name(EngineeringFactInput._meta.db_table)
                    with connection.cursor() as cursor:
                        cursor.execute(f'UPDATE {table} SET input_snapshot = %s, source_hash = %s WHERE id = %s',
                            [json.dumps(changed), _digest(changed), link.pk])
                else:
                    EngineeringDerivedFact.objects.filter(pk=link.source_fact_id).update(value={'decimal': '999'})
                self.assert_rejected(lambda: validate_extension_fact(origin, EngineeringDerivedFact.objects.get(pk=fact.pk)))
                transaction.set_rollback(True)

    def test_11_extension_audit_authorization_and_state_remain_required(self):
        _, origin, fact = self.extension()
        state = BusinessStateTransition.objects.get(object_type='EngineeringCalculationRecord',
            object_id=origin.pk, target_state='completed')
        audit_id = int(state.audit_reference.split(':')[-1])
        for label in ('authorization', 'chain', 'transition'):
            with self.subTest(mutation=label), transaction.atomic():
                if label == 'transition':
                    BusinessStateTransition.objects.filter(pk=state.pk).delete()
                else:
                    audit = OrganizationOperatingAuditRecord.objects.get(pk=audit_id)
                    after = deepcopy(audit.after_snapshot)
                    if label == 'authorization':
                        after['authorization']['allowed'] = False
                    else:
                        after['executionChain']['account'] = 'different-actor'
                    OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).update(after_snapshot=after)
                self.assert_rejected(lambda: validate_extension_fact(origin, fact)); transaction.set_rollback(True)

    def test_12_new_derivation_and_permissions_do_not_use_saved_consumer_bypass(self):
        main = self.main(); rule_ids = self.classified_rule(main)
        denied = User.objects.create_user(username='isolated-finalized-denied', company_id=self.company.pk)
        self.assert_rejected(lambda: EngineeringFactExtensionService.preview(user=denied,
            source_calculation_id=main.pk, rule_ids=rule_ids))
        with patch('pde.engineering_fact_extension_service._plan',
                side_effect=OperationRequirementError('ISOLATED_CURRENT_INPUT_REJECTED', 'isolated strict new derivation')):
            with self.assertRaises(OperationRequirementError) as caught:
                EngineeringFactExtensionService.preview(user=self.actor, source_calculation_id=main.pk, rule_ids=rule_ids)
            self.assertEqual(caught.exception.code, 'ISOLATED_CURRENT_INPUT_REJECTED')
