#!/usr/bin/env python
"""
lane2_cheatsig.py -- OFFLINE full-signature recovery + body grading for the
Loki cheat classes (FK-13 lane 2, S114).

WHAT IT ADDS OVER PRIOR ART
---------------------------
1. `cheat_impl_census.py` built its .text union from 10 dumps and did NOT include
   `dumps/tutorial-hero` (which did not exist yet).  That dump is the only IN-WORLD
   state we have and it decrypts pages the menu-state dumps never touch.  This tool
   unions ALL 11 and uses tutorial-hero (.rdata/.data 100%) as the base image, so
   every .rdata/.data read is coverage-clean by construction.
2. `uht_funcflags.py` recovered EFunctionFlags but never decoded the parameter
   list.  This decodes UHT's FPropertyParamsBase array -> a real C++ signature,
   with property flags (Parm / OutParm / ReturnParm / ConstParm / ReferenceParm)
   and resolved Class/Struct/Enum type names.
3. Name->exec-thunk comes from the FNameNativePtrPair registration array
   (`StaticRegisterNatives<Class>`), which is ICF-fold-safe: two functions folded
   onto one thunk both appear, whereas an RVA-keyed index silently loses one.

Every negative carries a coverage verdict.  A thunk or impl whose 4 KiB page is
all-zero is COVERAGE_BLOCKED ("never executed by any dumped process"), which is
NOT the same as "stub".

Usage:  python lane2_cheatsig.py [--class ALokiPlayerCheats] [--all] [--csv out.csv]
"""
import os, re, sys, csv, struct, bisect, argparse
from array import array

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
except ImportError:
    sys.exit("need capstone: pip install capstone")

ROOT = r"G:\git\Supervive Revival Project"
BASE_DUMP = os.path.join(ROOT, "dumps", "tutorial-hero", "SUPERVIVE-Win64-Shipping.dump.exe")
ALL_DUMPS = [os.path.join(ROOT, "dumps", d, "SUPERVIVE-Win64-Shipping.dump.exe")
             for d in ("menu", "store", "roster", "missions", "loadout",
                       "accountpass", "vmbuild", "toggles", "rcb", "tutorial-hero")] + \
            [os.path.join(ROOT, "dumps", "merged2.dump.exe")]
PDATA = os.path.join(ROOT, "tools", "strxref", "index", "pdata_union.csv")
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
UNION_CACHE = os.path.join(os.environ.get("TEMP", "."), "supervive_union_text_11.bin")

IMAGE_BASE = 0x7FF6505C0000          # tutorial-hero
TEXT_RVA, TEXT_SZ = 0x1000, 0x7649000
TEXT_END = TEXT_RVA + TEXT_SZ
PAGE = 0x1000

PROCESS_INTERNAL = 0x13454A0
# FFrame parameter-step / teardown helpers: landing on one of these means the
# thunk's real dispatch was not resolved here (usually an indirect call).
FRAME_HELPERS = {0x1345FB0, 0x1345FE0, 0x133F840, 0x133EEA0, 0x133EBE0,
                 0x12F3FC0, 0x13759A0, 0xFF9310, 0x133EB30, 0x135F5E0}
FOLDS = {
    0x0F7EC20: ("ret 0",              "RET_STUB",   "empty body"),
    0x0F7EB60: ("xor al,al; ret",     "FALSE_STUB", "always false"),
    0x0F7EB50: ("xor eax,eax; ret",   "ZERO_STUB",  "0 / nullptr"),
    0x0B9E1F0: ("mov al,1; ret",      "TRUE_STUB",  "always true"),
    0x05254180:("ret",                "RET_STUB",   "empty body (0x5254180)"),
}

# ------------------------------------------------------------------ image ---
_D = None
_UNION_STATS = {}


