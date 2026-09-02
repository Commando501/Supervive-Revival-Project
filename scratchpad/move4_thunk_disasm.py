"""Read the live thunk at RVA 0x5294270 and the shim-expected impl at RVA 0x5516610.

Both should be in .text. Print first 96 bytes of each; also print the last 16
bytes preceding each to see if they're padded (function boundary) or fall
inside a larger routine.
"""
import ctypes, struct, sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
psapi = ctypes.WinDLL("psapi")
psapi.EnumProcessModules.restype = wintypes.BOOL
psapi.EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
psapi.GetModuleBaseNameW.restype = wintypes.DWORD
psapi.GetModuleBaseNameW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]

h = k32.OpenProcess(0x0410, False, PID)
if not h:
    print(f"OpenProcess({PID}) failed: {ctypes.get_last_error()}")
    sys.exit(9)

mods = (wintypes.HMODULE * 512)()
needed = wintypes.DWORD(0)
psapi.EnumProcessModules(h, mods, ctypes.sizeof(mods), ctypes.byref(needed))
count = needed.value // ctypes.sizeof(wintypes.HMODULE)
base = None
buf = ctypes.create_unicode_buffer(260)
for i in range(count):
    psapi.GetModuleBaseNameW(h, mods[i], buf, 260)
    if buf.value.lower().startswith("supervive"):
        base = int(mods[i])
        break
print(f"module base = 0x{base:X}")

def rpm(addr, n):
    b = (ctypes.c_ubyte * n)()
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), b, n, ctypes.byref(got)):
        return None
    return bytes(b[:got.value])

for label, rva in [("LIVE thunk (Func @+0xE0 of UFunction)", 0x5294270),
                   ("SHIM-EXPECTED (docs say 'AdjustHealth impl')", 0x5516610)]:
    addr = base + rva
    print(f"\n===== {label} @ RVA 0x{rva:X} (VA 0x{addr:X}) =====")
    pre = rpm(addr - 16, 16)
    body = rpm(addr, 96)
    if pre:
        print("  [-16..0 preceding]:", " ".join(f"{b:02X}" for b in pre))
    if body:
        print("  [0..96 body     ]:", " ".join(f"{b:02X}" for b in body[:48]))
        print("                    ", " ".join(f"{b:02X}" for b in body[48:96]))
