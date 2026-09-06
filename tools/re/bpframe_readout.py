# bpframe_readout.py -- read a Blueprint's LIVE ubergraph locals out of its persistent
# UberGraphFrame. Read-only RPM. No injection, no .text writes.
#
#   usage: bpframe_readout.py <PID> <BASE-hex> <ClassNameSubstr> [propNameFilter]
#   e.g.:  bpframe_readout.py 1234 0x7FF7BFF50000 Comp_MainMenu_Onboarding IsFeatureEnabled
#
# ⚠⚠ KNOWN BLIND SPOT (S122) -- PREFER `bpframe_all.py` WHEN A CLASS HAS SEVERAL INSTANCES.
# This script stops at the FIRST object whose name is not `Default__*` and does not contain
# `GEN_VARIABLE`. That is not sufficient: for WBP_UI_MainMenu_NormalMainMenu there are THREE live
# objects -- the CDO plus TWO both named `MainMenu_NormalV2` -- and the first non-CDO match has an
# entirely default frame (HAS-RUN = 0 non-default locals of 219) while the real widget is the third
# (HAS-RUN = 61). So this script reported `False` for a graph that HAD NEVER RUN, on a menu that had
# been live for 74 minutes, and the answer looked measured. Both live-looking instances share the
# same NAME, so name matching cannot separate them either -- only the has-run control can.
# ⇒ FOURTH member of the class-lookup blind-spot family CLAUDE.md records for obj_by_class.py
# (substring), cheat_reach_probe.py (endswith) and class_props.py (class-of-class). The shared
# defect is "take the first match"; the shared fix is "enumerate and show your work".
# `tools/re/bpframe_all.py` prints EVERY instance with its own has-run control. Use it first.
#
# ⚠ And when you need a SCALAR (an int/enum/bool on a normal object rather than an ubergraph local),
# `tools/re/obj_scalars.py` is the companion to obj_props_dump.py, which prints only object/array
# properties and is therefore blind to things like WidgetSwitcher.ActiveWidgetIndex and Visibility.
#
# WHY THIS EXISTS (S121, 2026-08-15)
# ---------------------------------
# `tools/re/toggle_readout.py` answers "did the client read our feature-toggle value?" for the
# DECLARATIVE gates, because that widget stores its answer in a reflected UPROPERTY. It is
# structurally blind to the **10 BYTECODE keys** (`motd`, `LobbyRewards`, `ArmoryOnboarding`, …):
# those call `UClientConfigManager::IsFeatureEnabled(FString,bool)` from Blueprint and keep the
# result in a *local*, not a property. Nothing in this project could see them.
#
# ★ But Blueprint locals here are NOT stack-temporary. The generated class carries
#   `StructProperty UberGraphFrame` (`FPointerToUberGraphFrame`, Transient|DuplicateTransient), so
#   UE allocates ONE persistent frame per instance and every `CallFunc_*_ReturnValue` local lives
#   in it at a fixed offset. They therefore survive the call and are readable by plain RPM.
#
# ⇒ This turns the whole bytecode-gate family into a measurement, and it is not motd-specific:
#   any Blueprint's ubergraph locals become inspectable, which is exactly what was missing when
#   tracing why a predicate did not fire.
#
# MECHANICS [M, this build]
#   UObject:   Class @+0x18, Name @+0x20
#   UStruct:   SuperStruct @+0x48, ChildProperties @+0x58     (UFunction IS a UStruct)
#   FField:    ClassPtr @+0x08, Next @+0x18, Name @+0x20
#   FProperty: ElementSize @+0x34, Flags @+0x38, Offset_Internal @+0x44
#   FBoolProperty adds FieldSize/ByteOffset/ByteMask/FieldMask at +0x70..+0x73
#
# ⚠ The UberGraphFrame POINTER is the struct property's value: read the qword at
#   instance + UberGraphFrame.Offset. A NULL there means the persistent-frame path is off for this
#   class (the runtime cvar) — the probe says so rather than printing garbage.
# ⚠ Locals are only meaningful AFTER the graph has run at least once. A frame full of zeros can
#   mean "never executed", not "all false" — the same never-evaluated-vs-off ambiguity that
#   toggle_readout.py had to handle. Look for ANY non-zero local as the has-run control.
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
    """Walk a UStruct's ChildProperties (+ super chain). Yields (name, type, offset, boolinfo)."""
    out = []
    cur = struct_ptr; lvl = 0
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


