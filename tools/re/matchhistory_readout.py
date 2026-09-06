# matchhistory_readout.py — read the PARSED FMatchHistory off the live UMatchHistoryManager.
# Read-only ReadProcessMemory. No injection, no .text write, no allocation in the target.
#
#   usage: matchhistory_readout.py <PID> <BASE-hex> [--stride 0x128]
#
# ---------------------------------------------------------------------------------------------
# WHY THIS EXISTS
# ---------------------------------------------------------------------------------------------
# `GET /match-history/players/{id}` is served by a nested 15-field struct, and on this client a
# nested struct fails SILENTLY: FJsonObjectConverter ignores unknown keys, drops array elements it
# cannot build, and logs nothing when it "parses fine and populates nothing". FK-5's latency chain
# survived a YEAR in exactly that state — six nested defects, zero errors logged — because the only
# instruments available (`LogJson`, `Deserialization failure`, `Invalid response received`) are all
# blind to it. CLAUDE.md's rule for that endpoint generalises here: READ THE PARSED STRUCT.
#
# It also answers FK-21 directly. FK-21's whole complaint is that "Career -> History is empty" has
# two indistinguishable causes — an authentic empty and a broken deserialization. This separates
# them at the source, before any question of rendering arises.
#
# ---------------------------------------------------------------------------------------------
# THE LAYOUT [M] — from interactive.go's handleMatchHistory derivation, which resolved the gate
# field by disassembling MatchHistoryManager::IsMatchHistoryLoaded (thunk rva 0x54A6340, fold
# multiplicity 1) down to `IsMatchHistoryLoaded == ([this+0x68] >= -1)`:
#
#   +0x48  OnUpdatedMatchHistory   multicast delegate, 16 B
#   +0x58  FMatchHistory.ID        FString   (Data +0x58, Num +0x60, Max +0x64)
#   +0x68  FMatchHistory.Version   int64     <- the gate's field; -2 = NEVER LOADED
#   +0x70  FMatchHistory.Matches   TArray<FMatchHistoryEntry>  (Data +0x70, Num +0x78, Max +0x7C)
#
# FMatchHistoryEntry field offsets are from a live `struct_layout.py` dump (Offset_Internal).
#
# ---------------------------------------------------------------------------------------------
# HOW TO READ THE OUTPUT
#   Version -2                      -> the document was REJECTED (or never fetched). Grep Loki.log
#                                      for `LogJson` / `Unable to import` — it names the property.
#   Version >= -1, Matches.Num == 0 -> the document parsed and the ARRAY came back empty. Either we
#                                      served [] (the default) or every element was dropped.
#   Version >= -1, Matches.Num == N -> parsed AND the entries survived. A blank Career->History
#                                      panel is then a RENDER question, not a feed question.
#
# ---------------------------------------------------------------------------------------------
# ⚠ THIS TOOL'S OWN BLIND SPOTS — read them before quoting a number from it
#
# 1. IT ENUMERATES EVERY INSTANCE AND PRINTS THEM ALL. It does not "find the manager". This
#    project has FOUR recorded instances of a probe silently taking the first match of a class and
#    reporting the wrong object's state as measurement — obj_by_class.py (substring),
#    cheat_reach_probe.py (endswith), class_props.py (class-of-class), and bpframe_readout.py,
#    which reported a confident False for a graph that had NEVER RUN because two live objects
#    shared one name. **The CDO is a real instance and it will read Version 0 / Num 0 forever.**
#    Match on `Default__` in the name, and on Version == -2 vs 0, before believing anything.
# 2. IT CANNOT TELL "never fetched" FROM "fetched and rejected" — both leave the -2 sentinel.
#    Pair it with capture.log (was the GET issued at all, User-Agent `Loki/UE5-CL-0`?).
# 3. ENTRY 0 IS STRIDE-INDEPENDENT; ENTRIES 1+ ARE NOT. UStruct::PropertiesSize does not read back
#    at the stock +0x40 in this build (struct_layout.py prints size=0 for every struct), so the
#    stride is NOT measured — it is inferred from the last field (StartingRating @+0x124, +4,
#    aligned to 8 => 0x128). The tool VALIDATES it against entry 1's ID rather than trusting it,
#    and says so. If validation fails, only entry 0 is trustworthy.
# 4. A class census by NAME is weaker than one by POINTER EQUALITY. Both are printed; if they
#    disagree, trust neither and investigate.

