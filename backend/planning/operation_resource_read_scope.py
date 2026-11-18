"""Request-local proof scope; authorization remains in each MES service."""
from functools import wraps
from .test_work_order_service import source_read_scope
def scoped_execution_read(function):
 @wraps(function)
 @source_read_scope
 def run(*args,**kwargs):
  from .operation_predecessor_authority import verification_context
  from .mes_read_indexes import authorization_input_scope
  reader=kwargs.get('user') or (args[0] if args and getattr(args[0],'is_authenticated',False) else None)
  with verification_context(),authorization_input_scope(reader):return function(*args,**kwargs)
 return run
