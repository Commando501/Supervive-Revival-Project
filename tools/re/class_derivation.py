import ctypes, sys
from ctypes import wintypes
PID = int(sys.argv[1], 0); BASE = int(sys.argv[2], 16); OBJ = int(sys.argv[3], 16)
WANT = sys.argv[4] if len(sys.argv) > 4 else "PushPrompt"
NAMEPOOL = BASE + 0x9D81450
k32 = ctypes.WinDLL("kernel32", use_last_error=True); k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)


def rpm(a, n):
    b = (ctypes.c_ubyte*n)(); r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u32(b, o): return int.from_bytes(b[o:o+4], "little")
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


cls = p(OBJ+0x18)
print(f"object 0x{OBJ:X}  class = {oname(cls)}")
print("\n=== DERIVATION CHAIN (SuperStruct @+0x48) ===")
chain = []
cur = cls; lvl = 0
while lp(cur) and lvl < 20:
    chain.append(cur)
    print(f"  [{lvl}] 0x{cur:X}  {oname(cur)}")
    cur = p(cur+0x48); lvl += 1

# UStruct::Children (UField*) @ +0x50 ; UField::Next @ +0x28  -> the UFunction list
print(f"\n=== searching every class in the chain for a UFunction named '{WANT}' ===")
found = False
for cl in chain:
    f = p(cl+0x50); i = 0; names = []
    while lp(f) and i < 400:
        names.append(oname(f))
        f = p(f+0x28); i += 1
    hit = [n for n in names if WANT.lower() in n.lower()]
    print(f"  {oname(cl):46} {len(names):4} UFunctions" + (f"   <<< {hit}" if hit else ""))
    if hit: found = True
print(f"\n'{WANT}' reachable via the class chain: {found}")
