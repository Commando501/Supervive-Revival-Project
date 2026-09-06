# netcache_chain.py — S85. Build the CLIENT's cumulative FClassNetCache index space for a
# character (or any) class, walking the FULL inheritance chain, and diff it against the stub's
# per-tier (reps, funcs) counts to pinpoint a "ReceivedBunch: Invalid replicated field N" desync.
#
# WHY THIS EXISTS
# --------------
# S84 possess-a-Loki-character succeeds server-side (spawn+possess+"Join succeeded") but the stub
# then closes the channel on `Invalid replicated field 32 in LokiMinionCharacter`. Two blind fixes
# failed because the diff was never actually a diff: only the STUB's cumulative index space was
# computed (Actor 11/0 | Pawn 3/0 | Character 10/7 | LokiCharacter 2/14 @ base 31 => idx32 =
# CustomAnimationState) and the client's was ASSUMED identical. "Invalid field 32" MEANS the two
# index spaces disagree, so the client's 32 is by definition something else. This tool computes the
# CLIENT side the same way the stub's DumpClassNetCacheLayout does (Loki.cpp:1080), so the FIRST
# tier whose (reps,funcs) differ is visible directly.
#
# HOW GetClassNetCache / DumpClassNetCacheLayout INDEXES (must match exactly):
#   - Recurse to super FIRST; a class level's FieldsBase = Super->GetMaxIndex().
#   - Then this level's OWN replicated properties, ONE index each (ArrayDim collapsed — Loki.cpp:1118).
#   - Then this level's OWN net functions (FUNC_Net, non-override), name-sorted (case-insensitive).
#   - GetMaxIndex() for the level = base + own_reps + own_funcs; that is the next level's base.
#
# The failing field 32 is at/below LokiCharacter (base 31, its 2 props occupy 31..32), i.e. entirely
# within Actor/Pawn/Character/LokiCharacter — all loaded AT THE MENU (S84), so a menu capture suffices
# (no DS session needed). It still walks to the leaf if that class is loaded.
#
# OFFSETS (this build; identical to find_uclass.py / rep_expand_class.py / netfields_dump.py):
#   UObject: Class@+0x18  Name@+0x20
#   UStruct: SuperStruct@+0x48  Children(UField*)@+0x50  ChildProperties(FField*)@+0x58
#   UField:  Next@+0x30
#   FField:  Class@+0x08  Next@+0x18  Name@+0x20  ArrayDim@+0x30  PropertyFlags@+0x38(u64)
#   UFunction: FunctionFlags@+0xB8(u32)   (SuperStruct@+0x48 non-null => override, excluded)
#   Globals: NAMEPOOL=BASE+0x9D81450  OBJOBJECTS=BASE+0x9E38930
#
#   usage: netcache_chain.py <PID> <BASE-hex> <LeafClassName | 0xClassAddr>
#   e.g.:  netcache_chain.py 12345 0x7FF6AF000000 LokiMinionCharacter
#          netcache_chain.py 12345 0x7FF6AF000000 LokiCharacter          (field-32 lives here or above)
#          netcache_chain.py 12345 0x7FF6AF000000 0x2960876XXXX          (skip the name scan)
import ctypes, sys
from ctypes import wintypes
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # console may be cp1252
except Exception: pass

if len(sys.argv) < 4:
    print("usage: netcache_chain.py <PID> <BASE-hex> <LeafClassName | 0xClassAddr>"); sys.exit(1)
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); LEAF=sys.argv[3]
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930
PERCHUNK=65536; STRIDE=0x18

k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
if not h:
    print(f"OpenProcess failed for PID {PID} (err {ctypes.get_last_error()}). Elevated? Right PID?"); sys.exit(1)

def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u16(b,o): return int.from_bytes(b[o:o+2],"little")
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def p(a):
    b=rpm(a,8); return u64(b,0) if b else 0
_nc={}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8); r="?"
    if bp:
        bp=int.from_bytes(bp,"little")
        if looksptr(bp):
            hd=rpm(bp+off,2)
            if hd:
                hd=int.from_bytes(hd,"little"); ln=hd>>6; wide=hd&1
                if 0<ln<200:
                    s=rpm(bp+off+2,ln*(2 if wide else 1))
                    if s: r=("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace"))
    _nc[idx]=r; return r
def oname(o):
    b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def ocls(o):
    c=p(o+0x18); return oname(c) if looksptr(c) else "?"

