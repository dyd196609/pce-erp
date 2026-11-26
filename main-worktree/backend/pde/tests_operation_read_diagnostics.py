"""SIMULATED_FOR_TEST: diagnostic boundaries only; no real database or HTTP.

The fake connection invokes the actual execute-wrapper callback without opening
a Django connection. Real DRF JSON rendering verifies the emitted byte count.
"""
from contextlib import contextmanager
from copy import deepcopy
import json
import re
import threading
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from . import operation_read_diagnostics as diagnostics


class _NoDatabaseConnection:
    def __init__(self):
        self.local = threading.local()
        self.wrapper_entries = 0

    @contextmanager
    def execute_wrapper(self, callback):
        previous = getattr(self.local, 'callback', None)
        self.wrapper_entries += 1
        self.local.callback = callback
        try:
            yield
        finally:
            self.local.callback = previous

    def execute(self, sql, params, *, error=None):
        def executor(actual_sql, actual_params, many, context):
            if error is not None:
                raise error
            return ('SIMULATED_EXECUTOR_RESULT', actual_sql, actual_params, many)

        callback = getattr(self.local, 'callback', None)
        if callback is None:
            return executor(sql, params, False, {})
        return callback(executor, sql, params, False, {})


def _request(method='GET', **params):
    return SimpleNamespace(method=method, query_params=params)


def _response(value, status=200):
    response = Response(value, status=status)
    response.accepted_renderer = JSONRenderer()
    response.accepted_media_type = 'application/json'
    response.renderer_context = {}
    return response


