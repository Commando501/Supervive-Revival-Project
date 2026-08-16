import ctypes, sys
from ctypes import wintypes
PID = int(sys.argv[1], 0); BASE = int(sys.argv[2], 16); MOTD = int(sys.argv[3], 16)
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


def props(cls, limit=800):
    out = []; cur = cls; lvl = 0
    while lp(cur) and lvl < 14:
        f = p(cur+0x58); i = 0
        while lp(f) and i < limit:
            raw = rpm(f, 0x80) or b"\0"*0x80
            out.append((oname(f), ftype(f), i32(raw, 0x44)))
            f = p(f+0x18); i += 1
        cur = p(cur+0x48); lvl += 1
    return out


hdr = rpm(OBJOBJECTS, 0x18); objectsPtr = u64(hdr, 0); numEl = u32(hdr, 0x14)
nch = (numEl+PERCHUNK-1)//PERCHUNK; cp = rpm(objectsPtr, nch*8)
cands = []; cache = {}
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
        if cn == "WBP_UI_MainMenu_NormalMainMenu_C":
            cands.append((o, oname(o)))

print("ALL NormalMainMenu instances:")
for o, n in cands:
    print("   0x%X  %s" % (o, n))
real = [o for o, n in cands if "GEN_VARIABLE" not in n and not n.startswith("Default__")]
if not real:
    print("\nNO real instance (only archetypes) -- a NULL here would be meaningless"); sys.exit(1)

for tgt in real:
    print("\n=== REAL instance 0x%X ===" % tgt)
    ps_off = None
    for nm, ty, off in props(p(tgt+0x18)):
        if nm == "PromptStack":
            ps_off = off; print("  PromptStack prop +0x%X (%s)" % (off, ty)); break
    if ps_off is None:
        print("  no PromptStack property"); continue
    stack = p(tgt+ps_off)
    print("  PromptStack -> 0x%X  class=%s" % (stack, ocls(stack) if lp(stack) else "NULL"))
    if not lp(stack): continue
    scls = p(stack+0x18)
    # ⚠ print EVERY object/array property, INCLUDING nulls and empty arrays. The first pass
    # filtered those out, which meant an EMPTY WidgetList was indistinguishable from "no such
    # property" -- absence-is-not-evidence, in my own probe.
    print("   (all Object/Array properties, nulls and empties INCLUDED)")
    for nm, ty, off in props(scls):
        if ty in ("ObjectProperty", "WeakObjectProperty"):
            q = p(stack+off)
            mark = "   <<< THE MOTD WIDGET" if q == MOTD else ""
            print("   +0x%04X %-18s %-32s = %s%s" % (
                off, ty, nm, ("0x%X (%s)" % (q, ocls(q))) if lp(q) else "NULL", mark))
        elif ty == "ArrayProperty":
            b = rpm(stack+off, 16)
            if not b:
                print("   +0x%04X %-18s %-32s = <unreadable>" % (off, ty, nm)); continue
            d = u64(b, 0); n = i32(b, 8)
            print("   +0x%04X %-18s %-32s Num=%d" % (off, ty, nm, n))
            if 0 < n < 64 and lp(d):
                for k in range(min(n, 8)):
                    e = p(d+k*8)
                    if lp(e):
                        mark = "   <<< THE MOTD WIDGET" if e == MOTD else ""
                        print("        [%d] 0x%X %s (%s)%s" % (k, e, oname(e), ocls(e), mark))
print("\nMOTD widget = 0x%X" % MOTD)
