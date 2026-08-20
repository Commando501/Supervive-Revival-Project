# cdo_cooked_vs_runtime.py -- join EVERY live Blueprint CDO against the cooked
# AssetRegistry value of AActor::bCanEverReplicate (+0x6C), in one GUObjectArray walk.
#
#   usage: cdo_cooked_vs_runtime.py <PID> <BASE-hex>
#
# Pure ReadProcessMemory. No injection, no writes.
#
# WHY: S130 §12 established the cooked->runtime mapping on 3 loadable classes in both
# polarities.  Three is enough to discriminate, but not enough to call the mapping a
# law.  This walks every `Default__*_C` CDO that is live, looks up its cooked tag, and
# reports agreement/disagreement -- turning a 3/3 result into an N/N one, or finding
# the exception that breaks it.
#
# The cooked side is the extracted AssetRegistry (tools/extractor/out/
# assetregistry_candidates_Blueprint.json); only the 176 poolable-registered classes
# carry a bCanEverReplicate tag, so the join is naturally limited to those.
#
# A DISAGREEMENT IS THE INTERESTING RESULT -- it would mean the cooked class default is
# not what the runtime CDO carries, which is exactly the hypothesis §12 refuted on a
# small sample.  Print every one.
import ctypes, sys, json, io
from ctypes import wintypes

if len(sys.argv) < 3:
    print("usage: cdo_cooked_vs_runtime.py <PID> <BASE-hex>")
    sys.exit(2)

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
OBJ = BASE + 0x9E38930
NP = BASE + 0x9D81450
PERCHUNK = 65536
STRIDE = 0x18
OFF_REPL = 0x6C
OFF_POOL = 0x2D3
AR = r"G:\git\Supervive Revival Project\tools\extractor\out\assetregistry_candidates_Blueprint.json"

cooked = {}
for e in json.load(io.open(AR, encoding="utf-8")):
    t = e.get("Tags") or {}
    if "bCanEverReplicate" in t:
        cooked["Default__" + (e.get("AssetName") or "") + "_C"] = str(t["bCanEverReplicate"]).lower()
print("cooked bCanEverReplicate tags available: %d (unit: Blueprint assets)" % len(cooked))

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.OpenProcess.restype = wintypes.HANDLE
h = k.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed (err %d)" % ctypes.get_last_error())
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
op, num = u64(hdr, 0), u32(hdr, 0x14)
print("GUObjectArray ObjObjects=0x%X NumElements=%d" % (op, num))
nchunks = (num + PERCHUNK - 1) // PERCHUNK

live = {}
cdos = 0
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
            cdos += 1
            if nm in cooked and nm not in live:
                live[nm] = o

print("live CDOs: %d ; of those, joinable against a cooked tag: %d" % (cdos, len(live)))

agree = dis = unread = 0
byval = {"true": [0, 0], "false": [0, 0]}   # [agree, disagree]
mismatches = []
for nm, o in sorted(live.items()):
    b = rd(o + OFF_REPL, 1)
    if b is None:
        unread += 1
        continue
    rt = b[0]
    ck = cooked[nm]
    want = 1 if ck == "true" else 0
    if rt == want:
        agree += 1
        byval[ck][0] += 1
    else:
        dis += 1
        byval[ck][1] += 1
        mismatches.append((nm, ck, rt, o))

print("\n--- cooked vs runtime, AActor::bCanEverReplicate (+0x6C) ---")
print("  agree    : %d" % agree)
print("  DISAGREE : %d" % dis)
print("  unreadable: %d" % unread)
print("  by cooked value:  true -> %d agree / %d disagree ;  false -> %d agree / %d disagree"
      % (byval["true"][0], byval["true"][1], byval["false"][0], byval["false"][1]))

if byval["true"][0] + byval["true"][1] == 0 or byval["false"][0] + byval["false"][1] == 0:
    print("\n*** ONE-SIDED SAMPLE -- only one cooked value is represented, so agreement is")
    print("*** NOT evidence the read discriminates. Treat as inconclusive.")
else:
    print("\nboth cooked polarities are represented, so agreement is discriminating.")

if mismatches:
    print("\n--- DISAGREEMENTS (the interesting rows) ---")
    for nm, ck, rt, o in mismatches:
        print("  %-52s cooked=%-6s runtime=%d  obj=0x%X" % (nm, ck, rt, o))
