"""One consistent GET, one set of proof reads. Never a cross-request cache."""
from contextvars import ContextVar
from functools import wraps
from os import getpid
from time import perf_counter, thread_time, time
from uuid import uuid4
import json
import logging
from django.db import transaction, connection

_current = ContextVar('pce_routing_read_context', default=None)


def memo_read(namespace, key):
    def decorate(function):
        @wraps(function)
        def read(*args, **kwargs):
            context = _current.get()
            if context is None:
                return function(*args, **kwargs)
            identity = (namespace, key(*args, **kwargs))
            if identity not in context:
                context[identity] = function(*args, **kwargs)
            return context[identity]
        return read
    return decorate


_PHASES = ('taskSource', 'startProof', 'predecessor', 'custody', 'assembly')


class _ReadPhaseProfile:
    def __init__(self):
        self.active = None
        self.phases = {name: [0, 0.0, 0.0] for name in _PHASES}

    def result(self, wall_ms, cpu_ms):
        phase_times = {key: {'calls': count, 'wallMs': round(wall * 1000, 3),
            'cpuMs': round(cpu * 1000, 3)} for key, (count, wall, cpu) in self.phases.items()}
        return {
            'phases': phase_times,
            'unassignedWallMs': round(max(0, wall_ms - sum(p[1] for p in self.phases.values()) * 1000), 3),
            'unassignedCpuMs': round(max(0, cpu_ms - sum(p[2] for p in self.phases.values()) * 1000), 3),
        }


def routing_read_phase(name):
    """Accumulate exclusive time for optional diagnostics of the current GET."""
    def decorate(function):
        @wraps(function)
        def read(*args, **kwargs):
            context = _current.get()
            profile = context.get('__read_phase_profile__') if context is not None else None
            if profile is None:
                return function(*args, **kwargs)
            parent = profile.active
            elapsed_children = [0.0, 0.0]
            profile.active = elapsed_children
            wall_start, cpu_start = perf_counter(), thread_time()
            try:
                return function(*args, **kwargs)
            finally:
                cpu, wall = thread_time() - cpu_start, perf_counter() - wall_start
                profile.active = parent
                if parent is not None:
                    parent[0] += wall
                    parent[1] += cpu
                phase = profile.phases[name]
                phase[0] += 1
                phase[1] += max(0, wall - elapsed_children[0])
                phase[2] += max(0, cpu - elapsed_children[1])
        return read
    return decorate


def routing_read_request(function):
    @wraps(function)
    def read(self, request, *args, **kwargs):
        if request.method != 'GET' or _current.get() is not None:
            return function(self, request, *args, **kwargs)
        context = {'__http_get_read__':True,
            '__reader_id__':getattr(request.user,'pk',None),
            '__reader_company_id__':getattr(request.user,'company_id',None)}
        profile_requested = getattr(self, 'routing_phase_profile_requested', None)
        profile = _ReadPhaseProfile() if profile_requested and profile_requested(request) else None
        if profile is not None:
            context['__read_phase_profile__'] = profile
        started_unix = time() if profile is not None else None
        token = _current.set(context)
        start = perf_counter(); cpu_start = thread_time(); request_id = uuid4().hex
        metrics = {'queries': 0, 'sqlMs': 0.0, 'duplicates': 0}
        exact_queries = set()
        def observe(execute, sql, params, many, context):
            before = perf_counter()
            query_key = (sql, repr(params))
            if query_key in exact_queries: metrics['duplicates'] += 1
            exact_queries.add(query_key)
            try:
                return execute(sql, params, many, context)
            finally:
                metrics['queries'] += 1
                metrics['sqlMs'] += (perf_counter() - before) * 1000
        try:
            # All memoized proofs come from this GET's database snapshot;
            # concurrent changes are revalidated on the next request.
            with transaction.atomic(), connection.execute_wrapper(observe):
                response = function(self, request, *args, **kwargs)
            elapsed = (perf_counter() - start) * 1000
            cpu_ms = (thread_time() - cpu_start) * 1000
            response['Server-Timing'] = f'routing-read;dur={elapsed:.2f}'
            response['X-PCE-Routing-Query-Count'] = str(metrics['queries'])
            response['X-PCE-Read-Id'] = request_id
            response['X-PCE-Read-Thread-CPU-Ms'] = f'{cpu_ms:.2f}'
            response['X-PCE-Read-SQL-Ms'] = f"{metrics['sqlMs']:.2f}"
            logger = logging.getLogger('pce.routing_read')
            if profile is not None:
                logger.warning('pce_handover_read_phases %s', json.dumps({
                    'readId': request_id, 'pid': getpid(), 'startedUnix': started_unix,
                    'path': request.path, 'status': response.status_code, 'wallMs': round(elapsed, 3),
                    'cpuMs': round(cpu_ms, 3), **profile.result(elapsed, cpu_ms),
                }, separators=(',', ':')))
            logger.warning(
                'routing_read path=%s status=%s ms=%.2f queries=%s sql_ms=%.2f cpu_ms=%.2f duplicates=%s read_id=%s',
                request.path, response.status_code, elapsed, metrics['queries'], metrics['sqlMs'],
                cpu_ms, metrics['duplicates'], request_id)
            return response
        finally:
            _current.reset(token)
    return read
