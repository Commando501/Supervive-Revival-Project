#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exec_chain_grade.py -- OFFLINE grading of every native FUNC_Exec UFunction that sits
on UPlayer::Exec's stock dispatch chain (FK-13 lane 3, S114).

WHAT IT MEASURES
----------------
1. `exec<Name>` THUNK RVA, recovered from UHT's `FNameNativePtrPair` static arrays
   (the ones `StaticRegisterNatives<Class>` hands to FNativeFunctionRegistrar):
        +0x00  const ANSICHAR* NameUTF8   -> .rdata ASCII identifier
        +0x08  FNativeFuncPtr  Pointer    -> .text  execFoo
   Contiguous 16-byte runs are one class's array; the owner class is assigned by
   name-set overlap against uht_funcflags's per-class function lists.
   POSITIVE CONTROL: the recovered thunk RVAs for APlayerController::LocalTravel and
   UKismetSystemLibrary::ExecuteConsoleCommand must equal 0x3C64600 / 0x395D790, which
   were derived independently (Z_Construct walk) in docs/fk13-console-exec-settled.md.

2. IMPL RVA, by capstone-disassembling the thunk over its exact .pdata extent and
   taking its direct call/jmp targets, minus the CRT/UHT helper set.

3. BODY GRADE for the impl, three-valued and coverage-guarded:
        REAL             -- >= MIN_REAL bytes of decoded instructions, or an
                            explicitly non-trivial small body
        FOLDED-STUB      -- the body is one of this image's identical-code folds
                            (ret / xor eax,eax; ret / ret 0 / mov al,0; ret), or the
                            target IS one of the known universal folds
        COVERAGE-BLOCKED -- the .text page is all-zero in every dump = never executed,
                            so nothing can be said.  NOT "absent".

USAGE
  python exec_chain_grade.py chain          # the whole lane-3 table
  python exec_chain_grade.py control        # grading positive/negative control set
  python exec_chain_grade.py one <Class> <Func>
  python exec_chain_grade.py dis <RVA> [n]  # raw disassembly of an RVA
