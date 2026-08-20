# cdo_flag_readout.py -- read AActor::bCanEverReplicate (+0x6C) and bEnablePooling (+0x2D3)
# off LIVE Class Default Objects, to settle whether the RUNTIME CDO byte equals the
# COOKED class default that the AssetRegistry reports.
#
#   usage: cdo_flag_readout.py <PID> <BASE-hex>
#
# Pure ReadProcessMemory. No injection, no writes, no .text touched.
#
# WHY (S130 / FK-22 C7):
#   The pooled acquire does  `cmp byte ptr [CDO+0x6C], 0 ; jne -> return NULL`  [M],
#   and AActor+0x6C is AActor::bCanEverReplicate [M], whose C++ ctor default is 1
#   (AActor::AActor 0x3371800 -> 0x03371841 `mov byte ptr [rdi+0x6c], 1`) [M].
#   The COOKED AssetRegistry value for BP_DropPod_Tutorial is `true`, so C7 should
#   fire -- but that is [I] for the RUNTIME byte, because nothing has shown the
#   runtime CDO equals the cooked class default.  This probe closes that gap.
#
# PRE-REGISTERED PREDICTIONS (written before the first run; do not edit after):
#   Default__BP_DropPod_Tutorial_C   +0x6C = 1   (cooked true  -> C7 FIRES)
#   Default__BP_GemV2_C              +0x6C = 1   (cooked true)
#   Default__BP_HeroHeightIndicator_C+0x6C = 0   (cooked false; AND independently,
#                                                 ALokiHeroHeightIndicator's ctor does
#                                                 `mov byte [rbx+0x6c], dl` with dl=0)
#   all three                        +0x2D3 = 1  (all three are registered poolable
#                                                 at the menu -> a DIFFERENT offset,
#                                                 known-true for every target, which
#                                                 proves we are reading the right object)
#
# HOW TO READ THE RESULT
#   * predictions all hold            -> runtime CDO == cooked default; C7 fires; [I]->[M]
#   * DropPod reads 0                 -> C7 does NOT fire; the S130 model is wrong
#   * every target reads the SAME     -> the probe is not reading the field. VOID.
#   * a target is not found           -> that class is not loaded; NOT a zero.
#
# All 176 classes that log `LogActorPooling: Adding ... to list of poolable actors`
# do so at the MENU (measured: two menu-only logs, LVL_Tutorial count 0), so this
# needs no tutorial staging.
import ctypes, sys
from ctypes import wintypes

if len(sys.argv) < 3:
    print(__doc__ or "usage: cdo_flag_readout.py <PID> <BASE-hex>")
    sys.exit(2)

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
OBJ = BASE + 0x9E38930          # FUObjectArray+0x10 (ObjObjects) -- the constant this repo uses
NP = BASE + 0x9D81450           # name pool
PERCHUNK = 65536
STRIDE = 0x18

OFF_REPL = 0x6C                 # AActor::bCanEverReplicate  [M]
OFF_POOL = 0x2D3                # AActor::bEnablePooling     [M]

TARGETS = {
    # --- Blueprint CDOs (only exist once the BP class is actually LOADED) ---
    "Default__BP_DropPod_Tutorial_C":    dict(repl=1, pool=1, role="BP TARGET  (cooked true)"),
    "Default__BP_GemV2_C":               dict(repl=1, pool=1, role="BP TARGET  (cooked true)"),
    "Default__BP_HeroHeightIndicator_C": dict(repl=0, pool=1, role="BP CONTROL (cooked false)"),
    "Default__BP_DropPod_C":             dict(repl=1, pool=1, role="BP TARGET  (cooked true)"),

    # --- NATIVE CDOs.  These are created at module init, so they exist at the menu,
    #     and they are the RIGHT target: neither drop-pod Blueprint overrides
    #     bCanEverReplicate [M, bpdump @props], so the BP CDO simply inherits the
    #     native value.  Reading the native CDO answers the same question with one
    #     fewer inheritance hop -- and it is the exact object whose CONSTRUCTOR was
    #     disassembled, so prediction and measurement meet on the same bytes.
    "Default__LokiDropPod":              dict(repl=1, pool=None,
                                              role="NATIVE TARGET  (AActor ctor default; AS sets neither flag)"),
    "Default__LokiGem":                  dict(repl=1, pool=1,
                                              role="NATIVE TARGET  (LokiGem.as sets bEnablePooling=true)"),
    "Default__LokiHeroHeightIndicator":  dict(repl=0, pool=1,
                                              role="NATIVE CONTROL (its ctor 0x56774C0: mov [rbx+0x6c],dl dl=0; mov [rbx+0x2d3],1)"),
    "Default__LokiDropPodBase":          dict(repl=1, pool=None, role="NATIVE (ancestor, for the chain)"),
    "Default__Actor":                    dict(repl=1, pool=None,
                                              role="NATIVE ROOT CONTROL (AActor::AActor 0x03371841 mov byte [rdi+0x6c],1)"),
}

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.OpenProcess.restype = wintypes.HANDLE
h = k.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed for PID %d (err %d)" % (PID, ctypes.get_last_error()))
    sys.exit(1)


