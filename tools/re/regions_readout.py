# regions_readout.py -- read the client's PARSED FRegionHostList. Read-only RPM.
#
#   usage: regions_readout.py <PID> <BASE-hex>
#
# WHY (S121, 2026-08-15)
# ---------------------
# `GET /core-game/regions` feeds UCoreGameManager.ValidRegions (FRegionHostList). FK-5 measured
# that our FLAT payload parsed into one region with an EMPTY Routes map -> zero ULatencyMeasurers
# -> zero pings -> the "??? - ms" row. S121 shipped a NESTED payload and STILL saw 0 measurers,
# so the fix did not bind either -- and, exactly like the flat version, it produced NO parse error.
#
# ⇒ The failure mode on this endpoint is "parse succeeds, container stays empty". A log-based
#   instrument CANNOT see it. This probe reads the parsed struct directly.
#
# ★ THE ETAG IS A FREE POSITIVE CONTROL, and it is what makes this probe discriminating.
#   FRegionHostList carries `FString ETag` right after the array, and we control the exact string
#   we serve. So:
#       ETag == what we served  AND  Regions.Num == 0   -> the LIST bound; the ARRAY field name is wrong
#       ETag == what we served  AND  Routes.Num  == 0   -> the region bound; the ROUTES nesting is wrong
#       ETag empty                                      -> the whole struct never bound at all
#   Without the ETag, an empty array is uninterpretable -- the same ambiguity that let this bug
#   survive from FK-5 (2026-07-27) to now.
#
# Layout [M]:
#   UCoreGameManager.ValidRegions @ +0x6F0  (StructProperty, size 32) -- offset read live from
#     reflection by class_props.py; re-derive it rather than trusting this constant.
#   FRegionHostList { TArray<FRegionHost> Regions @ +0x00 ; FString ETag @ +0x10 }      // 32 B
#   FRegionHost { FString Name @0x00 ; FString Addr @0x10 ; int32 Port @0x20 ;
#                 bool CanExclude @0x24 ; TMap<FString,FRegionRoute> Routes @0x28 }     // 0x78 B
#   TArray  { void* Data ; int32 Num ; int32 Max }
#   TMap -> Elements.Data is a TArray, so Num lives at TMap+0x08 (S118 used the same shape).
import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
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
def looksptr(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0
def p(a):
    b = rpm(a, 8); return u64(b, 0) if b else 0


_nc = {}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk*8, 8); r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if looksptr(bp):
            hd = rpm(bp+off, 2)
            if hd:
                hd = int.from_bytes(hd, "little"); ln = hd >> 6; wide = hd & 1
                if 0 < ln < 200:
                    s = rpm(bp+off+2, ln*(2 if wide else 1))
                    if s:
                        r = ("".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(ln))
                             if wide else s.decode("latin1", "replace"))
    _nc[idx] = r; return r


def oname(o):
    b = rpm(o+0x20, 4); return fname(u32(b, 0)) if b else "?"


def fstring(a):
    b = rpm(a, 16)
    if not b: return None
    d = u64(b, 0); n = i32(b, 8)
    if n <= 0 or not looksptr(d) or n > 4096: return ""
    s = rpm(d, n*2)
    if not s: return None
    return "".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(n)).rstrip("\x00")


def tarray(a):
    b = rpm(a, 16)
    return (u64(b, 0), i32(b, 8), i32(b, 12)) if b else (0, -1, -1)


# ---- find the live CoreGameManager ----
hdr = rpm(OBJOBJECTS, 0x18)
objectsPtr = u64(hdr, 0); numEl = u32(hdr, 0x14)
nchunks = (numEl + PERCHUNK - 1)//PERCHUNK
cp = rpm(objectsPtr, nchunks*8)
mgr = 0; mgrcls = 0
for ci in range(nchunks):
    ch = int.from_bytes(cp[ci*8:ci*8+8], "little")
    if not looksptr(ch): continue
    cnt = min(PERCHUNK, numEl - ci*PERCHUNK)
    items = rpm(ch, cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        o = u64(items, j*STRIDE)
        if not looksptr(o): continue
        c = p(o+0x18)
        if looksptr(c) and oname(c) == "CoreGameManager" and not oname(o).startswith("Default__"):
            mgr, mgrcls = o, c; break
    if mgr: break

if not mgr:
    print("no live CoreGameManager"); sys.exit(1)
print(f"CoreGameManager @0x{mgr:X}")

# ---- resolve ValidRegions BY NAME (never trust a hardcoded offset) ----
off = None
cls = mgrcls; lvl = 0
while looksptr(cls) and lvl < 8:
    f = p(cls+0x58); i = 0
    while looksptr(f) and i < 400:
        if oname(f) == "ValidRegions":
            raw = rpm(f, 0x60)
            off = i32(raw, 0x44)
            break
        f = p(f+0x18); i += 1
    if off is not None: break
    cls = p(cls+0x48); lvl += 1

if off is None:
    print("ValidRegions property not found"); sys.exit(1)
print(f"ValidRegions @ +0x{off:X}  (resolved by name from live reflection)\n")

vr = mgr + off
data, num, mx = tarray(vr)
etag = fstring(vr + 0x10)

print(f"  Regions.Num = {num}   (Data=0x{data:X} Max={mx})")
print(f"  ETag        = {etag!r}      <-- POSITIVE CONTROL: compare to what ags served")
print()

if num <= 0:
    print("  >> Regions array is EMPTY.")
    print("  >> If ETag matches what we served, the LIST bound and the ARRAY field name is wrong.")
    print("  >> If ETag is empty too, the whole FRegionHostList never bound.")
    sys.exit(0)

REGION_STRIDE = 0x78
for i in range(min(num, 16)):
    r = data + i*REGION_STRIDE
    name = fstring(r + 0x00)
    addr = fstring(r + 0x10)
    b = rpm(r + 0x20, 8)
    port = i32(b, 0) if b else -1
    canx = bool(b[4]) if b else None
    # TMap Routes @ +0x28 ; its Elements.Data TArray Num sits at +0x08
    rb = rpm(r + 0x28, 16)
    routes_data = u64(rb, 0) if rb else 0
    routes_num = i32(rb, 8) if rb else -1
    print(f"  [{i}] Name={name!r} Addr={addr!r} Port={port} CanExclude={canx}")
    print(f"       Routes.Num = {routes_num}   (Data=0x{routes_data:X})")
    if routes_num == 0:
        print("       >> ROUTES EMPTY -> zero ULatencyMeasurers -> zero pings -> '??? - ms'.")
        print("       >> The region bound but the Routes MAP did not. Nesting/among-name issue")
        print("       >> INSIDE FRegionHost -- not a whole-struct rejection.")
