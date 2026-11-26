"""One consistent GET, one set of proof reads. Never a cross-request cache."""
from contextvars import ContextVar
from functools import wraps
from time import perf_counter
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


def routing_read_request(function):
    @wraps(function)
    def read(self, request, *args, **kwargs):
        if request.method != 'GET' or _current.get() is not None:
            return function(self, request, *args, **kwargs)
        token = _current.set({})
        start = perf_counter()
        metrics = {'queries': 0, 'sqlMs': 0.0}
        def observe(execute, sql, params, many, context):
            before = perf_counter()
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
            response['Server-Timing'] = f'routing-read;dur={elapsed:.2f}'
            response['X-PCE-Routing-Query-Count'] = str(metrics['queries'])
            logging.getLogger('pce.routing_read').warning(
                'routing_read path=%s status=%s ms=%.2f queries=%s sql_ms=%.2f',
                request.path, response.status_code, elapsed, metrics['queries'], metrics['sqlMs'])
            return response
        finally:
            _current.reset(token)
    return read
