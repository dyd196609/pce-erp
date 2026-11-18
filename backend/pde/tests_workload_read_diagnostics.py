"""SIMULATED_FOR_TEST: existing GET diagnostics must be bounded and secret-free."""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from . import calculation_batch_views as views


class WorkloadReadDiagnosticTests(TestCase):
    def request(self, action='designCalculationContext', **params):
        request = APIRequestFactory().get('/api/pde/a1-engineering/calculations/batch-reuse/',
            {'action': action, 'sourceRecordId': '11', 'unrelated': 'SIM_QUERY_SECRET', **params},
            HTTP_AUTHORIZATION='SIM_AUTH_SECRET', HTTP_COOKIE='SIM_COOKIE_SECRET')
        force_authenticate(request, user=SimpleNamespace(pk=7, company_id=9, is_authenticated=True))
        return request

    def records(self, logs):
        return [json.loads(line.split(' ', 1)[1]) for line in logs.output
            if line.startswith(('INFO:django.server:PCE_BATCH_READ_BEGIN ', 'INFO:django.server:PCE_BATCH_READ_END '))]

    def test_real_select_counts_and_stages_preserve_response_without_parameters(self):
        instances = []
        def original_response(view, request, execute=False):
            instances.append(view)
            with view._read_stage('sourceContext'), connection.cursor() as cursor:
                cursor.execute('SELECT %s', ['SIM_DATABASE_SECRET'])
            with view._read_stage('summary'), connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.execute('SELECT 2')
            return Response({'original': ['unchanged', 3]}, status=200)
        with patch.object(views.EngineeringCalculationBatchView, 'respond', original_response), \
             self.assertLogs('django.server', level='INFO') as logs:
            response = views.EngineeringCalculationBatchView.as_view()(self.request())
        self.assertEqual(response.data, {'original': ['unchanged', 3]})
        begin, end = self.records(logs)
        self.assertEqual(begin['requestId'], end['requestId'])
        self.assertEqual((end['httpStatus'], end['selectCount']), (200, 3))
        self.assertEqual(end['stages']['sourceContext']['selectCount'], 1)
        self.assertEqual(end['stages']['summary']['selectCount'], 2)
        self.assertEqual(end['companyId'], 9)
        self.assertEqual(end['userId'], 7)
        self.assertEqual(len(end['loadedReaderCodeSha256']), 64)
        for secret in ('SIM_AUTH_SECRET', 'SIM_COOKIE_SECRET', 'SIM_QUERY_SECRET', 'SIM_DATABASE_SECRET'):
            self.assertNotIn(secret, '\n'.join(logs.output))
        self.assertFalse(hasattr(instances[0], '_read_diagnostic'))

    def test_original_error_response_and_invalid_scope_are_not_changed(self):
        def original_response(view, request, execute=False):
            return Response({'errorCode': 'SIM_ORIGINAL_DENIAL'}, status=403)
        with patch.object(views.EngineeringCalculationBatchView, 'respond', original_response), \
             self.assertLogs('django.server', level='INFO') as logs:
            response = views.EngineeringCalculationBatchView.as_view()(self.request(sourceRecordId='SIM_SECRET'))
        self.assertEqual((response.status_code, response.data), (403, {'errorCode': 'SIM_ORIGINAL_DENIAL'}))
        _, end = self.records(logs)
        self.assertIsNone(end['sourceRecordId'])
        self.assertEqual(end['httpStatus'], 403)
        self.assertNotIn('SIM_SECRET', '\n'.join(logs.output))

    def test_unhandled_exception_is_not_claimed_as_http200_and_context_is_removed(self):
        instances = []
        def original_response(view, request, execute=False):
            instances.append(view)
            raise RuntimeError('SIM_UNHANDLED')
        with patch.object(views.EngineeringCalculationBatchView, 'respond', original_response), \
             self.assertLogs('django.server', level='INFO') as logs, \
             self.assertRaisesRegex(RuntimeError, 'SIM_UNHANDLED'):
            # Test the original GET handler's finally path directly; the global
            # API exception handler may legitimately convert this to a response.
            view = views.EngineeringCalculationBatchView()
            view.get(view.initialize_request(self.request(action='draftCatalog')))
        _, end = self.records(logs)
        self.assertIsNone(end['httpStatus'])
        self.assertFalse(hasattr(instances[0], '_read_diagnostic'))

    def test_other_get_actions_have_no_diagnostic_side_channel(self):
        with patch.object(views.EngineeringCalculationBatchView, 'respond', return_value=Response({'original': True})), \
             patch.object(views._read_logger, 'info') as logger:
            response = views.EngineeringCalculationBatchView.as_view()(self.request(action='catalog'))
        self.assertEqual(response.data, {'original': True})
        logger.assert_not_called()