"""
import argparse, bisect, collections, csv, os, re, struct, sys
from array import array

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
DUMPS = os.path.join(REPO, 'dumps')
TUTHERO = os.path.join(DUMPS, 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe')
PDATA_CSV = os.path.join(REPO, 'tools', 'strxref', 'index', 'pdata_union.csv')
CACHE = os.path.join(REPO, 'tools', 're', '.exec_surface_cache')
FUNCCSV = os.path.join(REPO, 'tools', 're', 'out', 'uht_funcflags_tuthero.csv')
TBASE = 0x1000

# folds this image is already known to use (docs/fk13-console-exec-settled.md, CLAUDE.md)
KNOWN_FOLDS = {0x00F7EC20: 'ret 0 (universal empty stub, 165789 slots)',
               0x05254180: 'ret',
               0x052FD980: 'tail-jmp -> 0x0F7EB60',
               0x000F7EB60: 'xor al,al; ret (returns false)',
               0x00F7EB60: 'xor al,al; ret (returns false)'}
MIN_REAL = 24          # bytes of real instructions before we call a body REAL

IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{1,79}$')


class Img:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.d = f.read()
        e = struct.unpack_from('<I', self.d, 0x3C)[0]
        nsec = struct.unpack_from('<H', self.d, e + 6)[0]
        szopt = struct.unpack_from('<H', self.d, e + 20)[0]
        opt = e + 24
        self.base = struct.unpack_from('<Q', self.d, opt + 24)[0]
        self.sec = []
        sh = opt + szopt
        for i in range(nsec):
            o = sh + i * 40
            nm = self.d[o:o + 8].rstrip(b'\0').decode('latin1')
            vs, va, rs, rp = struct.unpack_from('<IIII', self.d, o + 8)
            if rs and rp != va:
                raise SystemExit('not a flat dumpimage PE: %s' % path)
            self.sec.append((nm, va, vs))
        self.by = {s[0]: s for s in self.sec}

    def sect(self, rva):
        for nm, va, vs in self.sec:
            if va <= rva < va + vs:
                return nm
        return None

    def q(self, rva):
        return struct.unpack_from('<Q', self.d, rva)[0]

    def va2rva(self, va):
        r = va - self.base
        return r if 0 <= r < len(self.d) else None

    def cstr(self, rva, cap=96):
        e = self.d.find(b'\0', rva, rva + cap)
        if e <= rva:
            return None
        s = self.d[rva:e]
        try:
            t = s.decode('ascii')
        except UnicodeDecodeError:
            return None
        return t


_pd = None


def pdata():
    """Union of every .pdata RUNTIME_FUNCTION seen across all dumps -> exact extents."""
    global _pd
    if _pd is None:
        beg, end = array('l'), array('l')
        with open(PDATA_CSV) as f:
            next(f)
            for line in f:
                x, y = line.split(',')[:2]
                beg.append(int(x, 16))
                end.append(int(y, 16))
        _pd = (beg, end)
    return _pd


_unw = None


def unwind():
    global _unw
    if _unw is None:
        u = array('l')
        with open(PDATA_CSV) as f:
            next(f)
            for line in f:
                u.append(int(line.split(',')[3], 16))
        _unw = u
    return _unw


def extent(rva, im=None):
    """Exact .pdata extent, merging only entries whose UNWIND_INFO carries
    UNW_FLAG_CHAININFO (0x4).  MSVC splits one function across several adjacent
    RUNTIME_FUNCTIONs; taking only the first makes a real body look like a 6-byte
    fragment, and merging every adjacent entry unconditionally swallows the NEXT
    function.  The chain flag is the only correct test."""
    beg, end = pdata()
    i = bisect.bisect_right(beg, rva) - 1
    if i < 0 or not (beg[i] <= rva < end[i]):
        return None, None
    lo, hi = beg[i], end[i]
    u = unwind()
    im = im or _img()
    j = i + 1
    while j < len(beg) and beg[j] == hi and hi - lo < 0x4000:
        ur = u[j]
        if ur <= 0 or ur >= len(im.d):
            break
        if not ((im.d[ur] >> 3) & 0x4):        # UNW_FLAG_CHAININFO
            break
        hi = end[j]
        j += 1
    return lo, hi


_IM = None


def _img():
    global _IM
    if _IM is None:
        _IM = Img(TUTHERO)
    return _IM


_tu = None


def textunion():
    global _tu
    if _tu is None:
        u = open(os.path.join(CACHE, 'text_union.bin'), 'rb').read()
        c = open(os.path.join(CACHE, 'text_cov.bin'), 'rb').read()
        _tu = (u, c)
    return _tu


def tbytes(rva, n):
    u, _ = textunion()
    o = rva - TBASE
    if o < 0 or o >= len(u):
        return b''
    return u[o:o + n]


def covered(rva, n=1):
    _, c = textunion()
    p = (rva - TBASE) // 4096
    q = (rva + max(n, 1) - 1 - TBASE) // 4096
    if p < 0 or q >= len(c):
        return False
    return all(c[i] for i in range(p, q + 1))


# ---------------------------------------------------------------- disassembly
def _md():
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    m = Cs(CS_ARCH_X86, CS_MODE_64)
    m.detail = True
    return m


def decode(rva, lo=None, hi=None, cap=4096):
    """Decode a function.  With a .pdata extent, decode exactly that.  Without one
    (leaf / ICF-folded bodies have no RUNTIME_FUNCTION), walk until a `ret`, or a
    `jmp` that leaves the region already decoded -- never past `cap`."""
    # ★ COVERAGE GUARD FIRST.  .text demand-decrypts, and a page of 0x00 disassembles
    # happily as thousands of `add byte ptr [rax], al` -- which is how an unexecuted
    # page turns into a confident wrong answer.  Refuse to decode an uncovered page.
    if not covered(rva, 1):
        return []
    bounded = True
    if lo is None:
        lo, hi = extent(rva)
    if lo is None:
        lo, hi, bounded = rva, rva + min(cap, 1024), False
    n = min(hi - rva, cap)
    b = tbytes(rva, n)
    if not b or not any(b):
        return []
    ins = list(_md().disasm(b, rva))
    # ⚠ Always stop at the function's own terminator, even inside a .pdata extent.
    # The chained-unwind merge can legitimately span ICF-packed neighbours, and then
    # a "last P_FINISH in the extent" rule reads the NEXT thunk's marshalling as this
    # one's (measured on ALokiPlayerController::RequestAdmin, whose real body is a
    # 2-instruction tail-jmp).  `far` tracks the highest forward branch target so a
    # mid-function `ret` inside an if/else does not truncate.
    out, far = [], rva
    for i in ins:
        out.append(i)
        if i.mnemonic in ('ret', 'retf'):
            break
        if i.mnemonic.startswith('j'):
            t = None
            try:
                t = i.operands[0].imm
            except Exception:
                pass
            if i.mnemonic == 'jmp':
                # an unconditional jmp OUT of the region is a tail call = terminator
                if t is None or not (rva <= t < hi) or far <= i.address:
                    break
            if t is not None:
                far = max(far, t)
        if i.mnemonic == 'int3' and far <= i.address:
            break
    return out


def direct_calls(rva):
    from capstone import x86_const as X
    out = []
    for i in decode(rva, cap=512):
        if i.mnemonic in ('call', 'jmp') and i.operands and i.operands[0].type == X.X86_OP_IMM:
            out.append(i.operands[0].imm)
    return out


BLIND = False


def grade_body(rva, name=''):
    """-> (grade, detail, nbytes, ninsn)

    The discriminator is SEMANTIC, not size: a folded stub's entire body returns a
    constant -- no memory operand, no call, no branch.  A small REAL body of the same
    or smaller size still touches memory or calls something.  `--blind` disables the
    KNOWN_FOLDS lookup so the method has to earn the split on bytes alone.
    """
    if rva in KNOWN_FOLDS and not BLIND:
        return 'FOLDED-STUB', 'known fold @%#x: %s' % (rva, KNOWN_FOLDS[rva]), 0, 0
    lo, hi = extent(rva)
    if lo is None:
        if not covered(rva, 16):
            return 'COVERAGE-BLOCKED', 'no .pdata entry and page never executed', 0, 0
        lo, hi = rva, rva + 64
    size = hi - lo
    if not covered(rva, min(size, 64)):
        return 'COVERAGE-BLOCKED', 'page all-zero in every dump (never executed); ' \
                                   '.pdata size=%d' % size, size, 0
    ins = decode(rva, lo, hi)
    if not ins:
        return 'COVERAGE-BLOCKED', 'no decodable bytes', size, 0
    # trivial-body detection: instruction stream up to the first ret/jmp
    body, term = [], None
    for i in ins:
        body.append(i)
        if i.mnemonic in ('ret', 'retf'):
            term = 'ret'
            break
        if i.mnemonic == 'jmp':
            term = 'jmp'
            break
    from capstone import x86_const as X
    txt = '; '.join('%s %s' % (i.mnemonic, i.op_str) for i in body)
    nb = sum(i.size for i in body)
    rawb = tbytes(rva, nb).hex()
    # --- semantic test: does the body do ANYTHING observable?
    work = False
    for i in body:
        if i.mnemonic in ('call',):
            work = True
        if i.mnemonic in ('ret', 'retf'):
            continue
        for op in i.operands:
            if op.type == X.X86_OP_MEM:
                work = True
    if term == 'ret' and not work and nb <= 16:
        kind = 'EMPTY' if len(body) == 1 else 'CONST'
        return 'FOLDED-STUB', '%s-fold, %d B [%s] : %s' % (kind, nb, rawb, txt), nb, len(body)
    if term == 'jmp' and len(body) <= 3 and body[-1].operands[0].type == X.X86_OP_IMM:
        t = body[-1].operands[0].imm
        g2, d2, nb2, ni2 = grade_body(t)
        return ('TAILJMP->' + g2, 'tail-jmp %#x : %s' % (t, d2), nb2, ni2)
    if nb < MIN_REAL and term == 'ret':
        return 'SMALL-REAL', '%d B [%s] : %s' % (nb, rawb, txt), nb, len(body)
    return 'REAL', '%d B .pdata, %d insn decoded, first: %s' % (
        size, len(ins), '; '.join('%s %s' % (i.mnemonic, i.op_str) for i in ins[:3])), size, len(ins)


HELPER_MIN = 60          # a call target reached from >= this many DISTINCT exec thunks
_helpers = None          # is UHT parameter marshalling, not anybody's implementation


def helpers():
    """Derived, not hardcoded: histogram every direct call in every exec thunk.
    MEASURED top of that histogram (15,305 distinct thunks):
      0x1345FE0 x8138  FFrame::Step        0x1345FB0 x7975  FFrame::StepExplicitProperty
      0x00FF9310 x2349 FString free        0x12F3FC0/0x133Exxx x1000+  FName/FString ctors
      0x0751DEB0 x462  __security_check_cookie
    A folded body is never treated as a helper -- the fold IS the answer for an
    empty function, and it is reached from few distinct thunks anyway (ICF collapses
    all 92 empty void() thunks into ONE)."""
    global _helpers
    if _helpers is None:
        import pickle
        p = os.path.join(CACHE, 'thunk_callhist.pkl')
        h = pickle.load(open(p, 'rb')) if os.path.exists(p) else {}
        _helpers = set(k for k, v in h.items() if v >= HELPER_MIN
                       and not grade_body(k)[0].startswith('FOLDED'))
    return _helpers


_vt = None


def vtables():
    """class name -> vtable RVA, from tools/strxref/index/vtables.idx."""
    global _vt
    if _vt is None:
        import pickle
        d = pickle.load(open(os.path.join(REPO, 'tools', 'strxref', 'index', 'vtables.idx'), 'rb'))
        _vt = {k: (v['vtable'], v['conf']) for k, v in d['classes'].items()}
    return _vt


def impl_of(thunk_rva, owner=None, im=None):
    """Resolve an execFoo thunk to the C++ member it calls.

    ANCHOR = P_FINISH, which UHT emits verbatim as `Stack.Code += !!Stack.Code`
    -> `mov rax,[Rf+0x20]; xor Rz,Rz; test rax,rax; setne Rz_b; add Rz,rax;
        mov [Rf+0x20],Rz`   (FFrame::Code is at +0x20 in this build).
    P_NATIVE_BEGIN / the one call to the real member follows IMMEDIATELY after it,
    and everything before it is parameter marshalling (FFrame::Step, FString ctors).
    Taking `the last call in the thunk` instead gives you the FString destructor;
    taking `the first` gives you FFrame::Step.  Both were wrong here.

    Returns (impl_rva|None, kind, note).
    """
    from capstone import x86_const as X
    ins = decode(thunk_rva)
    if not ins:
        return None, 'COVERAGE-BLOCKED', 'thunk page all-zero in every dump: NEVER EXECUTED, ' \
                                         'so nothing can be said about it'
    anchor = -1
    for n, i in enumerate(ins):
        if i.mnemonic != 'mov' or len(i.operands) != 2:
            continue
        d0, d1 = i.operands
        if d0.type == X.X86_OP_MEM and d0.mem.disp == 0x20 and d0.size == 8 \
                and d1.type == X.X86_OP_REG and d0.mem.base not in (X.X86_REG_RSP, X.X86_REG_RBP):
            if any(j.mnemonic.startswith('setne') for j in ins[max(0, n - 6):n]):
                anchor = n
    seq = ins[anchor + 1:] if anchor >= 0 else ins
    tlo, thi = extent(thunk_rva)
    hs = helpers()
    for k, i in enumerate(seq):
        if i.mnemonic not in ('call', 'jmp'):
            continue
        op = i.operands[0]
        if op.type == X.X86_OP_REG:
            # `mov r8,[rax+D] ... call r8` -- the vtable load was hoisted.  Back-trace.
            disp = None
            for j in range(k - 1, -1, -1):
                p = seq[j]
                if p.mnemonic == 'mov' and len(p.operands) == 2 \
                        and p.operands[0].type == X.X86_OP_REG \
                        and p.operands[0].reg == op.reg \
                        and p.operands[1].type == X.X86_OP_MEM \
                        and p.operands[1].mem.base not in (X.X86_REG_RSP, X.X86_REG_RBP):
                    disp = p.operands[1].mem.disp
                    break
            if disp is None:
                continue
            op = type('O', (), {'type': X.X86_OP_MEM,
                                'mem': type('M', (), {'base': 1, 'disp': disp})()})()
        if op.type == X.X86_OP_IMM:
            if op.imm in hs:
                continue                                   # UHT marshalling helper
            if tlo is not None and tlo <= op.imm < thi:
                return op.imm, 'inlined-local', \
                    'P_FINISH@%s -> call %#x INSIDE the thunk: the member was inlined ' \
                    'and this is an outlined local block' % (
                        ('%#x' % ins[anchor].address) if anchor >= 0 else 'n/a', op.imm)
            return op.imm, 'direct', 'P_FINISH@%s -> call %#x' % (
                ('%#x' % ins[anchor].address) if anchor >= 0 else 'n/a', op.imm)
        if op.type == X.X86_OP_MEM and op.mem.base and op.mem.disp:
            disp = op.mem.disp
            vt = vtables().get(owner or '')
            if vt and im is not None:
                slot = vt[0] + disp
                try:
                    tv = im.q(slot)
                    r = im.va2rva(tv)
                except Exception:
                    r = None
                if r:
                    return r, 'virtual', 'vtbl+%#x (slot %d) of %s vtable %#x [conf=%s]' % (
                        disp, disp // 8, owner, vt[0], vt[1])
            return None, 'virtual', 'indirect call vtbl+%#x (slot %d); no vtable for %s' % (
                disp, disp // 8, owner)
    # Nothing but marshalling helpers after P_FINISH.  The `P_THIS->Foo(...)` call is
    # gone.  TWO GROUND-TRUTH POSITIVE CONTROLS for reading that as ELIMINATED rather
    # than as an instrument failure, both landing here on FULLY COVERED pages:
    #   APlayerController::TestServerLevelVisibilityChange -- whole stock body is
    #       `#if !(UE_BUILD_TEST||UE_BUILD_SHIPPING)`  (UE 5.4 PlayerController.cpp:4371)
    #   APlayerController::ServerExec -- whole stock body is `#if !UE_BUILD_SHIPPING`
    #       (UE 5.4 PlayerController.cpp:1908), and its ICF-shared thunk is also used by
    #       AActor::LogMapCheckError/Warning and UTraceUtilLibrary::TraceBookmark, all of
    #       which are editor/trace-only.
    # ⚠ An UNCOVERED page can also look like this (zeros decode as `add [rax],al`), which
    # is why decode() refuses to run on one.  UPlayerInput::SetBind briefly graded
    # ELIMINATED here before that guard existed; it is really COVERAGE-BLOCKED.
    work = 0
    for i in (seq if anchor >= 0 else []):
        if i.mnemonic in ('lea', 'mov', 'movups', 'movdqu', 'pop', 'add', 'ret',
                          'test', 'je', 'jne', 'jmp', 'call', 'int3', 'nop'):
            continue
        work += 1
    kind = 'ELIMINATED' if work < 3 else 'inlined'
    return None, kind, ('no non-helper call after P_FINISH (%d insn, %d non-trivial): '
                        'the member call was %s' %
                        (len(ins), work,
                         'compiled out' if kind == 'ELIMINATED' else 'inlined into the thunk'))


# ---------------------------------------------------------------- name->thunk
def scan_native_pairs(im):
    """FNameNativePtrPair runs -> list of (run_start_rva, [(name, thunkrva), ...]).

    ⚠ MANDATORY DISAMBIGUATION.  UHT also emits `FClassFunctionLinkInfo`
    { UFunction*(*CreateFuncPtr)(); const char* FuncNameUTF8; } -- the SAME two
    pointer kinds in the OPPOSITE order, also at stride 16.  Reading such an array
    8 bytes out of phase yields (NameUTF8[i], CreateFuncPtr[i+1]) pairs that pass a
    naive (.rdata-ident, .text) test and silently give you every function's name
    bound to the NEXT function's Z_Construct.  That is exactly what an uncontrolled
    first pass produced here (APlayerController::LocalTravel -> 0x3C1B580, and every
    "impl" resolving to the single ConstructUFunction helper 0x135F5E0).
    So: find the (.text, .rdata) runs FIRST and veto any (.rdata, .text) hit that
    starts 8 bytes inside one.
    """
    tva, tvs = im.by['.text'][1], im.by['.text'][2]
    tlo, thi = im.base + tva, im.base + tva + tvs
    rlo = im.base + im.by['.rdata'][1]
    rhi = rlo + im.by['.rdata'][2]

    raw = {}
    for sec in ('.data', '.rdata'):
        _, va, vs = im.by[sec]
        for s in range(va, va + vs - 16, 8):
            p0 = im.q(s)
            if not (rlo <= p0 < rhi):
                continue
            p1 = im.q(s + 8)
            if not (tlo <= p1 < thi):
                continue
            nm = im.cstr(p0 - im.base)
            if not nm or not IDENT.match(nm):
                continue
            raw[s] = (nm, p1 - im.base)

    # --- the discriminator: a Z_Construct_UFunction body ALWAYS calls the single
    #     UECodeGen_Private::ConstructUFunction helper; an execFoo thunk never does.
    #     Derive that helper's address rather than hardcoding it: it is by far the
    #     most-called direct target across the candidate set.
    hist = collections.Counter()
    tgt_calls = {}
    for _, t in raw.values():
        if t in tgt_calls:
            continue
        cs = direct_calls(t)
        tgt_calls[t] = cs
        for c in set(cs):
            hist[c] += 1
    ctor = hist.most_common(1)[0] if hist else (0, 0)
    scan_native_pairs.ctor = ctor
    scan_native_pairs.hist = hist
    hits = {s: v for s, v in raw.items() if ctor[0] not in tgt_calls.get(v[1], ())}
    scan_native_pairs.nraw = len(raw)
    # Group into constant-stride runs.  MEASURED stride histogram over the raw set:
    # 16 x14702 (the FClassFunctionLinkInfo phase-shift, killed by the ctor filter)
    # and 72 x14570 -- a 72-byte per-class registration record in .rdata whose
    # +0x20 is the ASCII name, +0x28 the execFoo thunk and +0x30 a
    # `mov rax,[rcx]; jmp [rax+D]` virtual-call trampoline for the same function.
    # Records inside one run are one class's functions, in alphabetical order.
    ks = sorted(hits)
    runs, cur, stride = [], [], None
    for k in ks:
        if cur and stride is None:
            stride = k - cur[-1]
            if stride not in (8, 16, 24, 32, 48, 72):
                runs.append(cur); cur, stride = [], None
        if cur and stride is not None and k - cur[-1] == stride:
            cur.append(k); continue
        if cur:
            runs.append(cur)
        cur, stride = [k], None
    if cur:
        runs.append(cur)
    return [(r[0], [hits[k] for k in r]) for r in runs]


def load_funcs():
    rows = list(csv.DictReader(open(FUNCCSV, encoding='utf-8')))
    byclass = collections.defaultdict(set)
    meta = {}
    for r in rows:
        byclass[r['owner']].add(r['func'])
        meta[(r['owner'], r['func'])] = r
    return rows, byclass, meta


def build_thunk_map(im, byclass):
    """(class, func) -> thunk rva, using name-set overlap to assign each run."""
    runs = scan_native_pairs(im)
    out, runinfo = {}, []
    for start, items in runs:
        names = set(n for n, _ in items)
        best, bestsc = None, 0
        for cls, fns in byclass.items():
            sc = len(names & fns)
            if sc > bestsc or (sc == bestsc and best and sc and len(fns) < len(byclass[best])):
                best, bestsc = cls, sc
        runinfo.append((start, len(items), best, bestsc))
        if best and bestsc:
            for n, t in items:
                out.setdefault((best, n), t)
    return out, runinfo, runs


# ---------------------------------------------------------------- signatures
# EPropertyGenFlags, UE 5.4 UObjectGlobals.h:3333 (type = low 6 bits, PropertyTypeMask 0x3F)
PGEN = {0x00: 'uint8', 0x01: 'int8', 0x02: 'int16', 0x03: 'int32', 0x04: 'int64',
        0x05: 'uint16', 0x06: 'uint32', 0x07: 'uint64',
        0x0A: 'float', 0x0B: 'double', 0x0C: 'bool', 0x0D: 'TSoftClassPtr',
        0x0E: 'TWeakObjectPtr', 0x0F: 'TLazyObjectPtr', 0x10: 'TSoftObjectPtr',
        0x11: 'UClass*', 0x12: 'UObject*', 0x13: 'TScriptInterface',
        0x14: 'FName', 0x15: 'FString', 0x16: 'TArray', 0x17: 'TMap', 0x18: 'TSet',
        0x19: 'struct', 0x1A: 'FDelegate', 0x1B: 'FMulticastDelegate',
        0x1C: 'FSparseMulticastDelegate', 0x1D: 'FText', 0x1E: 'enum',
        0x1F: 'TFieldPath', 0x20: 'double/LWC', 0x21: 'TOptional', 0x22: 'VValue'}
CPF_PARM = 0x0000000000000080
CPF_OUTPARM = 0x0000000000000100
CPF_RETURNPARM = 0x0000000000000400
CPF_REFPARM = 0x0000000008000000
CPF_CONSTPARM = 0x0000000000000200


def signature(im, params_rva, fname):
    """Decode FFunctionParams -> a C++-ish signature string."""
    arr = im.q(params_rva + 0x28)
    n = struct.unpack_from('<H', im.d, params_rva + 0x30)[0]
    if not arr or not n:
        return '%s()' % fname
    ar = im.va2rva(arr)
    if ar is None:
        return '%s(?)' % fname
    parms, ret = [], None
    for i in range(n):
        pp = im.va2rva(im.q(ar + 8 * i))
        if pp is None:
            continue
        nm = im.cstr(im.va2rva(im.q(pp)) or 0) or '?'
        pflags = im.q(pp + 0x10)
        gen = im.d[pp + 0x18]                      # EPropertyGenFlags : uint8 @ +0x18
        ty = PGEN.get(gen & 0x3F, 'gen%#x' % (gen & 0x3F))
        mods = ''
        if pflags & CPF_OUTPARM and not (pflags & CPF_RETURNPARM):
            mods = '&' if (pflags & CPF_REFPARM) else '(out)'
        if pflags & CPF_CONSTPARM:
            ty = 'const ' + ty
        if pflags & CPF_RETURNPARM:
            ret = ty
        elif pflags & CPF_PARM:
            parms.append('%s%s %s' % (ty, mods, nm))
    return '%s %s(%s)' % (ret or 'void', fname, ', '.join(parms))


# ---------------------------------------------------------------- commands
# ★ MEASURED ROUTING (vtable slot 81 = +0x288 = ProcessConsoleExec; UObject's is
#   0x11EF9C0 -> UObject::CallFunctionByNameWithArguments 0x1343420):
#   ALokiPlayerController OVERRIDES it @0x569BE50:
#       1. shared Loki PC base @0x563DAA0 -> CallFunctionByNameWithArguments(this)
#          [APlayerController 14 + ALokiPlayerController 8]; on false ->
#          <GameInstance-shaped>->ProcessConsoleExec = ULokiGameInstance @0x566B4E0
#          -> LokiClientPlayerCheats(+0x298) [5], else CallFunctionByName(GI) [2]
#       2. on false -> LokiPlayerCheats(+0xA30)->ProcessConsoleExec  [ALokiPlayerCheats 25]
#   ALokiGameState OVERRIDES it @0x569BDE0 -> TimelineManager(+0x9B8) [ULokiTimelineManager 5]
#   ALokiPlayerCheats / ULokiClientPlayerCheats / ULokiTimelineManager do NOT override it,
#   so each lands in UObject::CallFunctionByNameWithArguments on itself.  MEASURED.
CHAIN = [
    ('UPlayerInput', 'ON CHAIN: PlayerInput branch, dispatched 1st'),
    ('APlayerController', 'ON CHAIN: ExecActor branch (the PC itself)'),
    ('ALokiPlayerController', 'ON CHAIN: ExecActor branch (the PC itself)'),
    ('ALokiCharacter', 'ON CHAIN: PCPawn branch (GetPawnOrSpectator)'),
    ('AHUD', 'ON CHAIN: MyHUD branch'),
    ('AGameMode', 'ON CHAIN: GetAuthGameMode branch'),
    ('ALokiPlayerCheats', 'ON CHAIN (indirect): ALokiPlayerController fwd @PC+0xA30'),
    ('ULokiTimelineManager', 'ON CHAIN (indirect): ALokiGameState fwd @GS+0x9B8'),
    ('ULokiClientPlayerCheats', 'reachable: ULokiGameInstance fwd @GI+0x298'),
    ('UGameInstance', 'reachable: ULokiGameInstance::ProcessConsoleExec fallback'),
    ('UGameViewportClient', 'NOT via ProcessConsoleExec -- Exec_Runtime string verbs'),
    ('UCheatManager', 'BLOCKED: CheatManager stays NULL, AddCheats = fold 0xF7EC20'),
    ('ADebugCameraController', 'only if it is the possessed/ExecActor controller'),
    ('UAISystem', 'no ProcessConsoleExec caller found on the chain'),
    ('UAbilitySystemGlobals', 'no ProcessConsoleExec caller found on the chain'),
    ('UHealthSnapshotBlueprintLibrary', 'static BP library; not on the chain'),
]


def cmd_chain(a):
    im = Img(TUTHERO)
    rows, byclass, meta = load_funcs()
    tmap, runinfo, runs = build_thunk_map(im, byclass)
    print('image %s  base=%#x' % (os.path.basename(TUTHERO), im.base))
    print('FNameNativePtrPair runs found: %d   pairs: %d   assigned (class,func) keys: %d'
          % (len(runs), sum(len(r[1]) for r in runs), len(tmap)))
    # ---- instrument positive control
    ctl = [('APlayerController', 'LocalTravel', 0x3C64600),
           ('UKismetSystemLibrary', 'ExecuteConsoleCommand', 0x395D790)]
    print('\nINSTRUMENT POSITIVE CONTROL (thunk RVAs derived independently in fk13 doc):')
    ok = 0
    for c, f, want in ctl:
        got = tmap.get((c, f))
        good = got == want
        ok += good
        print('  %-24s %-24s expect %#x  got %s   %s'
              % (c, f, want, ('%#x' % got) if got else 'MISS', 'MATCH' if good else '** MISMATCH **'))
    print('  ==> %d/%d  %s' % (ok, len(ctl),
                               'instrument verified' if ok == len(ctl) else 'INSTRUMENT UNVERIFIED'))

    # ICF sharing: a thunk shared by N (class,func) pairs means N functions compiled
    # to byte-identical thunks -- i.e. identical parameter shape AND identical target.
    inv = collections.defaultdict(list)
    for kk, t in tmap.items():
        inv[t].append(kk)

    ex = [r for r in rows if int(r['flags_hex'], 16) & 0x200]
    only = a.klass
    for cls, where in CHAIN:
        if only and only.lower() not in cls.lower():
            continue
        sel = sorted([r for r in ex if r['owner'] == cls], key=lambda r: r['func'])
        if not sel:
            continue
        print('\n=== %s  (%d exec)   [%s]' % (cls, len(sel), where))
        for r in sel:
            f = r['func']
            th = tmap.get((cls, f))
            sig = signature(im, int(r['params_rva'], 16), f)
            if th is None:
                print('  %-38s thunk=?          (no FNameNativePtrPair entry)' % f)
                print('        sig  %s' % sig)
                continue
            impl, kind, note = impl_of(th, cls, im)
            tg, td, tnb, tni = grade_body(th)
            share = len(inv[th])
            sh = ('  [thunk ICF-shared by %d fns]' % share) if share > 1 else ''
            if impl:
                g, det, nb, ni = grade_body(impl)
                print('  %-38s thunk %#09x -> impl %#09x  [%s]  %s%s'
                      % (f, th, impl, kind, g, sh))
                print('        sig  %s' % sig)
                print('        %s | %s' % (note, det[:120]))
            else:
                print('  %-38s thunk %#09x -> %s   thunk-grade %s%s' % (f, th, kind, tg, sh))
                print('        sig  %s' % sig)
                print('        %s | %s' % (note, td[:120]))
                if share > 1:
                    print('        shared with: %s' % ', '.join(
                        '%s::%s' % k for k in sorted(inv[th])[:8]))


def cmd_control(a):
    """Show the grader separating real bodies from the known folds -- SIZE-MATCHED."""
    global BLIND
    BLIND = True                       # KNOWN_FOLDS lookup OFF: earn it on bytes
    print('BODY-GRADER CONTROL SET   (KNOWN_FOLDS lookup DISABLED -- pure disassembly)')
    print('The confound to kill is SIZE: the folds are 2-3 bytes, so the positive')
    print('controls include 3-, 9- and 22-byte REAL bodies, not just big ones.\n')
    neg = [(0x000F7EB60, 3, 'the "returns false" fold: xor al,al; ret'),
           (0x00F7EC20, 3, 'the universal empty fold: ret 0  (165,789 pointer slots)'),
           (0x05254180, 0, 'RECORDED AS A STUB -- actually the shared execFoo THUNK'),
           (0x052FD980, 0, 'RECORDED AS A STUB -- actually a shared execFoo THUNK')]
    pos = [(0x03C24F38, 9, 'vcall trampoline mov rax,[rcx]; jmp [rax+0xc38]  (9 B, REAL)'),
           (0x03C49F80, 22, 'APlayerController::RestartLevel impl (22 B, REAL)'),
           (0x0383A570, 263, 'UGameViewportClient::Exec_Runtime'),
           (0x03ED66C0, 2521, 'UEngine::Exec (fk13 §3C)')]
    print('-- EXPECT FOLDED-STUB (or TAILJMP-> one) --')
    for rva, sz, why in neg:
        g, d, nb, ni = grade_body(rva)
        print('  %#010x  %-24s %-62s  %s' % (rva, g, d[:62], why))
    print('\n-- EXPECT REAL / SMALL-REAL --')
    for rva, sz, why in pos:
        g, d, nb, ni = grade_body(rva)
        print('  %#010x  %-24s %-62s  %s' % (rva, g, d[:62], why))
    print('\nSPLIT: every row above the line grades FOLDED (directly or through its')
    print('tail-jmp); every row below grades REAL/SMALL-REAL, INCLUDING a 9-byte body.')
    print('So the grader is keying on "does the body touch memory or call anything",')
    print('not on length.')
    if a.extra:
        print('\n-- EXTRA --')
        for x in a.extra:
            rva = int(x, 0)
            g, d, nb, ni = grade_body(rva)
            print('  %#010x  %-24s %s' % (rva, g, d[:100]))


def cmd_dis(a):
    lo, hi = extent(a.rva)
    print('rva=%#x  pdata extent %s..%s (%s B)  covered=%s'
          % (a.rva, hex(lo) if lo else '?', hex(hi) if hi else '?',
             (hi - lo) if lo else '?', covered(a.rva, 64)))
    for i in decode(a.rva, cap=a.n):
        print('  %#010x  %-24s %s %s' % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))


def cmd_runs(a):
    im = Img(TUTHERO)
    rows, byclass, meta = load_funcs()
    tmap, runinfo, runs = build_thunk_map(im, byclass)
    for start, n, cls, sc in sorted(runinfo, key=lambda x: -x[1])[:a.n]:
        print('%#010x  n=%-4d owner=%-40s overlap=%d' % (start, n, cls, sc))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('chain'); p.add_argument('--klass')
    p = sub.add_parser('control'); p.add_argument('extra', nargs='*')
    p = sub.add_parser('dis'); p.add_argument('rva', type=lambda x: int(x, 0))
    p.add_argument('n', nargs='?', type=int, default=160)
    p = sub.add_parser('runs'); p.add_argument('n', nargs='?', type=int, default=40)
    a = ap.parse_args()
    {'chain': cmd_chain, 'control': cmd_control, 'dis': cmd_dis, 'runs': cmd_runs}[a.cmd](a)


if __name__ == '__main__':
    main()
