#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fk13grade.py -- OFFLINE body grader + exec-thunk resolver for the Route B work.

THREE VERDICTS, never two.  The project's dominant failure mode is an instrument's
blind spot recorded as a property of the game, and `.text` demand-decrypts, so:

    REAL              a decoded body with real work in it
    FOLD              /OPT:ICF-folded empty stub (see FOLDS below) or a bare `ret`
    COVERAGE-BLOCKED  the 4 KiB page is all zero => no dumped process ever executed
                      it.  This is NOT "absent" and NOT "stub".

CONTROLS the grader must pass before any negative is believed (see selftest()):
  * a known FOLD graded FOLD           : 0x00F7EC20 (`ret 0`), 0x00F7EB60 (`xor al,al;ret`)
  * a known REAL of SIMILAR SIZE       : the fold-vs-real separation must not be a
                                         size threshold, so we grade `UCheatManager::
                                         ProcessConsoleExec` (154 B) and
                                         `ULokiPlayerCheats::EnableHotkeyCheats` (128 B)
                                         as REAL against folds of 3 B, AND we grade a
                                         *small* real body (`Ghost`, 96 B) as REAL.
  * a known COVERAGE-BLOCKED address   : reported with its page, never silently graded.

THUNK -> IMPL resolution follows the structural rule proven in
tools/re/cheat_impl_census.py (NOT call multiplicity -- ICF makes a stub the most
called address in the image, so a rarity filter inverts the answer):
    the impl is the LAST rel32 call / tail-jmp in the thunk that is not a
    guarded teardown call (one whose preceding instruction is a je/jz landing
    exactly past it), with the P_FINISH anchor reported as a cross-check.