# ---- sweep the object array once: find the instance, its class, and the ubergraph UFunction ----
hdr = rpm(OBJOBJECTS, 0x18)
objectsPtr = u64(hdr, 0); numEl = u32(hdr, 0x14)
nch = (numEl + PERCHUNK - 1)//PERCHUNK
cp = rpm(objectsPtr, nch*8)

inst = cls = ufunc = 0
cache = {}
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
        on = None
        if not inst and CLSSUB in cn:
            on = oname(o)
            # prefer a REAL instance over the widget-tree archetype / CDO
            if not on.startswith("Default__") and "GEN_VARIABLE" not in on:
                inst, cls = o, c
        if not ufunc and cn == "Function":
            on = on if on is not None else oname(o)
            if on.startswith("ExecuteUbergraph_") and CLSSUB in on:
                ufunc = o
    if inst and ufunc:
        break

if not inst:
    print(f"no live non-archetype instance of a class containing '{CLSSUB}'"); sys.exit(1)
print(f"instance   0x{inst:X}  class={oname(cls)}")
if not ufunc:
    print("WARNING: ExecuteUbergraph_* UFunction not found -- cannot resolve local offsets"); sys.exit(1)
print(f"ubergraph  0x{ufunc:X}  {oname(ufunc)}")

# ---- the frame pointer ----
frame_off = None
for nm, ty, off, _ in props_of(cls):
    if nm == "UberGraphFrame":
        frame_off = off; break
if frame_off is None:
    print("no UberGraphFrame property on this class -- persistent frames are off for it"); sys.exit(1)
frame = p(inst + frame_off)
print(f"UberGraphFrame @ +0x{frame_off:X} -> 0x{frame:X}")
if not lp(frame):
    print("  frame pointer is NULL: UsePersistentUberGraphFrame() is off, or the graph never ran.")
    sys.exit(1)

locals_ = props_of(ufunc)
print(f"ubergraph locals: {len(locals_)}\n")


def readbool(addr, bi):
    if not bi:
        b = rpm(addr, 1); return None if b is None else bool(b[0])
    _, byteOff, _, fieldMask = bi
    b = rpm(addr + byteOff, 1)
    return None if b is None else bool(b[0] & fieldMask)


rows = []
nonzero = 0
for nm, ty, off, bi in sorted(locals_, key=lambda r: r[2]):
    a = frame + off
    v = None
    if ty == "BoolProperty":
        v = readbool(a, bi)
    elif ty in ("IntProperty",):
        b = rpm(a, 4); v = i32(b, 0) if b else None
    elif ty == "StrProperty":
        v = fstring(a)
    elif ty in ("ObjectProperty", "InterfaceProperty"):
        q = p(a); v = f"0x{q:X}" if q else "null"
    else:
        continue
    if v not in (None, False, 0, "", "null"):
        nonzero += 1
    if FILT and FILT not in nm.lower():
        continue
    rows.append((off, ty, nm, v))

for off, ty, nm, v in rows:
    print(f"  +0x{off:04X} {ty:16} {nm:52} = {v}")

print(f"\nsummary: printed={len(rows)}  non-default-locals-in-frame={nonzero}")
print("NOTE: non-default-locals is the HAS-RUN control. If it is 0, the graph has not executed and")
print("      every 'False' below is 'never evaluated', NOT 'evaluated false'.")
