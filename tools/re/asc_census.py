# asc_census.py -- S111 TASK ONE, step 1. Do GAME-SPAWNED pawns have an ability system?
# READ-ONLY RPM. No injection, no writes, no thread suspension.
#
#   usage: asc_census.py [PID|auto] [BASE|auto] [--hero 0x...]
#
# WHY. The force-open hero moves and animates but owns no ability system: the shim's own [GAS] block
# drives LokiPlayerState's wiring chain, resolves GetHeroAsset (BP_HeroAsset_Ronin_C) fine, and still
# reports all three storage slots NULL and "RESULT: initialised 0 -> 0 *** STILL NOT INITIALISED ***".
# The cheapest thing that halves the problem is to look at pawns WE did not spawn:
#
#   * game-spawned pawns HAVE an ASC and ours does not  => the SPAWN PATH is the difference, and the
#     route is ALokiGameMode::SpawnPlayer (Angelscript, decompiled) rather than our SpawnActorCls;
#   * NOTHING in the world has one                      => the ability system is not running in this
#     mode at all, and the target moves to whatever gates it. Copying a spawn path would be wasted.
#
# INSTRUMENT NOTES (memory/supervive-instrument-artifact-pattern.md -- 16+ instances, and S110 added
# three). Everything here is arranged so a null result cannot be an artifact of my own reading:
#   1. The property offset is resolved BY NAME per class, never hardcoded. A class that does not carry
#      the property is reported as "no such property", NOT as "null" -- those are different facts.
#   2. The resolved offset is PRINTED, so it can be checked against the shim's independently-derived
#      "[GAS] AbilitySystemComponentStorage @0xF00".
#   3. An INDEPENDENT witness runs alongside: a census of live AbilitySystemComponent OBJECTS and how
#      many have OwnerActor/AvatarActor set (what InitAbilityActorInfo populates). If pawns all read
#      null but hundreds of initialised ASCs exist, the storage is a cache and my read is not the story.
#   4. If the sweep finds no pawns at all, that is reported as INCONCLUSIVE, not as "no pawn has an ASC".
import ctypes, sys
from ctypes import wintypes

PROCNAME = "SUPERVIVE-Win64-Shipping.exe"
RVA_NAMEPOOL, RVA_OBJOBJECTS = 0x9D81450, 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF = 0x18, 0x20          # NON-STANDARD in this build (stock 0x10/0x18)
SUPER_OFF, CHILDPROPS_OFF = 0x48, 0x58
FIELD_NEXT, FPROP_NAME, FPROP_OFFSET = 0x18, 0x20, 0x44
STORAGE = ("AbilitySystemComponentStorage", "AttributeSetStorage", "AttributeSetHealthStorage")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

class PE32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]
class ME32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
                ("szModule", wintypes.WCHAR * 256), ("szExePath", wintypes.WCHAR * 260)]

def autopid():
    s = k32.CreateToolhelp32Snapshot(0x2, 0)
    if s == wintypes.HANDLE(-1).value: return None
    e = PE32W(); e.dwSize = ctypes.sizeof(PE32W); ok = k32.Process32FirstW(s, ctypes.byref(e)); f = None
    while ok:
        if e.szExeFile == PROCNAME: f = e.th32ProcessID; break
        ok = k32.Process32NextW(s, ctypes.byref(e))
    k32.CloseHandle(s); return f

def autobase(pid):
    s = k32.CreateToolhelp32Snapshot(0x18, pid)
    if s == wintypes.HANDLE(-1).value: return None
    e = ME32W(); e.dwSize = ctypes.sizeof(ME32W); ok = k32.Module32FirstW(s, ctypes.byref(e)); b = None
    while ok:
        if e.szModule == PROCNAME: b = ctypes.cast(e.modBaseAddr, ctypes.c_void_p).value; break
        ok = k32.Module32NextW(s, ctypes.byref(e))
    k32.CloseHandle(s); return b

args = [a for a in sys.argv[1:] if not a.startswith("--")]
HERO = 0
for i, a in enumerate(sys.argv):
    if a == "--hero" and i + 1 < len(sys.argv): HERO = int(sys.argv[i + 1], 16)
PID = autopid() if (not args or args[0] == "auto") else int(args[0], 0)
if not PID: print("could not find '%s' -- is the game running?" % PROCNAME); sys.exit(1)
BASE = autobase(PID) if (len(args) < 2 or args[1] == "auto") else int(args[1], 16)
if not BASE: print("could not resolve module base"); sys.exit(1)

