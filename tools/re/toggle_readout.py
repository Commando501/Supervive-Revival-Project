# toggle_readout.py -- read the CLIENT'S OWN ANSWER to a feature-toggle gate. Read-only RPM.
#
#   usage: toggle_readout.py <PID> <BASE-hex> [classNameSubstr]
#          default substr = ClientConfigVisbilityToggleWidget   (the typo is the game's)
#
# WHY THIS EXISTS (S121, 2026-08-15)
# ---------------------------------
# Until now nothing in this project could observe an IsFeatureEnabled RESULT, so a dark UI
# surface was ambiguous between "the flag is off" and "a companion condition is unmet".
# `UClientConfigManager::IsFeatureEnabled` logs NOTHING (measured: 0 BasicLog call sites in its
# 265-byte body, against a same-TU control that has 1), so no log verbosity can help.
#
# But the game gates most UI through a reusable Blueprint widget,
# WBP_UI_ClientConfigVisbilityToggleWidget_C, which STORES its computed answer in a reflected,
# persistent instance UPROPERTY: `Is Content Enabled`. Reading that is a direct measurement of
# the gate result, with zero injection and zero .text writes.
#
# The four properties together are self-interpreting:
#   IsEnabledByDefault == false  AND  Is Content Enabled == true
#       => reachable by NO path other than: FeatureToggles[FeatureKey] hit
#          -> entry.Config[ConfigKey] hit -> ToBool(value) == true.
#          i.e. OUR SERVED VALUE WAS READ. This is the discrimination we lacked.
#   IsEnabledByDefault == true   AND  Is Content Enabled == true   => uninformative (already on).
#   Is Content Enabled == false                                    => gate is OFF.
#
# ⚠ WHY NOT class_props.py: it locates a UClass by requiring ocls(obj)=="Class". A Blueprint
# class's own class is "BlueprintGeneratedClass", so that lookup can NEVER find this class and
# prints the misleading "not found (map not loaded yet?)". This resolves the class from a LIVE
# INSTANCE (obj+0x18) instead, which sidesteps the whole lookup. CLAUDE.md already records that
# obj_by_class.py (substring) and cheat_reach_probe.py (endswith) share a class-lookup blind
# spot -- this is a third instance of the same family. Do not "corroborate" one with another.
#
# Offsets (this build, per CLAUDE.md + class_props.py):
#   UObject Class@+0x18 Name@+0x20 ; UStruct SuperStruct@+0x48 ChildProperties@+0x58
#   FField Class(FFieldClass*)@+0x08 Next@+0x18 Name@+0x20
#   FProperty ElementSize@+0x34 Flags@+0x38 Offset_Internal@+0x44 ; sizeof(FProperty)==0x70
#   FBoolProperty (derived, so at +0x70): FieldSize@+0x70 ByteOffset@+0x71 ByteMask@+0x72
#                                         FieldMask@+0x73
import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
WANT = sys.argv[3] if len(sys.argv) > 3 else "ClientConfigVisbilityToggleWidget"

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK = 65536
STRIDE = 0x18

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed -- run elevated, and check the PID")
    sys.exit(1)


def rpm(a, n):
    b = (ctypes.c_ubyte * n)()
    r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u32(b, o): return int.from_bytes(b[o:o + 4], "little")
def i32(b, o): return int.from_bytes(b[o:o + 4], "little", signed=True)
def u64(b, o): return int.from_bytes(b[o:o + 8], "little")
def looksptr(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0
def p(a):
    b = rpm(a, 8)
    return u64(b, 0) if b else 0


_nc = {}


def fname(idx):
    if idx in _nc: return _nc[idx]
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk * 8, 8); r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if looksptr(bp):
            hd = rpm(bp + off, 2)
            if hd:
                hd = int.from_bytes(hd, "little"); ln = hd >> 6; wide = hd & 1
                if 0 < ln < 200:
                    s = rpm(bp + off + 2, ln * (2 if wide else 1))
                    if s:
                        r = ("".join(chr(s[i * 2] | (s[i * 2 + 1] << 8)) for i in range(ln))
                             if wide else s.decode("latin1", "replace"))
    _nc[idx] = r
    return r


def oname(o):
    b = rpm(o + 0x20, 4)
    return fname(u32(b, 0)) if b else "?"


def ftype(f):
    fc = p(f + 0x08)
    if not looksptr(fc): return "?"
    b = rpm(fc, 4)
    return fname(u32(b, 0)) if b else "?"


def fstring(a):
    """FString == TArray<TCHAR> {Data,Num,Max}. Returns '' for empty/unset."""
    b = rpm(a, 16)
    if not b: return None
    data = u64(b, 0); num = i32(b, 8)
    if num <= 0 or not looksptr(data) or num > 4096: return ""
    s = rpm(data, num * 2)
    if not s: return None
    out = "".join(chr(s[i * 2] | (s[i * 2 + 1] << 8)) for i in range(num))
    return out.rstrip("\x00")