def img():
    global _D
    if _D is not None:
        return _D
    with open(BASE_DUMP, "rb") as f:
        b = bytearray(f.read())
    if os.path.exists(UNION_CACHE) and os.path.getsize(UNION_CACHE) == TEXT_SZ:
        with open(UNION_CACHE, "rb") as f:
            b[TEXT_RVA:TEXT_END] = f.read()
        _UNION_STATS["cached"] = True
    else:
        conf = 0
        for p in ALL_DUMPS:
            if not os.path.exists(p) or os.path.abspath(p) == os.path.abspath(BASE_DUMP):
                continue
            with open(p, "rb") as f:
                d = f.read()
            for r in range(TEXT_RVA, TEXT_END, PAGE):
                pg = d[r:r + PAGE]
                if not pg.strip(b"\0"):
                    continue
                cur = bytes(b[r:r + PAGE])
                if not cur.strip(b"\0"):
                    b[r:r + PAGE] = pg
                elif cur != pg:
                    conf += 1
        _UNION_STATS["conflicts"] = conf
        with open(UNION_CACHE, "wb") as f:
            f.write(bytes(b[TEXT_RVA:TEXT_END]))
    _UNION_STATS["pages"] = sum(1 for r in range(TEXT_RVA, TEXT_END, PAGE)
                                if bytes(b[r:r + PAGE]).strip(b"\0"))
    _UNION_STATS["total"] = TEXT_SZ // PAGE
    _D = bytes(b)
    return _D


def decrypted(rva):
    p = rva & ~(PAGE - 1)
    return img()[p:p + PAGE].strip(b"\0") != b""


def range_ok(lo, hi):
    d = img()
    for p in range(lo & ~(PAGE - 1), hi, PAGE):
        if not d[p:p + PAGE].strip(b"\0"):
            return False
    return True


def rva_of(va):
    r = va - IMAGE_BASE
    return r if 0 <= r < 0xA9E1000 else None


def cstr(rva, cap=256):
    if rva is None:
        return None
    d = img()
    e = d.find(b"\0", rva, rva + cap)
    if e <= rva:
        return None
    s = d[rva:e]
    if any(c < 0x20 or c > 0x7e for c in s):
        return None
    return s.decode("ascii")


def wstr(rva, cap=200):
    if rva is None:
        return None
    d = img()
    out = []
    while len(out) < cap:
        c = struct.unpack_from("<H", d, rva)[0]
        if c == 0:
            break
        if c < 0x20 or c > 0x7e:
            return None
        out.append(chr(c))
        rva += 2
    return "".join(out) or None


def q(rva):
    return struct.unpack_from("<Q", img(), rva)[0]


# ------------------------------------------------------------------ pdata ---
_PD = None


def pdata():
    global _PD
    if _PD is None:
        beg, end = array("l"), array("l")
        with open(PDATA) as f:
            next(f)
            for line in f:
                a, b = line.split(",", 2)[:2]
                beg.append(int(a, 16)); end.append(int(b, 16))
        _PD = (beg, end)
    return _PD


def func_bounds(rva):
    beg, end = pdata()
    i = bisect.bisect_right(beg, rva) - 1
    if i < 0 or rva >= end[i]:
        return None, None
    lo = i
    while lo > 0 and beg[lo] == end[lo - 1] and beg[lo] % 16:
        lo -= 1
    hi = i
    while hi + 1 < len(beg) and beg[hi + 1] == end[hi] and beg[hi + 1] % 16:
        hi += 1
    return beg[lo], end[hi]


# ------------------------------------------- UHT class-registration name map -
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SECT = {}


def load_sections():
    d = img()
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    nsec = struct.unpack_from("<H", d, pe + 6)[0]
    optsz = struct.unpack_from("<H", d, pe + 20)[0]
    sh = pe + 24 + optsz
    for i in range(nsec):
        o = sh + i * 40
        nm = d[o:o + 8].rstrip(b"\0").decode("latin1")
        SECT[nm] = (struct.unpack_from("<I", d, o + 12)[0],
                    struct.unpack_from("<I", d, o + 8)[0])


_OWNER = None


def owner_map():
    """Z_Construct_UClass VA -> wide class name, from FClassRegisterCompiledInInfo."""
    global _OWNER
    if _OWNER is not None:
        return _OWNER
    lo, hi = IMAGE_BASE + TEXT_RVA, IMAGE_BASE + TEXT_END
    m = {}
    for s in (".data", ".rdata"):
        va, vs = SECT[s]
        d = img()
        for off in range(va, va + vs - 0x20, 8):
            f0 = struct.unpack_from("<Q", d, off)[0]
            if not (lo <= f0 < hi):
                continue
            f1 = struct.unpack_from("<Q", d, off + 8)[0]
            if not (lo <= f1 < hi):
                continue
            nm = wstr(rva_of(struct.unpack_from("<Q", d, off + 0x10)[0]), 120)
            if nm and NAME_RE.match(nm) and f0 not in m:
                m[f0] = nm
    _OWNER = m
    return m


