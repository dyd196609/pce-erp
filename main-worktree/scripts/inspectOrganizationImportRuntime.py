"""Bounded, allowlisted service inspection; never inspect browser processes."""
from pathlib import Path

original = Path(__file__).with_name('inspectDo4Runtime.py').read_text(encoding='utf-8')
start = original.index('        env =')
end = original.index('        entries =', start)
replacement = '''        env = ""
        address = pointer(params + 0x80)
        for offset in range(0, 131072, 256):
            env += read(address + offset, 256).decode("utf-16-le", errors="ignore")
            if "\\0\\0" in env:
                break
        if "\\0\\0" not in env:
            raise RuntimeError("Environment terminator not found; inspection incomplete")
'''
original = original[:start] + replacement + original[end:]
original = original.replace('"PYTHONPATH"}', '"PYTHONPATH", "PCE_NON_PRODUCTION_ACCEPTANCE", "PCE_DATABASE_IDENTITY", "PCE_ENVIRONMENT_LABEL"}')
exec(compile(original, 'inspectDo4Runtime.py', 'exec'))
