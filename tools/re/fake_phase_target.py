# fake_phase_target.py -- OFFLINE TEST HARNESS for tools/re/phase_readout.py.
# IT NEVER TOUCHES THE GAME. It allocates a fake ImageBase in ITS OWN process, builds a
# structurally faithful (but entirely synthetic) UE object graph there, and parks so the probe
# can attach to it. This is how phase_readout.py's SUCCESS path was validated with the game shut
# down -- a probe that first fails inside an armed tutorial window costs a whole launch, and only
# ~2 of 4 launches reach an armed window at all.
#
#   run the pair:
#     python tools/re/fake_phase_target.py 400000000 3            # terminal 1, prints READY + its pid
#     python tools/re/phase_readout.py <that-pid> 400000000       # terminal 2
#   add the word 'empty' to arg 3 to make the delegate + MatchStartDetails empty, which exercises
#   the "ARM A5 RUNNABLE: NO" branch. Vary the phase arg to exercise each gate verdict.
#
# It deliberately reproduces two real traps: an ARCHETYPE (Default__*) decoy sharing the GameMode
# class, and the FK-22 sec.9.1 DOUBLE "CurrentPhase" property (0xA44 and 0xF48).
import ctypes, sys, time
from ctypes import wintypes

BASE = int(sys.argv[1], 16)
PHASE = int(sys.argv[2]) if len(sys.argv) > 2 else 3

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
k32.VirtualAlloc.restype = ctypes.c_void_p
MEM_RESERVE, MEM_COMMIT, RW = 0x2000, 0x1000, 0x04

SPAN = 0x0A000000
r = k32.VirtualAlloc(ctypes.c_void_p(BASE), SPAN, MEM_RESERVE, RW)
if not r:
    print("reserve failed", ctypes.get_last_error()); sys.exit(1)


def commit(addr, n=0x2000):
    if not k32.VirtualAlloc(ctypes.c_void_p(addr), n, MEM_COMMIT, RW):
        print("commit failed at 0x%X" % addr, ctypes.get_last_error()); sys.exit(1)
    return addr


def wr(addr, data):
    ctypes.memmove(ctypes.c_void_p(addr), data, len(data))


def q(v): return int(v).to_bytes(8, "little", signed=False)
def d(v): return int(v).to_bytes(4, "little", signed=True)


KEEP = []


def buf(n):
    b = (ctypes.c_ubyte * n)()
    KEEP.append(b)
    return ctypes.addressof(b)


# ---- FName pool -------------------------------------------------------------------------------
NAMEPOOL = commit(BASE + 0x9D81450)
BLOCK = buf(0x20000)
wr(NAMEPOOL, q(BLOCK))
_cur = 2


def nm(s):
    global _cur
    off = _cur
    hdr = (len(s) << 6) | 0            # wide = 0 -> ASCII
    wr(BLOCK + off, hdr.to_bytes(2, "little") + s.encode("latin1"))
    _cur = (off + 2 + len(s) + 1) & ~1
    return off // 2                     # FName index (block 0)


# ---- object / class / property builders ---------------------------------------------------------
def obj(size, name, cls, vt=None):
    a = buf(size)
    wr(a, q(vt if vt else BASE + 0x1000))          # vtable (must be in-module for check (c))
    wr(a + 0x18, q(cls))
    wr(a + 0x20, d(nm(name)))
    return a


FIELDCLS = {}


def fieldcls(tyname):
    if tyname not in FIELDCLS:
        a = buf(0x20)
        wr(a, d(nm(tyname)))                       # ftype() reads the name index at +0x00
        FIELDCLS[tyname] = a
    return FIELDCLS[tyname]


def prop(name, ty, off):
    a = buf(0x90)
    wr(a + 0x08, q(fieldcls(ty)))
    wr(a + 0x20, d(nm(name)))
    wr(a + 0x44, d(off))
    return a


def mkclass(name, super_=0, props=()):
    c = buf(0x100)
    wr(c, q(BASE + 0x1000))
    wr(c + 0x18, q(0))
    wr(c + 0x20, d(nm(name)))
    wr(c + 0x48, q(super_))
    prev = None
    for pr in props:
        if prev is None:
            wr(c + 0x58, q(pr))
        else:
            wr(prev + 0x18, q(pr))
        prev = pr
    return c


# ---- the class hierarchy ------------------------------------------------------------------------
c_gmbase = mkclass("GameModeBase")
c_round = mkclass("LokiRoundGameMode", c_gmbase)
c_tut = mkclass("LokiTutorialGameMode", c_round)
c_bpgm = mkclass("BP_LokiGameMode_Tutorial_C", c_tut,
                 [prop("GameState", "ObjectProperty", 0x258)])

c_gsbase = mkclass("GameStateBase")
c_gs = mkclass("LokiGameState", c_gsbase, [
    prop("CurrentPhase", "ByteProperty", 0xA44),
    prop("OnRoundPhaseChanged", "MulticastInlineDelegateProperty", 0x590),
    prop("MatchStartDetails", "StrProperty", 0x738),
    prop("CurrentPhase", "ByteProperty", 0xF48),          # the FK-22 sec.9.1 AMBIGUITY, on purpose
])

