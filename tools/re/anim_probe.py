# anim_probe.py — is the body's SkeletalMeshComponent actually being POSED by a playing AnimSequence?
#
# S99. `PlayAnimation(...) ok` in the shim marker only proves the native call returned; it does NOT prove the
# skeleton moved. This probe answers that directly and read-only:
#   1. component -> AnimScriptInstance  (the UAnimSingleNodeInstance created by SetAnimationMode(SingleNode))
#   2. that instance's CurrentTime / Position float, sampled TWICE ~2s apart. Advancing == the anim is PLAYING,
#      so the pose is NOT the bind/T-pose.
#   3. the component's BoneSpaceTransforms/ComponentSpaceTransforms array length + a hash of the first N bone
#      quats, sampled twice — a second, independent witness that the skeleton is actually moving.
#
#   usage: anim_probe.py <PID> <BASE-hex> <compHex>
import ctypes, sys, time, struct
from ctypes import wintypes

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
COMP = int(sys.argv[3], 16)
NP = BASE + 0x9D81450          # FNamePool (this build)

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

def cname(o):
    c = clsof(o)
    if not looks(c): return "?"
    nb = rd(c + 0x20, 4)
    return fn(u32(nb)) if nb else "?"

def props(cls):
    """yield (name, offset, propClassName) walking the UStruct chain (ChildProperties@+0x58, Next@+0x18)."""
    d = 0
    while looks(cls) and d < 24:
        f = u64(rd(cls + 0x58, 8) or b"\0" * 8); n = 0
        while looks(f) and n < 2000:
            nb = rd(f + 0x20, 4); ob = rd(f + 0x44, 4)
            if nb and ob:
                yield fn(u32(nb)), u32(ob), cname(f)
            f = u64(rd(f + 0x18, 8) or b"\0" * 8); n += 1
        cls = u64(rd(cls + 0x48, 8) or b"\0" * 8)   # SuperStruct
        d += 1

def findprop(cls, want):
    for nm, off, _ in props(cls):
        if nm == want:
            return off
    return None

cc = clsof(COMP)
print("component 0x%X  class=%s" % (COMP, cname(COMP)))

# ---- 1. the anim instance -------------------------------------------------
aoff = findprop(cc, "AnimScriptInstance")
inst = 0
if aoff is not None:
    v = rd(COMP + aoff, 8)
    inst = u64(v) if v else 0
print("AnimScriptInstance@0x%s = 0x%X (%s)" % (("%X" % aoff) if aoff is not None else "?",
                                               inst, cname(inst) if looks(inst) else "-"))

# AnimationData (FSingleAnimationPlayData) — what asset SingleNode was told to play
doff = findprop(cc, "AnimationData")
if doff is not None:
    blob = rd(COMP + doff, 0x20)
    if blob:
        anim = u64(blob, 0)
        print("AnimationData@0x%X: AnimToPlay=0x%X (%s) looping=%d playing=%d pos=%.3f rate=%.3f" % (
            doff, anim, cname(anim) if looks(anim) else "-",
            blob[0x08], blob[0x09], struct.unpack_from("<f", blob, 0x0C)[0],
            struct.unpack_from("<f", blob, 0x10)[0]))

# time-ish floats on the anim instance
tcands = []
if looks(inst):
    ic = clsof(inst)
    for nm, off, _ in props(ic):
        if nm in ("CurrentTime", "Position", "PlayRate", "bPlaying", "bLooping", "CurrentAsset"):
            tcands.append((nm, off))
    print("anim-instance fields:", ", ".join("%s@0x%X" % t for t in tcands) or "(none matched)")

def sample():
    out = {}
    if looks(inst):
        for nm, off in tcands:
            b = rd(inst + off, 8)
            if not b: continue
            if nm in ("bPlaying", "bLooping"):
                out[nm] = b[0]
            elif nm == "CurrentAsset":
                out[nm] = "0x%X" % u64(b)
            else:
                out[nm] = round(struct.unpack_from("<f", b, 0)[0], 4)
    # bone transforms: USkeletalMeshComponent has TArray<FTransform> ComponentSpaceTransformsArray[2].
    # We don't need its exact offset — hash a window of the component that contains pose data by walking the
    # two known TArrays if we can find them by property name; else fall back to bounds.
    for arr in ("BoneSpaceTransforms", "ComponentSpaceTransforms"):
        o = findprop(cc, arr)
        if o is None: continue
        hdr = rd(COMP + o, 16)
        if not hdr: continue
        data = u64(hdr, 0); num = u32(hdr, 8)
        if looks(data) and 0 < num < 4096:
            blob = rd(data, min(num, 24) * 0x60)
            if blob:
                out[arr] = "n=%d h=%08X" % (num, (hash(blob) & 0xFFFFFFFF))
    return out

s1 = sample()
time.sleep(2.0)
s2 = sample()

print("\n--- sample A ---"); [print("  %-26s %s" % (kk, vv)) for kk, vv in s1.items()]
print("--- sample B (+2s) ---"); [print("  %-26s %s" % (kk, vv)) for kk, vv in s2.items()]

moved = [kk for kk in s1 if kk in s2 and s1[kk] != s2[kk]]
print("\nCHANGED over 2s: %s" % (", ".join(moved) if moved else "(nothing)"))
print("VERDICT: %s" % ("ANIMATION IS PLAYING — the skeleton is being posed (NOT bind/T-pose)"
                       if moved else "NO CHANGE — pose is static (bind/T-pose or paused)"))
