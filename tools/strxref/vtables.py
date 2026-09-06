#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vtables.py -- offline C++ vtable census + CLASS NAMING for the SUPERVIVE (UE5.4
              "Loki") cold image dump.  Stdlib only.  No live process.  Read-only.

Companion to strxref.py (imports it for the string/xref index and function
attribution).  Answers the second half of the FK-3 question: ".rdata is readable
after all -- so is VTABLE DUMPING revived, given MSVC RTTI is stripped?"

WHAT IS AND IS NOT RECOVERABLE HERE
-----------------------------------
MEASURED, not assumed:

  * .rdata holds 933,675 qwords that point into .text, in 104,903 maximal runs.
    Vtables are REAL and fully readable -- the documented LokiAssetManager vtable
    (docs/lokiassetmanager-vtable-dump.md, captured 2026-06-28 from the LIVE
    process with `usmapdump vtdump`) reproduces byte-for-byte from this cold dump.

  * BUT run boundaries are NOT vtable boundaries.  MSVC normally emits a pointer
    to the RTTI Complete Object Locator in the qword BEFORE each vtable, which
    separates adjacent vtables.  RTTI is stripped in this build, so that separator
    is gone and vtables are packed BACK-TO-BACK: the LokiAssetManager vtable is at
    slot 799 of a single 997-slot run.  Structure alone cannot cut them apart.

  * The cut comes from CODE: a vtable start is exactly an address that a
    constructor loads with `lea r64,[rip+X]` and stores with `mov [reg],r64`.
    29,501 8-aligned .rdata LEA targets land inside runs; 14,268 of them are
    install-shaped.  Cutting the runs at those points yields the vtable census.

  * Class NAMES do not come from RTTI (stripped).  They come from UE's own
    IMPLEMENT_CLASS boilerplate:

        UClass* UFoo::GetPrivateStaticClass() {
            GetPrivateStaticClassBody(StaticPackage() /* L"/Script/Loki" */,
                                      TEXT("UFoo"), ...,
                                      (UClass::ClassConstructorType)InternalConstructor<UFoo>,
                                      ...); }

    So: the wide string L"/Script/<Module>" pins the function as a
    GetPrivateStaticClass; the one class-name-shaped wide string it also
    references IS the class name; and the LAST .text LEA target in it is
    InternalConstructor<UFoo>, which tail-jumps to the real C++ constructor,
    which installs the vtable.  UE's reflection boilerplate is the substitute
    symbol table that RTTI would otherwise have been.

USAGE
-----
  vtables.py scan [--dump PATH]        build index/vtables.idx + full validation
  vtables.py stats                     run/vtable/naming distributions
  vtables.py classes [PATTERN] [-n N]  resolved class -> vtable map
  vtables.py name <ClassName> [--slots N]
  vtables.py at 0x<rdata_rva> [--slots N] [--strings]
  vtables.py who 0x<rdata_rva>         reverse: which class owns this vtable
  vtables.py verify                    re-run validation only