CPF_Net=0x20
FUNC_Net=0x40; FUNC_NetReliable=0x80; FUNC_Native=0x400
FUNC_NetMulticast=0x4000; FUNC_NetServer=0x200000; FUNC_NetClient=0x1000000
def netdir(fl):
    d=[]
    if fl&FUNC_NetServer: d.append("Server")
    if fl&FUNC_NetClient: d.append("Client")
    if fl&FUNC_NetMulticast: d.append("Multicast")
    if fl&FUNC_NetReliable: d.append("Reliable")
    return ",".join(d) if d else "?"

# ---- locate the leaf class object ----
def find_class(name):
    hdr=rpm(OBJOBJECTS,0x18)
    if not hdr: return []
    objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
    numChunks=(numEl+PERCHUNK-1)//PERCHUNK
    chunkPtrs=rpm(objectsPtr,numChunks*8); hits=[]
    for ci in range(numChunks):
        chunk=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
        if not looksptr(chunk): continue
        cnt=min(PERCHUNK,numEl-ci*PERCHUNK)
        items=rpm(chunk,cnt*STRIDE)
        if not items: continue
        for j in range(cnt):
            obj=u64(items,j*STRIDE)
            if not looksptr(obj): continue
            nb=rpm(obj+0x20,4)
            if not nb: continue
            if fname(u32(nb,0))==name and ocls(obj)=="Class":
                hits.append(obj)
    return hits

if LEAF.lower().startswith("0x"):
    leaf=int(LEAF,16)
else:
    hits=find_class(LEAF)
    if not hits:
        print(f"class '{LEAF}' NOT FOUND in GUObjectArray. If it is a match-only class "
              f"(e.g. LokiMinionCharacter), capture from a live DS session, or diagnose field 32 "
              f"against 'LokiCharacter' which is menu-loaded.")
        sys.exit(2)
    if len(hits)>1:
        print(f"warning: {len(hits)} classes named '{LEAF}', using first: "+", ".join(hex(x) for x in hits))
    leaf=hits[0]
    print(f"resolved {LEAF} -> UClass 0x{leaf:X}")

# ---- build the super chain root..leaf via SuperStruct@+0x48 ----
chain=[]; c=leaf; guard=0
while looksptr(c) and guard<40:
    chain.append(c); c=p(c+0x48); guard+=1
chain.reverse()   # root (UObject) .. leaf
print("chain (root..leaf): "+" -> ".join(oname(x) for x in chain))
print()

# ---- per-level own reps / own net funcs, exactly like DumpClassNetCacheLayout ----
def own_reps(cls):
    """Own CPF_Net properties, one entry per property (ArrayDim collapsed). Returns list of (name,arraydim)."""
    out=[]; f=p(cls+0x58); i=0
    while looksptr(f) and i<512:
        fb=rpm(f+0x38,8)
        fl=u64(fb,0) if fb else 0
        if fl & CPF_Net:
            nm=fname(u32(rpm(f+0x20,4) or b'\0\0\0\0',0))
            ad=u32(rpm(f+0x30,4) or b'\1\0\0\0',0) or 1
            out.append((nm,ad))
        f=p(f+0x18); i+=1
    return out
def own_netfuncs(cls):
    """Own FUNC_Net, non-override functions, name-sorted (case-insensitive) — the NetFields set."""
    out=[]; f=p(cls+0x50); i=0
    while looksptr(f) and i<800:
        if ocls(f)=="Function":
            fl=u32(rpm(f+0xB8,4) or b'\0\0\0\0',0)
            if fl & FUNC_Net:
                override = looksptr(p(f+0x48))   # SuperStruct non-null => override of a base net fn
                if not override:
                    out.append((oname(f),fl))
        f=p(f+0x30); i+=1
    out.sort(key=lambda x:x[0].lower())
    return out

# ---- emit cumulative index space + collect per-tier (reps,funcs) ----
idx=0
levels=[]   # (name, base, [repnames], [funcnames])
FIELD_LINES=[]  # (globalindex, kind, name, level)
for cls in chain:
    nm=oname(cls); base=idx
    reps=own_reps(cls); funcs=own_netfuncs(cls)
    levels.append((nm,base,reps,funcs))
    print(f"=== {nm}  base={base}  ownReps={len(reps)}  ownNetFuncs={len(funcs)}  -> GetMaxIndex={base+len(reps)+len(funcs)} ===")
    for pn,ad in reps:
        tag=f"{pn}" + (f" [ArrayDim={ad}!]" if ad!=1 else "")
        print(f"   [{idx:3}] PROP  {tag}")
        FIELD_LINES.append((idx,"PROP",pn,nm)); idx+=1
    for fnm,fl in funcs:
        print(f"   [{idx:3}] FUNC  {fnm:40} [{netdir(fl)}]")
        FIELD_LINES.append((idx,"FUNC",fnm,nm)); idx+=1