_STRUCTMAP = None


def struct_map():
    """Z_Construct_UScriptStruct/UEnum VA -> name, via FStructRegisterCompiledInInfo
    / FEnumRegisterCompiledInInfo ({OuterRegister, ... , const TCHAR* Name, ...})."""
    global _STRUCTMAP
    if _STRUCTMAP is not None:
        return _STRUCTMAP
    lo, hi = IMAGE_BASE + TEXT_RVA, IMAGE_BASE + TEXT_END
    m = {}
    d = img()
    for s in (".data", ".rdata"):
        va, vs = SECT[s]
        for off in range(va, va + vs - 0x28, 8):
            f0 = struct.unpack_from("<Q", d, off)[0]
            if not (lo <= f0 < hi):
                continue
            # try wide name at +0x08 / +0x10 / +0x18
            for delta in (0x08, 0x10, 0x18):
                nm = wstr(rva_of(struct.unpack_from("<Q", d, off + delta)[0]), 120)
                if nm and NAME_RE.match(nm) and len(nm) > 2:
                    m.setdefault(f0, nm)
                    break
    _STRUCTMAP = m
    return m


def typename(va):
    if not va:
        return "?"
    n = owner_map().get(va)
    if n:
        return n
    n = struct_map().get(va)
    if n:
        return n
    return "fn@%#x" % (va - IMAGE_BASE)


# --------------------------------------------------- FPropertyParams decode --
GEN = {0x00: "byte", 0x01: "int8", 0x02: "int16", 0x03: "int32", 0x04: "int64",
       0x05: "uint16", 0x06: "uint32", 0x07: "uint64", 0x0A: "float", 0x0B: "double",
       0x0C: "bool", 0x0D: "TSoftClassPtr", 0x0E: "TWeakObjectPtr", 0x0F: "TLazyObjectPtr",
       0x10: "TSoftObjectPtr", 0x11: "TSubclassOf", 0x12: "obj", 0x13: "TScriptInterface",
       0x14: "FName", 0x15: "FString", 0x16: "TArray", 0x17: "TMap", 0x18: "TSet",
       0x19: "struct", 0x1A: "delegate", 0x1B: "mcdelegate", 0x1C: "sparsedelegate",
       0x1D: "FText", 0x1E: "enum", 0x1F: "TFieldPath", 0x20: "double/LWC",
       0x21: "TOptional", 0x22: "VValue"}
# EPropertyFlags bits we care about
CPF_Parm          = 0x0000000000000080
CPF_OutParm       = 0x0000000000000100
CPF_ReturnParm    = 0x0000000000000400
CPF_ConstParm     = 0x0000000000000002
CPF_ReferenceParm = 0x0000000004000000

# which gen-types carry a trailing type-resolver pointer at +0x38
HAS_TYPEPTR = {0x00, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x19, 0x1A, 0x1B,
               0x1C, 0x1E, 0x1F}


def decode_prop(rva):
    d = img()
    name = cstr(rva_of(q(rva)))
    pflags = struct.unpack_from("<Q", d, rva + 0x10)[0]
    gen = d[rva + 0x18]
    ty = gen & 0x3F
    arraydim = struct.unpack_from("<H", d, rva + 0x30)[0]
    tname = None
    if ty in HAS_TYPEPTR:
        tp = struct.unpack_from("<Q", d, rva + 0x38)[0]
        if IMAGE_BASE + TEXT_RVA <= tp < IMAGE_BASE + TEXT_END:
            tname = typename(tp)
    return dict(name=name, pflags=pflags, gen=gen, ty=ty, tname=tname,
                arraydim=arraydim, rva=rva)


def render_type(p, inner=None):
    ty, tn = p["ty"], p["tname"]
    base = GEN.get(ty, "gen%#x" % ty)
    if ty == 0x12:
        base = ("%s*" % tn) if tn else "UObject*"
    elif ty in (0x11, 0x0D):
        base = "%s<%s>" % (GEN[ty], tn or "UObject")
    elif ty in (0x0E, 0x0F, 0x10, 0x13, 0x1F):
        base = "%s<%s>" % (GEN[ty], tn or "?")
    elif ty == 0x19:
        base = "F%s" % (tn or "?")
    elif ty == 0x1E:
        base = tn or "enum"
    elif ty == 0x00 and tn:
        base = tn
    elif ty in (0x1A, 0x1B, 0x1C):
        base = "%s<%s>" % (GEN[ty], tn or "?")
    elif ty in (0x16, 0x18):
        base = "%s<%s>" % (GEN[ty], inner or "?")
    elif ty == 0x17:
        base = "TMap<%s>" % (inner or "?,?")
    if p["arraydim"] > 1:
        base += "[%d]" % p["arraydim"]
    return base


