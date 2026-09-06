# obj_scalars.py -- print every reflected SCALAR property (int/bool/byte/enum/float/name/str) of a
# live UObject. This is the missing half of tools/re/obj_props_dump.py, which prints only
# Object/Array properties -- so state held in an int (a WidgetSwitcher's ActiveWidgetIndex) or an
# enum byte (ESlateVisibility) is invisible to it.
#
# WHY (S122): confirming that a notification badge is SHOWING needs ActiveWidgetIndex / Visibility.
# obj_props_dump.py cannot see either, and the object-property view happens to contain a plausible
# decoy -- `ActiveSequencePlayers = Num=2` on the badge -- which reads like "animations running, so
# it is visible" until you check sibling buttons and find they are 2 as well.
#
#   usage: obj_scalars.py <PID> <BASE-hex> <OBJ-hex> [nameFilter]
import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
OBJ = int(sys.argv[3], 16)
FILT = sys.argv[4].lower() if len(sys.argv) > 4 else None

NAMEPOOL = BASE + 0x9D81450
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed -- run elevated"); sys.exit(1)


def rpm(a, n):
    b = (ctypes.c_ubyte * n)(); r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u32(b, o): return int.from_bytes(b[o:o+4], "little")
def i32(b, o): return int.from_bytes(b[o:o+4], "little", signed=True)
def u64(b, o): return int.from_bytes(b[o:o+8], "little")
def lp(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0
def p(a):
    b = rpm(a, 8); return u64(b, 0) if b else 0


_c = {}
def fname(i):
    if i in _c: return _c[i]
    blk = i >> 16; off = (i & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk*8, 8); r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if lp(bp):
            hd = rpm(bp+off, 2)
            if hd:
                hd = int.from_bytes(hd, "little"); ln = hd >> 6; w = hd & 1
                if 0 < ln < 250:
                    s = rpm(bp+off+2, ln*(2 if w else 1))
                    if s:
                        r = ("".join(chr(s[k*2] | (s[k*2+1] << 8)) for k in range(ln))
                             if w else s.decode("latin1", "replace"))
    _c[i] = r; return r


def oname(o):
    b = rpm(o+0x20, 4); return fname(u32(b, 0)) if b else "?"


def ftype(f):
    fc = p(f+0x08)
    if not lp(fc): return "?"
    b = rpm(fc, 4); return fname(u32(b, 0)) if b else "?"


def fstring(a):
    b = rpm(a, 16)
    if not b: return None
    d = u64(b, 0); n = i32(b, 8)
    if n <= 0 or not lp(d) or n > 4096: return ""
    s = rpm(d, n*2)
    return "".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(n)).rstrip("\x00") if s else None


cls = p(OBJ + 0x18)
print(f"object 0x{OBJ:X}  class={oname(cls)}")

SCALARS = {"IntProperty", "BoolProperty", "ByteProperty", "EnumProperty", "FloatProperty",
           "DoubleProperty", "NameProperty", "StrProperty", "Int64Property", "UInt32Property",
           "Int16Property", "UInt16Property", "Int8Property"}

cur = cls; lvl = 0
while lp(cur) and lvl < 12:
    rows = []
    f = p(cur + 0x58); i = 0
    while lp(f) and i < 2000:
        nm = oname(f); ty = ftype(f)
        raw = rpm(f, 0x80) or b"\0" * 0x80
        off = i32(raw, 0x44)
        if ty in SCALARS and (not FILT or FILT in nm.lower()):
            a = OBJ + off
            v = "?"
            if ty == "BoolProperty":
                byteOff, fieldMask = raw[0x71], raw[0x73]
                bb = rpm(a + byteOff, 1)
                v = bool(bb[0] & fieldMask) if bb else None
            elif ty in ("IntProperty", "UInt32Property"):
                bb = rpm(a, 4); v = i32(bb, 0) if bb else None
            elif ty == "Int64Property":
                bb = rpm(a, 8); v = int.from_bytes(bb, "little", signed=True) if bb else None
            elif ty in ("ByteProperty", "EnumProperty", "Int8Property"):
                bb = rpm(a, 1); v = bb[0] if bb else None
            elif ty in ("Int16Property", "UInt16Property"):
                bb = rpm(a, 2); v = int.from_bytes(bb, "little") if bb else None
            elif ty == "FloatProperty":
                bb = rpm(a, 4)
                v = ctypes.c_float.from_buffer_copy(bb).value if bb else None
            elif ty == "DoubleProperty":
                bb = rpm(a, 8)
                v = ctypes.c_double.from_buffer_copy(bb).value if bb else None
            elif ty == "NameProperty":
                bb = rpm(a, 4); v = fname(u32(bb, 0)) if bb else None
            elif ty == "StrProperty":
                v = fstring(a)
            rows.append((off, ty, nm, v))
        f = p(f + 0x18); i += 1
    if rows:
        print(f"=== [{lvl}] {oname(cur)} ({len(rows)} scalar props) ===")
        for off, ty, nm, v in sorted(rows):
            print(f"   +0x{off:04X} {ty:16} {nm:44} = {v}")
    cur = p(cur + 0x48); lvl += 1