print(f"\n=== CLIENT GetMaxIndex(leaf) = {idx} ===\n")

# ---- what is at each interesting index ----
def at(i):
    for gi,kind,name,lvl in FIELD_LINES:
        if gi==i: return f"{kind} {name} ({lvl})"
    return "<out of range>"
for probe in (31,32,33):
    print(f"CLIENT field [{probe}] = {at(probe)}")

# ---- auto-diff vs the stub's known per-tier counts (S84 boot DumpClassNetCacheLayout) ----
# Reference = what the stub currently emits. Keyed by class name. (reps, funcs).
# Verify against the LIVE stub boot log 'NetCacheDump: --- <Class> ... ClassReps=.. NetFields=..'
# if the mirror has changed since S84.
#
# ★ S85 LIVE MEASUREMENT (client PID 40736, base 0x7FF6AF000000) — CLIENT TRUTH, cross-verified:
#   Character     client = (12,7)  <-- stub 10 is WRONG (SUPERVIVE dropped RepRootMotion, added
#                                       ReplicatedCharacterMovement + ReplicatedGravityScale => 12 reps)
#   LokiCharacter client = (13,14) <-- stub 2 was a TOOL-CAP BUG: rep_expand_class.py's i<40 walk saw
#                                       only 2 of 13 CPF_Net props (the other 11 are at child pos 49..158).
# The Character +2 is what fires "Invalid replicated field 32": client field 32 = ServerMovePacked
# (Character's name-sorted-last net func), stub field 32 = CustomAnimationState (LokiCharacter prop).
STUB_REF = {
    "Object":                 (0,0),
    "Actor":                  (11,0),   # includes the injected FPoolableActorServerState @ RepIndex 10
    "Pawn":                   (3,0),
    "Character":              (10,7),    # STUB current (stock UE5.4 minus RepRootMotion). CLIENT = (12,7).
    "LokiActor":              (0,0),     # skipped by the mirror (derives from stock ACharacter); client tier = 0/0
    "LokiCharacter":          (2,14),    # STUB current mirror. CLIENT = (13,14)  (S84's "2" = cap bug).
    "LokiHeroCharacter":      None,      # abstract; not in the possess chain
    "LokiMinionCharacter":    (3,1),
}
print("\n=== per-tier diff: CLIENT (measured) vs STUB (S84 reference) ===")
print(f"  {'tier':24} {'client(reps,funcs)':22} {'stub(reps,funcs)':20} verdict")
first_div=None
# stub's cumulative base, walked in the same order, skipping tiers the mirror doesn't have (LokiActor)
stub_idx=0
for nm,base,reps,funcs in levels:
    cli=(len(reps),len(funcs))
    ref=STUB_REF.get(nm,"?")
    if ref is None:
        v="(abstract / n/a)"
    elif ref=="?":
        v="?? no stub reference — ADD IT"
    elif tuple(ref)==cli:
        v="match"
    else:
        v=f"*** DIVERGE ***"
        if first_div is None: first_div=(nm,cli,tuple(ref),base)
    print(f"  {nm:24} {str(cli):22} {str(ref):20} {v}")

print()
if first_div:
    nm,cli,ref,base=first_div
    dr=cli[0]-ref[0]; df=cli[1]-ref[1]
    print(f"*** FIRST DIVERGENT TIER: {nm} -- client={cli} stub={ref} (d_reps={dr:+d} d_funcs={df:+d}) ***")
    print(f"    This tier's own fields start at CLIENT base index {base}. Every field at/after {base} is")
    print(f"    shifted by {dr+df:+d} on the wire relative to the stub -> the stub misreads the client's")
    print(f"    field indices from here down. FIX: make the stub mirror's '{nm}' tier own {cli[0]} reps +")
    print(f"    {cli[1]} net funcs (currently {ref[0]}+{ref[1]}). Re-run after the mirror change to confirm.")
else:
    print("No tier diverges from the S84 stub reference. If the live stub still errors, EITHER the stub")
    print("reference above is stale (check the live boot NetCacheDump) OR the desync is a per-field WIRE")
    print("format issue (enum bit-width / struct element format) at the matching index, not an index shift.")