def decode_signature(params_rva):
    """params_rva -> (sig_string, nprops, structsize)."""
    d = img()
    pa = rva_of(q(params_rva + 0x28))
    n = struct.unpack_from("<H", d, params_rva + 0x30)[0]
    ssz = struct.unpack_from("<H", d, params_rva + 0x32)[0]
    if not n:
        return "()  ->  void", 0, ssz
    if pa is None:
        return "<PropertyArray unreadable>", n, ssz
    props = []
    for i in range(n):
        pv = struct.unpack_from("<Q", d, pa + 8 * i)[0]
        pr = rva_of(pv)
        if pr is None:
            props.append(None); continue
        props.append(decode_prop(pr))
    # container inners: UHT emits <name>_Inner / _Key / _Value entries with the
    # SAME NameUTF8 as the container, immediately BEFORE the container entry.
    out, ret, pending = [], None, []
    for p in props:
        if p is None:
            out.append(("?", "?")); continue
        if not (p["pflags"] & CPF_Parm):
            # inner of a container that follows
            pending.append(p)
            continue
        inner = None
        if p["ty"] in (0x16, 0x18, 0x17) and pending:
            inner = ",".join(render_type(x) for x in pending)
        pending = []
        t = render_type(p, inner)
        mods = []
        if p["pflags"] & CPF_ConstParm:
            mods.append("const")
        if p["pflags"] & CPF_OutParm and not (p["pflags"] & CPF_ReturnParm):
            mods.append("out")
        if p["pflags"] & CPF_ReferenceParm:
            mods.append("&")
        entry = ("%s %s" % (" ".join(mods), t)).strip(), p["name"]
        if p["pflags"] & CPF_ReturnParm:
            ret = t
        else:
            out.append(entry)
    args = ", ".join("%s %s" % (t, nm) for t, nm in out)
    return "(%s)  ->  %s" % (args, ret or "void"), n, ssz