# ---- sweep the GUObjectArray once: collect instances whose CLASS NAME contains WANT ----
hdr = rpm(OBJOBJECTS, 0x18)
if not hdr:
    print("bad OBJOBJECTS/base"); sys.exit(1)
objectsPtr = u64(hdr, 0); numEl = u32(hdr, 0x14)
numChunks = (numEl + PERCHUNK - 1) // PERCHUNK
chunkPtrs = rpm(objectsPtr, numChunks * 8)

instances = []          # (obj, objName, clsPtr)
clsname_cache = {}
for ci in range(numChunks):
    chunk = int.from_bytes(chunkPtrs[ci * 8:ci * 8 + 8], "little")
    if not looksptr(chunk): continue
    cnt = min(PERCHUNK, numEl - ci * PERCHUNK)
    items = rpm(chunk, cnt * STRIDE)
    if not items: continue
    for j in range(cnt):
        obj = u64(items, j * STRIDE)
        if not looksptr(obj): continue
        c = p(obj + 0x18)
        if not looksptr(c): continue
        cn = clsname_cache.get(c)
        if cn is None:
            cn = oname(c); clsname_cache[c] = cn
        if WANT in cn:
            instances.append((obj, oname(obj), c))

print(f"found {len(instances)} live instances of class ~'{WANT}'")
if not instances:
    sys.exit(0)

# ---- resolve properties from the class of the FIRST instance (bypasses the UClass lookup) ----
CLS = instances[0][2]
print(f"resolved UClass @0x{CLS:X} = {oname(CLS)}  (via instance, NOT via a name lookup)\n")

WANTED = ("featurekey", "configkey", "isenabledbydefault", "is content enabled",
          "enabledvisibility", "disabledvisibility")
props = {}   # lowername -> (offset, type, boolinfo)
cls = CLS; level = 0
while looksptr(cls) and level < 12:
    f = p(cls + 0x58); i = 0
    while looksptr(f) and i < 600:
        nm = oname(f); ty = ftype(f)
        raw = rpm(f, 0x80) or b"\0" * 0x80
        off = i32(raw, 0x44)
        low = nm.lower()
        if low in WANTED and low not in props:
            binfo = None
            if ty == "BoolProperty":
                # FieldSize, ByteOffset, ByteMask, FieldMask at +0x70..+0x73
                binfo = (raw[0x70], raw[0x71], raw[0x72], raw[0x73])
            props[low] = (off, ty, binfo)
        f = p(f + 0x18); i += 1
    cls = p(cls + 0x48); level += 1

for k in WANTED:
    if k in props:
        off, ty, bi = props[k]
        extra = f"  bool(fieldSize={bi[0]} byteOff={bi[1]} byteMask=0x{bi[2]:02X} fieldMask=0x{bi[3]:02X})" if bi else ""
        print(f"  prop {k:22} +0x{off:04X} {ty}{extra}")
    else:
        print(f"  prop {k:22} NOT FOUND")
print()


def readbool(obj, spec):
    off, ty, bi = spec
    if not bi:
        b = rpm(obj + off, 1)
        return None if b is None else bool(b[0])
    fieldSize, byteOff, byteMask, fieldMask = bi
    b = rpm(obj + off + byteOff, 1)
    if b is None: return None
    return bool(b[0] & fieldMask)


rows = []
for obj, nm, c in instances:
    fk = fstring(obj + props["featurekey"][0]) if "featurekey" in props else None
    ck = fstring(obj + props["configkey"][0]) if "configkey" in props else None
    dflt = readbool(obj, props["isenabledbydefault"]) if "isenabledbydefault" in props else None
    en = readbool(obj, props["is content enabled"]) if "is content enabled" in props else None
    rows.append((fk or "", nm, dflt, en, ck or "", obj))

# The money column: default==False and enabled==True can ONLY come from our served value.
rows.sort(key=lambda r: (r[0].lower(), r[1]))
print(f"{'FeatureKey':34} {'instance':46} {'dflt':5} {'ENABLED':7} {'ConfigKey':10} verdict")
print("-" * 135)
for fk, nm, dflt, en, ck, obj in rows:
    if dflt is False and en is True:
        verdict = "*** SERVED VALUE READ ***"
    elif dflt is True and en is True:
        verdict = "on by default (uninformative)"
    elif en is False:
        verdict = "GATE OFF"
    else:
        verdict = "?"
    print(f"{fk:34} {nm[:46]:46} {str(dflt):5} {str(en):7} {ck:10} {verdict}")

# Summary counts -- parse THESE, never the row count above.
n_served = sum(1 for r in rows if r[2] is False and r[3] is True)
n_off = sum(1 for r in rows if r[3] is False)
n_dflt_on = sum(1 for r in rows if r[2] is True and r[3] is True)
print(f"\nsummary: total={len(rows)}  served-value-read={n_served}  gate-off={n_off}  "
      f"on-by-default={n_dflt_on}")