import ctypes, sys
from ctypes import wintypes

args = [a for a in sys.argv[1:]]
STRIDE = 0x128
if "--stride" in args:
    i = args.index("--stride"); STRIDE = int(args[i + 1], 0); del args[i:i + 2]
if len(args) < 2:
    sys.exit("usage: matchhistory_readout.py <PID> <BASE-hex> [--stride 0x128]")
PID = int(args[0], 0); BASE = int(args[1], 16)

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK = 65536
STRIDE_OBJ = 0x18
CLASS_NAME = "MatchHistoryManager"

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    sys.exit(f"OpenProcess({PID}) failed: {ctypes.get_last_error()} (elevated?)")


def rpm(a, n):
    b = (ctypes.c_ubyte * n)(); r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u32(b, o): return int.from_bytes(b[o:o + 4], "little")
def i32(b, o): return int.from_bytes(b[o:o + 4], "little", signed=True)
def i64(b, o): return int.from_bytes(b[o:o + 8], "little", signed=True)
def u64(b, o): return int.from_bytes(b[o:o + 8], "little")
def looksptr(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0
def p(a):
    b = rpm(a, 8); return u64(b, 0) if b else 0


_nc = {}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk = idx >> 16; off = (idx & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk * 8, 8); r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if looksptr(bp):
            hd = rpm(bp + off, 2)
            if hd:
                hd = int.from_bytes(hd, "little"); ln = hd >> 6; wide = hd & 1
                if 0 < ln < 200:
                    s = rpm(bp + off + 2, ln * (2 if wide else 1))
                    if s:
                        r = ("".join(chr(s[i * 2] | (s[i * 2 + 1] << 8)) for i in range(ln))
                             if wide else s.decode("latin1", "replace"))
    _nc[idx] = r; return r


def oname(o):
    b = rpm(o + 0x20, 4); return fname(u32(b, 0)) if b else "?"
def oclsptr(o):
    c = p(o + 0x18); return c if looksptr(c) else 0


def fstring(addr):
    """FString at `addr`: Data ptr, Num (incl. NUL), Max. UE FStrings are UTF-16."""
    data = p(addr); num = i32(rpm(addr + 8, 4) or b"\0" * 4, 0)
    if not looksptr(data) or not (0 < num < 4096):
        return "" if num == 0 else f"<bad Data=0x{data:X} Num={num}>"
    b = rpm(data, num * 2)
    if not b: return "<unreadable>"
    s = "".join(chr(b[i * 2] | (b[i * 2 + 1] << 8)) for i in range(num))
    return s.rstrip("\x00")


def enumerate_instances():
    """Walk GUObjectArray once, collecting every object whose CLASS is named CLASS_NAME."""
    op = p(OBJOBJECTS)
    hdr = rpm(OBJOBJECTS, 0x18)
    numEl = u32(hdr, 0x14) if hdr else 0
    nchunks = (numEl + PERCHUNK - 1) // PERCHUNK
    found, clsptrs, scanned = [], {}, 0
    for ci in range(nchunks):
        chunk = p(op + ci * 8)
        if not looksptr(chunk): continue
        cnt = (numEl - ci * PERCHUNK) if ci == nchunks - 1 else PERCHUNK
        for j in range(cnt):
            obj = p(chunk + j * STRIDE_OBJ)
            if not looksptr(obj): continue
            scanned += 1
            cp = oclsptr(obj)
            if not cp: continue
            if oname(cp) == CLASS_NAME:
                found.append(obj)
                clsptrs[cp] = clsptrs.get(cp, 0) + 1
    return found, clsptrs, scanned, numEl


ENTRY = [  # (offset, kind, label) — Offset_Internal from a live struct_layout.py dump
    (0x000, "str", "ID"),
    (0x020, "str", "QueueID"),
    (0x030, "u8", "IsRanked"),
    (0x038, "str", "GameVersion"),
    (0x048, "i32", "NumTeams"),
    (0x04C, "i32", "NumParticipants"),
    (0x060, "i32", "TeamInfo.Placement"),
    (0x10C, "i32", "CharacterLevel"),
    (0x120, "u8", "StartingRank(ERank)"),
    (0x124, "i32", "StartingRating"),
]
ERANK = ["Unranked", "Bronze4", "Bronze3", "Bronze2", "Bronze1", "Silver4", "Silver3", "Silver2",
         "Silver1", "Gold4", "Gold3", "Gold2", "Gold1", "Platinum4", "Platinum3", "Platinum2",
         "Platinum1", "Diamond4", "Diamond3", "Diamond2", "Diamond1", "Master4", "Master3",
         "Master2", "Master1", "GrandMaster", "Legend"]


def dump_entry(addr, idx):
    print(f"      --- Matches[{idx}] @0x{addr:X} ---")
    for off, kind, label in ENTRY:
        if kind == "str":
            v = fstring(addr + off)
            print(f"        +0x{off:03X} {label:22s} {v!r}")
        elif kind == "i32":
            b = rpm(addr + off, 4)
            print(f"        +0x{off:03X} {label:22s} {i32(b, 0) if b else '<unreadable>'}")
        else:
            b = rpm(addr + off, 1)
            raw = b[0] if b else None
            extra = ""
            if b and "ERank" in label:
                extra = f"  = {ERANK[raw]}" if raw < len(ERANK) else "  = <out of range>"
            print(f"        +0x{off:03X} {label:22s} {raw}{extra}")


insts, clsptrs, scanned, numEl = enumerate_instances()
print(f"GUObjectArray: NumElements={numEl}, objects scanned={scanned}")
print(f"class '{CLASS_NAME}': {len(insts)} instance(s); "
      f"distinct UClass pointers by name = {len(clsptrs)} "
      f"{'  <-- ⚠ EXPECTED 1' if len(clsptrs) != 1 else '(pointer-equality census agrees)'}")
for cp, n in clsptrs.items():
    print(f"  UClass 0x{cp:X}  instances={n}")
if not insts:
    sys.exit("\nNO INSTANCE FOUND. The manager may not be constructed yet, or the base/PID is "
             "wrong. This is NOT evidence about the document — it is a coverage miss.")

print()
for obj in insts:
    nm = oname(obj)
    is_cdo = nm.startswith("Default__")
    ver = i64(rpm(obj + 0x68, 8) or b"\0" * 8, 0)
    mdata = p(obj + 0x70)
    mnum = i32(rpm(obj + 0x78, 4) or b"\0" * 4, 0)
    mmax = i32(rpm(obj + 0x7C, 4) or b"\0" * 4, 0)
    did = fstring(obj + 0x58)
    tag = "  [CDO - control, expected inert]" if is_cdo else ""
    print(f"instance 0x{obj:X}  name={nm}{tag}")
    print(f"  +0x58 FMatchHistory.ID       {did!r}")
    print(f"  +0x68 FMatchHistory.Version  {ver}" +
          ("   <-- -2 = NEVER LOADED (rejected or never fetched)" if ver == -2 else
           "   <-- gate OPEN (>= -1)" if ver >= -1 else ""))
    print(f"  +0x70 FMatchHistory.Matches  Data=0x{mdata:X} Num={mnum} Max={mmax}")

    if is_cdo or mnum <= 0 or not looksptr(mdata):
        print()
        continue

    dump_entry(mdata, 0)
    if mnum >= 2:
        # Validate the INFERRED stride rather than trusting it (blind spot 3).
        probe = fstring(mdata + STRIDE)
        ok = isinstance(probe, str) and probe and not probe.startswith("<")
        print(f"      stride 0x{STRIDE:X} validation: Matches[1].ID = {probe!r} "
              f"{'OK' if ok else '<-- ⚠ FAILED; entries 1+ are NOT trustworthy'}")
        if ok:
            for i in range(1, min(mnum, 5)):
                dump_entry(mdata + i * STRIDE, i)
    print()

# ★ Parse THIS line, not the rows above (the CLAUDE.md rule for toggle_readout.py: parse the
# summary, never count rows — rows include the CDO and any archetype).
ZERO8 = b"\x00" * 8
parts = []
for o in insts:
    cdo = "(CDO)" if oname(o).startswith("Default__") else ""
    ver = i64(rpm(o + 0x68, 8) or ZERO8, 0)
    num = i32(rpm(o + 0x78, 4) or ZERO8, 0)
    parts.append(f"0x{o:X}{cdo} ver={ver} num={num}")
print("summary: " + "; ".join(parts))
