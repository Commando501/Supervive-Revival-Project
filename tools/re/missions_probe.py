# Read-only probe: locate the ProgressionManager's MissionsModel and read its map counts.
#   usage: missions_probe.py <PID>
# Non-disruptive RPM only. This build's UObject layout: Class@+0x18, Name@+0x20, Outer@+0x28.
import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1], 0)
BASE = 0x7FF682A80000
NAMEPOOL = BASE + 0x9D81450

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)

def rpm(a, n):
    b = (ctypes.c_ubyte * n)(); r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)

def u32(b, o): return int.from_bytes(b[o:o+4], "little")
def u64(b, o): return int.from_bytes(b[o:o+8], "little")
def looksptr(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0

_nc = {}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk*8, 8); r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if looksptr(bp):
            hd = rpm(bp + off, 2)
            if hd:
                hd = int.from_bytes(hd, "little"); ln = hd >> 6; wide = hd & 1
                if 0 < ln < 200:
                    s = rpm(bp + off + 2, ln*(2 if wide else 1))
                    if s: r = ("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide
                               else s.decode("latin1", "replace"))
    _nc[idx] = r; return r

def objname(obj):
    if not looksptr(obj): return "<null>"
    nb = rpm(obj + 0x20, 4)
    return fname(u32(nb, 0)) if nb else "?"

def clsname(obj):
    cb = rpm(obj + 0x18, 8)
    if not cb: return "?"
    cls = u64(cb, 0)
    nb = rpm(cls + 0x20, 4)
    return fname(u32(nb, 0)) if nb else "?"

# The two live (non-CDO) MissionsModel instances found by obj_iter.
CANDIDATES = [0x26B135FEF80, 0x26B09558800]
PROGMGR = 0x26A25C07A20

print("== ProgressionManager field scan for MissionsModel ptr ==")
pm = rpm(PROGMGR, 0x400)
for o in range(0x28, 0x400, 8):
    v = u64(pm, o)
    if v in CANDIDATES:
        print(f"  ProgressionManager+0x{o:X} -> MissionsModel 0x{v:X}")

print("\n== Each live MissionsModel: Outer + map Nums ==")
# UE5 TMap = TSet<TPair> ; FScriptSparseArray.Data is a TScriptArray {void* Data; int32 Num; int32 Max}.
# ArrayNum lives at map_base + 0x08. We print candidate map offsets 0x28/0x30/0x80/0xD0 (per prior recon)
# and any 0x08-offset int that looks like a small count next to a heap ptr.
for mm in CANDIDATES:
    outer = u64(rpm(mm + 0x28, 8), 0)
    print(f"\nMissionsModel 0x{mm:X}  Class={clsname(mm)}  Outer=0x{outer:X} ({objname(outer)}/{clsname(outer)})")
    body = rpm(mm, 0x120)
    if not body:
        print("  (unreadable)"); continue
    for o in range(0x28, 0x118, 8):
        data = u64(body, o); num = u32(body, o+8); mx = u32(body, o+0xC)
        if looksptr(data) and 0 <= num <= mx <= 100000 and mx > 0:
            print(f"  +0x{o:X}: Data=0x{data:X} Num={num} Max={mx}   (candidate TArray/TMap)")
