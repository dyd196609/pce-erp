"""Bounded request-local timings; never business facts or proof approvals."""
from contextvars import ContextVar
from functools import wraps
import hashlib
import json
import logging
import threading
from time import perf_counter, time
from uuid import uuid4

from django.db import connection

CONTRACT = 'PCE-OPERATION-READ-DIAGNOSTICS-V1'
_current = ContextVar('pce_operation_read_diagnostic', default=None)
_lock = threading.Lock()
_active = {}
_logger = logging.getLogger('pce.operation_read')


def read_span(name):
    def decorate(function):
        @wraps(function)
        def measured(*args, **kwargs):
            metrics = _current.get()
            if metrics is None:
                return function(*args, **kwargs)
            start = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                span = metrics['spans'].setdefault(name, {'calls': 0, 'ms': 0.0})
                span['calls'] += 1
                span['ms'] += (perf_counter() - start) * 1000
        return measured
    return decorate


def observe_operation_read(function):
    """Measure existing GETs, including simultaneous reads on this process.

    No SQL, parameters, credentials, source snapshots or authorization results
    are exposed. Inclusive spans overlap and must not be added together.
    SQLite does not expose separate lock-wait duration: record only actual SQL
    execution elapsed/max and lock errors, without calling absence zero wait.
    """
    @wraps(function)
    def measured(request, *args, **kwargs):
        if getattr(request, 'method', None) != 'GET':
            return function(request, *args, **kwargs)
        params = request.query_params
        purpose = 'route' if params.get('routeOverview') == '1' else 'detail' if params.get('productionPlanId') else 'catalog'
        metrics = {'contractVersion': CONTRACT, 'diagnosticOnly': True,
            'requestId': uuid4().hex, 'purpose': purpose, 'startedAtEpochMs': time() * 1000,
            'finishedAtEpochMs': None, 'nativeMs': None, 'queryCount': 0,
            'duplicateExactQueryCount': 0, 'sqlMs': 0.0, 'maxSqlMs': 0.0,
            'lockErrorCount': 0, 'concurrentReadsAtEntry': 0, 'maxConcurrentReads': 1, 'spans': {}}
        fingerprints = set()
        start = perf_counter()
        with _lock:
            metrics['concurrentReadsAtEntry'] = len(_active)
            _active[metrics['requestId']] = metrics
            for row in _active.values():
                row['maxConcurrentReads'] = max(row['maxConcurrentReads'], len(_active))
        token = _current.set(metrics)

        def execute(executor, sql, params, many, context):
            query_start = perf_counter()
            metrics['queryCount'] += 1
            digest = hashlib.sha256((sql + repr(params)).encode()).digest()
            if digest in fingerprints:
                metrics['duplicateExactQueryCount'] += 1
            fingerprints.add(digest)
            try:
                return executor(sql, params, many, context)
            except Exception as error:
                if 'locked' in str(error).lower() or 'busy' in str(error).lower():
                    metrics['lockErrorCount'] += 1
                raise
            finally:
                elapsed = (perf_counter() - query_start) * 1000
                metrics['sqlMs'] += elapsed
                metrics['maxSqlMs'] = max(metrics['maxSqlMs'], elapsed)

        try:
            with connection.execute_wrapper(execute):
                response = function(request, *args, **kwargs)
        finally:
            metrics['nativeMs'] = (perf_counter() - start) * 1000
            metrics['finishedAtEpochMs'] = time() * 1000
            with _lock:
                _active.pop(metrics['requestId'], None)
            _current.reset(token)
        # Diagnostic fields never change the service facts or their success.
        if isinstance(getattr(response, 'data', None), dict):
            response.data = {**response.data, 'readDiagnostics': metrics}
        original_render = response.render

        def render():
            render_start = perf_counter()
            rendered = original_render()
            render_ms = (perf_counter() - render_start) * 1000
            size = len(response.content)
            response['Server-Timing'] = ', '.join((
                f'native;dur={metrics["nativeMs"]:.3f}', f'sql;dur={metrics["sqlMs"]:.3f}',
                f'render;dur={render_ms:.3f}', f'responseBytes;dur={size}',
                f'queryCount;dur={metrics["queryCount"]}'))
            _logger.warning('PCE_OPERATION_READ %s', json.dumps({**metrics,
                'renderMs': render_ms, 'responseBytes': size}, separators=(',', ':')))
            return rendered
        response.render = render
        return response
    return measured
