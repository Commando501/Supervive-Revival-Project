import ctypes, sys
from ctypes import wintypes
PID = int(sys.argv[1], 0); BASE = int(sys.argv[2], 16)
NAMEPOOL = BASE + 0x9D81450; OBJOBJECTS = BASE + 0x9E38930; PERCHUNK = 65536; STRIDE = 0x18
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


def findprop(cls, want):
    cur = cls; lvl = 0
    while lp(cur) and lvl < 14:
        f = p(cur+0x58); i = 0
        while lp(f) and i < 800:
            if oname(f) == want:
                raw = rpm(f, 0x80); return i32(raw, 0x44), ftype(f)
            f = p(f+0x18); i += 1
        cur = p(cur+0x48); lvl += 1
    return None, None


hdr = rpm(OBJOBJECTS, 0x18); objectsPtr = u64(hdr, 0); numEl = u32(hdr, 0x14)
nch = (numEl+PERCHUNK-1)//PERCHUNK; cp = rpm(objectsPtr, nch*8)
by = {}
cache = {}
for ci in range(nch):
    ch = int.from_bytes(cp[ci*8:ci*8+8], "little")
    if not lp(ch): continue
    cnt = min(PERCHUNK, numEl-ci*PERCHUNK); items = rpm(ch, cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        o = u64(items, j*STRIDE)
        if not lp(o): continue
        c = p(o+0x18)
        if not lp(c): continue
        cn = cache.get(c)
        if cn is None: cn = oname(c); cache[c] = cn
        if cn in ("Comp_MainMenu_Onboarding_C", "WBP_UI_MainMenu_MenuRootV2_C",
                  "WBP_UI_MainMenu_NormalMainMenu_C"):
            by.setdefault(cn, []).append(o)

for cn in ("Comp_MainMenu_Onboarding_C", "WBP_UI_MainMenu_MenuRootV2_C",
           "WBP_UI_MainMenu_NormalMainMenu_C"):
    print(f"{cn}: {len(by.get(cn,[]))} instance(s)")
    for o in by.get(cn, []):
        print(f"   0x{o:X}  {oname(o)}")
print()

# 1) Onboarding -> Main Menu Widget (a TScriptInterface: {ObjectPtr, InterfacePtr})
for o in by.get("Comp_MainMenu_Onboarding_C", []):
    off, ty = findprop(p(o+0x18), "Main Menu Widget")
    if off is None:
        print(f"onboarding 0x{o:X}: no 'Main Menu Widget' property"); continue
    tgt = p(o+off)
    print(f"onboarding 0x{o:X} ({oname(o)})  MainMenuWidget(+0x{off:X},{ty}) -> "
          f"{'0x%X (%s : %s)' % (tgt, oname(tgt), ocls(tgt)) if lp(tgt) else 'NULL'}")
print()

# 2) MenuRootV2 -> MainMenu_NormalV2 -> PromptStack
for o in by.get("WBP_UI_MainMenu_MenuRootV2_C", []):
    off, ty = findprop(p(o+0x18), "MainMenu_NormalV2")
    if off is None:
        print(f"menuroot 0x{o:X}: no MainMenu_NormalV2 property"); continue
    nv = p(o+off)
    line = f"menuroot 0x{o:X} ({oname(o)})  MainMenu_NormalV2(+0x{off:X}) -> "
    if not lp(nv):
        print(line + "NULL"); continue
    poff, _ = findprop(p(nv+0x18), "PromptStack")
    ps = p(nv+poff) if poff is not None else 0
    print(line + f"0x{nv:X}   its PromptStack -> " +
          (f"0x{ps:X} ({ocls(ps)})  ** VALID **" if lp(ps) else "NULL  ** DEAD END **"))