# ------------------------------------------ FNameNativePtrPair registration --
def nativefn_table():
    """MEASURED THIS SESSION (S114 lane 2).  `.data 0x99da7e0..0x9cd2be8` holds
    9,771 records at a 0x48 stride.  Each record's static (relocated) fields are:

        +0x20  const char*      NameUTF8          (ASCII, e.g. "CheatAutoStrafe")
        +0x28  FNativeFuncPtr   execThunk         (.text, the UHT `execFoo`)
        +0x30  <member fn>      &Class::Foo       (.text: the DIRECT body address for
                                                   a non-virtual fn, or a 6-byte vcall
                                                   thunk `mov rax,[rcx]; jmp [rax+SLOT]`
                                                   for a virtual one)
        +0x38, +0x40  0
      (+0x00/+0x08/+0x18 are runtime-written heap fields -- they differ per process,
       while every .text/.rdata field above is byte-identical across all 11 dumps
       after rebasing, i.e. the table is static image data.)

    Detection signature used here is the static part only: {name*, .text, .text, 0, 0}.

    CONTROLS (measured):
      * 92.0% (80/87) of vcall-thunk PMFs dispatch through the SAME vtable slot the
        exec thunk uses -> the +0x30 field really is `&Class::Foo`.
      * 54.0% (601/1112) of direct PMFs are a rel32 target inside their own exec
        thunk; the residual is dominated by MSVC inlining the body INTO the thunk
        (e.g. Vector_Down) and by thunk bounds that merge adjacent pdata fragments.
      * Cross-check vs docs/fk6-cheat-impl-census.csv: every disagreement is a row
        FK-6 itself resolved "VIRTUAL <class> vtable[+N]", i.e. FK-6 walked one hop
        further; the table's value is the vcall thunk for that same slot.

    Returns {name: [(thunkRVA, pmfRVA), ...]} plus the ICF multiplicity of each pmf.
    """
    d = img()
    B = IMAGE_BASE
    TLO, THI = B + TEXT_RVA, B + TEXT_END
    out = {}
    from collections import Counter, defaultdict
    out = defaultdict(list)
    mult = Counter()
    for s in (".data", ".rdata"):
        va, vs = SECT[s]
        for off in range(va, va + vs - 0x28, 8):
            n = struct.unpack_from("<Q", d, off)[0]
            if not (B <= n < B + 0xA9E1000):
                continue
            t = struct.unpack_from("<Q", d, off + 8)[0]
            if not (TLO <= t < THI):
                continue
            i = struct.unpack_from("<Q", d, off + 16)[0]
            if not (TLO <= i < THI):
                continue
            # Stride corroboration instead of "trailing qwords are zero".
            # CONTROL THAT CAUGHT THE BUG: requiring zeros at +0x18/+0x20 silently
            # dropped ALokiPlayerController::{IsAdmin, ServerRequestAdmin,
            # GetPlayerCheats, WarnRequiresAdmin, ServerTriggerControllerCheatCommand,
            # AuthCheatChangeCharacter, RequestAdmin} -- 7 names known to exist from
            # the UHT table -- because their +0x18 holds a live heap value.
            ok = False
            for delta in (-0x48, 0x48):
                o2 = off + delta
                if not (va <= o2 < va + vs - 0x18):
                    continue
                n2 = struct.unpack_from("<Q", d, o2)[0]
                t2 = struct.unpack_from("<Q", d, o2 + 8)[0]
                i2 = struct.unpack_from("<Q", d, o2 + 16)[0]
                if B <= n2 < B + 0xA9E1000 and TLO <= t2 < THI and TLO <= i2 < THI:
                    ok = True
                    break
            if not ok:
                continue
            nm = cstr(n - B, 128)
            if not nm or not NAME_RE.match(nm):
                continue
            out[nm].append((t - B, i - B, off))
            mult[i - B] += 1
    return out, mult


def vcall_slot(rva):
    """If rva is `mov rax,[rcx]; jmp qword [rax+disp32]`, return disp32, else None."""
    if not decrypted(rva):
        return None
    b = img()[rva:rva + 11]
    if b[:3] == b"\x48\x8b\x01" and b[3:5] == b"\xff\xa0":
        return struct.unpack_from("<I", b, 5)[0]
    return None


def native_regs(min_run=3):
    """Scan .rdata/.data for runs of FNameNativePtrPair {const char* NameUTF8;
    FNativeFuncPtr Pointer;} -- i.e. the StaticRegisterNatives<Class> tables.
    Step is 8, not 16: a 16-byte record can start at either 8-byte phase.
    Returns list of runs; each run is [(name, thunk_rva), ...]."""
    d = img()
    lo, hi = IMAGE_BASE + TEXT_RVA, IMAGE_BASE + TEXT_END
    runs = []
    for s in (".rdata", ".data"):
        va, vs = SECT[s]
        end = va + vs - 16
        n = (end - va) // 8
        # pass 1: cheap classification of every 8-byte slot
        kind = bytearray(n + 2)      # 1 = name ptr, 2 = code ptr
        for i in range(n):
            off = va + i * 8
            v = struct.unpack_from("<Q", d, off)[0]
            if lo <= v < hi:
                kind[i] = 2
            elif v:
                r = v - IMAGE_BASE
                if 0 <= r < 0xA9E1000:
                    kind[i] = 1     # candidate; string validated lazily
        i = 0
        while i < n - 1:
            if kind[i] == 1 and kind[i + 1] == 2:
                cur, j = [], i
                while j < n - 1 and kind[j] == 1 and kind[j + 1] == 2:
                    nm = cstr(struct.unpack_from("<Q", d, va + j * 8)[0] - IMAGE_BASE, 128)
                    if not nm or not NAME_RE.match(nm):
                        break
                    fp = struct.unpack_from("<Q", d, va + (j + 1) * 8)[0]
                    cur.append((nm, fp - IMAGE_BASE))
                    j += 2
                if len(cur) >= min_run:
                    runs.append(cur)
                i = max(j, i + 1)
            else:
                i += 1
    return runs


# -------------------------------------------------------------- thunk walk --
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True