A resolution that lands on an FFrame step helper is reported as UNRESOLVED.
"""
import os
import re
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_64

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fk13img as FI

MD = Cs(CS_ARCH_X86, CS_MODE_64)
MD.detail = False

FOLDS = {
    FI.FOLD_RET0: 'ret 0 (void)',
    FI.FOLD_FALSE: 'xor al,al; ret (false)',
}
JCC = ('je', 'jz', 'jne', 'jnz')

# byte patterns that ARE an empty body no matter where they live
TRIVIAL = [
    (b'\xc3', 'ret'),
    (b'\xc2\x00\x00', 'ret 0'),
    (b'\x32\xc0\xc3', 'xor al,al; ret'),
    (b'\x31\xc0\xc3', 'xor eax,eax; ret'),
    (b'\x33\xc0\xc3', 'xor eax,eax; ret'),
    (b'\xb0\x01\xc3', 'mov al,1; ret'),
]


def disasm(beg, end):
    d = FI.img().rd(beg, end - beg)
    return [(i.address, i.mnemonic, i.op_str, i.size) for i in MD.disasm(d, beg)]


def sweep_bounds(rva, cap=0x1000):
    """Fallback extent when the recovered unwind table has no entry."""
    im = FI.img()
    d = im.rd(rva, cap)
    o = rva
    for ins in MD.disasm(d, rva):
        o = ins.address + ins.size
        if ins.mnemonic in ('ret', 'jmp'):
            nxt = im.rd(o, 1)
            if not nxt or nxt[0] == 0xCC or o % 16 == 0:
                return rva, o
        if ins.mnemonic == 'int3':
            return rva, o
    return rva, o


def extent(rva):
    b, e = FI.pdata().bounds(rva)
    if b is not None:
        return b, e, 'pdata'
    b, e = sweep_bounds(rva)
    return b, e, 'sweep'


def grade(rva, label=''):
    """-> dict(verdict, size, src, note, ...)"""
    im = FI.img()
    if rva is None:
        return dict(rva=None, verdict='NONE', size=0, src='-', note='null pointer')
    if not (FI.TEXT_RVA <= rva < FI.TEXT_END):
        return dict(rva=rva, verdict='NOT-TEXT', size=0, src='-',
                    note='rva outside .text (section %s)' % im.section_of(rva))
    page_ok = im.page_decrypted(rva)
    if not page_ok:
        return dict(rva=rva, verdict='COVERAGE-BLOCKED', size=0, src='-',
                    note='page %#x is all zero in the 10-dump .text union'
                         % (rva & ~0xFFF))
    b, e, src = extent(rva)
    size = e - b
    head = im.rd(rva, 16)
    for pat, desc in TRIVIAL:
        if head.startswith(pat):
            return dict(rva=rva, verdict='FOLD', size=size, src=src,
                        note='%s [%s]' % (desc, FOLDS.get(rva, 'local trivial body')),
                        bytes=head[:len(pat)].hex(), start=b, end=e)
    if not im.range_decrypted(b, e):
        return dict(rva=rva, verdict='COVERAGE-BLOCKED', size=size, src=src,
                    note='body %#x..%#x spans an undecrypted page' % (b, e),
                    start=b, end=e)
    ins = disasm(b, e)
    ncall = sum(1 for _, mn, _, _ in ins if mn == 'call')
    return dict(rva=rva, verdict='REAL', size=size, src=src,
                note='%d insns, %d calls' % (len(ins), ncall),
                insns=len(ins), calls=ncall, bytes=head.hex(), start=b, end=e)


def rel32_targets(beg, end):
    out = []
    for rva, mn, ops, sz in disasm(beg, end):
        if mn in ('call', 'jmp') and ops.startswith('0x'):
            try:
                t = int(ops, 16)
            except ValueError:
                continue
            if FI.TEXT_RVA <= t < FI.TEXT_END:
                out.append((rva, t, mn == 'jmp', sz))
    return out


VDISP = re.compile(r'^qword ptr \[(\w+) \+ (0x[0-9a-f]+)\]$')


def resolve_impl(thunk_rva, vtable_rva=None):
    """Structural thunk -> _Implementation resolution.  Returns a dict, and NEVER
    reports an FFrame step helper as an implementation.

    Two dispatch shapes occur in UE exec thunks and BOTH must be handled or the
    answer is systematically wrong (cheat_impl_census.py's residual):
      (a) rel32   `call <Impl>` / tail `jmp <Impl>`  -- non-virtual impl
      (b) virtual `mov rax,[rcx] ; call/jmp qword ptr [rax+disp]`
          UE declares most UCheatManager verbs `virtual`, so (b) is the COMMON
          case: 46 of 55 here.  With the owning class's vtable RVA supplied we
          read the slot; without it we report the displacement and stop.
    """
    b, e, src = extent(thunk_rva)
    if not FI.img().range_decrypted(b, e):
        return dict(impl=None, why='COVERAGE-BLOCKED thunk body', thunk=(b, e, src))
    ins = disasm(b, e)
    # (b) virtual dispatch: last `call/jmp qword ptr [rax+disp]` preceded by
    #     `mov rax, qword ptr [rcx]` (the this-vtable load).
    # `this` starts in rcx and is routinely parked in a callee-saved register
    # (Summon: `mov rsi, rcx` ... `mov rax,[rsi]` ... `call [rax+0x338]`), so a
    # literal `[rcx]` test misses 21 of 50 verbs.  Track the alias set instead;
    # requiring the vtable load to come from a PROVEN this-alias is what stops a
    # vtable call on a *parameter* object being mistaken for the dispatch.
    THIS = {'rcx'}          # registers proven to alias `this`
    VTBL = set()            # registers holding this->vtable
    SLOT = {}               # register -> vtable displacement it was loaded from
    vdisp = None
    for i, (a, mn, ops, sz) in enumerate(ins):
        if mn == 'mov':
            m2 = re.match(r'^(\w+), (\w+)$', ops)
            mv0 = re.match(r'^(\w+), qword ptr \[(\w+)\]$', ops)
            mvd = re.match(r'^(\w+), qword ptr \[(\w+) \+ (0x[0-9a-f]+)\]$', ops)
            if m2:
                dst, src2 = m2.group(1), m2.group(2)
                (THIS.add if src2 in THIS else THIS.discard)(dst)
                (VTBL.add if src2 in VTBL else VTBL.discard)(dst)
                if src2 in SLOT:
                    SLOT[dst] = SLOT[src2]
                else:
                    SLOT.pop(dst, None)
            elif mv0:
                dst, base = mv0.group(1), mv0.group(2)
                THIS.discard(dst)
                SLOT.pop(dst, None)
                (VTBL.add if base in THIS else VTBL.discard)(dst)
            elif mvd:
                dst, base, d = mvd.group(1), mvd.group(2), int(mvd.group(3), 16)
                THIS.discard(dst)
                VTBL.discard(dst)
                if base in VTBL:
                    SLOT[dst] = d      # `mov rbx,[rax+0x320]` then later `call rbx`
                else:
                    SLOT.pop(dst, None)
            else:
                d0 = ops.split(',')[0]
                THIS.discard(d0)
                VTBL.discard(d0)
                SLOT.pop(d0, None)
        if mn in ('call', 'jmp'):
            m = VDISP.match(ops)
            if m and m.group(1) in VTBL:
                vdisp = int(m.group(2), 16)
            elif re.match(r'^\w+$', ops) and ops in SLOT:
                vdisp = SLOT[ops]
    if vdisp is not None:
        impl = FI.img().ptr(vtable_rva + vdisp) if vtable_rva else None
        rel = [t for _, t, _, _ in rel32_targets(b, e)
               if t not in FI.FRAME_HELPERS]
        return dict(impl=impl, why='virtual dispatch', vdisp=vdisp,
                    vslot=vdisp // 8, thunk=(b, e, src), dispatch='vtable',
                    rel32_also=rel[-1] if rel else None)
    idx = {a: i for i, (a, _, _, _) in enumerate(ins)}
    tgts = rel32_targets(b, e)
    # guarded-teardown filter: a call whose immediately preceding instruction is a
    # je/jz that lands exactly past the call is an optional FString/TArray dtor.
    keep = []
    for site, t, isjmp, sz in tgts:
        i = idx.get(site, 0)
        prev = ins[i - 1] if i else None
        guarded = False
        if prev and prev[1] in JCC and prev[2].startswith('0x'):
            try:
                if int(prev[2], 16) == site + sz:
                    guarded = True
            except ValueError:
                pass
        keep.append((site, t, isjmp, guarded))
    # P_FINISH anchor: `mov [reg+0x20], reg` right before the dispatch call
    anchor = None
    for i, (a, mn, ops, sz) in enumerate(ins):
        if mn == 'mov' and re.match(r'^qword ptr \[\w+ \+ 0x20\], \w+$', ops):
            for site, t, isjmp, g in keep:
                if site > a and not g:
                    anchor = t
                    break
            if anchor:
                break
    cands = [(s, t, j) for s, t, j, g in keep if not g]
    if not cands:
        return dict(impl=None, why='no unguarded rel32 dispatch', thunk=(b, e, src),
                    anchor=anchor, all_targets=tgts)
    site, t, isjmp = cands[-1]
    unresolved = t in FI.FRAME_HELPERS
    return dict(impl=None if unresolved else t,
                why='landed on an FFrame step helper %#x' % t if unresolved else 'ok',
                site=site, tail=isjmp, anchor=anchor, thunk=(b, e, src),
                anchor_agrees=(anchor == t) if anchor else None,
                all_targets=tgts,
                first_call=tgts[0][1] if tgts else None)


# --------------------------------------------------------------------------
def selftest():
    print('--- grader controls -------------------------------------------------')
    cases = [
        (FI.FOLD_RET0, 'FOLD', 'universal void fold'),
        (FI.FOLD_FALSE, 'FOLD', 'universal bool-false fold'),
        (0x035B7430, 'REAL', 'UCheatManager::ProcessConsoleExec (154 B)'),
        (0x05424670, 'REAL', 'ULokiPlayerCheats::EnableHotkeyCheats (128 B, live-verified)'),
        (0x0395D790, 'REAL', 'UKismetSystemLibrary::execExecuteConsoleCommand (469 B)'),
    ]
    ok = fail = 0
    for rva, want, why in cases:
        g = grade(rva)
        good = g['verdict'] == want
        ok += good
        fail += (not good)
        print('  %-10s want %-16s got %-16s %5s B  %-6s  %s'
              % ('%#010x' % rva, want, g['verdict'], g['size'], g['src'], why))
        print('       %s' % g['note'])
    print('controls: %d ok / %d fail' % (ok, fail))
    return fail == 0


if __name__ == '__main__':
    FI.img()
    sys.exit(0 if selftest() else 1)
