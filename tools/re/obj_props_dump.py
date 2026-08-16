import ctypes, sys
from ctypes import wintypes
PID = int(sys.argv[1], 0); BASE = int(sys.argv[2], 16); OBJ = int(sys.argv[3], 16)
NAMEPOOL = BASE + 0x9D81450
k32 = ctypes.WinDLL("kernel32", use_last_error=True); k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)


def rpm(a, n):
    b = (ctypes.c_ubyte*n)(); r = ctypes.c_size_t(0)
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
    blk = i >> 16; off = (i & 0xFFFF) << 1; bp = rpm(NAMEPOOL+blk*8, 8); r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if lp(bp):
            hd = rpm(bp+off, 2)
            if hd:
                hd = int.from_bytes(hd, "little"); ln = hd >> 6; w = hd & 1
                if 0 < ln < 250:
                    s = rpm(bp+off+2, ln*(2 if w else 1))
                    if s:
                        r = ("".join(chr(s[k*2] | (s[k*2+1] << 8)) for k in range(ln)) if w
                             else s.decode("latin1", "replace"))
    _c[i] = r; return r


def oname(o):
    b = rpm(o+0x20, 4); return fname(u32(b, 0)) if b else "?"


def ocls(o):
    c = p(o+0x18); return oname(c) if lp(c) else "?"


def ftype(f):
    fc = p(f+0x08)
    if not lp(fc): return "?"
    b = rpm(fc, 4); return fname(u32(b, 0)) if b else "?"


cls = p(OBJ+0x18)
print(f"object 0x{OBJ:X}  class={oname(cls)}\n")
cur = cls; lvl = 0
hits = []
while lp(cur) and lvl < 16:
    rows = []
    f = p(cur+0x58); i = 0
    while lp(f) and i < 900:
        nm = oname(f); ty = ftype(f)
        raw = rpm(f, 0x80) or b"\0"*0x80
        off = i32(raw, 0x44)
        val = ""
        if ty in ("ObjectProperty", "WeakObjectProperty"):
            q = p(OBJ+off)
            if lp(q):
                kc = ocls(q); val = f"0x{q:X} ({kc})"
                if "Stack" in kc or "Container" in kc or "Activatable" in kc:
                    hits.append((nm, off, q, kc))
            else:
                val = "NULL"
        elif ty == "ArrayProperty":
            b = rpm(OBJ+off, 16)
            val = f"Num={i32(b,8)}" if b else "?"
        if val:
            rows.append((off, ty, nm, val))
        f = p(f+0x18); i += 1
    if rows:
        print(f"=== [{lvl}] {oname(cur)} ({len(rows)} obj/array props) ===")
        for off, ty, nm, val in sorted(rows):
            print(f"   +0x{off:04X} {ty:18} {nm:38} = {val}")
    cur = p(cur+0x48); lvl += 1

print("\n=== CANDIDATE PROMPT CONTAINERS (class name contains Stack/Container/Activatable) ===")
if hits:
    for nm, off, q, kc in hits:
        print(f"   {nm:38} +0x{off:04X} -> 0x{q:X}  ({kc})")
else:
    print("   none found among REFLECTED object properties")
    print("   ⚠ a native (non-UPROPERTY) member would NOT appear here -- absence is not evidence")
