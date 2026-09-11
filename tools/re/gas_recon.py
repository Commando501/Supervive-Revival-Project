# gas_recon.py — ONE-PASS reconnaissance of the force-open hero's GameplayAbilitySystem.
#
# S100. The question this answers: does the force-open hero already OWN a working ability system that merely needs
# initialising, or must the ability system be built from scratch? Sessions on this route die in seconds, so this
# collects everything in a single pass instead of over several launches.
#
# Sections:
#   A  ownership   — the hero's AbilitySystemComponentStorage / AttributeSetStorage / AttributeSetHealthStorage.
#                    Non-null => the actor's own constructor built them and we inherit them for free.
#   B  init state  — the ASC's OwnerActor / AvatarActor. These are exactly what InitAbilityActorInfo(owner, avatar)
#                    populates, and they ARE reflected, so "has GAS been initialised" is a direct read, not an
#                    inference. Plus the granted-ability and spawned-attribute counts.
#   C  values      — actual attribute numbers (FGameplayAttributeData = vtable@0x0, BaseValue@0x8, CurrentValue@0xC).
#                    All-zero means the init effect / curve table never applied.
#   D  ability data— the hero's Ability1/2/3 + AbilityDodgeRoll class properties: is the ability CONTENT even set?
#   E  callable API— UFunctions on the ASC class chain with a NATIVE thunk (Func@+0xE0), i.e. reachable through the
#                    project's ProcessInternal native-call primitive. This is the "what can we actually drive" list.
#   F  reference   — another live ASC in the same world (the actor pool primes hundreds). If NO ASC anywhere is
#                    initialised, we are chasing something this world never does; if some are, we have a template.
#
#   usage: gas_recon.py <PID> <BASE-hex> <heroHex>
#
# Offsets (this build): UObject Class@+0x18 Name@+0x20 | UStruct SuperStruct@+0x48 Children(UField*)@+0x50
#                       ChildProperties(FField*)@+0x58 | FField Next@+0x18 Name@+0x20 Offset@+0x44 BoolMask@+0x70
#                       UField.Next@+0x30 | UFunction FunctionFlags@+0xB8 Func@+0xE0
import ctypes, sys, struct
from ctypes import wintypes

PID  = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
HERO = int(sys.argv[3], 16)
NAMEPOOL   = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18

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
def looks(v):    return 0x10000 <= v < 0x0001000000000000
def p(a):        b = rd(a, 8); return u64(b) if b else 0
def f32(a):      b = rd(a, 4); return struct.unpack("<f", b)[0] if b else float("nan")

_nc = {}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk, off = idx >> 16, (idx & 0xFFFF) << 1
    r = "?"; bp = rd(NAMEPOOL + blk * 8, 8)
    if bp:
        bp = u64(bp)
        if looks(bp):
            hd = rd(bp + off, 2)
            if hd:
                hd = u32(hd + b"\0\0"); ln = hd >> 6; wide = hd & 1
                if 0 < ln < 200:
                    s = rd(bp + off + 2, ln * (2 if wide else 1))
                    if s: r = ("".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(ln))
                               if wide else s.decode("latin1", "replace"))
    _nc[idx] = r; return r

def oname(o):
    b = rd(o + 0x20, 4); return fname(u32(b)) if b else "?"
_cn = {}
def ocls(o):
    c = p(o + 0x18)
    if not looks(c): return "?"
    r = _cn.get(c)                      # cache by class pointer: the full-array sweep hits ~188k objects but
    if r is None:                       # only a few thousand distinct classes, so this removes most of the reads
        r = oname(c); _cn[c] = r
    return r
def desc(o):
    return ("0x%X (%s)" % (o, ocls(o))) if looks(o) else ("NULL" if o == 0 else "0x%X" % o)

def props(cls):
    """(name, offset, propClass) over the whole SuperStruct chain."""
    d = 0
    while looks(cls) and d < 24:
        f = p(cls + 0x58); n = 0
        while looks(f) and n < 3000:
            nb = rd(f + 0x20, 4); ob = rd(f + 0x44, 4)
            if nb and ob: yield fname(u32(nb)), u32(ob), ocls(f)
            f = p(f + 0x18); n += 1
        cls = p(cls + 0x48); d += 1

