"""Typed source identity and admission boundary regression tests; no database."""
from copy import deepcopy
from types import SimpleNamespace as N
from unittest.mock import patch
from django.test import SimpleTestCase

from . import baseline_source_identity as identity
from . import formal_engineering_continuation_service as service
from .engineering_calculation_service import EngineeringCalculationError


class BaselineSourceIdentityTests(SimpleTestCase):
    def setUp(self):
        self.snapshot = {"designItem": {"id": 42, "existingDesignData": {
            "provenance": {"sourceType": "USER_ENTRY", "sourceObject": "registered-object"}}},
            "source": {"recordId": 23, "attributeId": 34, "sourceVersion": "V2",
                       "sourceContentHash": "source-digest", "externalSource": "registered-object",
                       "rawSheet": "display label", "rawValue": {"sourceType": "USER_ENTRY"}},
            "revision": {"id": 56, "revision": 3, "designData": {"test": "controlled"}}}
        line = N(pk=12, sales_order_id=11, sales_order=N(company_id=9))
        obj = N(pk=42, company_id=9, sales_order_item=line, source_record_id=23, source_attribute_id=34)
        self.item = N(pk=78, baseline=N(pk=67, company_id=9, sales_order_id=11),
                      design_item=obj, design_item_id=42, source_record=N(pk=23, company_id=9),
                      source_attribute=N(pk=34, sales_order_item_id=12, external_source="registered-object",
                                         raw_value=deepcopy(self.snapshot["source"]["rawValue"])),
                      design_revision_id=56, design_revision_no=3,
                      design_revision=N(pk=56, revision=3, design_item_id=42),
                      source_version_snapshot="V2", source_content_hash_snapshot="source-digest")
        self.refresh()
        self.serializer = self.enterContext(patch(
            'pde.product_version_management_service._content_snapshot',
            return_value={"revision": deepcopy(self.snapshot["revision"])}))

    def refresh(self):
        self.item.content_snapshot = self.snapshot
        self.item.content_hash = identity._hash(self.snapshot)

    def resolve(self): return identity.resolve_baseline_source_identity(self.item)

    def error(self, code):
        with self.assertRaises(EngineeringCalculationError) as caught: self.resolve()
        self.assertEqual(caught.exception.code, code)

    def test_native_repeatable_scoped_identity_without_coordinates(self):
        first = self.resolve()
        self.assertEqual(first, self.resolve())
        self.assertEqual(first['type'], 'NATIVE_DESIGN_REVISION')
        self.assertEqual(first['companyId'], 9)
        self.assertIsNone(first['sourceSheet']); self.assertIsNone(first['sourceRow'])
        self.assertNotIn(self.item.content_hash, first['sourceKey'])

    def test_key_is_content_independent_and_revision_specific(self):
        key = self.resolve()['sourceKey']
        self.snapshot['revision']['designData']['note'] = 'test provenance'
        self.serializer.return_value['revision'] = deepcopy(self.snapshot['revision']); self.refresh()
        self.assertEqual(self.resolve()['sourceKey'], key)
        self.item.design_revision.pk = self.item.design_revision_id = self.snapshot['revision']['id'] = 57
        self.item.design_revision.revision = self.item.design_revision_no = self.snapshot['revision']['revision'] = 4
        self.serializer.return_value['revision'] = deepcopy(self.snapshot['revision']); self.refresh()
        self.assertNotEqual(self.resolve()['sourceKey'], key)

    def test_content_tamper_rejected_before_reference_resolution(self):
        self.snapshot['source']['rawSheet'] = 'tampered'
        self.error('BASELINE_ITEM_CONTENT_HASH_MISMATCH')

    def test_cross_company_and_order_and_attribute_rejected(self):
        for target, field, value in [(self.item.design_item, 'company_id', 8),
                (self.item.source_record, 'company_id', 8),
                (self.item.design_item.sales_order_item, 'sales_order_id', 10),
                (self.item.design_item.sales_order_item.sales_order, 'company_id', 8),
                (self.item.source_attribute, 'sales_order_item_id', 10)]:
            with self.subTest(field=field):
                old=getattr(target, field); setattr(target, field, value)
                self.error('BASELINE_NATIVE_SOURCE_SCOPE_MISMATCH'); setattr(target, field, old)

    def test_wrong_frozen_revision_rejected(self):
        self.snapshot['revision']['id']=99; self.refresh()
        self.error('BASELINE_NATIVE_REVISION_MISMATCH')

    def test_revision_of_another_design_rejected(self):
        self.item.design_revision.design_item_id=99
        self.error('BASELINE_NATIVE_REVISION_MISMATCH')

    def test_missing_revision_explicit(self):
        self.item.design_revision_id=None
        self.error('BASELINE_NATIVE_REVISION_REQUIRED')

    def test_missing_real_registration_and_changed_raw_rejected(self):
        self.snapshot['source']['externalSource']=''; self.refresh()
        self.error('BASELINE_NATIVE_SOURCE_MISMATCH')
        self.snapshot['source']['externalSource']='registered-object'; self.refresh()
        self.item.source_attribute.raw_value={'sourceType': 'USER_ENTRY', 'changed': True}
        self.error('BASELINE_NATIVE_SOURCE_MISMATCH')

    def test_revision_content_mismatch_explicit(self):
        self.serializer.return_value['revision']['designData']['changed']=True
        self.error('BASELINE_NATIVE_REVISION_CONTENT_MISMATCH')

    def test_excel_original_locator_and_missing_row_contract_preserved(self):
        self.snapshot['source']['rawValue']={'sourceType':'EXCEL_IMPORT'}
        provenance=self.snapshot['designItem']['existingDesignData']['provenance']
        provenance.clear(); provenance.update(sourceSheet='real sheet', sourceRow=24)
        self.refresh(); result=self.resolve()
        self.assertEqual(result, {'type':'EXCEL_SOURCE_ROW', 'sourceKey':'real sheet:24',
                                  'sourceSheet':'real sheet','sourceRow':24})
        self.serializer.assert_not_called()
        del provenance['sourceRow']; self.refresh()
        self.error('BASELINE_STABLE_SOURCE_IDENTITY_REQUIRED')

    def test_native_marker_cannot_relabel_an_import(self):
        self.snapshot['source']['rawValue']={'sourceType':'EXCEL_IMPORT'}; self.refresh()
        self.error('BASELINE_NATIVE_SOURCE_MISMATCH')


