# obj_by_chain.py -- census live UObjects by CLASS DERIVATION CHAIN (read-only RPM, no injection).
#
# WHY THIS EXISTS (S136): tools/re/obj_by_class.py matches the class LEAF NAME only -- it reads
# UClass->NamePrivate (cls+0x20) and never walks SuperStruct. So it can answer
#   "is there an object whose class is literally named *AIController*?"          (leaf substring)
# but it CANNOT answer
#   "does ANY AController-DERIVED object exist?"                                  (derivation)
# A controller subclass named e.g. BP_TutorialBot_C or PC_MainMenu_C matches neither
# "AIController" nor "Controller", and S114 already burned a sitting on exactly that
# (PC_MainMenu_C is invisible to both obj_by_class substring AND cheat_reach_probe endswith --
#  "two instruments sharing one blind spot is not corroboration", docs/method-rules.md S114-a).
#
# S135 stated the blind spot explicitly and left it open:
#   "I counted only classes whose chain/leaf contains BotController or AIController. A controller
#    of some other class name would have been missed."  (docs/s135-queue-arms-a-match.md:449)
# This probe closes it: it walks UStruct::SuperStruct (+0x48) for every live object's class and
# matches if ANY ancestor name matches. That is the only strategy that cannot miss a subclass.
#
#   usage: obj_by_chain.py <PID> <BASE-hex> <ChainName|=ExactChainName> [LIMIT|all]
#     e.g. obj_by_chain.py 43456 0x7FF608F40000 =Controller all   # EXACT ancestor  <-- USE THIS
#          obj_by_chain.py 43456 0x7FF608F40000 Controller all    # substring (noisy)
#          obj_by_chain.py 43456 0x7FF608F40000 Controller        # tally only, no rows
#
# ★ PREFER THE '=' EXACT FORM for a base class. UHT strips the A/U/F prefix, so AController is
#   registered as "Controller" and AAIController as "AIController". Substring "Controller" also
#   matches ~190 ActorComponents named Comp_PlayerController_* which are NOT controllers at all;
#   "=Controller" matches the base class itself and therefore EVERY AController subclass, whatever
#   it is named. Measured 2026-08-21 on a live client: substring -> 193 hits / 66 classes, of which
#   exactly ONE is AController-derived. The substring form's 193 is noise, not an answer.
#
# OUTPUT CONTRACT -- read these lines, never a row count:
#   "NumElements=N"                 objects walked (the denominator; quote it)
#   "found N LIVE (non-CDO) ..."    THE ANSWER. Parse this, never `| grep -c`.
#   "distinct classes: N"           + a per-class tally with each class's full chain.
# The per-class tally is IMMUNE to the row cap by construction, which is the whole point --
# obj_by_class's cap-at-60 produced a wrong published number on 2026-08-14 (126 read as 60).
#
# Layout constants are this build's (non-stock): UObject Class@+0x18, Name@+0x20, Outer@+0x28,
# ObjectFlags@+0x0C, InternalIndex@+0x10; UStruct::SuperStruct@+0x48.
# Read-only: OpenProcess + ReadProcessMemory only. Nothing is written. Safe on a live sitting.
import ctypes, os, sys
from ctypes import wintypes
from collections import Counter

if len(sys.argv) < 4:
    print(__doc__ if __doc__ else "usage: obj_by_chain.py <PID> <BASE-hex> <ChainNameSubstr> [LIMIT|all]")
    sys.exit(2)

PID = int(sys.argv[1], 0); BASE = int(sys.argv[2], 16); WANT = sys.argv[3]
_lim = sys.argv[4] if len(sys.argv) > 4 else os.environ.get("OBJ_BY_CHAIN_LIMIT", "60")
LIMIT = 0 if str(_lim).lower() in ("all", "none", "0", "-1") else int(_lim, 0)

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930      # FChunkedFixedUObjectArray: +0x00 Objects**, +0x14 NumElements
PERCHUNK = 65536; STRIDE = 0x18

k32 = ctypes.WinDLL("kernel32", use_last_error=True); k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print(f"OpenProcess({PID}) failed err={ctypes.get_last_error()} -- run ELEVATED. RUN IS VOID.")
    sys.exit(1)


def rpm(a, n):
    b = (ctypes.c_ubyte * n)(); r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u32(b, o): return int.from_bytes(b[o:o+4], "little")