def pmap(cls):
    m = {}
    for nm, off, pc in props(cls):
        m.setdefault(nm, (off, pc))
    return m

def arr(base, off):
    """TArray<T> at base+off -> (dataPtr, Num, Max); (0,-1,-1) if implausible."""
    b = rd(base + off, 16)
    if not b: return (0, -1, -1)
    d, n, mx = u64(b, 0), int.from_bytes(b[8:12], "little", signed=True), int.from_bytes(b[12:16], "little", signed=True)
    if n < 0 or mx < n or mx > 1 << 20: return (0, -1, -1)
    return (d, n, mx)

def attrdata(base, off):
    """FGameplayAttributeData: vtable@0x0, BaseValue@0x8, CurrentValue@0xC."""
    return (f32(base + off + 8), f32(base + off + 0xC))

print("=" * 78)
print("GAS RECON — hero %s" % desc(HERO))
print("=" * 78)

hcls = p(HERO + 0x18)
hp = pmap(hcls)

# ---------------------------------------------------------------- A. ownership
print("\n--- A. OWNERSHIP (did the hero's own constructor build these?) ---")
asc = 0; sets = []
for want in ("AbilitySystemComponentStorage", "AttributeSetStorage", "AttributeSetHealthStorage",
             "AbilitySystemComponent", "AbilitySystem"):
    if want not in hp:
        print("   %-32s  <property not on this class chain>" % want); continue
    off, pc = hp[want]
    v = p(HERO + off)
    print("   %-32s @0x%04X  %s" % (want, off, desc(v)))
    if looks(v):
        if "AbilitySystemComponent" in ocls(v) and not asc: asc = v
        elif "AttributeSet" in ocls(v): sets.append(v)

# ------------------------------------------------------------- B. init state
print("\n--- B. INIT STATE (OwnerActor/AvatarActor are what InitAbilityActorInfo sets) ---")
if not looks(asc):
    print("   NO ASC on the hero -> section B/C/E reference the class only")
else:
    ap = pmap(p(asc + 0x18))
    for want in ("OwnerActor", "AvatarActor"):
        if want in ap:
            off, _ = ap[want]; v = p(asc + off)
            flag = "  <== INITIALISED" if looks(v) else "  <== NOT SET (InitAbilityActorInfo has not run)"
            print("   %-32s @0x%04X  %s%s" % (want, off, desc(v), flag))
        else:
            print("   %-32s  <not found>" % want)
    for want in ("SpawnedAttributes", "DefaultStartingData", "ActiveStartupEffects",
                 "AllReplicatedInstancedAbilities", "SpawnedTargetActors"):
        if want in ap:
            off, _ = ap[want]; d, n, mx = arr(asc, off)
            print("   %-32s @0x%04X  Num=%s" % (want, off, n if n >= 0 else "?"))
            if want == "SpawnedAttributes" and n > 0 and looks(d):
                for i in range(min(n, 8)):
                    e = p(d + i * 8)
                    print("        [%d] %s" % (i, desc(e)))
    # ActivatableAbilities is a FastArraySerializer struct; locate its inner TArray heuristically.
    if "ActivatableAbilities" in ap:
        off, _ = ap["ActivatableAbilities"]
        found = None
        for probe in range(0, 0x60, 8):
            d, n, mx = arr(asc, off + probe)
            if n >= 0 and mx > 0 and looks(d):
                found = (probe, n, mx); break
        print("   %-32s @0x%04X  %s" % ("ActivatableAbilities", off,
              ("Items Num=%d (inner +0x%X, heuristic)" % (found[1], found[0])) if found
              else "no populated inner TArray found -> 0 abilities granted"))

# ------------------------------------------------------------------ C. values
print("\n--- C. ATTRIBUTE VALUES (all-zero => the init effect / curve table never applied) ---")
if not sets:
    print("   no attribute sets to read")
for s in sets:
    sp = pmap(p(s + 0x18))
    want = [w for w in ("Health", "MaxHealth", "Shield", "MaxShield",
                        "Level", "MoveSpeed", "MaxMoveSpeed", "FogOfWarRadius") if w in sp]
    print("   %s" % desc(s))
    for w in want:
        off, _ = sp[w]; b, c = attrdata(s, off)
        print("        %-18s base=%-12.3f current=%.3f" % (w, b, c))