c_world = mkclass("World", 0, [prop("AuthorityGameMode", "ObjectProperty", 0x180),
                               prop("GameState", "ObjectProperty", 0x188)])
c_pc = mkclass("LokiPlayerController")

# ---- the instances -------------------------------------------------------------------------------
GS = obj(0xC00, "BP_LokiGameState_Tutorial_C_0", c_gs)
GM = obj(0xC00, "BP_LokiGameMode_Tutorial_C_0", c_bpgm)
GM_CDO = obj(0xC00, "Default__BP_LokiGameMode_Tutorial_C", c_bpgm)   # archetype decoy
GS_CDO = obj(0xC00, "Default__LokiGameState", c_gs)
WORLD = obj(0x200, "LVL_Tutorial", c_world)
SUB = obj(0x100, "Comp_GameMode_DropPlane_Tutorial", c_pc)           # delegate subscriber

wr(GM + 0x258, q(GS))
wr(GM + 0x790, q(0))
wr(GM + 0x7B0, b"\x00")
wr(GM + 0x7C0, b"\x04")                                             # initializer Finished
wr(WORLD + 0x180, q(GM))
wr(WORLD + 0x188, q(GS))

wr(GS + 0xA44, bytes([PHASE]))

# OnRoundPhaseChanged: TArray<FScriptDelegate> stride 16 {UObject* Object; FName FunctionName}
ENTRIES = buf(0x40)
wr(ENTRIES, q(SUB) + d(nm("OnRoundPhaseChanged")) + d(0))
EMPTY = "empty" in sys.argv
wr(GS + 0x590, (q(0) + d(0) + d(0)) if EMPTY else (q(ENTRIES) + d(1) + d(1)))

# MatchStartDetails FString (UTF-16, Num counts the NUL)
S = "tutorial"
SBUF = buf(0x40)
wr(SBUF, (S + "\x00").encode("utf-16-le"))
wr(GS + 0x738, (q(0) + d(0) + d(0)) if EMPTY else (q(SBUF) + d(len(S) + 1) + d(len(S) + 1)))
wr(GS + 0x748, q(0) + d(0) + d(0))

# ---- FUObjectArray ------------------------------------------------------------------------------
ALL = [GS, GM, GM_CDO, GS_CDO, WORLD, SUB] + list(FIELDCLS.values()) + \
      [c_gmbase, c_round, c_tut, c_bpgm, c_gsbase, c_gs, c_world, c_pc]
CHUNK = buf(0x18 * (len(ALL) + 4))
for i, o in enumerate(ALL):
    wr(CHUNK + i * 0x18, q(o))
CHUNKTAB = buf(0x40)
wr(CHUNKTAB, q(CHUNK))

# ⚠⚠ FUObjectArray LAYOUT -- THIS BLOCK IS THE ONE THE FIRST DRAFT GOT WRONG, AND IT MATTERED.
# The harness originally put the element count at OUTER+0x18/+0x1C, i.e. a THIRD layout matching
# neither the probe nor the game. That is why it could not detect the probe's own NumElements
# defect: the test had ingested the error it exists to catch (method-rules rule 9). Ground truth,
# and what every sibling probe reads:
#
#   FUObjectArray (OUTER, base+0x9E38920)
#     +0x00 int32  ObjFirstGCIndex
#     +0x04 int32  ObjLastNonGCIndex
#     +0x08 int32  MaxObjectsNotConsideredByGC
#     +0x0C int32  OpenForDisregardForGC
#     +0x10 ...    FChunkedFixedUObjectArray ObjObjects   <-- base+0x9E38930, the INNER array
#            +0x00 (OUTER+0x10) FUObjectItem** Objects        <-- the chunk table
#            +0x08 (OUTER+0x18) FUObjectItem*  PreAllocatedObjects
#            +0x10 (OUTER+0x20) int32          MaxElements
#            +0x14 (OUTER+0x24) int32          NumElements     <-- THE COUNT
#            +0x18 (OUTER+0x28) int32          MaxChunks
#            +0x1C (OUTER+0x2C) int32          NumChunks
FUOBJ = commit(BASE + 0x9E38920)
_MAXEL = 65536 * 4
_NCHUNK = (len(ALL) + 65535) // 65536
wr(FUOBJ, d(39295) + d(39294) + d(45000) + d(0)                 # +0x00 .. +0x0F
          + q(CHUNKTAB) + q(0)                                   # +0x10 Objects, +0x18 PreAlloc
          + d(_MAXEL) + d(len(ALL))                              # +0x20 MaxElements, +0x24 NumElements
          + d(4) + d(_NCHUNK))                                   # +0x28 MaxChunks, +0x2C NumChunks

ROOT = commit(BASE + 0x99D3CA8 & ~0xFFF, 0x2000)
wr(BASE + 0x99D3CA8, d(64))
wr(BASE + 0x99D3CD4, d(32))       # Num() = 64-32 = 32, the S123 receipt

print("READY base=0x%X gm=0x%X gs=0x%X phase=%d objects=%d" % (BASE, GM, GS, PHASE, len(ALL)))
sys.stdout.flush()
time.sleep(45)