def u64(b, o): return int.from_bytes(b[o:o+8], "little")
def looksptr(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0


_nc = {}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk*8, 8); r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if looksptr(bp):
            hd = rpm(bp + off, 2)
            if hd:
                hd = int.from_bytes(hd, "little"); ln = hd >> 6; wide = hd & 1
                if 0 < ln < 200:
                    s = rpm(bp + off + 2, ln * (2 if wide else 1))
                    if s:
                        r = ("".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(ln)) if wide
                             else s.decode("latin1", "replace"))
    _nc[idx] = r; return r


def objname(o):
    b = rpm(o + 0x20, 4); return fname(u32(b, 0)) if b else "?"


# Per-UClass memo of the FULL derivation chain. One walk per class, not per object --
# S135 measured an unmemoised design holding the game thread ~12-15 s over 136k objects.
_chain = {}
def chain_of(cls):
    if cls in _chain: return _chain[cls]
    out = []; cur = cls; d = 0
    while looksptr(cur) and d < 24:
        out.append(objname(cur))
        b = rpm(cur + 0x48, 8)                       # UStruct::SuperStruct
        cur = int.from_bytes(b, "little") if b else 0
        d += 1
    _chain[cls] = out; return out


hdr = rpm(OBJOBJECTS, 0x18)
if not hdr:
    print("failed to read OBJOBJECTS (bad BASE?) -- RUN IS VOID"); sys.exit(1)
objectsPtr = u64(hdr, 0); numEl = u32(hdr, 0x14)
print(f"NumElements={numEl}")
numChunks = (numEl + PERCHUNK - 1) // PERCHUNK
chunkPtrs = rpm(objectsPtr, numChunks * 8)
if not chunkPtrs:
    print("failed to read chunk pointer table -- RUN IS VOID"); sys.exit(1)

EXACT = WANT.startswith("=")
want = WANT[1:].lower() if EXACT else WANT.lower()
match = ((lambda ch: any(c.lower() == want for c in ch)) if EXACT
         else (lambda ch: any(want in c.lower() for c in ch)))
print(f"match mode: {'EXACT ancestor name' if EXACT else 'substring in any ancestor name'}  target='{want}'")
hits = []; cdos = 0; walked = 0
for ci in range(numChunks):
    chunk = int.from_bytes(chunkPtrs[ci*8:ci*8+8], "little")
    if not looksptr(chunk): continue
    cnt = min(PERCHUNK, numEl - ci*PERCHUNK)
    items = rpm(chunk, cnt * STRIDE)
    if not items: continue
    for j in range(cnt):
        obj = u64(items, j*STRIDE)
        if not looksptr(obj): continue
        # one read gets Class(+0x18), Name(+0x20) and Outer(+0x28)
        b = rpm(obj + 0x18, 0x18)
        if not b: continue
        cls = u64(b, 0)
        if not looksptr(cls): continue
        walked += 1
        ch = chain_of(cls)
        if not match(ch): continue
        nm = fname(u32(b, 8))
        if nm.startswith("Default__"):               # CDOs are not live instances
            cdos += 1; continue
        outer = u64(b, 0x10)
        on = objname(outer) if looksptr(outer) else "-"
        hits.append((obj, ch[0], nm, on, tuple(ch)))

print(f"objects walked (readable class ptr): {walked}")
print(f"CDOs matched and EXCLUDED: {cdos}")
print(f"found {len(hits)} LIVE (non-CDO) instance(s) whose CLASS CHAIN contains '{WANT}':")

_shown = hits if LIMIT == 0 else hits[:LIMIT]
for obj, leaf, nm, on, ch in _shown:
    print(f"  obj=0x{obj:X}  Class={leaf}  Name={nm}  Outer={on}")
if LIMIT and len(hits) > LIMIT:
    print(f"  ... {len(hits)-LIMIT} more not shown (detail list capped at {LIMIT}).")
    print(f"  !! DO NOT COUNT THESE LINES -- the real total is {len(hits)}, printed above.")
    print(f"  !! Pass 'all' as the 4th argument to print every row.")

tally = Counter((leaf, ch) for _, leaf, _, _, ch in hits)
print(f"\ndistinct matching classes: {len(tally)}   (this tally is NOT capped)")
for (leaf, ch), n in tally.most_common():
    print(f"  {n:6}  {leaf}")
    print(f"          chain: {' <- '.join(ch)}")