h = k32.OpenProcess(0x0410, False, PID) or k32.OpenProcess(0x1F0FFF, False, PID)
if not h: print("OpenProcess failed -- run elevated"); sys.exit(2)
_got = ctypes.c_size_t(0)

def rd(a, n):
    if not a or n <= 0: return None
    b = (ctypes.c_ubyte * n)()
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(_got)) or _got.value != n:
        return None
    return bytes(b)
def u32(b, o=0): return int.from_bytes(b[o:o+4], "little")
def u64(b, o=0): return int.from_bytes(b[o:o+8], "little")
def looks(v): return 0x10000 <= v < 0x0001_0000_0000_0000
def p(a):
    b = rd(a, 8); return u64(b) if b else 0

_nc = {}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk, off = idx >> 16, (idx & 0xFFFF) << 1
    r = "?"; bp = rd(BASE + RVA_NAMEPOOL + blk * 8, 8)
    if bp:
        bp = u64(bp)
        if looks(bp):
            hd = rd(bp + off, 2)
            if hd:
                hd = int.from_bytes(hd, "little"); ln, wide = hd >> 6, hd & 1
                if 0 < ln < 200:
                    s = rd(bp + off + 2, ln * (2 if wide else 1))
                    if s: r = ("".join(chr(s[i*2] | (s[i*2+1] << 8)) for i in range(ln))
                               if wide else s.decode("latin1", "replace"))
    _nc[idx] = r; return r
def oname(o):
    b = rd(o + NAME_OFF, 4); return fname(u32(b)) if b else "?"

# ---- per-class caches: ~188k objects but only a few thousand distinct classes ------------------
_cname, _chain, _poff = {}, {}, {}
def cname(c):
    r = _cname.get(c)
    if r is None: r = _cname[c] = oname(c)
    return r
def chain(c):
    """class-name chain up the SuperStruct links."""
    r = _chain.get(c)
    if r is not None: return r
    out, cur, d = [], c, 0
    while looks(cur) and d < 24:
        out.append(cname(cur)); cur = p(cur + SUPER_OFF); d += 1
    _chain[c] = out; return out
def propoff(c, want):
    """offset of a named UPROPERTY over the whole super chain, or None. Resolved BY NAME."""
    key = (c, want)
    r = _poff.get(key)
    if r is not None: return r if r >= 0 else None
    cur, d = c, 0
    while looks(cur) and d < 24:
        f, n = p(cur + CHILDPROPS_OFF), 0
        while looks(f) and n < 3000:
            nb, ob = rd(f + FPROP_NAME, 4), rd(f + FPROP_OFFSET, 4)
            if nb and ob and fname(u32(nb)) == want:
                _poff[key] = u32(ob); return u32(ob)
            f = p(f + FIELD_NEXT); n += 1
        cur = p(cur + SUPER_OFF); d += 1
    _poff[key] = -1; return None

def is_pawnlike(c):
    """An ancestor must BE UE's Pawn or Character class.

    ⚠ The first version of this tested `"Character" in n` over the chain, and the run at 18:45 duly
    reported "0 of 107 pawn-like actors have an ASC" -- with a denominator made of UMG widgets
    (WBP_UI_CharacterNameplate_*), components (CharacterMovementComponent, LokiCharacterSpringArmComponent)
    and subsystems, because their OWN leaf names contain "Character". Only two entries were real pawns.
    A substring test on a leaf name is not an inheritance test; exact-match the ancestor instead."""
    return any(n == "Pawn" or n == "Character" for n in chain(c))

# ================================================================================================
print("=" * 100)
print("asc_census   pid=%d  base=0x%X%s" % (PID, BASE, ("  hero=0x%X" % HERO) if HERO else ""))
print("=" * 100)
hdr = rd(BASE + RVA_OBJOBJECTS, 0x18)
if not hdr: print("FUObjectArray does not parse -- wrong base?"); sys.exit(1)
objectsPtr, numEl = u64(hdr, 0), u32(hdr, 0x14)
if not looks(objectsPtr) or not (0 < numEl < 8_000_000): print("header looks wrong"); sys.exit(1)
nchunks = (numEl + PERCHUNK - 1) // PERCHUNK
cptr = rd(objectsPtr, nchunks * 8)
print("objects=0x%X numElements=%d chunks=%d" % (objectsPtr, numEl, nchunks))

