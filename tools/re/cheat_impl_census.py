#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cheat_impl_census.py -- FK-6: resolve every cheat exec-THUNK to its _Implementation
                        and classify the IMPLEMENTATION bodies, offline.

WHY
---
memory/supervive-cheat-surface-inventory.md records a "DEFINITIVE CLOSE -- the cheat
function bodies are compiled out of shipping (S74, disasm-verified)".  The actual
evidence behind it was TWO disassembled bodies out of 65 functions.  This tool
measures the other 63 (and the other cheat classes) the same way S74 measured its two,
but exhaustively and offline.

The distinction that matters and that a naive re-parse gets wrong:

  * an auto-generated `exec` THUNK (DECLARE_FUNCTION(execFoo)) ALWAYS has real code --
    it unpacks FFrame params -- even when the Foo_Implementation it calls is `ret`.
    A census of THUNK bodies therefore says NOTHING about whether bodies were stripped.
  * the claim under test is about the _Implementation.  So: disassemble the thunk,
    resolve thunk -> impl, and classify the IMPL.

INPUTS (all offline, read-only)
  docs/session-74-cheat-enum-dump.txt   live UFunction enum, BASE=0x7FF6B54F0000
  dumps/merged.dump.exe                 cold image, ImageBase 0x7FF6AF000000, file off == RVA
  tools/strxref/index/pdata_union.csv   382,282 EXACT function bounds (recovered unwind table)
  tools/strxref/index/callmult.pkl      global E8 rel32 call-site multiplicity

HEURISTIC (stated so it can be audited, per project rules)
  ** A multiplicity filter DOES NOT WORK here and using one inverts the answer. **
  MSVC /OPT:ICF folds every byte-identical function in the image into one address, so
  a STRIPPED impl (`ret`, `xor al,al; ret`) ends up with THOUSANDS of call sites while
  a real impl has 1.  Ranking by "rare callee" therefore discards exactly the stubs the
  question is about.  Measured here: 0xF7EC20 (`ret 0`, the canonical empty void body)
  has 4,784 call sites; 0xF7EB60 (`xor al,al; ret`) has 192.

  The rule actually used is STRUCTURAL, from the shape of DECLARE_FUNCTION(execFoo):
      <param steps: FFrame::Step / StepExplicitProperty>
      <P_FINISH:  test rax,rax ; setne rN ; add rN,rax ; mov [frame+0x20],rN>
      call Foo_Implementation            <-- the impl
      [ mov [Z_Param__Result], al/rax ]  optional result store
      [ test rcx,rcx ; je +N ; call <dtor> ]*  optional FString/TArray teardown
      <epilogue> ret
  => the impl is the LAST rel32 call/tail-jmp in the thunk that is NOT a guarded
  teardown call (a call whose immediately preceding instruction is a je/jz landing
  exactly past it).  Ties to the P_FINISH anchor are reported as a cross-check.

  Validators reported:
    V0  fraction of picks that are P_FINISH-anchored (the independent structural signal)
    V1  fraction that land EXACTLY on a recovered .pdata entry
    V2  fraction whose first bytes are a plausible function prologue

USAGE
  python cheat_impl_census.py                 full report
  python cheat_impl_census.py --class LokiPlayerCheats
  python cheat_impl_census.py --func CheatChangeHero --verbose
  python cheat_impl_census.py --csv out.csv