def grade_body(rva):
    """Return (verdict, detail, size)."""
    if rva in FOLDS:
        txt, verdict, meaning = FOLDS[rva]
        return verdict, "%s -- %s" % (txt, meaning), 3
    if not decrypted(rva):
        return "COVERAGE_BLOCKED", "impl page %#x all-zero in all 11 dumps" % (rva & ~0xFFF), 0
    b, e = func_bounds(rva)
    d = img()
    raw = d[rva:rva + 16]
    # canonical folded shapes, wherever they live
    if raw[:3] == b"\xc2\x00\x00":
        return "RET_STUB", "c2 00 00 (ret 0)", 3
    if raw[:1] == b"\xc3":
        return "RET_STUB", "c3 (ret)", 1
    if raw[:3] == b"\x32\xc0\xc3":
        return "FALSE_STUB", "32 c0 c3 (xor al,al; ret)", 3
    if raw[:3] == b"\x33\xc0\xc3":
        return "ZERO_STUB", "33 c0 c3 (xor eax,eax; ret)", 3
    if raw[:3] == b"\xb0\x01\xc3":
        return "TRUE_STUB", "b0 01 c3 (mov al,1; ret)", 3
    if b is not None:
        lim, bound = e, "pdata"
        if not range_ok(rva, min(lim, rva + 0x1000)):
            return "COVERAGE_BLOCKED", "body [%#x,%#x) runs into an undecrypted page" % (rva, lim), 0
        ins = list(md.disasm(d[rva:lim], rva))
    else:
        # No unwind record: sweep to the first `ret` that no earlier forward branch
        # jumps past.  NEVER report a fixed 0x400 window as a size -- that was how
        # FK-6-era sweeps turned 13-byte folded helpers into "259 ins, 1024 B".
        bound = "sweep-to-ret (NO .pdata entry)"
        if not range_ok(rva, rva + 0x40):
            return "COVERAGE_BLOCKED", "body page undecrypted", 0
        ins, maxt = [], rva
        for i in md.disasm(d[rva:rva + 0x400], rva):
            ins.append(i)
            if i.mnemonic.startswith("j") and i.op_str.startswith("0x"):
                maxt = max(maxt, int(i.op_str, 16))
            if i.mnemonic.startswith("ret") and i.address >= maxt:
                break
        lim = (ins[-1].address + ins[-1].size) if ins else rva
    ncall = sum(1 for i in ins if i.mnemonic == "call")
    size = lim - rva
    first = "; ".join("%s %s" % (i.mnemonic, i.op_str) for i in ins[:4])
    if size <= 24 and ncall == 0:
        return "TRIVIAL", "%d ins, %d B, %s :: %s" % (len(ins), size, bound, first), size
    return "REAL", "%d ins, %d calls, %d B, %s" % (len(ins), ncall, size, bound), size


def walk_thunk(thunk):
    """Find the thunk's final dispatch target. Returns (impl_rva, how)."""
    d = img()
    if thunk == PROCESS_INTERNAL:
        return thunk, "thunk IS ProcessInternal (script/BP-implemented)"
    if not decrypted(thunk):
        return None, "THUNK page %#x all-zero in all 11 dumps" % (thunk & ~0xFFF)
    b, e = func_bounds(thunk)
    lim = e if b is not None else thunk + 0x300
    if not range_ok(thunk, min(lim, thunk + 0x1000)):
        return None, "THUNK body [%#x,%#x) runs into an undecrypted page" % (thunk, lim)
    ins = list(md.disasm(d[thunk:lim], thunk))
    if not ins:
        return None, "no decodable instructions"
    # last call/jmp with an immediate target that is NOT a frame helper
    cands = []
    for i in ins:
        if i.mnemonic in ("call", "jmp") and i.op_str.startswith("0x"):
            t = int(i.op_str, 16)
            cands.append((i.address, i.mnemonic, t))
    real = [c for c in cands if c[2] not in FRAME_HELPERS]
    if not real:
        if cands:
            return cands[-1][2], "ONLY frame helpers (%d) -- unresolved" % len(cands)
        # indirect dispatch?
        ind = [i for i in ins if i.mnemonic in ("call", "jmp") and not i.op_str.startswith("0x")]
        if ind:
            return None, "indirect dispatch only: %s %s" % (ind[-1].mnemonic, ind[-1].op_str)
        return None, "no dispatch found in %d ins" % len(ins)
    a, mn, t = real[-1]
    return t, "%s rel32 @%#x (skipped %d frame-helper calls)" % (mn, a, len(cands) - len(real))