pawns, ascs, companions = [], [], []
live = 0
for ci in range(nchunks):
    chunk = u64(cptr, ci * 8)
    if not looks(chunk): continue
    cnt = min(PERCHUNK, numEl - ci * PERCHUNK)
    blob = rd(chunk, cnt * STRIDE)          # one RPM per chunk, not per object
    if blob is None: continue
    for j in range(cnt):
        o = u64(blob, j * STRIDE)
        if not looks(o): continue
        live += 1
        hb = rd(o + CLASS_OFF, (NAME_OFF - CLASS_OFF) + 4)   # class ptr + name id in ONE read
        if not hb: continue
        c = u64(hb, 0)
        if not looks(c): continue
        nm = fname(u32(hb, NAME_OFF - CLASS_OFF))
        if nm.startswith("Default__"): continue              # CDOs are not spawned pawns
        cn = cname(c)
        if "AbilitySystemComponent" in cn: ascs.append((o, c, cn, nm)); continue
        if cn.startswith("LokiPlayerState_") or "PlayerState_HeroAffiliated" in cn:
            companions.append((o, cn, nm)); continue
        if is_pawnlike(c): pawns.append((o, c, cn, nm))
print("live objects=%d   pawn-like=%d   ASC objects=%d   PlayerState companions=%d"
      % (live, len(pawns), len(ascs), len(companions)))

# ---- 1. PAWNS --------------------------------------------------------------------------------
print()
print("--- 1. PAWN-LIKE ACTORS and their ability-system storage --------------------------------")
if not pawns:
    print("   NO pawn-like actors live in this process.")
    print("   => INCONCLUSIVE for the S111 question. This is a fact about the world being empty,")
    print("      NOT about pawns lacking an ASC. Re-run inside a staged tutorial world.")
else:
    groups, offs_seen = {}, {}
    for (o, c, cn, nm) in pawns:
        off = propoff(c, STORAGE[0])
        if off is None:
            key = (cn, "NO SUCH PROPERTY"); groups.setdefault(key, []).append((o, nm, None)); continue
        offs_seen[cn] = off
        v = p(o + off)
        groups.setdefault((cn, "storage"), []).append((o, nm, v))
    nonnull = 0
    for (cn, kind) in sorted(groups):
        lst = groups[(cn, kind)]
        if kind == "NO SUCH PROPERTY":
            print("   %-46s x%-4d  (class has no %s)" % (cn, len(lst), STORAGE[0]))
            continue
        nn = [x for x in lst if x[2]]
        nonnull += len(nn)
        print("   %-46s x%-4d  @0x%X  non-null: %d/%d" % (cn, len(lst), offs_seen[cn], len(nn), len(lst)))
        for (o, nm, v) in lst[:3]:
            tag = "  <== OUR HERO" if (HERO and o == HERO) else ""
            extra = ""
            if v:
                extra = "  -> 0x%X (%s)" % (v, cname(p(v + CLASS_OFF)) if looks(p(v + CLASS_OFF)) else "?")
            print("        0x%X %-34s storage=%s%s%s" % (o, nm[:34], ("0x%X" % v) if v else "NULL", extra, tag))
    print()
    print("   pawn-like actors with a NON-NULL %s : %d of %d" % (STORAGE[0], nonnull, len(pawns)))

# ---- 2. INDEPENDENT WITNESS: the ASC objects themselves ---------------------------------------
print()
print("--- 2. INDEPENDENT WITNESS: live AbilitySystemComponent objects -------------------------")
print("   (storage on the pawn is only a CACHE -- S100. These are the real objects.)")
if not ascs:
    print("   NONE. No AbilitySystemComponent object is live anywhere in this process.")