# ------------------------------------------------------------ D. ability data
print("\n--- D. ABILITY CONTENT on the hero (is the ability set even assigned?) ---")
n_ab = 0
for nm, off, pc in props(hcls):
    if ("Ability" in nm) and pc in ("ClassProperty", "ObjectProperty"):
        v = p(HERO + off)
        if looks(v) or nm in ("Ability1", "Ability2", "Ability3", "AbilityDodgeRoll"):
            print("   %-34s @0x%04X  %s" % (nm, off, desc(v)))
            n_ab += 1
    if n_ab >= 20: break
if not n_ab: print("   (none found)")

# --------------------------------------------------------- E. callable API
print("\n--- E. CALLABLE ASC API (native thunk => reachable via the ProcessInternal primitive) ---")
KEYS = ("init", "give", "grant", "activate", "input", "attribute", "applygameplayeffect",
        "abilityspec", "clearability", "refresh")
# ⚠ S100: this used to key off the hero's ASC INSTANCE, so when the hero had no ASC (which is the actual
# situation) the whole section silently printed nothing — exactly the case where the callable API matters most.
# Resolve the UClass by NAME instead, so the API list is available whether or not an instance exists.
cls = p(asc + 0x18) if looks(asc) else 0
if not cls:
    hdr0 = rd(OBJOBJECTS, 0x18)
    if hdr0:
        op, ne = u64(hdr0, 0), u32(hdr0, 0x14)
        if looks(op) and 0 < ne < 8000000:
            for ci in range((ne + PERCHUNK - 1) // PERCHUNK):
                cp = rd(op + ci * 8, 8)
                if not cp: break
                ch = u64(cp)
                if not looks(ch): continue
                c2 = ne - ci * PERCHUNK if ci == (ne + PERCHUNK - 1) // PERCHUNK - 1 else PERCHUNK
                bl = rd(ch, c2 * STRIDE)
                if bl is None: continue
                for j in range(c2):
                    o2 = u64(bl, j * STRIDE)
                    if looks(o2) and ocls(o2) == "Class" and oname(o2) == "LokiAbilitySystemComponent":
                        cls = o2; break
                if cls: break
    print("   (no ASC instance — listing the LokiAbilitySystemComponent CLASS API instead)")
shown = 0
d = 0
while looks(cls) and d < 8:
    cn = oname(cls)
    fld = p(cls + 0x50); n = 0
    while looks(fld) and n < 4000:
        if ocls(fld) == "Function":
            fn = oname(fld); low = fn.lower()
            if any(kw in low for kw in KEYS):
                thunk = p(fld + 0xE0)
                print("   %-46s %-28s thunk=%s" % (fn, cn, ("0x%X" % thunk) if thunk else "NONE (BP bytecode)"))
                shown += 1
        fld = p(fld + 0x30); n += 1
        if shown >= 40: break
    if shown >= 40: break
    cls = p(cls + 0x48); d += 1
if not shown: print("   (no matching functions — is the ASC pointer valid?)")

# ------------------------------------------------------------- F. reference
print("\n--- F/G. WORLD SWEEP: reference ASCs + the PlayerState companion actors ---")
# ★ S100: the hero's AbilitySystemComponentStorage is only a CACHE. schema.txt shows the real owner is
#   `LokiPlayerState_HeroAffiliated` — a companion ACTOR (same pattern as LokiPlayerState_Missions /
#   LokiPlayerState_Stats) carrying AbilitySystemComponent + AttributeSet + AttributeSetHealth + PlayerInventory.
#   So "does the hero have GAS" is really "does that companion actor exist and is it populated". One sweep
#   collects both that and the reference ASCs, because a second full pass costs more than the session has.
hdr = rd(OBJOBJECTS, 0x18)
tot = init = 0; examples = []
ps_companions = []          # LokiPlayerState_* actors
hero_affil = []             # LokiPlayerState_HeroAffiliated instances
healthy_asc = 0             # a fully-initialised ASC to use as a template
if hdr:
    objectsPtr, numEl = u64(hdr, 0), u32(hdr, 0x14)
    if looks(objectsPtr) and 0 < numEl < 8000000:
        chunks = (numEl + PERCHUNK - 1) // PERCHUNK
        ownOff = avaOff = None
        for ci in range(chunks):
            cp = rd(objectsPtr + ci * 8, 8)
            if not cp: break
            chunk = u64(cp)
            if not looks(chunk): continue
            cnt = numEl - ci * PERCHUNK if ci == chunks - 1 else PERCHUNK
            # Bulk-read the whole chunk's item array in one RPM. Per-object reads here would be ~188k syscalls
            # and take minutes — far longer than a force-open session survives.
            blob = rd(chunk, cnt * STRIDE)
            if blob is None: continue
            for j in range(cnt):
                o = u64(blob, j * STRIDE)
                if not looks(o): continue
                cn = ocls(o)
                if cn.startswith("LokiPlayerState_") or "PlayerState_HeroAffiliated" in cn:
                    if not oname(o).startswith("Default__"):
                        ps_companions.append((o, cn))
                        if "HeroAffiliated" in cn: hero_affil.append(o)
                    continue
                if "AbilitySystemComponent" not in cn: continue
                if oname(o).startswith("Default__"): continue
                if ownOff is None:
                    m = pmap(p(o + 0x18))
                    if "OwnerActor" not in m: continue
                    ownOff, avaOff = m["OwnerActor"][0], m["AvatarActor"][0]
                tot += 1
                ow, av = p(o + ownOff), p(o + avaOff)
                if looks(ow) or looks(av):
                    init += 1
                    if not healthy_asc: healthy_asc = o
                    if len(examples) < 4:
                        examples.append((o, ow, av))
print("   live non-CDO AbilitySystemComponents : %d" % tot)
print("   ...with OwnerActor or AvatarActor set: %d" % init)
for o, ow, av in examples:
    print("      %s  Owner=%s  Avatar=%s" % (desc(o), desc(ow), desc(av)))
print("\n   => %s" % ("SOME ability systems ARE initialised in this world — there is a working template to copy."
                      if init else
                      "NOTHING in this world has an initialised ability system (pool actors are dormant); "
                      "we would be the first to do it."))

print("\n--- G. THE PLAYER'S GAS CARRIER (LokiPlayerState_HeroAffiliated) ---")
seen = {}
for o, cn in ps_companions:
    seen[cn] = seen.get(cn, 0) + 1
if seen:
    for cn in sorted(seen): print("   live %-44s x%d" % (cn, seen[cn]))
else:
    print("   NO LokiPlayerState_* companion actors exist at all")
if hero_affil:
    for o in hero_affil[:3]:
        print("   %s" % desc(o))
        m = pmap(p(o + 0x18))
        for w in ("AbilitySystemComponent", "AttributeSet", "AttributeSetHealth", "PlayerInventory"):
            if w in m:
                off, _ = m[w]; v = p(o + off)
                print("        %-26s @0x%04X  %s" % (w, off, desc(v)))
            else:
                print("        %-26s  <not on class>" % w)
else:
    print("   => NO LokiPlayerState_HeroAffiliated instance exists — the carrier the hero's")
    print("      AbilitySystemComponentStorage would point at was never created.")

print("\n--- H. TEMPLATE: a healthy, initialised ASC to copy from ---")
if healthy_asc:
    m = pmap(p(healthy_asc + 0x18))
    print("   %s" % desc(healthy_asc))
    for w in ("OwnerActor", "AvatarActor"):
        if w in m: print("        %-26s %s" % (w, desc(p(healthy_asc + m[w][0]))))
    for w in ("SpawnedAttributes", "DefaultStartingData", "ActiveStartupEffects"):
        if w in m:
            d, n, mx = arr(healthy_asc, m[w][0])
            print("        %-26s Num=%s" % (w, n if n >= 0 else "?"))
            if w == "SpawnedAttributes" and n > 0 and looks(d):
                for i in range(min(n, 6)): print("             [%d] %s" % (i, desc(p(d + i * 8))))
    if "ActivatableAbilities" in m:
        off = m["ActivatableAbilities"][0]; found = None
        for probe in range(0, 0x60, 8):
            d, n, mx = arr(healthy_asc, off + probe)
            if n >= 0 and mx > 0 and looks(d): found = (probe, n); break
        print("        %-26s %s" % ("ActivatableAbilities",
              ("Items Num=%d (inner +0x%X)" % (found[1], found[0])) if found else "no populated inner TArray"))
else:
    print("   (none found)")
print("=" * 78)