# ------------------------------------------------------------------- main ---
def load_funcflags():
    p = os.path.join(ROOT, "tools", "re", "out", "uht_funcflags_tuthero.csv")
    return list(csv.DictReader(open(p)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--klass", action="append", default=None)
    ap.add_argument("--csv")
    ap.add_argument("--execonly", action="store_true")
    ap.add_argument("--regruns", action="store_true")
    a = ap.parse_args()
    classes = a.klass or ["ALokiPlayerCheats", "ULokiClientPlayerCheats"]

    img(); load_sections()
    print("[img] base=%#x  .text union pages %d/%d (%.2f%%)  conflicts=%s cached=%s"
          % (IMAGE_BASE, _UNION_STATS.get("pages", 0), _UNION_STATS.get("total", 0),
             100.0 * _UNION_STATS.get("pages", 0) / max(_UNION_STATS.get("total", 1), 1),
             _UNION_STATS.get("conflicts"), _UNION_STATS.get("cached")))

    rows = load_funcflags()
    print("[uht] %d native UFunction registrations" % len(rows))

    tbl, mult = nativefn_table()
    print("[tbl] native-fn records: %d distinct names" % len(tbl))

    for cls in classes:
        crows = [r for r in rows if r["owner"] == cls]
        names = set(r["func"] for r in crows)
        # the class's records are contiguous in .data -> pick the cluster whose
        # record offsets sit in the same span as the majority of this class's names
        offs = [o for n in names for _, _, o in tbl.get(n, [])]
        if offs:
            offs.sort()
            mid = offs[len(offs) // 2]
            lo, hi = mid - 0x8000, mid + 0x8000
        else:
            lo = hi = 0
        reg = {}
        for n in names:
            cands = [c for c in tbl.get(n, []) if lo <= c[2] <= hi]
            if not cands:
                cands = tbl.get(n, [])
            if cands:
                reg[n] = cands[0]
        print("\n================ %s ================" % cls)
        print("declared native UFunctions (UHT): %d ; native-fn table matched %d/%d names"
              % (len(crows), len(reg), len(names)))
        sel = [r for r in crows if (not a.execonly or "Exec" in r["flags"].split("|"))]
        out = []
        for r in sorted(sel, key=lambda x: x["func"]):
            prva = int(r["params_rva"], 16)
            sig, nprop, ssz = decode_signature(prva)
            ent = reg.get(r["func"])
            thunk = impl = None
            how = ""
            if ent is None:
                verdict, detail, isz = "NO_TABLE_ENTRY", "name absent from native-fn table", 0
            else:
                thunk, impl, _ = ent
                slot = vcall_slot(impl)
                if thunk == PROCESS_INTERNAL:
                    verdict, detail, isz = "SCRIPT", "thunk IS ProcessInternal", 0
                elif slot is not None:
                    how = "VIRTUAL vtable[+%#x]" % slot
                    verdict, detail, isz = grade_body(impl)
                    verdict = "VIRTUAL_" + verdict
                else:
                    how = "direct &%s::%s" % (cls, r["func"])
                    verdict, detail, isz = grade_body(impl)
                detail += "  [ICF mult=%d]" % mult.get(impl, 0)
            out.append(dict(cls=cls, func=r["func"], flags=r["flags"],
                            thunk=thunk, impl=impl, verdict=verdict,
                            detail=detail, how=how, sig=sig, nprop=nprop,
                            ssz=ssz, params=r["params_rva"], isize=isz))
            print("  %-36s %-18s thunk=%-10s impl=%-10s  %s"
                  % (r["func"], verdict,
                     ("%#x" % thunk) if thunk else "-",
                     ("%#x" % impl) if impl else "-", sig))
            print("       %s | %s" % (how or "-", detail))
        from collections import Counter
        print("  --- verdicts:", dict(Counter(o["verdict"] for o in out)))
        if a.csv:
            newf = not os.path.exists(a.csv)
            with open(a.csv, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
                if newf:
                    w.writeheader()
                for o in out:
                    o = dict(o)
                    o["thunk"] = "%#x" % o["thunk"] if o["thunk"] else ""
                    o["impl"] = "%#x" % o["impl"] if o["impl"] else ""
                    w.writerow(o)


if __name__ == "__main__":
    main()
