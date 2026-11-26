"""SIMULATED_FOR_TEST: source loading can omit its optional heavy projection.

The view is exercised with explicit synthetic service results. SimpleTestCase
forbids all database access, including accidental business writes.
"""

from contextlib import ExitStack
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import call, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from . import calculation_batch_views as views
from .engineering_calculation_service import EngineeringCalculationError
from .operation_requirement_service import OperationRequirementError


class EngineeringSourceReadLoadingTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(pk=1, company_id=1, is_authenticated=True)
        self.draft = {
            'id': 11, 'sourceVersion': 'SIMULATED_FOR_TEST-V1',
            'rows': [{'id': 'SIM-OBJECT-1', 'quantity': '7'}],
            'currentDesignInputs': [{'designItemId': 6, 'quantity': '7'}],
            'linkedOrders': [{'salesOrderId': 3, 'orderNo': 'SIMULATED_FOR_TEST-ORDER'}],
            'sourceCalculation': {'rows': [{'value': '7'}], 'resultNature': 'SOURCE'},
        }
        self.context = {'draft': self.draft, 'sourceRecordId': 11,
            'resolvedBy': 'SIMULATED_FOR_TEST', 'candidateScope': 'tenant-and-view-permission-scoped'}
        self.summary = {'contractVersion': 'PCE-ENGINEERING-WORKLOAD-SUMMARY-V1',
            'factSource': 'server', 'readStatus': 'loaded', 'readStatusLabel': 'SIMULATED_FOR_TEST loaded',
            'counts': {'formalFactCount': 1}, 'formalSavedFacts': [{'sourceFactId': 9}],
            'businessWriteCount': 0}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.isolation = self.stack.enter_context(patch.object(views.service, 'verify_read_isolation',
            return_value={'verified': True, 'databaseIdentity': 'SIMULATED_FOR_TEST'}))
        self.authorize = self.stack.enter_context(patch.object(views.service, 'authorize_read'))
        self.source = self.stack.enter_context(patch.object(views.service, 'design_calculation_context',
            side_effect=lambda user, source_id: deepcopy(self.context)))
        self.build_summary = self.stack.enter_context(patch.object(views, 'build_engineering_workload_summary',
            side_effect=lambda **kwargs: deepcopy(self.summary)))

    def get(self, include=None, *, action='designCalculationContext', source_id='11', user=None):
        query = {'action': action, 'sourceRecordId': source_id}
        if include is not None:
            query['includeWorkloadSummary'] = include
        request = self.factory.get('/api/pde/a1-engineering/calculations/batch-reuse/', query)
        force_authenticate(request, user=user or self.user)
        return views.EngineeringCalculationBatchView.as_view()(request)

    def assert_original_context_preserved(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['factLoadStatus'], 'loaded')
        for key, value in self.context.items():
            actual = response.data[key]
            if key == 'draft':
                actual = {name: item for name, item in actual.items() if name != 'engineeringWorkloadSummary'}
            self.assertEqual(actual, value)

    def test_default_keeps_complete_summary_and_source_contract(self):
        response = self.get()
        self.assert_original_context_preserved(response)
        summary = response.data['draft']['engineeringWorkloadSummary']
        self.assertEqual(summary['counts'], self.summary['counts'])
        self.assertEqual(summary['formalSavedFacts'], self.summary['formalSavedFacts'])
        self.assertEqual(summary['readStatus'], 'loaded')
        self.assertEqual(summary['factLoadStatus'], 'loaded')
        self.build_summary.assert_called_once()

    def test_explicit_true_keeps_existing_full_summary_behavior(self):
        response = self.get('true')
        self.assert_original_context_preserved(response)
        self.assertEqual(response.data['draft']['engineeringWorkloadSummary']['counts'], self.summary['counts'])
        self.build_summary.assert_called_once()

    def test_explicit_false_reads_source_without_building_or_faking_summary(self):
        response = self.get('false')
        self.assert_original_context_preserved(response)
        self.isolation.assert_called_once_with()
        self.authorize.assert_called_once_with(self.user)
        self.source.assert_called_once_with(self.user, '11')
        self.build_summary.assert_not_called()
        summary = response.data['draft']['engineeringWorkloadSummary']
        self.assertEqual(summary['factSource'], 'server')
        self.assertEqual(summary['readStatus'], 'not_requested')
        self.assertEqual(summary['factLoadStatus'], 'not_requested')
        self.assertEqual(summary['readStatusLabel'], '当前工程数据录入尚未请求工程作业量汇总')
        self.assertEqual(summary['businessWriteCount'], 0)
        self.assertEqual((summary['sourceRecordId'], summary['tenantId']), (11, 1))
        for absent in ('counts', 'rows', 'formalSavedFacts', 'workshopViews', 'resultCount', 'passed'):
            self.assertNotIn(absent, summary)

    def test_false_is_not_a_cross_request_summary_cache(self):
        first = self.get('false')
        second = self.get('true')
        self.assertEqual(first.data['draft']['engineeringWorkloadSummary']['readStatus'], 'not_requested')
        self.assertEqual(second.data['draft']['engineeringWorkloadSummary']['readStatus'], 'loaded')
        self.assertEqual(self.source.call_count, 2)
        self.build_summary.assert_called_once()

    def test_draft_catalog_keeps_full_projection_even_with_false_parameter(self):
        with patch.object(views.service, 'draft_catalog', return_value={'drafts': [deepcopy(self.draft)]}) as catalog:
            response = self.get('false', action='draftCatalog')
        self.assertEqual(response.status_code, 200)
        catalog.assert_called_once_with(self.user, None)
        self.source.assert_not_called()
        self.build_summary.assert_called_once()
        self.assertEqual(response.data['drafts'][0]['engineeringWorkloadSummary']['counts'], self.summary['counts'])

    def test_invalid_parameter_fails_without_reading_or_building_source(self):
        for value in ('', 'False', 'FALSE', '0', '1', 'garbage'):
            with self.subTest(value=value):
                response = self.get(value)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['factLoadStatus'], 'read_failed')
                self.assertEqual(response.data['code'], 'BATCH_SOURCE_READ_FAILED')
                self.assertEqual(response.data['details']['reason'], '工程作业量汇总读取选项无效；仅允许true或false')
        self.assertEqual(self.isolation.call_count, 6)
        self.assertEqual(self.authorize.call_count, 6)
        self.source.assert_not_called()
        self.build_summary.assert_not_called()

    def test_source_failure_with_false_is_preserved_as_failure(self):
        self.source.side_effect = OperationRequirementError('SOURCE_FACT_MISMATCH', 'SIMULATED_FOR_TEST source denied',
            {'sourceRecordId': 11})
        response = self.get('false')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'SOURCE_FACT_MISMATCH')
        self.assertEqual(response.data['details'], {'sourceRecordId': 11})
        self.assertEqual(response.data['factLoadStatus'], 'read_failed')
        self.assertNotIn('draft', response.data)
        self.build_summary.assert_not_called()

    def test_missing_source_with_false_does_not_become_empty_success(self):
        self.source.side_effect = ValueError('DESIGN_CALCULATION_CONTEXT_NOT_FOUND')
        response = self.get('false')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['factLoadStatus'], 'read_failed')
        self.assertEqual(response.data['message'], 'DESIGN_CALCULATION_CONTEXT_NOT_FOUND')
        self.assertNotIn('draft', response.data)
        self.build_summary.assert_not_called()

    def test_permission_denial_remains_a_denial_before_optional_parameter(self):
        self.authorize.side_effect = EngineeringCalculationError('PERMISSION_DENIED', 'SIMULATED_FOR_TEST no view')
        response = self.get('false')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['code'], 'PERMISSION_DENIED')
        self.source.assert_not_called()
        self.build_summary.assert_not_called()

    def test_isolation_failure_remains_fail_closed(self):
        self.isolation.side_effect = EngineeringCalculationError('NON_PRODUCTION_ISOLATION_REQUIRED', 'SIMULATED_FOR_TEST isolation')
        response = self.get('false')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['code'], 'NON_PRODUCTION_ISOLATION_REQUIRED')
        self.authorize.assert_not_called()
        self.source.assert_not_called()
        self.build_summary.assert_not_called()

    def test_each_request_passes_its_current_user_and_source_identity(self):
        other = SimpleNamespace(pk=2, company_id=2, is_authenticated=True)

        def load(user, source_id):
            return {'draft': {'id': int(source_id), 'ownerCompanyId': user.company_id},
                'sourceRecordId': int(source_id)}

        self.source.side_effect = load
        first = self.get('false', source_id='11')
        second = self.get('false', source_id='22', user=other)
        self.assertEqual(self.source.call_args_list, [call(self.user, '11'), call(other, '22')])
        self.assertEqual(self.authorize.call_args_list, [call(self.user), call(other)])
        self.assertEqual((first.data['tenantId'], first.data['draft']['id']), (1, 11))
        self.assertEqual((second.data['tenantId'], second.data['draft']['id']), (2, 22))
        self.assertEqual(second.data['draft']['engineeringWorkloadSummary']['tenantId'], 2)
        self.build_summary.assert_not_called()

    def test_default_summary_failure_still_preserves_source_and_unknown_facts(self):
        self.build_summary.side_effect = OperationRequirementError('SIM_SUMMARY_FAILURE', 'SIMULATED_FOR_TEST summary')
        response = self.get()
        self.assert_original_context_preserved(response)
        summary = response.data['draft']['engineeringWorkloadSummary']
        self.assertEqual(summary['readStatus'], 'read_failed')
        self.assertIsNone(summary['counts']['formalFactCount'])
        self.assertEqual(summary['errorCode'], 'SIM_SUMMARY_FAILURE')
