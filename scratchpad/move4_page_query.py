"""VirtualQueryEx both RVAs to see if the shim-expected address is decrypted."""
import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
psapi = ctypes.WinDLL("psapi")
psapi.EnumProcessModules.restype = wintypes.BOOL
psapi.EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
psapi.GetModuleBaseNameW.restype = wintypes.DWORD
psapi.GetModuleBaseNameW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p),
                ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD),
                ("__pad1", wintypes.DWORD),
                ("RegionSize", ctypes.c_size_t),
                ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("__pad2", wintypes.DWORD)]

PROT = {0x01: "NOACCESS", 0x02: "R", 0x04: "RW", 0x08: "WCOPY", 0x10: "X", 0x20: "RX",
        0x40: "RWX", 0x80: "XWCOPY", 0x100: "GUARD"}

h = k32.OpenProcess(0x0410, False, PID)
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

for label, rva in [("LIVE thunk", 0x5294270), ("SHIM-EXPECTED", 0x5516610),
                   ("nearby-page-boundary", 0x5516000), ("baseline-known-decrypted-in-r3", 0x0F7EC20)]:
    addr = base + rva
    mbi = MEMORY_BASIC_INFORMATION()
    got = k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
    if got == 0:
        print(f"  {label} @ 0x{addr:X}: VirtualQueryEx FAILED")
        continue
    state = "COMMIT" if mbi.State == 0x1000 else ("RESERVE" if mbi.State == 0x2000 else f"0x{mbi.State:X}")
    prot_str = " | ".join(name for bit, name in PROT.items() if mbi.Protect & bit) or f"0x{mbi.Protect:X}"
    print(f"  {label:35s} @ 0x{addr:X} RVA=0x{rva:X}: {state} {prot_str} region 0x{mbi.RegionSize:X}")