def rd(a, n):
    b = (ctypes.c_ubyte * n)()
    r = ctypes.c_size_t(0)
    if not a or not k.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u32(b, o): return int.from_bytes(b[o:o + 4], "little")
def u64(b, o): return int.from_bytes(b[o:o + 8], "little")
def looks(v): return 0x10000 <= v < 0x1000000000000


def fname(idx):
    blk = idx >> 16
    off = (idx & 0xFFFF) << 1
    bp = rd(NP + blk * 8, 8)
    if not bp:
        return "?"
    bp = int.from_bytes(bp, "little")
    if not looks(bp):
        return "?"
    b2 = rd(bp + off, 2)
    if not b2:
        return "?"
    hd = int.from_bytes(b2, "little")
    ln = hd >> 6
    w = hd & 1
    if ln <= 0 or ln > 200:
        return "?"
    s = rd(bp + off + 2, ln * (2 if w else 1))
    if not s:
        return "?"
    return "".join(chr(s[i * 2] | (s[i * 2 + 1] << 8)) for i in range(ln)) if w else s.decode("latin1", "replace")


hdr = rd(OBJ, 0x18)
if not hdr:
    print("cannot read GUObjectArray at 0x%X -- wrong base?" % OBJ)
    sys.exit(1)
op = u64(hdr, 0)
num = u32(hdr, 0x14)
print("GUObjectArray @0x%X  ObjObjects=0x%X  NumElements=%d" % (OBJ, op, num))
if not looks(op) or not (1000 < num < 5000000):
    print("*** implausible header -- VOID, do not interpret ***")
    sys.exit(1)

nchunks = (num + PERCHUNK - 1) // PERCHUNK
found = {}
cdo_count = [0]
for ci in range(nchunks):
    cp = rd(op + ci * 8, 8)
    if not cp:
        continue
    chunk = u64(cp, 0)
    if not looks(chunk):
        continue
    cnt = (num - ci * PERCHUNK) if ci == nchunks - 1 else PERCHUNK
    for j in range(cnt):
        ep = rd(chunk + j * STRIDE, 8)
        if not ep:
            continue
        o = u64(ep, 0)
        if not looks(o):
            continue
        nb = rd(o + 0x20, 4)
        if not nb:
            continue
        nm = fname(u32(nb, 0))
        if nm.startswith("Default__"):
            cdo_count[0] += 1
        if nm in TARGETS and nm not in found:
            found[nm] = o

print("\nDefault__ objects live in this process: %d (unit: CDOs) -- so a NOT LOADED row means that class is genuinely absent, not that the walk failed" % cdo_count[0])
print("\n%-36s %-40s %10s %10s" % ("object", "role", "+0x6C", "+0x2D3"))
print("-" * 100)
vals = {}
for nm, spec in TARGETS.items():
    o = found.get(nm)
    if not o:
        print("%-36s %-40s %10s %10s" % (nm, spec["role"], "-", "-"))
        continue
    a = rd(o + OFF_REPL, 1)
    b = rd(o + OFF_POOL, 1)
    av = a[0] if a else None
    bv = b[0] if b else None
    vals[nm] = av
    ok6 = "PASS" if av == spec["repl"] else "*** FAIL ***"
    okd = "(no prediction)" if spec["pool"] is None else ("PASS" if bv == spec["pool"] else "*** FAIL ***")
    print("%-36s %-40s %10s %10s   obj=0x%X" % (nm, spec["role"], av, bv, o))
    print("%-36s %-40s   predicted %d -> %-12s predicted %d -> %s"
          % ("", "", spec["repl"], ok6,
             -1 if spec["pool"] is None else spec["pool"], okd))

print("\n--- instrument check ---")
seen = set(v for v in vals.values() if v is not None)
if len(vals) >= 2 and len(seen) == 1:
    print("*** every target read the SAME value (%r). The probe is probably not reading the"
          % seen.pop())
    print("*** field at all. TREAT THIS RUN AS VOID.")
elif len(seen) > 1:
    print("targets differ (%s) -- the probe discriminates, so the values are real reads."
          % sorted(seen))
else:
    print("not enough targets found to run the check.")
