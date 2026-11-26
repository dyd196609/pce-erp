"""Versioned reuse of a successful, completed historical closure for GET only.

SQLite DELETE journal + an acquired read transaction pins the file snapshot.
The digest covers EVERY database byte (including grants and audit records), not
max IDs, timestamps or a guessed revision. WAL/other engines never use it.
Only the source proof is reused; the calling service qualifies today's reader
on every request. Commands always call current_closure without this adapter.
"""
from collections import OrderedDict
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from threading import Lock
from contextvars import ContextVar
from contextlib import contextmanager
from django.db import connection
from django.utils import timezone
from django.conf import settings

_cache=OrderedDict()
_lock=Lock()
_get_scope=ContextVar('completed_closure_http_get',default=None)

@contextmanager
def completed_closure_read_scope():
    connection.ensure_connection()
    token=_get_scope.set((id(connection.connection),getattr(connection.connection,'total_changes',None)))
    try:yield
    finally:_get_scope.reset(token)

def read_completed_closure(order):
    from .finished_goods_authority import current_closure
    frame=_get_scope.get()
    if connection.vendor!='sqlite' or not connection.in_atomic_block or frame is None:
        return current_closure(order)
    if frame!=(id(connection.connection),connection.connection.total_changes):return current_closure(order)
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA journal_mode');mode=cursor.fetchone()[0]
        if mode!='delete':return current_closure(order)
        # Acquire a SHARED read lock before hashing. No DELETE-journal writer
        # can change the main file until this read transaction finishes.
        cursor.execute('SELECT COUNT(*) FROM sqlite_master');cursor.fetchone()
    path=Path(connection.settings_dict['NAME'])
    if not path.is_file():return current_closure(order)
    raw=connection.connection;write_epoch=raw.total_changes
    digest=sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    today=timezone.localdate() if timezone.is_aware(timezone.now()) else timezone.now().date()
    key=(str(path.resolve()),digest.hexdigest(),today.isoformat(),settings.TIME_ZONE,
        tuple((f.attname,repr(getattr(order,f.attname))) for f in order._meta.concrete_fields))
    with _lock:
        found=_cache.get(key)
        if found is not None:
            _cache.move_to_end(key)
            return deepcopy(found)
    result=current_closure(order)
    # Never cache a waiting/invalid result or anything across an observed write.
    if result['ready'] and raw.total_changes==write_epoch:
        with _lock:
            _cache[key]=deepcopy(result)
            while len(_cache)>4:_cache.popitem(last=False)
    return result
