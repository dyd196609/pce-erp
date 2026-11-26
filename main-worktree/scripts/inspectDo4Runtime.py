"""Read-only, allowlisted Windows process runtime settings (never output secrets)."""
import ctypes as c
import json
import struct
import sys

k = c.WinDLL("kernel32", use_last_error=True)
n = c.WinDLL("ntdll")
k.OpenProcess.argtypes = [c.c_ulong, c.c_int, c.c_ulong]
k.OpenProcess.restype = c.c_void_p
k.ReadProcessMemory.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
k.CloseHandle.argtypes = [c.c_void_p]
n.NtQueryInformationProcess.argtypes = [c.c_void_p, c.c_ulong, c.c_void_p, c.c_ulong, c.c_void_p]


def inspect(pid):
    handle = k.OpenProcess(0x0410, False, pid)
    if not handle:
        raise OSError(c.get_last_error(), "OpenProcess read access failed")
    def read(address, length):
        buffer = c.create_string_buffer(length)
        count = c.c_size_t()
        k.ReadProcessMemory(handle, address, buffer, length, c.byref(count))
        if not count.value:
            raise OSError(c.get_last_error(), "ReadProcessMemory failed")
        return buffer.raw[:count.value]
    def pointer(address):
        return struct.unpack("<Q", read(address, 8))[0]
    def unicode(address):
        data = read(address, 16)
        length = struct.unpack_from("<H", data)[0]
        target = struct.unpack_from("<Q", data, 8)[0]
        return read(target, length).decode("utf-16-le") if length else ""
    try:
        info = c.create_string_buffer(48)
        result = n.NtQueryInformationProcess(handle, 0, info, 48, None)
        if result != 0:
            raise OSError(result, "NtQueryInformationProcess failed")
        peb = struct.unpack_from("<Q", info.raw, 8)[0]
        params = pointer(peb + 0x20)
        env = read(pointer(params + 0x80), 65536).decode("utf-16-le", errors="ignore")
        entries = env.split("\0\0", 1)[0].split("\0")
        allowed = {"PCE_DATABASE_PATH", "PCE_API_PROXY_TARGET", "DJANGO_SETTINGS_MODULE", "PYTHONPATH"}
        values = {}
        for entry in entries:
            key, _, value = entry.partition("=")
            if key in allowed:
                values[key] = value
        return {"pid": pid, "cwd": unicode(params + 0x38), "imagePath": unicode(params + 0x60),
                "commandLine": unicode(params + 0x70), "allowlistedEnvironment": values}
    finally:
        k.CloseHandle(handle)


print(json.dumps([inspect(int(pid)) for pid in sys.argv[1:]], ensure_ascii=False, indent=2))
