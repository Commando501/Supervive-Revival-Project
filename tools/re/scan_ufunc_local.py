# Locate specific UFunction objects of the tile class by scanning a small heap region
# near a KNOWN UFunction of the same class (their allocations cluster). Read-only RPM.
#   usage: scan_ufunc_local.py <PID> <anchorUFuncAddr-hex> <nameId-hex> [nameId-hex ...]
# Prints obj addr + Outer name for each object whose Name==nameId and Class==anchor's Class.
import ctypes, sys
from ctypes import wintypes

PID    = int(sys.argv[1], 0)
ANCHOR = int(sys.argv[2], 16)             # a known UFunction of the target class (e.g. IsPreviewable)
TARGETS= [int(x,16) for x in sys.argv[3:]]
BASE = 0x7FF682A80000
NAMEPOOL = BASE + 0x9D81450
CLASS_OFF, NAME_OFF, OUTER_OFF = 0x18, 0x20, 0x28

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def fname(idx):
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8);
    if not bp: return "?"
    bp=int.from_bytes(bp,"little")
    if not looksptr(bp): return "?"
    hd=rpm(bp+off,2)
    if not hd: return "?"
    hd=int.from_bytes(hd,"little"); ln=hd>>6; wide=hd&1
    if ln<=0 or ln>200: return "?"
    s=rpm(bp+off+2,ln*(2 if wide else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace")

ab = rpm(ANCHOR, 0x30)
funcClass = u64(ab, CLASS_OFF)
print(f"anchor 0x{ANCHOR:X}  Name={fname(u32(ab,NAME_OFF))}  Class=0x{funcClass:X} ({fname(u32(rpm(funcClass,0x28),NAME_OFF))})  Outer={fname(u32(rpm(u64(ab,OUTER_OFF),0x28),NAME_OFF))}")

# scan a window around the anchor (UFunctions of a class cluster within a few pages)
lo = (ANCHOR & ~0xFFFF) - 0x20000
hi = (ANCHOR & ~0xFFFF) + 0x20000
found = {t: [] for t in TARGETS}
a = lo
CHUNK = 0x10000
while a < hi:
    buf = rpm(a, CHUNK)
    if buf:
        for off in range(0, CHUNK-0x30, 8):
            nm = u32(buf, off+NAME_OFF)
            if nm in found:
                cls = u64(buf, off+CLASS_OFF)
                if cls == funcClass:
                    obj = a+off
                    outer = u64(buf, off+OUTER_OFF)
                    on = fname(u32(rpm(outer,0x28),NAME_OFF)) if looksptr(outer) else "?"
                    found[nm].append((obj, on))
    a += CHUNK
for t in TARGETS:
    for obj,on in found[t]:
        print(f"  id=0x{t:X}  obj=0x{obj:X}  slot(+0xE0)=0x{obj+0xE0:X}  Outer={on}")
    if not found[t]:
        print(f"  id=0x{t:X}  NOT FOUND in window")
