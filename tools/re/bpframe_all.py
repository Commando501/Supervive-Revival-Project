# bpframe_all.py -- like tools/re/bpframe_readout.py, but enumerates EVERY instance of the class
# instead of stopping at the first non-archetype one, and prints each instance's HAS-RUN control.
#
# WHY (S122): bpframe_readout.py stops at the first object whose name is not `Default__*` and does
# not contain `GEN_VARIABLE`. For WBP_UI_MainMenu_NormalMainMenu that picked an instance whose
# frame is entirely default (non-default-locals = 0 out of 219) on a menu that had been live for
# 74 minutes -- i.e. it found a template, not the running widget, and the answer it printed was
# `never evaluated` dressed as a measurement.
#
# This is a FOURTH member of the class-lookup blind-spot family CLAUDE.md records
# (obj_by_class.py = substring, cheat_reach_probe.py = endswith, class_props.py = class-of-class).
# The shared defect is "take the first match"; the shared fix is "enumerate and show your work".
#
#   usage: bpframe_all.py <PID> <BASE-hex> <ClassNameSubstr> [propNameFilter]
import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
CLSSUB = sys.argv[3]
FILT = sys.argv[4].lower() if len(sys.argv) > 4 else None

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK = 65536
STRIDE = 0x18

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


_nc = {}
def fname(i):
    if i in _nc: return _nc[i]
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
    _nc[i] = r; return r


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


def props_of(struct_ptr, limit=1200):
    out = []; cur = struct_ptr; lvl = 0
    while lp(cur) and lvl < 12:
        f = p(cur+0x58); i = 0
        while lp(f) and i < limit:
            nm = oname(f); ty = ftype(f)
            raw = rpm(f, 0x80) or b"\0"*0x80
            off = i32(raw, 0x44)
            bi = (raw[0x70], raw[0x71], raw[0x72], raw[0x73]) if ty == "BoolProperty" else None
            out.append((nm, ty, off, bi))
            f = p(f+0x18); i += 1
        cur = p(cur+0x48); lvl += 1
    return out


# ---- sweep once, collect EVERY instance + the ubergraph UFunction ----
hdr = rpm(OBJOBJECTS, 0x18)
objectsPtr = u64(hdr, 0); numEl = u32(hdr, 0x14)
nch = (numEl + PERCHUNK - 1)//PERCHUNK
cp = rpm(objectsPtr, nch*8)

insts = []; ufunc = 0; cache = {}
for ci in range(nch):
    ch = int.from_bytes(cp[ci*8:ci*8+8], "little")
    if not lp(ch): continue
    cnt = min(PERCHUNK, numEl - ci*PERCHUNK)
    items = rpm(ch, cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        o = u64(items, j*STRIDE)
        if not lp(o): continue
        c = p(o+0x18)
        if not lp(c): continue
        cn = cache.get(c)
        if cn is None:
            cn = oname(c); cache[c] = cn
        if CLSSUB in cn:
            insts.append((o, c, oname(o)))
        elif cn == "Function":
            on = oname(o)
            if on.startswith("ExecuteUbergraph_") and CLSSUB in on:
                ufunc = o

print(f"instances of a class containing '{CLSSUB}': {len(insts)}")
if not insts:
    sys.exit(1)
if not ufunc:
    print("no ExecuteUbergraph_* UFunction found"); sys.exit(1)
print(f"ubergraph  0x{ufunc:X}  {oname(ufunc)}")
locals_ = props_of(ufunc)
print(f"ubergraph locals: {len(locals_)}\n")


def readbool(addr, bi):
    if not bi:
        b = rpm(addr, 1); return None if b is None else bool(b[0])
    _, byteOff, _, fieldMask = bi
    b = rpm(addr + byteOff, 1)
    return None if b is None else bool(b[0] & fieldMask)


def readval(a, ty, bi):
    if ty == "BoolProperty": return readbool(a, bi)
    if ty == "IntProperty":
        b = rpm(a, 4); return i32(b, 0) if b else None
    if ty == "StrProperty": return fstring(a)
    if ty in ("ObjectProperty", "InterfaceProperty"):
        q = p(a); return f"0x{q:X}" if q else "null"
    return "?"


for o, c, nm in insts:
    frame_off = None
    for pn, ty, off, _ in props_of(c):
        if pn == "UberGraphFrame":
            frame_off = off; break
    frame = p(o + frame_off) if frame_off is not None else 0
    tag = "ARCHETYPE" if (nm.startswith("Default__") or "GEN_VARIABLE" in nm) else "instance"
    if not lp(frame):
        print(f"0x{o:X}  {tag:9}  {nm:56} frame=NULL  (graph never ran / no persistent frame)")
        continue
    nonzero = 0
    for pn, ty, off, bi in locals_:
        v = readval(frame + off, ty, bi)
        if v not in (None, False, 0, "", "null", "?"):
            nonzero += 1
    print(f"0x{o:X}  {tag:9}  {nm:56} frame=0x{frame:X}  HAS-RUN(non-default locals)={nonzero}")
    if FILT:
        for pn, ty, off, bi in sorted(locals_, key=lambda r: r[2]):
            if FILT not in pn.lower():
                continue
            v = readval(frame + off, ty, bi)
            print(f"        +0x{off:04X} {ty:16} {pn:52} = {v}")
