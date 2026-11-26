"""Optional call-owned raw-input provider; contains no authorization decisions."""
from contextvars import ContextVar
from contextlib import contextmanager
_current=ContextVar('authorization_raw_input_provider',default=None)

def current_inputs():return _current.get()

@contextmanager
def use_inputs(provider):
    token=_current.set(provider)
    try:yield
    finally:_current.reset(token)
