#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vcallsites.py -- OFFLINE: every indirect call/jmp through a fixed vtable
                 displacement, attributed to its enclosing pdata function.

Purpose: find the ROUTER.  A virtual dispatched at slot D shows up as
`call qword ptr [reg+D]`; the function containing the MOST such sites is the
dispatcher (e.g. UPlayer::Exec fans out to 8 ProcessConsoleExec targets).

Coverage-guarded: functions whose .text pages are all-zero were NEVER EXECUTED
and are skipped, and the count of skipped functions/bytes is printed.  A zero
here is only meaningful next to that number.

  usage:  vcallsites.py <disp-hex> [--min N] [--region LO HI]
"""
import argparse, bisect, os, struct, sys
from array import array
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
TUTHERO = os.path.join(REPO, 'dumps', 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe')
PDATA_CSV = os.path.join(REPO, 'tools', 'strxref', 'index', 'pdata_union.csv')


def load_text(path):
    d = open(path, 'rb').read()
    e = struct.unpack_from('<I', d, 0x3C)[0]
    nsec = struct.unpack_from('<H', d, e + 6)[0]
    szopt = struct.unpack_from('<H', d, e + 20)[0]
    for i in range(nsec):
        o = e + 24 + szopt + i * 40
        nm = d[o:o + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, rp = struct.unpack_from('<IIII', d, o + 8)
        if nm == '.text':
            return d[va:va + vsz], va
    raise SystemExit('no .text')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('disp', type=lambda x: int(x, 16))
    ap.add_argument('--min', type=int, default=1)
    ap.add_argument('--region', nargs=2, type=lambda x: int(x, 16))
    a = ap.parse_args()

    from capstone import Cs, CS_ARCH_X86, CS_MODE_64, x86_const as X
    MD = Cs(CS_ARCH_X86, CS_MODE_64); MD.detail = True
    STACK = {X.X86_REG_RSP, X.X86_REG_RBP}

    txt, tbase = load_text(TUTHERO)

    def live(rva, n):
        p, q = (rva - tbase) >> 12, (rva + n - 1 - tbase) >> 12
        return all(any(txt[i << 12:(i + 1) << 12]) for i in range(p, q + 1))

    beg, end = array('l'), array('l')
    with open(PDATA_CSV) as f:
        next(f)
        for line in f:
            x, y, _s, _u, _k = line.split(',')
            beg.append(int(x, 16)); end.append(int(y, 16))

    lo, hi = a.region if a.region else (tbase, tbase + len(txt))
    i0, i1 = bisect.bisect_left(beg, lo), bisect.bisect_left(beg, hi)

    hits = defaultdict(list)
    nfn = nskip = 0
    for i in range(i0, i1):
        s, e = beg[i], end[i]
        nfn += 1
        if not live(s, e - s):
            nskip += 1
            continue
        code = txt[s - tbase:e - tbase]
        for ins in MD.disasm(code, s):
            if ins.mnemonic not in ('call', 'jmp'):
                continue
            for op in ins.operands:
                if op.type == X.X86_OP_MEM and op.mem.disp == a.disp and op.mem.base not in STACK \
                        and op.mem.base != 0:
                    hits[s].append((ins.address, ins.mnemonic + ' ' + ins.op_str))
    tot = sum(len(v) for v in hits.values())
    print('disp %#x (vtable index %d)   scope %#x..%#x' % (a.disp, a.disp // 8, lo, hi))
    print('pdata functions in scope: %d ; skipped as NEVER-EXECUTED (all-zero pages): %d (%.1f%%)'
          % (nfn, nskip, 100.0 * nskip / max(nfn, 1)))
    print('indirect call/jmp sites at that displacement: %d in %d functions\n' % (tot, len(hits)))
    for fn, v in sorted(hits.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(v) < a.min:
            continue
        print('  fn %#09x  x%d' % (fn, len(v)))
        for ad, s in v:
            print('        %#09x  %s' % (ad, s))


if __name__ == '__main__':
    main()