class OperationReadDiagnosticsTests(SimpleTestCase):
    """SimpleTestCase forbids real database access, including test DB access."""

    def setUp(self):
        self.connection = _NoDatabaseConnection()
        self.connection_patch = patch.object(diagnostics, 'connection', self.connection)
        self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)
        self.assertIsNone(diagnostics._current.get())
        with diagnostics._lock:
            self.assertEqual(diagnostics._active, {})

    def tearDown(self):
        self.assertIsNone(diagnostics._current.get())
        self.assertIsNone(getattr(self.connection.local, 'callback', None))
        with diagnostics._lock:
            self.assertEqual(diagnostics._active, {})

    def test_get_preserves_facts_and_exposes_only_numeric_measurements_and_rendered_size(self):
        facts = {'factSource': 'server', 'passed': False, 'scope': {'productionPlanId': 407},
            'statusLabel': '模拟正式读取事实保留', 'quantity': '78.048000', 'blockers': ['SIMULATED_BLOCKER']}
        original = deepcopy(facts)
        secret_sql = 'SELECT SIMULATED_PRIVATE_COLUMN FROM SIMULATED_PRIVATE_TABLE WHERE key=%s'
        secret_params = ('SIMULATED_SECRET_PARAMETER_NOT_FOR_DIAGNOSTICS',)
        executor_results = []

        @diagnostics.read_span('allocationValidation')
        def read_one():
            executor_results.append(self.connection.execute(secret_sql, secret_params))

        @diagnostics.observe_operation_read
        @diagnostics.read_span('routeAggregate')
        def read(request):
            read_one()
            read_one()
            return _response(facts, status=409)

        with patch.object(diagnostics._logger, 'warning') as logger:
            response = read(_request(routeOverview='1', productionPlanId='407'))
            self.assertEqual(response.status_code, 409, 'Diagnostics cannot change success or status')
            self.assertEqual(facts, original, 'The service-owned facts dictionary is not mutated')
            self.assertEqual({key: value for key, value in response.data.items() if key != 'readDiagnostics'}, original)
            self.assertEqual(executor_results, [('SIMULATED_EXECUTOR_RESULT', secret_sql, secret_params, False)] * 2)
            metrics = response.data['readDiagnostics']
            self.assertEqual(set(metrics), {'contractVersion', 'diagnosticOnly', 'requestId', 'purpose',
                'startedAtEpochMs', 'finishedAtEpochMs', 'nativeMs', 'queryCount', 'duplicateExactQueryCount',
                'sqlMs', 'maxSqlMs', 'lockErrorCount', 'concurrentReadsAtEntry', 'maxConcurrentReads', 'spans'})
            self.assertEqual(metrics['contractVersion'], diagnostics.CONTRACT)
            self.assertIs(metrics['diagnosticOnly'], True)
            self.assertRegex(metrics['requestId'], r'^[0-9a-f]{32}$')
            self.assertEqual(metrics['purpose'], 'route')
            self.assertEqual(metrics['queryCount'], 2)
            self.assertEqual(metrics['duplicateExactQueryCount'], 1)
            self.assertEqual(metrics['lockErrorCount'], 0)
            self.assertEqual(metrics['concurrentReadsAtEntry'], 0)
            self.assertEqual(metrics['maxConcurrentReads'], 1)
            self.assertEqual(set(metrics['spans']), {'routeAggregate', 'allocationValidation'})
            self.assertEqual(metrics['spans']['routeAggregate']['calls'], 1)
            self.assertEqual(metrics['spans']['allocationValidation']['calls'], 2)
            for span in metrics['spans'].values():
                self.assertEqual(set(span), {'calls', 'ms'})
                self.assertGreaterEqual(span['ms'], 0)
            for field in ('startedAtEpochMs', 'finishedAtEpochMs', 'nativeMs', 'sqlMs', 'maxSqlMs'):
                self.assertIsInstance(metrics[field], (int, float))
                self.assertGreaterEqual(metrics[field], 0)
            self.assertGreaterEqual(metrics['finishedAtEpochMs'], metrics['startedAtEpochMs'])
            self.assertNotIn('Server-Timing', response)
            self.assertIs(response.render(), response)
            self.assertEqual(json.loads(response.content)['readDiagnostics'], metrics)
            header = dict(re.findall(r'([A-Za-z]+);dur=([0-9.]+)', response['Server-Timing']))
            self.assertEqual(set(header), {'native', 'sql', 'render', 'responseBytes', 'queryCount'})
            self.assertEqual(int(header['responseBytes']), len(response.content))
            self.assertGreater(len(response.content), len(response.content.decode('utf-8')),
                'The byte count must account for actual UTF-8 Chinese output')
            self.assertEqual(int(header['queryCount']), 2)
            self.assertTrue(all(float(value) >= 0 for value in header.values()))
            logger.assert_called_once()
            logged = json.loads(logger.call_args.args[1])
            self.assertEqual(logged['responseBytes'], len(response.content))
            self.assertGreaterEqual(logged['renderMs'], 0)
            exposed = json.dumps({'metrics': metrics, 'logged': logged, 'header': response['Server-Timing']})
            for private_value in (secret_sql, secret_params[0], 'SIMULATED_PRIVATE_TABLE', 'SIMULATED_PRIVATE_COLUMN'):
                self.assertNotIn(private_value, exposed)

    def test_non_get_requests_do_not_add_diagnostics_wrap_sql_or_change_the_response(self):
        for method in ('POST', 'PATCH', 'HEAD'):
            with self.subTest(method=method):
                response = _response({'factSource': 'server', 'passed': False}, status=403)

                @diagnostics.observe_operation_read
                def read(request):
                    return response

                with patch.object(diagnostics._logger, 'warning') as logger:
                    self.assertIs(read(_request(method=method, routeOverview='1')), response)
                    self.assertEqual(response.data, {'factSource': 'server', 'passed': False})
                    self.assertNotIn('render', response.__dict__)
                    response.render()
                    self.assertNotIn('Server-Timing', response)
                    logger.assert_not_called()
        self.assertEqual(self.connection.wrapper_entries, 0)

    def test_exception_cleans_current_context_and_active_reads_without_swallowing_the_error(self):
        observed = []
        failure = RuntimeError('SIMULATED database is locked')

        @diagnostics.observe_operation_read
        @diagnostics.read_span('budgetRead')
        def broken(request):
            observed.append(diagnostics._current.get())
            self.connection.execute('SELECT SIMULATED_QUERY', ('SIMULATED_PARAMETER',), error=failure)

        with patch.object(diagnostics._logger, 'warning') as logger:
            with self.assertRaises(RuntimeError) as caught:
                broken(_request(productionPlanId='407'))
            self.assertIs(caught.exception, failure)
            logger.assert_not_called()
        self.assertEqual(observed[0]['lockErrorCount'], 1)
        self.assertEqual(observed[0]['spans']['budgetRead']['calls'], 1)
        self.assertIsNotNone(observed[0]['finishedAtEpochMs'])
        self.assertIsNone(diagnostics._current.get())
        self.assertIsNone(getattr(self.connection.local, 'callback', None))
        with diagnostics._lock:
            self.assertEqual(diagnostics._active, {})

        @diagnostics.observe_operation_read
        def next_read(request):
            return _response({'factSource': 'server'})

        response = next_read(_request())
        self.assertEqual(response.data['readDiagnostics']['purpose'], 'catalog')
        self.assertEqual(response.data['readDiagnostics']['concurrentReadsAtEntry'], 0)
        self.assertEqual(response.data['readDiagnostics']['maxConcurrentReads'], 1)
        self.assertEqual(response.data['readDiagnostics']['queryCount'], 0)
        self.assertEqual(response.data['readDiagnostics']['spans'], {})

    def test_concurrent_count_is_process_local_observed_reads_and_ends_before_render(self):
        first_entered = threading.Event()
        release_first = threading.Event()
        responses, failures = [], []

        @diagnostics.observe_operation_read
        def first_read(request):
            first_entered.set()
            if not release_first.wait(timeout=5):
                raise AssertionError('The bounded synthetic concurrent read was not released')
            return _response({'factSource': 'server', 'name': 'SIMULATED_FIRST'})

        def worker():
            try:
                responses.append(first_read(_request(routeOverview='1')))
            except BaseException as error:
                failures.append(error)

        @diagnostics.observe_operation_read
        def second_read(request):
            self.assertEqual(len(diagnostics._active), 2)
            return _response({'factSource': 'server', 'name': 'SIMULATED_SECOND'})

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            self.assertTrue(first_entered.wait(timeout=5))
            self.assertIsNone(diagnostics._current.get(), 'ContextVar does not leak from the other thread')
            second = second_read(_request(productionPlanId='407'))
            self.assertEqual(second.data['readDiagnostics']['purpose'], 'detail')
            self.assertEqual(second.data['readDiagnostics']['concurrentReadsAtEntry'], 1)
            self.assertEqual(second.data['readDiagnostics']['maxConcurrentReads'], 2)
            with diagnostics._lock:
                self.assertEqual(len(diagnostics._active), 1)
        finally:
            release_first.set()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(responses), 1)
        first_metrics = responses[0].data['readDiagnostics']
        self.assertEqual(first_metrics['concurrentReadsAtEntry'], 0)
        self.assertEqual(first_metrics['maxConcurrentReads'], 2)
        with diagnostics._lock:
            self.assertEqual(diagnostics._active, {})
        with patch.object(diagnostics._logger, 'warning') as logger:
            responses[0].render()
            second.render()
            self.assertEqual(logger.call_count, 2)
        with diagnostics._lock:
            self.assertEqual(diagnostics._active, {}, 'Rendering is outside the observed native-read interval')

    def test_span_without_an_observed_get_preserves_returns_and_exceptions(self):
        value = object()

        @diagnostics.read_span('preparationRead')
        def untouched(argument):
            return argument

        self.assertIs(untouched(value), value)
        failure = ValueError('SIMULATED_SPAN_FAILURE')

        @diagnostics.read_span('requirementValidation')
        def broken():
            raise failure

        with self.assertRaises(ValueError) as caught:
            broken()
        self.assertIs(caught.exception, failure)
        self.assertIsNone(diagnostics._current.get())