class CurrentBoundaryTests(SimpleTestCase):
    def test_create_checks_maintain_before_even_existing_instance_read(self):
        with patch.object(service.EngineeringCalculationService, '_authorize',
                          side_effect=EngineeringCalculationError('DENIED', 'denied')) as auth, \
                patch.object(service.SalesOrderItem, 'objects') as query:
            with self.assertRaises(EngineeringCalculationError):
                service.FormalEngineeringContinuationService.create_instance(
                    user=N(company_id=9), sales_order_item_id=12, idempotency_key='test')
            query.select_related.assert_not_called()
            self.assertEqual(auth.call_args.kwargs['action_code'], 'production.engineering.order.maintain')

    def test_validate_denial_precedes_any_context_read(self):
        with patch.object(service.EngineeringCalculationService, '_authorize',
                          side_effect=EngineeringCalculationError('DENIED','denied')), \
                patch.object(service, '_resolve_context') as context:
            with self.assertRaises(EngineeringCalculationError):
                service.FormalEngineeringContinuationService.validate(
                    user=N(company_id=9), sales_order_item_id=12, engineering_instance_id=13, baseline_id=14)
            context.assert_not_called()

    def test_execute_denial_never_enters_atomic_writer(self):
        with patch.object(service.EngineeringCalculationService, '_authorize',
                          side_effect=EngineeringCalculationError('DENIED','denied')), \
                patch.object(service.FormalEngineeringContinuationService, '_execute_atomic') as writer:
            with self.assertRaises(EngineeringCalculationError):
                service.FormalEngineeringContinuationService.execute(user=N(company_id=9))
            writer.assert_not_called()

    def test_native_admission_never_borrows_workbook(self):
        with patch.object(service,'run_batch') as batch:
            result=service._preview_baseline_inputs(['native-key'],
                [{'sourceKey':'native-key','sourceIdentity':{'type':'NATIVE_DESIGN_REVISION'}}],
                {'sourceData':'unrelated workbook'})
            self.assertEqual(result['rows'],[])
            self.assertEqual(result['resultPositionCount'],0)
            self.assertEqual(result['blockers'][0]['code'],'NATIVE_DESIGN_CALCULATION_ADAPTER_REQUIRED')
            batch.assert_not_called()

    def test_import_dispatch_keeps_workbook_and_design_inputs(self):
        inputs=[{'sourceKey':'sheet:2','sourceIdentity':{'type':'EXCEL_SOURCE_ROW'}}]
        workbook={'proof':{'version':'V2'}}
        with patch.object(service,'run_batch',return_value={'rows':[]}) as batch:
            service._preview_baseline_inputs(['sheet:2'],inputs,workbook)
            batch.assert_called_once_with(['sheet:2'],design_inputs=inputs,workbook_source_context=workbook)

    def test_atomic_native_block_happens_before_any_business_write(self):
        # Exercise only the undecorated body against stubs. No transaction,
        # database, calculation or manufacturing action is run by this test.
        inputs=[{'sourceKey':'native-key','sourceIdentity':{'type':'NATIVE_DESIGN_REVISION'}}]
        with patch.object(service,'_resolve_context',return_value=(None,None,None,[],inputs,{})), \
                patch.object(service,'_package_rules',return_value={}), \
                patch.object(service,'_selected_workbook',return_value=None), \
                patch.object(service.EngineeringCalculationRecord,'objects') as records, \
                patch.object(service.CodeRule,'next_code') as numbering:
            fn=service.FormalEngineeringContinuationService._execute_atomic.__func__.__wrapped__
            with self.assertRaises(EngineeringCalculationError) as caught:
                fn(service.FormalEngineeringContinuationService,user=N(company_id=9),
                   sales_order_item_id=12,engineering_instance_id=13,baseline_id=14,
                   decision={},execution_chain={})
            self.assertEqual(caught.exception.code,'NATIVE_DESIGN_CALCULATION_ADAPTER_REQUIRED')
            self.assertEqual(records.mock_calls,[]); numbering.assert_not_called()
