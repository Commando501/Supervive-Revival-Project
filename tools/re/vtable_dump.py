# vtable_dump.py -- dump a live UObject's C++ vtable as RVAs, for offline slot analysis.
# READ-ONLY RPM. No injection, no writes.
#
#   usage: vtable_dump.py <PID|auto> <BASE-hex|auto> <objHex> [nslots] [outFile]
#
# WHY (S111). To read APawn::PossessedBy you need its ADDRESS, and it is a C++ virtual with no
# UFunction, no reflection name, and no RTTI in a shipping build -- so the only handle is the vtable
# slot. The vtable lives in .rdata (100% covered in dumps/tutorial-hero/) but the POINTER to it lives
# in the heap object, and `usmapdump dumpimage` captures the module image only, not the heap. So the
# vtable base has to be read from a live process once; after that the slot analysis is offline.
#
# Pair this with the slot index recovered by disassembling AController::Possess -> PossessInternal,
# which ends in `call qword ptr [rax + 0xNN]` on the pawn -- that 0xNN IS the PossessedBy slot.
#
# Prints every slot as base-relative so the output is directly usable against a dumpimage capture
# (which sets ImageBase to the live base, so file offset == RVA). Slots outside the module are flagged
# rather than dropped: a non-module entry means the read went off the end of the table.
import ctypes, sys
from ctypes import wintypes

PROCNAME = "SUPERVIVE-Win64-Shipping.exe"
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

class PE32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]
class ME32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
                ("szModule", wintypes.WCHAR * 256), ("szExePath", wintypes.WCHAR * 260)]

def autopid():
    s = k32.CreateToolhelp32Snapshot(0x2, 0)
    e = PE32W(); e.dwSize = ctypes.sizeof(PE32W); ok = k32.Process32FirstW(s, ctypes.byref(e)); f = None
    while ok:
        if e.szExeFile == PROCNAME: f = e.th32ProcessID; break
        ok = k32.Process32NextW(s, ctypes.byref(e))
    k32.CloseHandle(s); return f
def autobase(pid):
    s = k32.CreateToolhelp32Snapshot(0x18, pid)
    e = ME32W(); e.dwSize = ctypes.sizeof(ME32W); ok = k32.Module32FirstW(s, ctypes.byref(e)); b = None
    while ok:
        if e.szModule == PROCNAME: b = ctypes.cast(e.modBaseAddr, ctypes.c_void_p).value; break
        ok = k32.Module32NextW(s, ctypes.byref(e))
    k32.CloseHandle(s); return b

a = sys.argv[1:]
PID = autopid() if (not a or a[0] == "auto") else int(a[0], 0)
if not PID: print("game not running"); sys.exit(1)
BASE = autobase(PID) if (len(a) < 2 or a[1] == "auto") else int(a[1], 16)
OBJ = int(a[2], 16)
N = int(a[3]) if len(a) > 3 else 400
OUT = a[4] if len(a) > 4 else None

h = k32.OpenProcess(0x0410, False, PID) or k32.OpenProcess(0x1F0FFF, False, PID)
if not h: print("OpenProcess failed -- run elevated"); sys.exit(2)
g = ctypes.c_size_t(0)
def rd(addr, n):
    b = (ctypes.c_ubyte * n)()
    if not addr or not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), b, n, ctypes.byref(g)) or g.value != n:
        return None
    return bytes(b)

MODSZ = 0x0B000000
vt = rd(OBJ, 8)
if not vt: print("cannot read the object at 0x%X" % OBJ); sys.exit(1)
vt = int.from_bytes(vt, "little")
lines = []
def emit(s):
    print(s); lines.append(s)
emit("object 0x%X   base 0x%X" % (OBJ, BASE))
if not (BASE <= vt < BASE + MODSZ):
    emit("vtable 0x%X is OUTSIDE the module -- not a live UObject (freed? wrong address?)" % vt)
    sys.exit(1)
emit("vtable @0x%X = base+0x%X" % (vt, vt - BASE))
emit("")
emit("slot  off     target            rva")
blob = rd(vt, N * 8)
if blob is None:
    # the table may run into an unreadable page; back off until a read succeeds
    while N > 8:
        N //= 2
        blob = rd(vt, N * 8)
        if blob is not None:
            emit("(only %d slots readable)" % N); break
if blob is None: print("vtable unreadable"); sys.exit(1)
outside = 0
for i in range(N):
    p = int.from_bytes(blob[i*8:i*8+8], "little")
    if BASE <= p < BASE + MODSZ:
        emit("[%3d] +0x%03X  0x%016X  base+0x%X" % (i, i * 8, p, p - BASE))
    else:
        outside += 1
        emit("[%3d] +0x%03X  0x%016X  <-- OUTSIDE MODULE (table probably ends here)" % (i, i * 8, p))
        if outside >= 3: emit("(stopping: 3 consecutive non-module entries)"); break
if OUT:
    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\nwrote %s" % OUT)
