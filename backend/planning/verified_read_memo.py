"""Reuse identical source verification only inside one SQLite read epoch.

No process/global cache, no persisted eligibility. Mutations, savepoint rollback,
physical connection and outer transaction changes invalidate the proof. Caller
model values are part of the key so an unsaved changed object is never blessed.
"""
from functools import wraps
from copy import deepcopy
from inspect import signature

def verified_source_read(function):
    """Memoize a named read by actor, full arguments and current DB epoch."""
    parameters=signature(function)
    @wraps(function)
    def read(*args,**kwargs):
        from pde.routing_read_context import _current
        from .operation_predecessor_authority import _context,_proof_cache_epoch
        from django.utils import timezone
        bound=parameters.bind(*args,**kwargs);bound.apply_defaults()
        cache,context=_current.get(),_context.get()
        if cache is None or context is None or bound.arguments.get('write'):
            return function(*args,**kwargs)
        epoch=_proof_cache_epoch(context)
        if epoch is None:return function(*args,**kwargs)
        values=tuple((k,(v.pk,v.company_id,v.is_active,v.is_superuser) if k=='user' else repr(v)) for k,v in bound.arguments.items())
        key=('verified_source_read',function.__module__,function.__name__,epoch,timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date(),values)
        if key not in cache:cache[key]=function(*args,**kwargs)
        return deepcopy(cache[key])
    return read

def verified_model_read(function):
    def evaluate(row,args,kwargs,copy_result):
        from pde.routing_read_context import _current
        from .operation_predecessor_authority import _context, _proof_cache_epoch, _historical_proof_only
        cache, context = _current.get(), _context.get()
        if row is None or cache is None or context is None or kwargs or any(not hasattr(x,'_meta') for x in args):
            result=function(row,*args,**kwargs)
            return result if copy_result else None
        epoch = _proof_cache_epoch(context)
        if epoch is None:
            result=function(row,*args,**kwargs)
            return result if copy_result else None
        values = tuple((x._meta.label_lower,tuple((f.attname,repr(getattr(x,f.attname))) for f in x._meta.concrete_fields if f.attname!='password')) for x in (row,*args))
        key = ('verified_model_read', function.__module__, function.__name__, epoch, _historical_proof_only.get(), values)
        if key not in cache:
            cache[key] = function(row,*args)
        return deepcopy(cache[key]) if copy_result else None
    @wraps(function)
    def read(row,*args,**kwargs):return evaluate(row,args,kwargs,True)
    # Callers that only assert integrity must not repeatedly clone the large
    # verified operation/audit model graph. The private cache is never exposed.
    def validate_only(row,*args,**kwargs):return evaluate(row,args,kwargs,False)
    read.validate_only=validate_only
    return read


def verified_http_get_read(function):
    """Identical authority decisions may repeat within one HTTP GET snapshot.

    Commands never use this decorator's memo; every write adjudication keeps
    the original authority call. DB writes/rollback invalidate the read epoch.
    """
    memoized=verified_source_read(function)
    @wraps(function)
    def read(*args,**kwargs):
        from pde.routing_read_context import _current
        cache=_current.get()
        if cache is None or cache.get('__http_get_read__') is not True:
            return function(*args,**kwargs)
        return memoized(*args,**kwargs)
    return read