"""

import argparse
import bisect
import os
import pickle
import re
import struct
import sys
import time
from array import array
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strxref                                    # noqa: E402
from strxref import BuildError, PE, Index         # noqa: E402

VT_INDEX = os.path.join(HERE, "index", "vtables.idx")
SCHEMA = r"G:\git\Supervive Revival Project\schema.txt"

# ---- disassembly-lite -----------------------------------------------------
# lea r64,[rip+disp32] : REX.W(48 or 4C for REX.R) / 8D / modrm(mod=00,rm=101) / disp32
RX_LEA = re.compile(rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]")
BRANCH = (b"\xe8", b"\xe9")           # call rel32, jmp rel32
TERM = 0xC3

# Ground truth: captured 2026-06-28 from the LIVE process with `usmapdump vtdump`
# (docs/lokiassetmanager-vtable-dump.md).  Independent of this tool.
GT_VTABLE = 0x888CB78
GT_SLOTS = {0: 0x52A7AB0, 47: 0x12CC100, 88: 0x34CF9F0, 94: 0x34AB870,
            95: 0x34CA500, 97: 0x34B6FC0, 111: 0x34C0420, 127: 0x34AA740}
GT_CLASS = "ULokiAssetManager"

# Class->vtable pairs recovered from the LIVE process in earlier sessions (CDO scan
# + `usmapdump findptr`), recorded in docs/.  Independent of this tool.
GT_CLASS_VTABLES = [
    ("ULokiAssetManager", 0x888CB78, "lokiassetmanager-vtable-dump.md:110"),
    ("ALokiPlayerState", 0x8A2D718, "lokiassetmanager-vtable-dump.md:575"),
    # docs/lokiassetmanager-vtable-dump.md:584 records "+0x88ADED0".  That is a
    # TRANSCRIPTION TYPO (8A -> 88).  Adjudicated by measurement, three ways:
    #   0x88ADED0  no code references it at all, and it shares 5% of its first 40
    #              slots with UObject's vtable -- impossible for a UObject subclass.
    #   0x8AADED0  referenced by 2 LEAs, 88 slots (same length as UObject's), shares
    #              97.5% of its first 40 slots with UObject's vtable, and its slot 0
    #              (0x54A44A0) is in the same compilation unit as UMissionsModel's
    #              GetPrivateStaticClass (0x54A2BF0) and InternalConstructor (0x54A30C0).
    ("UMissionsModel", 0x8AADED0, "lokiassetmanager-vtable-dump.md:584 (typo-corrected)"),
    ("UAssetRegistryImpl", 0x79D5328, "lokiassetmanager-vtable-dump.md:896"),
    ("ULocalPlayer", 0x8117130, "session-79-moonshot-plan.md:1105"),
]
# Live-verified SHARED vtable: 10 distinct subclass CDOs were observed sharing it
# (docs/lokiassetmanager-vtable-dump.md:898).  Proof that many-to-one vtable->class
# is a real property of the binary (MSVC ICF), not an artifact of this tool.
GT_SHARED_VTABLE = (0x76EF750, "UAssetRegistry base, >=10 CDOs share it")


# --------------------------------------------------------------------------
# Exact function bounds from the recovered unwind table -- WITH CHAIN MERGING.
# --------------------------------------------------------------------------
# strxref.true_func() returns one RUNTIME_FUNCTION range.  On x64 a single C++
# function may own SEVERAL of them (chained UNWIND_INFO, UNW_FLAG_CHAININFO), so a
# raw range is a FRAGMENT bound, not a function bound.  MEASURED on
# index/pdata_union.csv: 147,176 of 382,282 ranges begin exactly where the previous
# one ends, and 129,033 of those begin at a NON-16-aligned address.  MSVC aligns
# real function entries to 16, so an unaligned continuation is a chained fragment
# while an aligned one is a genuinely adjacent next function.
#
# PROOF this matters, not a style preference: 0x12BF4B0 (ULinkerPlaceholderClass's
# constructor) has raw bounds 0x12BF4B0..0x12BF4C1 = 17 bytes, yet its own
# `jz` at +0x0C targets 0x12BF4FB.  A jump inside a function cannot leave it.
# Merging unaligned continuations gives 0x12BF4B0..0x12BF4FD (77 bytes), which
# contains the target.  382,282 fragments -> 253,249 functions.
_MERGED = {}


def merged_func(rva):
    """Exact (begin, end) with chained unwind fragments merged, or (None, None)."""
    p = strxref.load_pdata()
    if not p:
        return None, None
    beg, end = p
    i = bisect.bisect_right(beg, rva) - 1
    if i < 0 or rva >= end[i]:
        return None, None
    while i > 0 and beg[i] == end[i - 1] and beg[i] % 16:
        i -= 1
    hit = _MERGED.get(beg[i])
    if hit:
        return hit
    e, k, n = end[i], i + 1, len(beg)
    while k < n and beg[k] == e and beg[k] % 16:
        e = end[k]
        k += 1
    _MERGED[beg[i]] = (beg[i], e)
    return beg[i], e


def lea_dest_reg(d, o):
    """Register number written by the `lea` at offset o."""
    return ((d[o] & 0x04) << 1) | ((d[o + 2] >> 3) & 0x07)


def store_after_lea(d, o):
    """If the instruction after `lea` at o is `mov [base+disp], <that same reg>`,
    return disp, else None.  Encoding: REX(48|4C) 89 modrm [sib] [disp8/32]."""
    p = o + 7
    if d[p] not in (0x48, 0x4C, 0x49, 0x4D) or d[p + 1] != 0x89:
        return None
    src = ((d[p] & 0x04) << 1) | ((d[p + 2] >> 3) & 0x07)
    if src != lea_dest_reg(d, o):
        return None
    modrm = d[p + 2]
    mod, rm = modrm >> 6, modrm & 0x07
    if mod == 3:
        return None                        # register-to-register, not a store
    q = p + 3
    if rm == 4:                            # SIB byte
        q += 1
    if mod == 0:
        return 0 if rm != 5 else None      # rm==5 -> rip-relative, not a `this` store
    if mod == 1:
        return struct.unpack_from("<b", d, q)[0]
    return struct.unpack_from("<i", d, q)[0]


# --------------------------------------------------------------------------
# 1. structural scan: runs of consecutive .text pointers in .rdata
# --------------------------------------------------------------------------
def scan_runs(pe):
    d, ib = pe.d, pe.imagebase
    _, tva, tvs, _, _ = pe.sec(".text")
    tend = tva + tvs
    _, rva, rvs, _, _ = pe.sec(".rdata")
    start = (rva + 7) & ~7
    n = (rva + rvs - start) // 8
    q = array("Q")
    q.frombytes(d[start:start + n * 8])
    lo, hi = ib + tva, ib + tend
    runs = []
    i = 0
    nzero = nother = ntext = 0
    while i < n:
        v = q[i]
        if not (lo <= v < hi):
            if v == 0:
                nzero += 1
            else:
                nother += 1
            i += 1
            continue
        j = i
        while j < n and lo <= q[j] < hi:
            j += 1
        ntext += j - i
        runs.append((start + i * 8, j - i))
        i = j
    return runs, dict(text=ntext, zero=nzero, other=nother, slots=n)


# --------------------------------------------------------------------------
# 2. code scan: LEA targets into .rdata, and which are install-shaped
# --------------------------------------------------------------------------
def scan_lea_targets(pe):
    d = pe.d
    _, tva, tvs, _, _ = pe.sec(".text")
    _, rva, rvs, _, _ = pe.sec(".rdata")
    rlo, rhi = rva, rva + rvs
    tx = d[tva:tva + tvs]
    up = struct.unpack_from
    lea = Counter()
    inst = defaultdict(list)          # rdata target -> [(site, disp)]
    for m in RX_LEA.finditer(tx):
        o = m.start()
        if o + 12 > len(tx):
            continue
        t = tva + o + 7 + up("<i", tx, o + 3)[0]
        if not (rlo <= t < rhi):
            continue
        lea[t] += 1
        disp = store_after_lea(tx, o)
        if disp is not None:
            inst[t].append((tva + o, disp))
    return lea, inst


def cut_runs(runs, cuts):
    """Split each run at the given 8-aligned addresses.  Returns (start, nslots,
    head_flag) where head_flag means 'this piece begins at the run head and no
    code references it', i.e. its start is UNPROVEN."""
    cs = sorted(cuts)
    out = []
    for a, l in runs:
        end = a + l * 8
        i = bisect.bisect_left(cs, a)
        pts = []
        while i < len(cs) and cs[i] < end:
            pts.append(cs[i])
            i += 1
        if not pts:
            out.append((a, l, True))
            continue
        if pts[0] != a:
            pts.insert(0, a)
            head = True
        else:
            head = False
        for k, c in enumerate(pts):
            e = pts[k + 1] if k + 1 < len(pts) else end
            out.append((c, (e - c) // 8, head and k == 0))
    return out


# --------------------------------------------------------------------------
# 3. UE reflection boilerplate -> class names
# --------------------------------------------------------------------------
CLASSNAME = re.compile(r"^[UAFIT][A-Z][A-Za-z0-9_]{1,90}$")


def find_gpsc(idx, d):
    """Every UFoo::GetPrivateStaticClass, keyed by entry RVA.

    Discovery is structural, not name-guessing: a function qualifies iff it
    references a wide L"/Script/<Module>" string AND exactly one other wide string
    shaped like a C++ class name.  Returns {entry: (name, (modules...))}.
    """
    script = []
    for i in range(len(idx.s_rva)):
        if idx.s_enc[i] != ord("U"):
            continue
        t = idx.text_of(i, d)
        if t.startswith("/Script/") and "." not in t and 8 < len(t) < 48:
            script.append(i)
    fn2mod = defaultdict(set)
    for i in script:
        t = idx.text_of(i, d)
        for site, _k, _s in idx.refs_to(i):
            e, _f, _ti, _end = idx.func_of(site)
            if e:
                fn2mod[e].add(t)
    out, stat = {}, Counter()
    for e, mods in fn2mod.items():
        _e, _f, _ti, end = idx.func_of(e)
        names = set()
        for _site, si, _kind in idx.refs_in(e, end):
            if idx.s_enc[si] != ord("U"):
                continue
            t = idx.text_of(si, d)
            if CLASSNAME.match(t):
                names.add(t)
        if len(names) == 1:
            out[e] = (names.pop(), tuple(sorted(mods)))
            stat["named"] += 1
        else:
            stat["ambiguous" if names else "no-name"] += 1
    return out, stat


# --------------------------------------------------------------------------
# 4. constructor walk: GetPrivateStaticClass -> InternalConstructor -> vtable
# --------------------------------------------------------------------------
MAXWIN = 0x800          # bytes of a GetPrivateStaticClass body we are willing to scan
THUNKWIN = 0x30         # InternalConstructor is a ~20-byte thunk
CTORWIN = 0x200         # ctor prologue window in which the vtable install happens
MAXTHUNK = 3            # chained tail-jump thunks to follow


class Walker:
    def __init__(self, pe, idx, vt_starts):
        self.d = pe.d
        _, self.tva, tvs, _, _ = pe.sec(".text")
        self.tend = self.tva + tvs
        _, rva, rvs, _, _ = pe.sec(".rdata")
        self.rlo, self.rhi = rva, rva + rvs
        self.idx = idx
        self.vt = vt_starts                     # set of accepted vtable starts
        self._win = {}

    def window(self, f):
        """[lo,hi) of a function body.

        Prefers the EXACT bounds recovered from the packer's dynamic function table
        (strxref.true_func, S102 -- minidump stream 13, 382,282 exact ranges).  Falls
        back to strxref's next-candidate upper bound, then to a fixed window, so this
        still works if index/pdata_union.csv is absent."""
        w = self._win.get(f)
        if w is None:
            tb, te = merged_func(f)
            if tb == f:
                w = (f, min(te, f + MAXWIN))
            else:
                e, _fl, _ti, end = self.idx.func_of(f)
                hi = min(end, f + MAXWIN) if e == f else f + 0x200
                w = (f, min(hi, self.tend))
            self._win[f] = w
        return w

    def text_leas(self, lo, hi):
        d = self.d
        out = []
        for m in RX_LEA.finditer(d[lo:hi]):
            o = m.start()
            if o + 7 > hi - lo:
                continue
            t = lo + o + 7 + struct.unpack_from("<i", d, lo + o + 3)[0]
            if self.tva <= t < self.tend:
                out.append((lo + o, t))
        return out

    def installs(self, lo, hi):
        """(site, vtable_rva, disp) for every vtable-install in [lo,hi)."""
        d = self.d
        out = []
        for m in RX_LEA.finditer(d[lo:hi]):
            o = m.start()
            if o + 12 > hi - lo:
                continue
            s = lo + o
            t = s + 7 + struct.unpack_from("<i", d, s + 3)[0]
            if t not in self.vt:
                continue
            disp = store_after_lea(d, s)
            if disp is not None:
                out.append((s, t, disp))
        return out

    def tail_branches(self, lo, hi):
        """TAIL branch targets (jmp rel32 / jcc rel32) inside [lo,hi).

        Deliberately EXCLUDES `call` (E8).  That exclusion is the whole
        correctness argument for the ctor walk: MSVC compiles
            InternalConstructor<T> -> [thunk] -> jmp T::T(FObjectInitializer const&)
        so a TAIL branch stays inside the same object's construction, whereas a
        CALL from the ctor is the BASE-class ctor -- which installs the BASE's
        vtable.  Following calls is exactly how an earlier version of this walk
        mis-assigned 3,287 derived classes their base's vtable.

        A TAIL branch must also be the LAST instruction of the thunk, i.e. the very
        next byte is `ret`/`int3`.  Without that test a forward `jz <epilogue>` --
        the null check `if (!Obj) return;` -- is mistaken for the tail jump and the
        walk lands in the middle of the next function.  (Measured: that was the
        UMissionsModel miss; UE emits both shapes.)
        """
        d = self.d
        out = []
        b = d[lo:hi]
        for m in re.finditer(rb"\xe9", b):
            o = m.start()
            if o + 5 > len(b):
                continue
            t = lo + o + 5 + struct.unpack_from("<i", d, lo + o + 1)[0]
            if self.tva <= t < self.tend:
                out.append((lo + o, t))
        for m in re.finditer(rb"\x0f[\x80-\x8f]", b):
            o = m.start()
            if o + 7 > len(b) or b[o + 6] not in (0xC3, 0xCC):
                continue
            t = lo + o + 6 + struct.unpack_from("<i", d, lo + o + 2)[0]
            if self.tva <= t < self.tend:
                out.append((lo + o, t))
        out.sort()
        return out

    def real_ctor(self, ic):
        """Follow InternalConstructor's tail-jump chain to the real C++ ctor."""
        f = ic
        for _ in range(MAXTHUNK):
            br = self.tail_branches(f, f + THUNKWIN)
            if not br:
                return f
            f = br[0][1]
        return f

    def vt_leas(self, lo, hi):
        """(offset, vtable_rva, store_disp_or_None) for LEAs of vtable candidates."""
        d = self.d
        out = []
        n = hi - lo
        for m in RX_LEA.finditer(d[lo:hi]):
            o = m.start()
            if o + 7 > n:
                continue
            s = lo + o
            t = s + 7 + struct.unpack_from("<i", d, s + 3)[0]
            if t in self.vt:
                out.append((o, t, store_after_lea(d, s) if o + 12 <= n else None))
        return out

    def is_internal_ctor(self, f):
        """InternalConstructor<T> shape: read [rcx] into a register and test it,
        then tail-branch to the real ctor.  Both observed encodings:
            48 8B 01 48 85 C0 ...        (mov rax,[rcx]; test rax,rax)
            40 53 48 83 EC 20 48 8B 19 48 85 DB ...  (frame, then mov rbx,[rcx])
        """
        b = self.d[f:f + 24]
        if len(b) < 12 or not any(b):
            return False
        i = b.find(b"\x48\x8b")
        if i < 0 or i > 10:
            return False
        j = b.find(b"\x48\x85", i)
        return 0 <= j - i <= 6


def resolve_classes(pe, idx, gpsc, vt_starts, ctorwin=CTORWIN, rule="first"):
    """class name -> primary vtable, via GetPrivateStaticClass -> InternalConstructor
    -> (tail jumps only) -> the real ctor -> its first vtable LEA.

    `rule` selects how the primary is picked among the ctor's vtable LEAs:
      "first"  -- lowest offset in the ctor body.  MSVC calls the BASE ctor first
                  and installs THIS class's vtable immediately after, so the first
                  vtable literal a ctor mentions is its own.
      "lastd0" -- the last one with an adjacent `mov [reg+0], r64`, else "first".
                  Correct instead of "first" only when the base ctor was inlined.
    Both are MEASURED against ground truth in verify(); see docs/strxref-vtables.md.
    """
    w = Walker(pe, idx, vt_starts)
    res, stat = {}, Counter()
    for g, (name, mods) in gpsc.items():
        _e, _f, _ti, end = idx.func_of(g)
        tgts = [t for _s, t in w.text_leas(g, min(end, g + MAXWIN))]
        ic = next((t for t in reversed(tgts) if w.is_internal_ctor(t)), None)
        if ic is None:
            ic = tgts[-1] if tgts else None
            stat["ic-by-position"] += 1
        else:
            stat["ic-by-shape"] += 1
        if ic is None:
            stat["no-ctor"] += 1
            continue
        ctor = w.real_ctor(ic)
        rec = dict(gpsc=g, ic=ic, ctor=ctor, vtable=None, conf="NONE",
                   modules=mods, subobjects=[], cands=[])
        if not any(pe.d[ctor:ctor + 64]):
            stat["ctor-page-not-decrypted"] += 1
            rec["conf"] = "NO-CODE"
            res[name] = rec
            continue
        tb, te = merged_func(ctor)
        hi = min(te, ctor + ctorwin) if tb == ctor else ctor + ctorwin
        cands = w.vt_leas(ctor, hi)
        if not cands:
            stat["no-vtable-lea"] += 1
            res[name] = rec
            continue
        d0 = [c for c in cands if c[2] == 0]
        pick = d0[-1] if (rule == "lastd0" and d0) else cands[0]
        rec["vtable"] = pick[1]
        rec["cands"] = [(o, v, dp) for o, v, dp in cands]
        rec["subobjects"] = sorted({(v, dp) for o, v, dp in cands
                                    if v != pick[1] and dp not in (None, 0)})
        # HIGH when the pick is unambiguous: it is the only vtable literal, or it
        # is the first AND carries a `mov [reg+0]` store.
        rec["conf"] = "HIGH" if (len(cands) == 1 or pick[2] == 0) else "MED"
        stat["resolved"] += 1
        stat["conf-" + rec["conf"]] += 1
        res[name] = rec
    return res, stat


# --------------------------------------------------------------------------
# 5. independent validator: inheritance similarity (schema.txt)
# --------------------------------------------------------------------------
def load_super(path=SCHEMA):
    """{ClassName(no prefix): SuperName(no prefix)} from schema.txt."""
    sup = {}
    rx = re.compile(r"^  ([A-Za-z0-9_]+) : (?:UClass|UStruct):([A-Za-z0-9_]+)")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = rx.match(line)
                if m:
                    sup[m.group(1)] = m.group(2)
    except OSError:
        return {}
    return sup


def slots_of(d, ib, rva, n):
    return [struct.unpack_from("<Q", d, rva + i * 8)[0] - ib for i in range(n)]


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def build(dump_path, log=print):
    t0 = time.time()
    pe = PE(dump_path)
    idx = Index.load(strxref.INDEX_PATH)
    if os.path.abspath(idx.dump_path) != os.path.abspath(dump_path):
        raise BuildError("strxref index was built from %s but this run uses %s -- "
                         "rebuild strxref first" % (idx.dump_path, dump_path))
    d = pe.d
    log("vtables build  dump=%s" % dump_path)

    t = time.time()
    runs, rstat = scan_runs(pe)
    log("  .rdata qword slots %d : text-ptr %d  zero %d  other %d ; %d maximal runs [%.1fs]"
        % (rstat["slots"], rstat["text"], rstat["zero"], rstat["other"], len(runs),
           time.time() - t))

    t = time.time()
    lea, inst = scan_lea_targets(pe)
    log("  .rdata LEA targets %d ; install-shaped %d  [%.1fs]"
        % (len(lea), len(inst), time.time() - t))

    run_start = [a for a, _l in runs]

    def in_run(rva):
        i = bisect.bisect_right(run_start, rva) - 1
        if i < 0:
            return False
        a, l = runs[i]
        return a <= rva < a + l * 8

    cuts_all = {t_ for t_ in lea if t_ % 8 == 0 and in_run(t_)}
    cuts_inst = {t_ for t_ in inst if t_ % 8 == 0 and in_run(t_)}
    log("  cuts: any-LEA %d ; install-shaped %d" % (len(cuts_all), len(cuts_inst)))

    vts = cut_runs(runs, cuts_all)
    log("  vtable candidates after cutting: %d" % len(vts))
    vt_by_start = {a: (l, head) for a, l, head in vts}

    t = time.time()
    gpsc, gstat = find_gpsc(idx, d)
    log("  GetPrivateStaticClass functions named: %d  (%s)  [%.1fs]"
        % (len(gpsc), dict(gstat), time.time() - t))

    t = time.time()
    res, rstat2 = resolve_classes(pe, idx, gpsc, set(vt_by_start))
    log("  classes walked: %d  (%s)  [%.1fs]" % (len(res), dict(rstat2), time.time() - t))

    ix = dict(version=2, dump_path=os.path.abspath(dump_path), imagebase=pe.imagebase,
              sections=pe.sections, runs=runs, vts=vts, classes=res,
              lea=dict(lea), inst={k: v for k, v in inst.items()},
              rstat=rstat, gstat=dict(gstat), rstat2=dict(rstat2),
              n_cuts_all=len(cuts_all), n_cuts_inst=len(cuts_inst),
              build_secs=round(time.time() - t0, 1))
    os.makedirs(os.path.dirname(VT_INDEX), exist_ok=True)
    with open(VT_INDEX, "wb") as f:
        pickle.dump(ix, f, protocol=5)
    log("  index written: %s (%.1f MB)  TOTAL %.1fs"
        % (VT_INDEX, os.path.getsize(VT_INDEX) / 1e6, time.time() - t0))
    return ix, pe, idx


def load():
    if not os.path.exists(VT_INDEX):
        raise SystemExit("no vtable index -- run:  python vtables.py scan")
    with open(VT_INDEX, "rb") as f:
        ix = pickle.load(f)
    if ix.get("version") != 2:
        raise SystemExit("stale vtable index -- run:  python vtables.py scan")
    pe = PE(ix["dump_path"])
    idx = Index.load(strxref.INDEX_PATH)
    return ix, pe, idx


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------
def verify(ix, pe, idx, P=print):
    d, ib = pe.d, pe.imagebase
    ok = []
    P("=" * 78)
    P("VTABLE VALIDATION")
    P("=" * 78)

    # -- GT1: the live-captured LokiAssetManager vtable reproduces from this dump
    P("[GT-1] docs/lokiassetmanager-vtable-dump.md was captured 2026-06-28 from the")
    P("       LIVE process (usmapdump vtdump). Reproduce it from the cold dump:")
    good = 0
    for slot, want in sorted(GT_SLOTS.items()):
        got = struct.unpack_from("<Q", d, GT_VTABLE + slot * 8)[0] - ib
        m = got == want
        good += m
        P("         slot %3d  want 0x%07X  got 0x%07X  %s" % (slot, want, got, "OK" if m else "MISS"))
    ok.append(good == len(GT_SLOTS))
    P("       %d / %d slots match  ->  .rdata vtables ARE readable in the cold dump"
      % (good, len(GT_SLOTS)))

    # -- GT2: the structural scan finds it, and the cut lands on its true start
    hit = [(a, l, h) for a, l, h in ix["vts"] if a == GT_VTABLE]
    P("[GT-2] cut-derived vtable starting exactly at 0x%08X: %s"
      % (GT_VTABLE, ("len %d slots (head-unproven=%s)" % (hit[0][1], hit[0][2])) if hit else "NOT FOUND"))
    ok.append(bool(hit))

    # -- GT3: the naming pipeline reaches the right vtable from the class name alone.
    # Every pair below was captured from the LIVE process in an earlier session.
    P("[GT-3] name->vtable via GetPrivateStaticClass -> InternalConstructor -> ctor,")
    P("       against class/vtable pairs captured LIVE in earlier sessions:")
    good = 0
    for nm, want, src in GT_CLASS_VTABLES:
        c = ix["classes"].get(nm)
        got = c["vtable"] if c else None
        m = got == want
        good += m
        P("         %-22s want 0x%08X  got %-12s %-5s %s   [%s]"
          % (nm, want, ("0x%08X" % got) if got else "None",
             c["conf"] if c else "-", "OK" if m else "MISS", src))
    P("       %d / %d" % (good, len(GT_CLASS_VTABLES)))
    ok.append(good == len(GT_CLASS_VTABLES))

    # -- GT4: independent structural check -- inheritance similarity.
    # A derived class's vtable must share most of its base's slots (only overrides
    # differ) and be at least as long.  The inheritance graph comes from schema.txt
    # (UE reflection data), which this tool never touches otherwise.
    sup = load_super()
    P("[GT-4] inheritance-similarity control (super chain from schema.txt, %d classes):"
      % len(sup))
    byname = {k: v for k, v in ix["classes"].items() if v["vtable"]}
    nostrip = {k.lstrip("UAFIT") if False else k[1:]: v for k, v in byname.items()}
    tested = shared = 0
    ratios = []
    for name, v in byname.items():
        base = sup.get(name[1:])
        if not base:
            continue
        cand = [nm for nm in byname if nm[1:] == base]
        if not cand:
            continue
        bv = byname[cand[0]]["vtable"]
        if bv == v["vtable"]:
            continue
        nb = min(vt_len(ix, bv), vt_len(ix, v["vtable"]), 400)
        if nb < 8:
            continue
        a = slots_of(d, ib, v["vtable"], nb)
        b = slots_of(d, ib, bv, nb)
        same = sum(1 for x, y in zip(a, b) if x == y)
        ratios.append(same / nb)
        tested += 1
        shared += same / nb >= 0.5
    if tested:
        ratios.sort()
        P("         %d class/super vtable pairs both resolved" % tested)
        P("         median shared-slot fraction %.1f%% ; %d of %d pairs share >=50%%  (%.1f%%)"
          % (100 * ratios[len(ratios) // 2], shared, tested, 100.0 * shared / tested))
        P("         random pairs would share ~0%%; this is the accuracy control.")
        ok.append(shared / tested > 0.8)
    else:
        P("         no testable pairs")

    # -- GT5: many-to-one is REAL (MSVC identical-COMDAT-folding), not a tool bug
    P("[GT-5] vtable sharing:")
    n_multi = Counter(v["vtable"] for v in ix["classes"].values() if v["vtable"])
    dupes = [(k, n) for k, n in n_multi.items() if n > 1]
    nshared = sum(n for _k, n in dupes)
    P("         distinct vtables assigned: %d to %d classes ; %d vtables carry >1 class"
      % (len(n_multi), sum(n_multi.values()), len(dupes)))
    sv, why = GT_SHARED_VTABLE
    P("         control: 0x%08X (%s) -> this tool assigns it to %d classes"
      % (sv, why, n_multi.get(sv, 0)))
    P("         Sharing is a PROPERTY OF THE BINARY: MSVC folds identical vtables")
    P("         (classes that add no virtual of their own), so vtable->class is")
    P("         many-to-one and NOT invertible.  Verified live in an earlier session.")
    ok.append(n_multi.get(sv, 0) > 1)

    # -- GT5b: negative controls
    off = struct.unpack_from("<Q", d, GT_VTABLE + 3)[0]   # deliberately misaligned
    P("[GT-5b] misaligned read at vtable+3 -> 0x%016X (not an image pointer: %s)"
      % (off, not (ib <= off < ib + pe.sizeofimage)))
    ok.append(not (ib <= off < ib + pe.sizeofimage))

    # -- GT6: RTTI really is stripped (this is WHY names must come from UE)
    _, rva, rvs, _, _ = pe.sec(".rdata")
    nrtti = d.count(b".?AV", rva, rva + rvs) + d.count(b".?AU", rva, rva + rvs)
    P("[GT-6] MSVC RTTI type descriptors ('.?AV'/'.?AU') in .rdata: %d" % nrtti)
    P("       -> 0 means no vtable can be named from RTTI; naming MUST come from")
    P("          UE's IMPLEMENT_CLASS boilerplate (that is what this tool does).")
    ok.append(nrtti == 0)

    nfail = sum(1 for x in ok if not x)
    P("")
    P("VALIDATION: %d checks, %d failed" % (len(ok), nfail))
    P("=" * 78)
    return nfail


def vt_len(ix, rva):
    for a, l, _h in ix["vts"]:
        if a == rva:
            return l
    return 0


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def cmd_stats(ix, pe, idx, args):
    P = print
    rs = ix["rstat"]
    P("dump        : %s" % ix["dump_path"])
    P(".rdata      : %d qword slots -> %d point into .text (%.1f%%), %d zero, %d other"
      % (rs["slots"], rs["text"], 100.0 * rs["text"] / rs["slots"], rs["zero"], rs["other"]))
    lens = [l for _a, l in ix["runs"]]
    P("runs        : %d maximal text-pointer runs; max %d slots" % (len(ix["runs"]), max(lens)))
    h = Counter(lens)
    P("              len 1: %d   2-3: %d   4-7: %d   8-31: %d   32-127: %d   >=128: %d"
      % (h[1], sum(v for k, v in h.items() if 2 <= k <= 3),
         sum(v for k, v in h.items() if 4 <= k <= 7),
         sum(v for k, v in h.items() if 8 <= k <= 31),
         sum(v for k, v in h.items() if 32 <= k <= 127),
         sum(v for k, v in h.items() if k >= 128)))
    P("cuts        : any-LEA %d ; install-shaped %d" % (ix["n_cuts_all"], ix["n_cuts_inst"]))
    vl = [l for _a, l, _h in ix["vts"]]
    vl.sort()
    P("vtables     : %d candidates after cutting" % len(ix["vts"]))
    P("              slot-count  min %d  p25 %d  median %d  p75 %d  p90 %d  max %d"
      % (vl[0], vl[len(vl) // 4], vl[len(vl) // 2], vl[3 * len(vl) // 4],
         vl[int(len(vl) * .9)], vl[-1]))
    hh = Counter(vl)
    P("              1-3 slots: %d   4-7: %d   8-31: %d   32-127: %d   128-511: %d   >=512: %d"
      % (sum(v for k, v in hh.items() if k <= 3), sum(v for k, v in hh.items() if 4 <= k <= 7),
         sum(v for k, v in hh.items() if 8 <= k <= 31),
         sum(v for k, v in hh.items() if 32 <= k <= 127),
         sum(v for k, v in hh.items() if 128 <= k <= 511),
         sum(v for k, v in hh.items() if k >= 512)))
    unproven = sum(1 for _a, _l, hd in ix["vts"] if hd)
    P("              starts unproven (run head, no code reference): %d" % unproven)
    cl = ix["classes"]
    named = sum(1 for v in cl.values() if v["vtable"])
    P("classes     : %d GetPrivateStaticClass found; %d resolved to a vtable (%.1f%%)"
      % (len(cl), named, 100.0 * named / max(len(cl), 1)))
    mods = Counter(m for v in cl.values() for m in v["modules"])
    P("              top modules: %s" % ", ".join("%s=%d" % (m.split("/")[-1], n)
                                                  for m, n in mods.most_common(8)))
    lok = [k for k, v in cl.items() if any("Loki" in m for m in v["modules"])]
    lokv = [k for k in lok if cl[k]["vtable"]]
    P("              /Script/Loki: %d classes, %d with a vtable" % (len(lok), len(lokv)))
    sec = sum(1 for v in cl.values() if v["subobjects"])
    P("              whose ctor also installs >=1 SUBOBJECT vtable: %d" % sec)
    # decrypted-page reachability of slot targets
    d, ib = pe.d, pe.imagebase
    tot = dec = 0
    for a, l, _h in ix["vts"][:20000]:
        for i in range(min(l, 64)):
            v = struct.unpack_from("<Q", d, a + i * 8)[0] - ib
            tot += 1
            dec += d[v] != 0
    P("slot targets: %d sampled, %.1f%% land in DECRYPTED .text (the rest are real"
      % (tot, 100.0 * dec / max(tot, 1)))
    P("              pointers whose CODE this dump never captured)")


def slot_label(idx, d, rva, maxs=3):
    """Best-effort name for a vtable slot target, from the strings its function uses.

    Uses the EXACT function bounds recovered from the packer's dynamic function
    table when available (S102); otherwise strxref's upper-bound extent, which
    under-reports (the heuristic bound averages ~259 bytes)."""
    tb, te = merged_func(rva)
    if tb == rva:
        e, end = tb, te
    else:
        e, f, ti, end = idx.func_of(rva)
        if e is None:
            return "?", []
        end = min(end, e + 0x2000)
    refs = idx.refs_in(e, end)
    out = []
    seen = set()
    for _site, si, _k in refs:
        if si in seen:
            continue
        seen.add(si)
        t = idx.text_of(si, d)
        out.append(t)
        if len(out) >= maxs:
            break
    return ("0x%07X" % e), out


def dump_vtable(ix, pe, idx, rva, n=None, strings=False, P=print):
    d, ib = pe.d, pe.imagebase
    L = vt_len(ix, rva)
    piece = next(((a, l, h) for a, l, h in ix["vts"] if a == rva), None)
    owner = [k for k, v in ix["classes"].items() if v["vtable"] == rva]
    P("vtable  0x%08X   slots %s   owner %s"
      % (rva, L if L else "?", owner or "<unnamed>"))
    if piece and piece[2]:
        P("        NOTE: this piece starts at a run head with no code reference --")
        P("              its START is unproven (it may be the tail of another vtable).")
    P("        length is an UPPER BOUND: the next cut is the next CODE-REFERENCED")
    P("        vtable start; a vtable whose ctor page is not decrypted leaves no cut.")
    n = n or (L or 32)
    shared = Counter()
    for i in range(n):
        v = struct.unpack_from("<Q", d, rva + i * 8)[0] - ib
        shared[v] += 1
    for i in range(n):
        v = struct.unpack_from("<Q", d, rva + i * 8)[0] - ib
        e, strs = slot_label(idx, d, v)
        dec = "" if d[v] else "  [page not decrypted]"
        s = ""
        if strings and strs:
            s = "  " + " | ".join(repr(x[:40]) for x in strs[:2])
        P("  [%3d] 0x%07X  fn %s%s%s" % (i, v, e, dec, s))


# --------------------------------------------------------------------------
# technique (a): name a vtable from the strings its methods reference
# --------------------------------------------------------------------------
# UE C++ logs the qualified name of the emitting method in a large fraction of its
# warning/error/ensure text ("ULokiGameFeatureToggles::Get %s called ...").  So the
# `Ident::` tokens reachable from a vtable's slots are a naming signal that owes
# nothing to RTTI.  This block MEASURES how good that signal actually is, scored
# against the independent UE-boilerplate name map built above.
RX_QUAL = re.compile(r"\b([UAFIST][A-Za-z0-9_]{2,60})::")
RX_FILE = re.compile(r"([A-Za-z0-9_]{3,60})\.(?:cpp|h)\b")


def vtable_tokens(ix, pe, idx, rva, nslots=None, maxslots=200, span="all"):
    """Counter of class-name tokens harvested from the strings of a vtable's slots.

    `span` picks WHICH slots: "head" (first N) are almost entirely INHERITED base
    virtuals; "tail" (last N) are where a derived class's own overrides sit, because
    MSVC appends new virtuals after the base's.  Measured: that choice changes the
    answer, so it is a parameter, not a detail.

    Returns (tokens, nslots_scanned, nslots_with_code, nslots_with_strings)."""
    d, ib = pe.d, pe.imagebase
    L = vt_len(ix, rva) or 32
    n = min(nslots or L, maxslots)
    if span == "tail":
        rng = range(max(0, L - n), L)
    elif span == "head":
        rng = range(n)
    else:
        rng = range(min(L, maxslots))
    tok = Counter()
    seen_fn = set()
    have_code = have_str = 0
    n = len(rng)
    for i in rng:
        v = struct.unpack_from("<Q", d, rva + i * 8)[0] - ib
        if not (idx.text_va <= v < idx.text_end):
            continue
        pg = v & ~0xFFF
        if not any(d[pg:pg + 4096]):
            continue                      # page this dump never decrypted
        have_code += 1
        e, _f, _ti, end = idx.func_of(v)
        if e is None or e in seen_fn:
            continue
        seen_fn.add(e)
        got = False
        for _site, si, _k in idx.refs_in(e, min(end, e + 0x1000)):
            t = idx.text_of(si, d)
            for m in RX_QUAL.finditer(t):
                tok[m.group(1)] += 1
                got = True
            for m in RX_FILE.finditer(t):
                tok["*" + m.group(1)] += 1
                got = True
        have_str += got
    return tok, n, have_code, have_str


def cmd_strings(ix, pe, idx, args):
    rva = args.target if isinstance(args.target, int) else None
    if rva is None:
        c = ix["classes"].get(args.target)
        if not c or not c["vtable"]:
            print("no vtable for %r" % args.target)
            return
        rva = c["vtable"]
    tok, n, hc, hs = vtable_tokens(ix, pe, idx, rva, args.slots, span=args.span)
    owner = [k for k, v in ix["classes"].items() if v["vtable"] == rva]
    print("vtable 0x%08X  owner %s" % (rva, owner or "<unnamed>"))
    print("  %d slots scanned; %d land in decrypted .text; %d distinct fns reference strings"
          % (n, hc, hs))
    if not tok:
        print("  no qualified-name tokens found")
        return
    print("  top tokens ('*X' = source file X.cpp):")
    for t, c in tok.most_common(args.n):
        print("    %-46s %d" % (t, c))


def cmd_bench(ix, pe, idx, args):
    """Score technique (a) -- strings-only naming -- against the UE-boilerplate map."""
    cl = ix["classes"]
    owners = defaultdict(list)
    for k, v in cl.items():
        if v["vtable"]:
            owners[v["vtable"]].append(k)
    uniq = [(vt, ns[0]) for vt, ns in owners.items() if len(ns) == 1]
    uniq.sort()
    if args.n:
        step = max(1, len(uniq) // args.n)
        uniq = uniq[::step][:args.n]
    span = args.span
    tot = hit1 = hit3 = anytok = anywhere = 0
    slots_tot = slots_code = slots_str = 0
    fam = 0
    for vt, name in uniq:
        tok, n, hc, hs = vtable_tokens(ix, pe, idx, vt, nslots=args.slots, span=span)
        slots_tot += n; slots_code += hc; slots_str += hs
        tot += 1
        if not tok:
            continue
        anytok += 1
        ranked = [t for t, _c in tok.most_common(8) if not t.startswith("*")]
        bare = name[1:]
        if ranked and ranked[0] in (name, bare):
            hit1 += 1
        if name in ranked[:3] or bare in ranked[:3]:
            hit3 += 1
        if name in tok or bare in tok:
            anywhere += 1
        # "family" credit: the top token is a class in the same inheritance chain
        if ranked and (bare.startswith(ranked[0].lstrip("UAFIST")[:6] or "\0")
                       or ranked[0].lstrip("UAFIST")[:6] in bare):
            fam += 1
    P = print
    P("TECHNIQUE (a): naming a vtable from its methods' strings")
    P("  scored against the %d vtables the UE-boilerplate route names UNIQUELY" % len(owners))
    P("  sample: %d vtables, span=%s, <=%d slots each" % (tot, span, args.slots))
    P("  slots: %d scanned, %d (%.1f%%) in decrypted .text, %d fns reference any string"
      % (slots_tot, slots_code, 100.0 * slots_code / max(slots_tot, 1), slots_str))
    P("  vtables yielding >=1 qualified-name token : %d / %d = %.1f%%"
      % (anytok, tot, 100.0 * anytok / max(tot, 1)))
    P("  top-1 token == the true class name        : %d / %d = %.1f%%"
      % (hit1, tot, 100.0 * hit1 / max(tot, 1)))
    P("  true class name in top-3 tokens           : %d / %d = %.1f%%"
      % (hit3, tot, 100.0 * hit3 / max(tot, 1)))
    P("  true class name ANYWHERE in the token set  : %d / %d = %.1f%%"
      % (anywhere, tot, 100.0 * anywhere / max(tot, 1)))
    P("  top-1 token shares a stem with the class  : %d / %d = %.1f%%"
      % (fam, tot, 100.0 * fam / max(tot, 1)))
    P("  (a vtable is dominated by INHERITED slots, so the token that wins is")
    P("   usually a BASE class -- which is why this is a weak identifier on its own")
    P("   but a good sanity check once the boilerplate route has proposed a name.)")


def cmd_reflect(ix, pe, idx, args):
    """Technique (b): can UE reflection data identify a vtable? Measure, don't assume."""
    P = print
    cl = ix["classes"]
    sup = load_super()
    P("TECHNIQUE (b): cross-reference against UE reflection data")
    P("")
    # b1 -- name dictionary agreement
    names = {k[1:] for k in cl}
    inter = names & set(sup)
    P("  b1. name agreement: %d class names recovered from the binary; schema.txt has"
      % len(names))
    P("      %d UStructs; %d of our names appear there (%.1f%%)."
      % (len(sup), len(inter), 100.0 * len(inter) / max(len(names), 1)))
    P("      -> the two sources were produced by completely different means")
    P("         (UHT reflection dump vs. this static walk), so this is a real control.")
    missing = sorted(names - set(sup))[:6]
    P("      names we recovered that schema.txt lacks (%d): %s ..."
      % (len(names - set(sup)), missing))
    # b2 -- does reflected member count predict vtable length?
    props = {}
    try:
        with open(SCHEMA, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"^  ([A-Za-z0-9_]+) : .*?\((\d+) props\)", line)
                if m:
                    props[m.group(1)] = int(m.group(2))
    except OSError:
        props = {}
    pairs = [(props[k[1:]], vt_len(ix, v["vtable"]))
             for k, v in cl.items() if v["vtable"] and k[1:] in props]
    pairs = [(a, b) for a, b in pairs if b]
    if pairs:
        n = len(pairs)
        mx = sum(a for a, _b in pairs) / n
        my = sum(b for _a, b in pairs) / n
        sxy = sum((a - mx) * (b - my) for a, b in pairs)
        sxx = sum((a - mx) ** 2 for a, _b in pairs)
        syy = sum((b - my) ** 2 for _a, b in pairs)
        r = sxy / ((sxx * syy) ** 0.5) if sxx and syy else 0.0
        P("")
        P("  b2. reflected PROPERTY count vs vtable slot count, %d classes: r = %+.3f"
          % (n, r))
        P("      -> near zero. UPROPERTYs are offsets in a UClass property list; they")
        P("         are not virtuals and never appear in a vtable.")
    # b3 -- the proposal in the brief: match vtable size against native function count
    bt = os.path.join(r"G:\git\Supervive Revival Project\tools\asdump\out", "binds_types.csv")
    if os.path.exists(bt):
        meth = {}
        with open(bt, encoding="utf-8", errors="replace") as f:
            hdr = f.readline().rstrip("\n").split(",")
            ti, mi = hdr.index("type_name"), hdr.index("num_methods")
            for line in f:
                p = line.rstrip("\n").split(",")
                if len(p) > max(ti, mi) and p[mi].isdigit():
                    meth[p[ti]] = int(p[mi])
        pairs = [(meth[k], vt_len(ix, v["vtable"]))
                 for k, v in cl.items() if v["vtable"] and k in meth]
        pairs = [(a, b) for a, b in pairs if b]
        if pairs:
            n = len(pairs)
            mx = sum(a for a, _b in pairs) / n
            my = sum(b for _a, b in pairs) / n
            sxy = sum((a - mx) * (b - my) for a, b in pairs)
            sxx = sum((a - mx) ** 2 for a, _b in pairs)
            syy = sum((b - my) ** 2 for _a, b in pairs)
            r = sxy / ((sxx * syy) ** 0.5) if sxx and syy else 0.0
            P("")
            P("  b3. AS-exposed METHOD count (tools/asdump/out/binds_types.csv) vs vtable")
            P("      slot count, %d classes both sources know: r = %+.3f" % (n, r))
            P("      -> also near zero, and structurally it must be: a UFUNCTION is")
            P("         registered as a static `exec` thunk in the UClass function map.")
            P("         It is NOT a C++ virtual and occupies no vtable slot.  Matching")
            P("         'vtable method count/order' against a UClass function list")
            P("         therefore CANNOT work -- the two lists describe different things.")
    P("")
    P("  VERDICT on (b): reflection data is an excellent NAME DICTIONARY and an")
    P("  excellent INHERITANCE oracle (it is what validates the vtable map, see")
    P("  GT-4), but it cannot identify a vtable by shape.")


def cmd_diff(ix, pe, idx, args):
    """Show only the slots where a class differs from its base -- its OVERRIDES and
    its NEW virtuals.  A 347-slot dump is unreadable; a 30-slot diff is the class."""
    d, ib = pe.d, pe.imagebase
    cl = ix["classes"]
    c = cl.get(args.name)
    if not c or not c["vtable"]:
        print("no vtable for %r" % args.name)
        return
    base = args.base
    if not base:
        sup = load_super().get(args.name[1:])
        base = next((k for k in cl if k[1:] == sup and cl[k]["vtable"]), None) if sup else None
    if not base:
        print("no resolved base for %s -- pass --base <ClassName>" % args.name)
        return
    a, b = c["vtable"], cl[base]["vtable"]
    la, lb = vt_len(ix, a), vt_len(ix, b)
    print("%s 0x%08X (%d slots)   vs base %s 0x%08X (%d slots)"
          % (args.name, a, la, base, b, lb))
    if a == b:
        print("  IDENTICAL vtable -- %s adds no virtual of its own (MSVC folded them)."
              % args.name)
        return
    nov = nnew = 0
    for i in range(la):
        va = struct.unpack_from("<Q", d, a + i * 8)[0] - ib
        vb = struct.unpack_from("<Q", d, b + i * 8)[0] - ib if i < lb else None
        if vb is not None and va == vb:
            continue
        kind = "NEW " if vb is None else "OVR "
        nov += vb is not None
        nnew += vb is None
        e, strs = slot_label(idx, d, va)
        s = ("   " + " | ".join(repr(x[:52]) for x in strs[:2])) if strs else ""
        print("  [%3d] %s 0x%07X%s%s" % (i, kind, va,
                                         "" if d[va] else " [page not decrypted]", s))
    print("  %d overrides, %d new virtuals" % (nov, nnew))


def cmd_slotof(ix, pe, idx, args):
    """Reverse lookup: which NAMED class vtables contain this code address, at what slot?

    This is the payoff for shim work.  The project records ~617 bare function RVAs;
    any of them that is a virtual can instead be called as `vtable[N]` off a live
    object, which is what every existing shim already does by hand for
    LokiAssetManager slot 94.
    """
    d, ib = pe.d, pe.imagebase
    want = args.rva
    named = {}
    for k, v in ix["classes"].items():
        if v["vtable"]:
            named.setdefault(v["vtable"], []).append(k)
    hits = []
    for a, l, _h in ix["vts"]:
        if l < 2:
            continue
        for i in range(l):
            if struct.unpack_from("<Q", d, a + i * 8)[0] - ib == want:
                hits.append((a, i, named.get(a)))
    if not hits:
        e, _f, ti, _end = idx.func_of(want)
        print("0x%07X appears in NO vtable." % want)
        print("  -> it is a non-virtual function (static, free, or a direct-call-only")
        print("     member). strxref says: entry 0x%s tier %s"
              % (("%07X" % e) if e else "?", ti))
        return
    innamed = [h for h in hits if h[2]]
    print("0x%07X appears in %d vtable(s), %d of them named:" % (want, len(hits), len(innamed)))
    for a, i, own in (innamed or hits)[:args.n]:
        print("  slot %-4d of 0x%08X  %s" % (i, a, ", ".join(own) if own else "<unnamed>"))
    if innamed and len(hits) > len(innamed):
        print("  (+%d unnamed vtables also contain it -- inherited by classes whose")
        print("   ctor page this dump has not decrypted)" % (len(hits) - len(innamed)))


def cmd_classes(ix, pe, idx, args):
    cl = ix["classes"]
    pat = args.pattern
    rows = []
    for k, v in sorted(cl.items()):
        if pat and pat.lower() not in k.lower():
            continue
        rows.append((k, v))
    print("%d class(es)%s" % (len(rows), (" matching %r" % pat) if pat else ""))
    for k, v in rows[:args.n]:
        print("  %-46s vtable %-12s slots %-5s %-5s %s"
              % (k, ("0x%08X" % v["vtable"]) if v["vtable"] else "-",
                 vt_len(ix, v["vtable"]) if v["vtable"] else "-", v["conf"],
                 v["modules"][0] if v["modules"] else ""))


def cmd_name(ix, pe, idx, args):
    cl = ix["classes"]
    v = cl.get(args.name)
    if v is None:
        cands = [k for k in cl if args.name.lower() in k.lower()]
        print("no class named %r. did you mean: %s" % (args.name, cands[:12]))
        return
    print("class   %s   module %s" % (args.name, ", ".join(v["modules"])))
    print("gpsc    0x%07X  (UFoo::GetPrivateStaticClass)" % v["gpsc"])
    print("ctor    0x%07X  (InternalConstructor<UFoo>)" % v["ic"])
    if v["subobjects"]:
        print("subobject vtables installed by the same ctor (inline members / MI):")
        for vt, disp in v["subobjects"]:
            print("        0x%08X at this+0x%X" % (vt, disp))
    if not v["vtable"]:
        print("primary vtable NOT resolved (conf=%s)" % v["conf"])
        return
    print("")
    dump_vtable(ix, pe, idx, v["vtable"], args.slots, args.strings)


def cmd_at(ix, pe, idx, args):
    dump_vtable(ix, pe, idx, args.rva, args.slots, args.strings)


def cmd_who(ix, pe, idx, args):
    rva = args.rva
    exact = [k for k, v in ix["classes"].items() if v["vtable"] == rva]
    if exact:
        print("0x%08X is the primary vtable of %s" % (rva, ", ".join(exact)))
        return
    sec = [(k, disp) for k, v in ix["classes"].items() for vt, disp in v["subobjects"] if vt == rva]
    if sec:
        print("0x%08X is a SECONDARY (interface) vtable of %s"
              % (rva, ", ".join("%s@+0x%X" % (k, dsp) for k, dsp in sec)))
        return
    # containing piece
    for a, l, h in ix["vts"]:
        if a <= rva < a + l * 8:
            own = [k for k, v in ix["classes"].items() if v["vtable"] == a]
            print("0x%08X is slot %d of the vtable candidate at 0x%08X (len %d, owner %s)"
                  % (rva, (rva - a) // 8, a, l, own or "<unnamed>"))
            return
    print("0x%08X is not inside any text-pointer run in .rdata" % rva)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("scan"); p.add_argument("--dump", default=strxref.DEFAULT_DUMP)
    sub.add_parser("stats")
    sub.add_parser("verify")
    p = sub.add_parser("classes"); p.add_argument("pattern", nargs="?")
    p.add_argument("-n", type=int, default=60)
    p = sub.add_parser("name"); p.add_argument("name")
    p.add_argument("--slots", type=int); p.add_argument("--strings", action="store_true")
    p = sub.add_parser("at"); p.add_argument("rva", type=lambda s: int(s, 0))
    p.add_argument("--slots", type=int); p.add_argument("--strings", action="store_true")
    p = sub.add_parser("who"); p.add_argument("rva", type=lambda s: int(s, 0))
    p = sub.add_parser("strings", help="class-name tokens harvested from a vtable's methods")
    p.add_argument("target", type=lambda s: int(s, 0) if s.startswith("0x") else s)
    p.add_argument("--slots", type=int); p.add_argument("-n", type=int, default=15)
    p.add_argument("--span", choices=("head", "tail", "all"), default="all")
    p = sub.add_parser("bench", help="score strings-only naming against the boilerplate map")
    p.add_argument("-n", type=int, default=400, help="sample size (0 = all)")
    p.add_argument("--slots", type=int, default=40)
    p.add_argument("--span", choices=("head", "tail", "all"), default="tail")
    sub.add_parser("reflect", help="score UE-reflection cross-reference")
    p = sub.add_parser("diff", help="a class's OVERRIDES + NEW virtuals vs its base")
    p.add_argument("name"); p.add_argument("--base")
    p = sub.add_parser("slotof", help="which class vtables contain this code RVA, at what slot")
    p.add_argument("rva", type=lambda s: int(s, 0)); p.add_argument("-n", type=int, default=12)
    args = ap.parse_args(argv)

    if args.cmd == "scan":
        ix, pe, idx = build(args.dump)
        print("")
        return 1 if verify(ix, pe, idx) else 0
    if not args.cmd:
        ap.print_help()
        return 0
    ix, pe, idx = load()
    if args.cmd == "stats":
        cmd_stats(ix, pe, idx, args)
    elif args.cmd == "verify":
        return 1 if verify(ix, pe, idx) else 0
    elif args.cmd == "classes":
        cmd_classes(ix, pe, idx, args)
    elif args.cmd == "name":
        cmd_name(ix, pe, idx, args)
    elif args.cmd == "at":
        cmd_at(ix, pe, idx, args)
    elif args.cmd == "who":
        cmd_who(ix, pe, idx, args)
    elif args.cmd == "strings":
        cmd_strings(ix, pe, idx, args)
    elif args.cmd == "bench":
        cmd_bench(ix, pe, idx, args)
    elif args.cmd == "reflect":
        cmd_reflect(ix, pe, idx, args)
    elif args.cmd == "slotof":
        cmd_slotof(ix, pe, idx, args)
    elif args.cmd == "diff":
        cmd_diff(ix, pe, idx, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
