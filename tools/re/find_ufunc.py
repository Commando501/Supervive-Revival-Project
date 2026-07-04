import ctypes, sys
from ctypes import wintypes

PID  = int(sys.argv[1]) if len(sys.argv) > 1 else 62212
NAME = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0x777E46   # FName index of the function name
BASE = 0x7FF682A80000
NAMEPOOL = BASE + 0x9D81450
CLASS_OFF = 0x18
NAME_OFF  = 0x20
OUTER_OFF = 0x28

# findptr hits (Name-field locations) — pass as remaining args (hex), else use the IsPreviewable set.
HITS = [int(x,16) for x in sys.argv[3:]] or [
 0x26BDCB52CA0,0x26BEADC5B18,0x26C42E5C1A8,0x26C81467708,0x26C81758008,
 0x26C83313A60,0x26C833E0238,0x26CF455F310,0x26CFB2097D0,0x26D001D4620,0x26D001D4D20,0x26D001D6F20,
]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h: print("OpenProcess failed", ctypes.get_last_error()); sys.exit(1)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def fname(idx):
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8)
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

for hitAddr in HITS:
    obj = hitAddr - NAME_OFF
    o = rpm(obj, 0x40)
    if not o:
        print(f"  hit 0x{hitAddr:X}: obj unreadable"); continue
    nm = u32(o, NAME_OFF)
    if nm != NAME:
        # maybe this hit isn't a UObject Name; skip
        continue
    cls = u64(o, CLASS_OFF); outer = u64(o, OUTER_OFF)
    clsName = outerName = "?"
    if looksptr(cls):
        cb = rpm(cls, 0x28)
        if cb: clsName = fname(u32(cb, NAME_OFF))
    if looksptr(outer):
        ob = rpm(outer, 0x28)
        if ob: outerName = fname(u32(ob, NAME_OFF))
    print(f"  obj=0x{obj:X}  Name=IsPreviewable  Class={clsName}  Outer={outerName}")