"""
import argparse
import bisect
import os
import pickle
import re
import struct
import sys
from array import array
from collections import Counter, defaultdict

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
except ImportError:
    sys.exit("need capstone:  pip install capstone")

ROOT = r"G:\git\Supervive Revival Project"
  # 2026-08-14 (S121, FK-18/FK-19): merged2 is the canonical cold image -- same ImageBase
  # 0x7FF6AF000000, byte-identical .rdata/.data, and a STRICT .text superset (16,625 vs
  # 15,833 decrypted pages). docs/fk18-fk19-multistate-merge-settled.md
DUMP = os.path.join(ROOT, "dumps", "merged2.dump.exe")
ENUM = os.path.join(ROOT, "docs", "session-74-cheat-enum-dump.txt")
PDATA = os.path.join(ROOT, "tools", "strxref", "index", "pdata_union.csv")
CALLMULT = os.path.join(ROOT, "tools", "strxref", "index", "callmult.pkl")

# ---------------------------------------------------------------------------
# .text UNION across every per-state dump, including ones `mergedumps` REJECTS.
#
# MEASURED (this session): .text pages are byte-IDENTICAL across dumps taken at
# different ASLR bases -- 0 conflicts over every page present in two or more of
# the 10 dumps, including dumps/rcb (base 0x7FF79D3B0000 vs merged's
# 0x7FF6AF000000).  That corroborates strxref's "x64 code here is 100%
# RIP-relative" finding: nothing in .text is relocated, so a different-base dump
# is still byte-mergeable FOR .text (mergedumps refuses it only because .data
# and .rdata genuinely are not).  Unioning raises .text from 15,833 decrypted
# pages (52.29%) to 16,435 (54.27%) and, decisively for FK-6, decrypts the
# AreHotkeyCheatsEnabled / CheatChangeHero / ServerCheatSpawnActor thunk pages
# that merged.dump.exe alone does not have.
# ---------------------------------------------------------------------------
# 2026-08-14 (FK-19): `mergedumps` no longer refuses cross-base inputs, so this in-process
# union is redundant -- prefer dumps/merged2.dump.exe (16,625 pages, 54.90%), which is this
# same union baked into one file. The list below was missing `tutorial-hero` (570 pages
# merged lacks -- the best single image on disk) and `lobby-dispatch-decrypted` (29); both
# are added here so the standalone path matches merged2 exactly.
EXTRA_DUMPS = [os.path.join(ROOT, "dumps", d, "SUPERVIVE-Win64-Shipping.dump.exe")
               for d in ("menu", "store", "roster", "missions", "loadout",
                         "accountpass", "vmbuild", "toggles", "rcb",
                         "tutorial-hero", "lobby-dispatch-decrypted")]
# ⚠ 2026-08-14 (S121) — STALE-CACHE HAZARD, PARTIALLY MITIGATED.
# This tool builds its own .text union from a hardcoded dump list and caches it to %TEMP%, where
# the ONLY freshness test is the cache's SIZE — which is a constant. Adding a capture therefore
# can never invalidate it. That is the identical defect that froze
# tools/strxref/index/pagecov.json on 2026-07-26 and left statecov.py printing 15,833 / 54.27%
# long after the truth was 16,638 / 54.95%.
# MITIGATION SO FAR: the stale cache files were deleted, so the next run rebuilds.
# PROPER FIX (not done): dumps/merged2.dump.exe IS this union already — verified a superset of
# all 12 state dumps with 0 pages missing — so this in-process union is redundant. Read merged2
# and delete the union machinery, or stamp the cache with each input's (path, mtime, size).
UNION_CACHE = os.path.join(
    os.environ.get("TEMP", "."), "supervive_union_text.bin")

LIVE_BASE = 0x7FF6B54F0000        # BASE recorded in the S74 enum dump
TEXT_RVA, TEXT_END = 0x1000, 0x1000 + 0x7649000
PAGE = 0x1000
PROCESS_INTERNAL = 0x13454A0      # base+0x13454A0, the project's native-call primitive
# FFrame param-step / teardown helpers.  Landing on one of these means the thunk's
# real dispatch was an indirect call this tool could not resolve (typically a
# virtual call on a PARAMETER's vtable, not on `this`) -> report SUSPECT, never
# score it as a body.  Measured residual: 19 of 272 resolutions (7.0%).
FRAME_HELPERS = {0x1345FB0, 0x1345FE0, 0x133F840, 0x133EEA0, 0x133EBE0,
                 0x12F3FC0, 0x13759A0, 0xFF9310}
MULT_MAX = 6

# ---------------------------------------------------------------- image ----
_IMG = None
UNION = True
UNION_STATS = {}


def img():
    global _IMG
    if _IMG is None:
        with open(DUMP, "rb") as f:
            base = bytearray(f.read())
        if UNION:
            if os.path.exists(UNION_CACHE) and \
               os.path.getsize(UNION_CACHE) == TEXT_END - TEXT_RVA:
                with open(UNION_CACHE, "rb") as f:
                    base[TEXT_RVA:TEXT_END] = f.read()
            else:
                conf = 0
                for p in EXTRA_DUMPS:
                    if not os.path.exists(p):
                        continue
                    with open(p, "rb") as f:
                        d = f.read()
                    for r in range(TEXT_RVA, TEXT_END, PAGE):
                        pg = d[r:r + PAGE]
                        if not pg.strip(b"\0"):
                            continue
                        cur = bytes(base[r:r + PAGE])
                        if not cur.strip(b"\0"):
                            base[r:r + PAGE] = pg
                        elif cur != pg:
                            conf += 1
                UNION_STATS["conflicts"] = conf
                with open(UNION_CACHE, "wb") as f:
                    f.write(bytes(base[TEXT_RVA:TEXT_END]))
            UNION_STATS["pages"] = sum(
                1 for r in range(TEXT_RVA, TEXT_END, PAGE)
                if bytes(base[r:r + PAGE]).strip(b"\0"))
        _IMG = bytes(base)
    return _IMG


def decrypted(rva):
    """True if the 4 KiB page containing rva is present (non-zero) in the image."""
    p = rva & ~(PAGE - 1)
    return img()[p:p + PAGE].strip(b"\0") != b""


def range_ok(lo, hi):
    """True only if EVERY page spanned by [lo,hi) is decrypted (no truncation)."""
    d = img()
    for p in range(lo & ~(PAGE - 1), hi, PAGE):
        if not d[p:p + PAGE].strip(b"\0"):
            return False
    return True


# ---------------------------------------------------------------- pdata ----
_PD = None


def pdata():
    global _PD
    if _PD is None:
        beg, end = array("l"), array("l")
        with open(PDATA) as f:
            next(f)
            for line in f:
                a, b = line.split(",", 2)[:2]
                beg.append(int(a, 16))
                end.append(int(b, 16))
        _PD = (beg, end)
    return _PD


_MERGED = {}


def func_bounds(rva):
    """EXACT (begin, end) with chained unwind fragments merged, or (None, None).
    A (None, None) means 'no crash process ever decrypted this', not 'no function'."""
    beg, end = pdata()
    i = bisect.bisect_right(beg, rva) - 1
    if i < 0 or rva >= end[i]:
        return None, None
    while i > 0 and beg[i] == end[i - 1] and beg[i] % 16:
        i -= 1
    if beg[i] in _MERGED:
        return _MERGED[beg[i]]
    e, k, n = end[i], i + 1, len(beg)
    while k < n and beg[k] == e and beg[k] % 16:
        e = end[k]
        k += 1
    _MERGED[beg[i]] = (beg[i], e)
    return beg[i], e


def is_entry(rva):
    """True if rva is exactly a recovered function entry (fragment or merged head)."""
    beg, _ = pdata()
    i = bisect.bisect_left(beg, rva)
    return i < len(beg) and beg[i] == rva


# ------------------------------------------------------------- callmult ----
_MULT = None


def mult():
    global _MULT
    if _MULT is None:
        with open(CALLMULT, "rb") as f:
            _MULT = pickle.load(f)
    return _MULT


# ----------------------------------------------------------------- parse ----
RX_CLASS = re.compile(r"^#{10} UClass (\S+) @")
RX_OWNER = re.compile(r"^  === \[(\d+)\] (\S+)\s+\((\d+) UFunction\) ===")
RX_FUNC = re.compile(r"^    (\S+)\s+\[([^\]]*)\] thunk=0x([0-9A-Fa-f]+)")


class Fn:
    __slots__ = ("cls", "owner", "depth", "name", "flags", "thunk", "rva", "sig")

    def __init__(self, cls, owner, depth, name, flags, thunk, sig):
        self.cls, self.owner, self.depth = cls, owner, depth
        self.name, self.flags, self.thunk = name, flags, thunk
        self.rva = thunk - LIVE_BASE
        self.sig = sig


def parse_enum():
    out, cls, owner, depth = [], None, None, -1
    with open(ENUM, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    for i, ln in enumerate(lines):
        m = RX_CLASS.match(ln)
        if m:
            cls = m.group(1)
            continue
        m = RX_OWNER.match(ln)
        if m:
            depth, owner = int(m.group(1)), m.group(2)
            continue
        m = RX_FUNC.match(ln)
        if m and cls:
            sig = lines[i + 1].strip() if i + 1 < len(lines) else ""
            flags = [x.strip() for x in m.group(2).split(",") if x.strip()]
            out.append(Fn(cls, owner, depth, m.group(1), flags,
                          int(m.group(3), 16), sig))
    return out


# ------------------------------------------------------------------ disasm --
MD = Cs(CS_ARCH_X86, CS_MODE_64)
MD.detail = False


def disasm(beg, end):
    """[(rva, mnemonic, op_str, size)] linear sweep."""
    d = img()[beg:end]
    return [(i.address, i.mnemonic, i.op_str, i.size)
            for i in MD.disasm(d, beg)]


def sweep_bounds(rva, cap=0x800):
    """Fallback extent when the unwind table has no entry: stop after a ret/jmp
    that is followed by int3/nop padding or 16-alignment."""
    d = img()
    o = rva
    lim = rva + cap
    for ins in MD.disasm(d[rva:lim], rva):
        o = ins.address + ins.size
        if ins.mnemonic in ("ret", "jmp") or (ins.mnemonic == "int3"):
            nxt = d[o:o + 1]
            if not nxt or nxt[0] == 0xCC or o % 16 == 0:
                return rva, o
    return rva, o


def extent(rva):
    b, e = func_bounds(rva)
    if b is not None:
        return b, e, "pdata"
    b, e = sweep_bounds(rva)
    return b, e, "sweep"


def rel32_targets(beg, end):
    """Ordered [(site, target, is_jmp)] for rel32 call/jmp decoded properly
    (capstone, not byte-regex, so displacements/immediates cannot alias)."""
    out = []
    for rva, mn, ops, sz in disasm(beg, end):
        if mn in ("call", "jmp") and ops.startswith("0x"):
            try:
                t = int(ops, 16)
            except ValueError:
                continue
            if TEXT_RVA <= t < TEXT_END:
                out.append((rva, t, mn == "jmp"))
    return out


JCC = ("je", "jz", "jne", "jnz")

# --------------------------------------------------------------- vtables ----
# UE declares many *_Implementation as VIRTUAL, so the generated exec thunk ends
# in `mov rax,[this] ; jmp qword ptr [rax+disp]` -- an indirect dispatch with no
# rel32 to follow.  Those are not "inlined": the impl is the vtable slot.
# vtable RVAs from tools/strxref/vtables.py (3,599-entry class->vtable map).
IMAGEBASE = 0x7FF6AF000000
VTABLE = {
    "LokiPlayerCheats":                    0x08A1A690,   # ALokiPlayerCheats, 266 slots
    "CheatManager":                        0x07FA7E28,   # UCheatManager, 144
    "CheatManagerExtension":               0x07FA7B50,   # UCheatManagerExtension, 91
    "GameFeatureAction_AddCheats":         0x08809698,   # 96
    "LokiCharacterCheatDetectionComponent": 0x088EE978,  # 152
    "LokiClientPlayerCheats":              0x076EF750,   # 88
}
RX_VSLOT = re.compile(r"^qword ptr \[(\w+) \+ (0x[0-9a-f]+)\]$")


def vslot(cls, disp):
    """Concrete function RVA behind <cls> vtable slot at byte offset disp."""
    vt = VTABLE.get(cls)
    if vt is None:
        return None
    q = struct.unpack_from("<Q", img(), vt + disp)[0]
    if q == 0:
        return None
    r = q - IMAGEBASE
    return r if TEXT_RVA <= r < TEXT_END else None


RX_MOVSLOT = re.compile(r"^(\w+), qword ptr \[(\w+) \+ (0x[0-9a-f]+)\]$")


def vdispatch(beg, end, cls):
    """(impl_rva, disp) if the thunk's FINAL dispatch is a <cls> vtable call.

    Two encodings occur:
      A  mov rax,[this] ; jmp/call qword ptr [rax+disp]      (dispatch at the site)
      B  mov rax,[this] ; mov rbx,[rax+disp] ; ... ; call rbx (slot hoisted to a reg)
    """
    ins = disasm(beg, end)
    for i in range(len(ins) - 1, -1, -1):
        rva, mn, ops, sz = ins[i]
        if mn not in ("jmp", "call"):
            continue
        m = RX_VSLOT.match(ops)
        if m:                                              # form A
            disp = int(m.group(2), 16)
            prev = " ".join(x[1] + " " + x[2] for x in ins[max(0, i - 3):i])
            if "qword ptr [" not in prev:
                continue
            t = vslot(cls, disp)
            if t is not None:
                return t, disp
            continue
        if re.fullmatch(r"[re][a-z0-9]+", ops):            # form B: call <reg>
            for j in range(i - 1, max(-1, i - 24), -1):
                mm = RX_MOVSLOT.match(ins[j][2]) if ins[j][1] == "mov" else None
                if mm and mm.group(1) == ops:
                    disp = int(mm.group(3), 16)
                    t = vslot(cls, disp)
                    if t is not None:
                        return t, disp
                    break
    return None, None


def thunk_calls(beg, end):
    """[(site, target, is_jmp, guarded, pfinish)] for every rel32 call/tail-jmp,
    with the two structural flags the impl rule uses.

      guarded  -- the instruction right before it is a jcc landing exactly past the
                  call: the `if (p) dtor(p);` teardown shape, never the impl.
      pfinish  -- the 3 instructions before it are the P_FINISH idiom
                  (setne rN ; add rN,rax ; mov [reg+0x20],rN), which in a
                  DECLARE_FUNCTION thunk immediately precedes the impl call.
    """
    ins = disasm(beg, end)
    out = []
    for i, (rva, mn, ops, sz) in enumerate(ins):
        if mn not in ("call", "jmp") or not ops.startswith("0x"):
            continue
        try:
            t = int(ops, 16)
        except ValueError:
            continue
        if not (TEXT_RVA <= t < TEXT_END):
            continue
        if mn == "jmp" and beg <= t < end:
            continue                                   # intra-function branch
        guarded = False
        if i and ins[i - 1][1] in JCC and ins[i - 1][2].startswith("0x"):
            try:
                guarded = int(ins[i - 1][2], 16) == rva + sz
            except ValueError:
                pass
        win = [x[1] + " " + x[2] for x in ins[max(0, i - 4):i]]
        pf = any(w.startswith("setne") for w in win) and \
            any(w.startswith("mov qword ptr [") and "+ 0x20]" in w for w in win)
        out.append((rva, t, mn == "jmp", guarded, pf))
    return out


# -------------------------------------------------------------- classify ----
def body_class(rva):
    """Classify an implementation body.  Returns (verdict, detail, size)."""
    if rva == PROCESS_INTERNAL:
        return "SCRIPT", "ProcessInternal (BP/script bytecode, not native)", 0
    if not decrypted(rva):
        return "UNVERIFIABLE", "impl page never decrypted in any dump", 0
    b, e, how = extent(rva)
    if not range_ok(b, e):
        return "UNVERIFIABLE", f"impl body [{b:#x},{e:#x}) crosses an undecrypted page", 0
    d = img()
    raw = d[b:e]
    ins = disasm(b, e)
    n = len(ins)
    # ---- exact stub shapes.  ICF makes these SHARED addresses: every
    # `void f(...){}` in the image folds onto one `ret`/`ret 0`.
    STUBS = [
        (b"\xC3",             "RET_STUB",   "C3 (ret) -- empty body"),
        (b"\xC2\x00\x00",     "RET_STUB",   "C2 00 00 (ret 0) -- empty body"),
        (b"\x32\xC0\xC3",     "FALSE_STUB", "32 C0 C3 (xor al,al; ret) -- always false"),
        (b"\x33\xC0\xC3",     "ZERO_STUB",  "33 C0 C3 (xor eax,eax; ret) -- 0 / nullptr"),
        (b"\x48\x33\xC0\xC3", "ZERO_STUB",  "48 33 C0 C3 (xor rax,rax; ret) -- 0 / nullptr"),
        (b"\xB0\x01\xC3",     "TRUE_STUB",  "B0 01 C3 (mov al,1; ret) -- always true"),
        (b"\x48\x8B\xC1\xC3", "TRIVIAL",    "48 8B C1 C3 (mov rax,rcx; ret) -- identity"),
    ]
    for pat, verd, why in STUBS:
        if raw[:len(pat)] == pat:
            return verd, f"{why}   [{mult().get(rva, 0)} ICF call sites]", len(pat)
    # trivial: no calls, few instructions, no branching
    calls = [t for _s, t, _j, _g, _p in thunk_calls(b, e)]
    stop = next((k for k, x in enumerate(ins) if x[1] in ("ret", "jmp")), n - 1)
    if stop <= 5 and not calls:
        txt = "; ".join(f"{m} {o}".strip() for _a, m, o, _s in ins[:stop + 1])
        return "TRIVIAL", txt[:110] + f"   [{mult().get(rva, 0)} ICF call sites]", \
            ins[stop][0] + ins[stop][3] - b
    return "REAL", f"{n} ins, {len(calls)} calls, {how} bounds", e - b


# ------------------------------------------------------------------ resolve --
class Res:
    __slots__ = ("fn", "thunk_ok", "tbeg", "tend", "thow", "tins",
                 "cands", "impl", "impl_why", "verdict", "detail", "isize",
                 "pfinish")


def resolve(fn, mult_max=MULT_MAX):
    r = Res()
    r.fn = fn
    r.cands = []
    r.impl = None
    r.impl_why = ""
    r.pfinish = False
    if fn.rva == PROCESS_INTERNAL:
        r.thunk_ok = True
        r.tbeg = r.tend = fn.rva
        r.thow = "-"
        r.tins = 0
        r.impl = PROCESS_INTERNAL
        r.impl_why = "thunk IS ProcessInternal"
        r.verdict, r.detail, r.isize = "SCRIPT", \
            "BP/script-implemented UFunction (no native impl exists)", 0
        return r
    if not decrypted(fn.rva):
        r.thunk_ok = False
        r.tbeg = r.tend = fn.rva
        r.thow = "-"
        r.tins = 0
        r.verdict, r.detail, r.isize = "UNVERIFIABLE", \
            "THUNK page never decrypted -- impl not reachable offline", 0
        return r
    r.thunk_ok = True
    r.tbeg, r.tend, r.thow = extent(fn.rva)
    if not range_ok(r.tbeg, r.tend):
        r.tins = 0
        r.verdict, r.detail, r.isize = "UNVERIFIABLE", \
            f"THUNK body [{r.tbeg:#x},{r.tend:#x}) runs into an undecrypted page", 0
        return r
    tg = thunk_calls(r.tbeg, r.tend)
    r.tins = len(disasm(r.tbeg, r.tend))
    M = mult()
    r.cands = [(s, t, j, M.get(t, 0), g, p) for (s, t, j, g, p) in tg]
    r.pfinish = False
    # The impl is the FINAL dispatch of the thunk.  Scan backwards past the
    # epilogue and any guarded teardown call; the first dispatch found is it.
    # It may be rel32 (non-virtual impl) or an indirect vtable slot (virtual impl).
    ins = disasm(r.tbeg, r.tend)
    guarded_sites = {s for (s, t, j, m, g, p) in r.cands if g}
    pf_sites = {s for (s, t, j, m, g, p) in r.cands if p}
    vt, vd = vdispatch(r.tbeg, r.tend, fn.cls)
    for i in range(len(ins) - 1, -1, -1):
        rva, mn, ops, sz = ins[i]
        if mn not in ("call", "jmp") or rva in guarded_sites:
            continue
        if ops.startswith("0x"):
            t = int(ops, 16)
            if r.tbeg <= t < r.tend or func_bounds(t)[0] == r.tbeg:
                continue                       # intra-function branch/fragment
            r.impl, r.pfinish = t, rva in pf_sites
            r.impl_why = ("P_FINISH-anchored " if r.pfinish else "final ") + \
                f"{'jmp' if mn == 'jmp' else 'call'} rel32 (mult={M.get(t, 0)})"
            break
        if RX_VSLOT.match(ops) or re.fullmatch(r"[re][a-z0-9]+", ops):
            if vt is not None:
                r.impl = vt
                r.impl_why = f"VIRTUAL {fn.cls} vtable[+{vd:#x}] -> {vt:#x}"
            else:
                r.impl_why = f"VIRTUAL dispatch {ops} -- vtable unresolved"
            break
    if r.impl is None and not r.impl_why:
        r.impl_why = ("only teardown calls -> impl INLINED" if r.cands
                      else "no rel32 callee at all -> impl INLINED into the thunk")
    if r.impl is None:
        # inlined: classify the thunk body itself as the observable behaviour
        r.verdict, r.detail, r.isize = "INLINED", \
            f"thunk {r.tins} ins / {r.tend - r.tbeg} B, {len(r.cands)} helper calls", \
            r.tend - r.tbeg
    elif r.impl in FRAME_HELPERS:
        r.verdict, r.detail, r.isize = "SUSPECT",             f"resolved to FFrame helper {r.impl:#x} -- unresolved indirect dispatch", 0
    else:
        r.verdict, r.detail, r.isize = body_class(r.impl)
    return r


# -------------------------------------------------------------------- main --
GROUPS = ["REAL", "SCRIPT", "INLINED", "RET_STUB", "FALSE_STUB", "ZERO_STUB",
          "TRUE_STUB", "TRIVIAL", "SUSPECT", "UNVERIFIABLE"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="cls", default=None)
    ap.add_argument("--owner", default=None, help="only functions DECLARED by this class")
    ap.add_argument("--func", default=None)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--mult-max", type=int, default=MULT_MAX)
    a = ap.parse_args()

    fns = parse_enum()
    if a.cls:
        fns = [f for f in fns if f.cls == a.cls]
    if a.owner:
        fns = [f for f in fns if f.owner == a.owner]
    if a.func:
        fns = [f for f in fns if a.func.lower() in f.name.lower()]

    res = [resolve(f, a.mult_max) for f in fns]

    # ---- per-class census -------------------------------------------------
    print("=" * 96)
    print("CLASS CENSUS  (owner = the class that DECLARES the UFunction)")
    print("=" * 96)
    byclass = defaultdict(Counter)
    for r in res:
        byclass[(r.fn.cls, r.fn.owner)][r.verdict] += 1
    print(f"{'enumerated class':38} {'declaring owner':26} {'n':>4}  distribution")
    for (c, o), cnt in sorted(byclass.items()):
        tot = sum(cnt.values())
        dist = " ".join(f"{k}={cnt[k]}" for k in GROUPS if cnt[k])
        print(f"{c:38} {o:26} {tot:4}  {dist}")

    print()
    print("=" * 96)
    print("IMPLEMENTATION-BODY DISTRIBUTION  (all selected functions)")
    print("=" * 96)
    tot = Counter(r.verdict for r in res)
    n = len(res)
    for k in GROUPS:
        if tot[k]:
            print(f"  {k:14} {tot[k]:5}  {100.0 * tot[k] / n:5.1f}%")
    print(f"  {'TOTAL':14} {n:5}")

    # ---- validators -------------------------------------------------------
    chosen = [r for r in res if r.impl and r.impl != PROCESS_INTERNAL]
    v0 = sum(1 for r in chosen if r.pfinish)
    v1 = sum(1 for r in chosen if is_entry(r.impl))
    d = img()
    PRO = (b"\x40", b"\x41", b"\x48", b"\x4c", b"\x53", b"\x55", b"\x56", b"\x57",
           b"\x33", b"\x32", b"\xc3", b"\xb0", b"\x8b", b"\xe9", b"\x0f")
    v2 = sum(1 for r in chosen if decrypted(r.impl) and d[r.impl:r.impl + 1] in PRO)
    print()
    print("HEURISTIC VALIDATORS")
    print(f"  chosen impls (non-script)                    {len(chosen)}")
    if chosen:
        print(f"  V0 P_FINISH-anchored (structural, independent) {v0}/{len(chosen)}"
              f"  ({100.0*v0/len(chosen):.1f}%)")
        print(f"  V1 land EXACTLY on a recovered .pdata entry  {v1}/{len(chosen)}"
              f"  ({100.0*v1/len(chosen):.1f}%)")
        print(f"  V2 start with a plausible prologue byte      {v2}/{len(chosen)}"
              f"  ({100.0*v2/len(chosen):.1f}%)")

    # ---- ICF folding ------------------------------------------------------
    fold = defaultdict(list)
    for f in fns:
        fold[f.thunk].append(f)
    shared = {k: v for k, v in fold.items() if len(v) > 1}
    if shared:
        print()
        print("=" * 96)
        print("IDENTICAL-COMDAT-FOLDING  (>1 UFunction sharing one thunk address)")
        print("  MSVC /OPT:ICF folds byte-identical functions.  Two thunks with DIFFERENT")
        print("  signatures can only fold if the impl call was inlined away to the same code.")
        print("=" * 96)
        for k in sorted(shared, key=lambda x: -len(shared[x])):
            v = shared[k]
            rr = next(r for r in res if r.fn.thunk == k)
            print(f"  0x{k - LIVE_BASE:08X}  x{len(v):<3} {rr.verdict:12} "
                  + ", ".join(f"{x.owner}::{x.name}" for x in v)[:150])

    # ---- per-function detail ---------------------------------------------
    print()
    print("=" * 96)
    print("PER-FUNCTION")
    print("=" * 96)
    print(f"{'owner':22} {'function':36} {'thunkRVA':>9} {'implRVA':>9} "
          f"{'sz':>5} {'verdict':12} detail")
    for r in sorted(res, key=lambda x: (x.fn.cls, x.fn.depth, x.fn.name)):
        i = f"{r.impl:#09x}" if r.impl else "-"
        print(f"{r.fn.owner:22} {r.fn.name:36} {r.fn.rva:#09x} {i:>9} "
              f"{r.isize:5} {r.verdict:12} {r.detail[:60]}")
        if a.verbose:
            print(f"      flags={','.join(r.fn.flags)}")
            print(f"      sig  ={r.fn.sig}")
            print(f"      thunk=[{r.tbeg:#x},{r.tend:#x}) {r.thow} {r.tins} ins")
            print(f"      pick ={r.impl_why}")
            for site, t, j, m, g, pf in r.cands:
                tag = " guarded-teardown" if g else (" P_FINISH" if pf else "")
                print(f"        {'jmp ' if j else 'call'} {t:#09x}  mult={m:<6}"
                      f" @{site:#x}{tag}"
                      f"{'   <-- CHOSEN' if t == r.impl else ''}")

    if a.csv:
        with open(a.csv, "w", encoding="utf-8") as f:
            f.write("class,owner,function,flags,thunk_rva,impl_rva,impl_size,"
                    "verdict,detail,pick_reason,sig\n")
            for r in res:
                f.write(f'{r.fn.cls},{r.fn.owner},{r.fn.name},'
                        f'"{"|".join(r.fn.flags)}",{r.fn.rva:#x},'
                        f'{r.impl if r.impl else 0:#x},{r.isize},{r.verdict},'
                        f'"{r.detail}","{r.impl_why}","{r.fn.sig}"\n')
        print(f"\nwrote {a.csv}")


if __name__ == "__main__":
    main()