else:
    ownOff = avaOff = None
    for (o, c, cn, nm) in ascs:
        ownOff = propoff(c, "OwnerActor"); avaOff = propoff(c, "AvatarActor")
        if ownOff is not None: break
    if ownOff is None:
        print("   %d live ASC objects, but OwnerActor/AvatarActor did NOT resolve by name." % len(ascs))
        print("   => init state UNRESOLVED (reported, not guessed).")
    else:
        init, ex = 0, []
        for (o, c, cn, nm) in ascs:
            ow, av = p(o + ownOff), p(o + avaOff)
            if looks(ow) or looks(av):
                init += 1
                if len(ex) < 5: ex.append((o, cn, ow, av))
        print("   live non-CDO ASC objects              : %d" % len(ascs))
        print("   ...with OwnerActor or AvatarActor set : %d   (OwnerActor@0x%X AvatarActor@0x%X)"
              % (init, ownOff, avaOff))
        for (o, cn, ow, av) in ex:
            print("      0x%X %-38s Owner=0x%X (%s)  Avatar=0x%X" %
                  (o, cn, ow, cname(p(ow + CLASS_OFF)) if looks(ow) else 0, av))
        # ---- 2b. WHO owns them, and is any of them OURS? -------------------------------------
        # The first sweep showed 344 initialised ASCs all owned by scenery (BP_PineTree_ScavBay_C).
        # "The ability system runs here" is true but nearly vacuous if only destructibles use it, so
        # group by owner class, and call out anything hero- or PlayerState-shaped explicitly.
        byowner, ours = {}, []
        for (o, c, cn, nm) in ascs:
            ow, av = p(o + ownOff), p(o + avaOff)
            if not (looks(ow) or looks(av)): continue
            a = ow if looks(ow) else av
            ocn = cname(p(a + CLASS_OFF)) if looks(p(a + CLASS_OFF)) else "?"
            byowner[ocn] = byowner.get(ocn, 0) + 1
            if (HERO and (ow == HERO or av == HERO)) or "PlayerState" in ocn or "HERO" in ocn.upper():
                ours.append((o, cn, a, ocn))
        print("\n   initialised ASCs by OWNER class:")
        for ocn in sorted(byowner, key=lambda x: -byowner[x])[:12]:
            print("      %-46s x%d" % (ocn, byowner[ocn]))
        print("\n   ASCs owned by a HERO or a PlayerState: %d" % len(ours))
        for (o, cn, a, ocn) in ours[:6]:
            print("      ASC 0x%X (%s)  owner 0x%X (%s)" % (o, cn, a, ocn))
        if not ours:
            print("      NONE -- every initialised ability system in this world belongs to something")
            print("      that is not a hero or a player. The init path being exercised is the")
            print("      destructible/scenery one, which may not be the hero path at all.")

# ---- 3. the PlayerState companions ------------------------------------------------------------
print()
print("--- 3. LokiPlayerState_* companion actors (the real GAS owner, per S100) ----------------")
seen = {}
for (o, cn, nm) in companions: seen[cn] = seen.get(cn, 0) + 1
if seen:
    for cn in sorted(seen): print("   %-46s x%d" % (cn, seen[cn]))
else:
    print("   none live.")

# ---- VERDICT ----------------------------------------------------------------------------------
print()
print("=" * 100)
if not pawns:
    print("VERDICT: INCONCLUSIVE -- no pawn-like actor exists here. Re-run in a staged tutorial world.")
else:
    nn = sum(1 for (o, c, cn, nm) in pawns
             if propoff(c, STORAGE[0]) is not None and p(o + propoff(c, STORAGE[0])))
    anyinit = 0
    if ascs:
        oo = None
        for (o, c, cn, nm) in ascs:
            oo = propoff(c, "OwnerActor")
            if oo is not None: break
        if oo is not None:
            av = propoff(ascs[0][1], "AvatarActor") or oo
            anyinit = sum(1 for (o, c, cn, nm) in ascs if looks(p(o + oo)) or looks(p(o + av)))
    if nn:
        print("VERDICT: SOME pawns DO carry an ability system (%d of %d)." % (nn, len(pawns)))
        print("  => the spawn path IS the difference if ours is among the nulls. Next: spawn through")
        print("     ALokiGameMode::SpawnPlayer instead of SpawnActorCls, and diff the two pawns.")
    elif ascs and anyinit:
        print("VERDICT: no pawn caches one, but %d of %d live ASC objects ARE initialised." % (anyinit, len(ascs)))
        print("  => the ability system RUNS here; the storage on the pawn is just an unpopulated cache.")
        print("     Next: find who owns those initialised ASCs (section 3) and copy that wiring.")
    elif ascs:
        print("VERDICT: %d ASC objects exist but NONE is initialised, and no pawn caches one." % len(ascs))
        print("  => dormant pool. Nothing in this world has ever run the init; we would be first.")
    else:
        print("VERDICT: no pawn carries one and NO ASC object exists at all in this process.")
        print("  => the ability system is not instantiated in this mode. Copying a spawn path would")
        print("     be wasted; the target is whatever gates ASC creation.")
print("=" * 100)
