# gas_probe.py — how far is the force-open hero from having a working GameplayAbilitySystem?
#
# S99b, for scoping "playable". S94 established only that the hero has NO AttributeSet (attributeSet == 0x0).
# That single fact does not distinguish two VERY different situations:
#   (A) the hero has a LokiAbilitySystemComponent but it was never initialised/populated
#       -> the gap is "add the default attribute set + grant abilities", a bounded job;
#   (B) the hero has no ASC at all
#       -> the gap is "reconstruct the whole ability-system init the server-authoritative deploy performs".
# This prints exactly which one it is, plus every ability/attribute-shaped object that DOES exist live.
#
#   usage: gas_probe.py <PID> <BASE-hex> [heroHex]
import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
HERO = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0

NP = BASE + 0x9D81450          # FNamePool
OO = BASE + 0x9E38930          # GUObjectArray
PERCHUNK, ITEMSTRIDE = 64 * 1024, 24

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.OpenProcess.restype = wintypes.HANDLE
h = k.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed"); sys.exit(1)

def rd(a, n):
    b = (ctypes.c_ubyte * n)(); r = ctypes.c_size_t(0)
    if not a or not k.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)

def u32(b, o=0): return int.from_bytes(b[o:o+4], "little")
def u64(b, o=0): return int.from_bytes(b[o:o+8], "little")
def looks(v): return 0x10000 <= v < 0x1000000000000

def fn(idx):
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = rd(NP + blk * 8, 8)
    if not bp: return "?"
    bp = u64(bp)
    if not looks(bp): return "?"
    b2 = rd(bp + off, 2)
    if not b2: return "?"
    hd = int.from_bytes(b2, "little"); ln = hd >> 6; w = hd & 1
    if ln <= 0 or ln > 200: return "?"
    s = rd(bp + off + 2, ln * (2 if w else 1))
    if not s: return "?"
    return "".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(ln)) if w else s.decode("latin1", "replace")

def clsof(o):
    b = rd(o + 0x18, 8); return u64(b) if b else 0
def nameof(o):
    b = rd(o + 0x20, 4); return fn(u32(b)) if b else "?"
def cnameof(o):
    c = clsof(o); return nameof(c) if looks(c) else "?"

def props(cls):
    d = 0
    while looks(cls) and d < 24:
        f = u64(rd(cls + 0x58, 8) or b"\0" * 8); n = 0
        while looks(f) and n < 2500:
            nb = rd(f + 0x20, 4); ob = rd(f + 0x44, 4)
            if nb and ob:
                yield fn(u32(nb)), u32(ob), cnameof(f)
            f = u64(rd(f + 0x18, 8) or b"\0" * 8); n += 1
        cls = u64(rd(cls + 0x48, 8) or b"\0" * 8)
        d += 1

# ---- 1. the hero's own ability-shaped properties ---------------------------
if HERO:
    print("hero 0x%X (%s)" % (HERO, cnameof(HERO)))
    hits = 0
    for nm, off, pc in props(clsof(HERO)):
        low = nm.lower()
        if "abilit" in low or "attribute" in low or "gameplayeffect" in low:
            v = rd(HERO + off, 8)
            val = u64(v) if v else 0
            tag = ("-> 0x%X (%s)" % (val, cnameof(val))) if looks(val) else ("= 0x%X  <== EMPTY" % val)
            print("   %-42s @0x%04X  %-22s %s" % (nm, off, pc, tag))
            hits += 1
    if not hits:
        print("   (no ability/attribute-named UPROPERTY on this class chain)")
else:
    print("(no hero passed; skipping per-hero properties)")

# ---- 2. what GAS objects exist live at all --------------------------------
print("\nlive GAS-shaped objects (class name contains AbilitySystemComponent / AttributeSet / GameplayAbility):")
oo = rd(OO, 0x18)
counts, samples = {}, {}
if oo:
    objectsPtr = u64(oo, 0); numEl = int.from_bytes(oo[0x14:0x18], "little", signed=True)
    if looks(objectsPtr) and 0 < numEl < 8000000:
        chunks = (numEl + PERCHUNK - 1) // PERCHUNK
        for ci in range(chunks):
            cp = rd(objectsPtr + ci * 8, 8)
            if not cp: break
            chunk = u64(cp)
            if not looks(chunk): continue
            cnt = numEl - ci * PERCHUNK if ci == chunks - 1 else PERCHUNK
            for j in range(cnt):
                it = rd(chunk + j * ITEMSTRIDE, 8)
                if not it: continue
                obj = u64(it)
                if not looks(obj): continue
                cn = cnameof(obj)
                if ("AbilitySystemComponent" in cn) or ("AttributeSet" in cn) or ("GameplayAbility" in cn):
                    on = nameof(obj)
                    if on.startswith("Default__"):
                        key = cn + "  (CDO only)"
                    else:
                        key = cn
                        samples.setdefault(cn, []).append((obj, on))
                    counts[key] = counts.get(key, 0) + 1

if counts:
    for kk in sorted(counts):
        print("   %-58s x%d" % (kk, counts[kk]))
else:
    print("   (none)")

print("\nlive (non-CDO) instances:")
if samples:
    for cn, lst in sorted(samples.items()):
        for obj, on in lst[:4]:
            print("   0x%X  %s  (%s)" % (obj, on, cn))
else:
    print("   NONE — no ability system instantiated at all in this world")
