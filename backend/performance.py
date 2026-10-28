"""Per-request durations only: no tokens, query strings or business values."""
import contextvars,time
from contextlib import contextmanager

_current=contextvars.ContextVar('request_durations',default=None)

@contextmanager
def measure(name):
 start=time.perf_counter()
 try:yield
 finally:
  values=_current.get()
  if values is not None:values[name]=values.get(name,0)+(time.perf_counter()-start)*1000

@contextmanager
def request_metrics():
 values={};token=_current.set(values)
 try:yield values
 finally:_current.reset(token)
