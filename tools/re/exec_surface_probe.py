#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exec_surface_probe.py -- OFFLINE instrument for FK-13 lane 2 (exec-command surface).

Built 2026-08-12.  Stdlib + capstone.  No live process, no injection.

WHAT IT DOES
------------
Three measurements, each with a built-in positive control, over the cold
`dumpimage` snapshots in dumps/:

  textunion   Build a MAXIMALLY-covered .text by unioning ALL dumps -- including
              the ones `usmapdump mergedumps` REFUSES (different ImageBase).
              That refusal is over-conservative: this image has ZERO relocations
              targeting .text (measured: 1,403,750 relocs -> 1,257,732 .rdata +
              146,018 .data + 0 .text), so .text bytes are base-independent.
              merged.dump.exe alone = 52.29% of pages; the union = 54.83%.

  lit         Exact NUL-terminated literal presence (UTF-16LE *and* ASCII) with
              an explicit control list.  Use .rdata from dumps/tutorial-hero,
              which is 100% READABLE (merged is 99.64% by page but only 63% by
              non-zero byte -- the byte metric is misleading for .rdata).
              An absent literal is only meaningful when sibling literals from
              the SAME translation unit's literal pool are present -- print the
              pool with `pool` and check.

  pool        Dump every wide literal in an RVA window, in address order.  MSVC
              emits one contiguous pool per translation unit in source order, so
              a `#if`-stripped block shows up as a GAP between surviving
              neighbours.  This is the strongest offline evidence available for
              "this code was compiled out" -- far stronger than a bare zero hit.

  tarray      Find `TArray` member iteration at a fixed struct offset D: a load
              of the Data pointer at [base+D] paired with a load of ArrayNum at
              [base+D+8] off the SAME non-stack base register, capstone-verified,
              coverage-guarded.  `--region LO HI` scopes it to one code region and
              also prints the region-scoped POSITIVE CONTROL (how many OTHER
              offsets in the same region do show the shape).

WHY THE CONTROLS ARE MANDATORY HERE
-----------------------------------
FK-13 exists because an ASCII-only string scan of a binary whose .text was still
encrypted got recorded as "the dev console is fully stripped".  Every negative
this tool prints is therefore accompanied by the control that proves the
instrument could have seen a positive.  Do not quote a zero from this tool
without quoting its control.

EXAMPLES
--------
  python exec_surface_probe.py textunion                  # build/refresh the union
  python exec_surface_probe.py lit NoDebugExecBindings KEYBINDING \
        --control DisableTouch "Duplicate mapping of key %s for axis %s"
  python exec_surface_probe.py pool 0x8247700 0x8247860   # UEngine::Exec verb pool
  python exec_surface_probe.py tarray 0x1a8 --region 0x3F10000 0x3F40000
"""

import argparse, bisect, collections, os, re, struct, sys
from array import array

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
DUMPS = os.path.join(REPO, 'dumps')
MERGED = os.path.join(DUMPS, 'merged.dump.exe')
TUTHERO = os.path.join(DUMPS, 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe')
PDATA_CSV = os.path.join(REPO, 'tools', 'strxref', 'index', 'pdata_union.csv')
CACHE = os.path.join(REPO, 'tools', 're', '.exec_surface_cache')
TBASE = 0x1000

STRING_SECTIONS = ('.rdata', '.data', '_RDATA', '.rodata', '.rsrc')


# --------------------------------------------------------------------------
class Img:
    """Flat dumpimage/mergedumps PE where file offset == RVA."""

    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.d = f.read()
        d = self.d
        if d[:2] != b'MZ':
            raise SystemExit('%s: not a PE' % path)
        e = struct.unpack_from('<I', d, 0x3C)[0]
        if d[e:e + 4] != b'PE\0\0':
            raise SystemExit('%s: bad PE signature' % path)
        _m, nsec, _, _, _, szopt, _ = struct.unpack_from('<HHIIIHH', d, e + 4)
        opt = e + 24
        self.imagebase = struct.unpack_from('<Q', d, opt + 24)[0]
        self.sizeofimage = struct.unpack_from('<I', d, opt + 56)[0]
        self.sections = []
        sh = opt + szopt
        for i in range(nsec):
            o = sh + i * 40
            name = d[o:o + 8].rstrip(b'\0').decode('latin1')
            vsize, vaddr, rawsize, rawptr = struct.unpack_from('<IIII', d, o + 8)
            if rawsize and rawptr != vaddr:
                raise SystemExit('%s: not a flat image (offset != RVA); do not point '
                                 'this tool at an on-disk PE' % path)
            self.sections.append((name, vaddr, vsize))
        self._by = {s[0]: s for s in self.sections}

    def bytes_of(self, name):
        _, va, vs = self._by[name]
        return self.d[va:va + min(vs, len(self.d) - va)], va

    def secof(self, rva):
        for name, va, vs in self.sections:
            if va <= rva < va + vs:
                return name
        return None

    def wstr(self, rva, maxn=512):
        b = self.d[rva:rva + maxn]
        out = []
        for i in range(0, len(b) - 1, 2):
            if b[i] == 0 and b[i + 1] == 0:
                break
            out.append(b[i:i + 2])
        return b''.join(out).decode('utf-16le', 'replace')


def all_dumps():
    out = [MERGED] if os.path.exists(MERGED) else []
    import glob
    out += sorted(glob.glob(os.path.join(DUMPS, '*', 'SUPERVIVE-Win64-Shipping.dump.exe')))
    return out


# --------------------------------------------------------------------------
def check_no_text_relocs(im):
    """The claim that licenses cross-ImageBase .text unioning.  Re-measure it."""
    rb, rbase = im.bytes_of('.reloc')
    o, total = 0, 0
    per = collections.Counter()
    n = len(rb)
    while o + 8 <= n:
        pageRVA, blkSize = struct.unpack_from('<II', rb, o)
        if blkSize == 0:
            break
        for i in range((blkSize - 8) // 2):
            ent = struct.unpack_from('<H', rb, o + 8 + i * 2)[0]
            if ent >> 12 == 0:
                continue
            total += 1
            per[im.secof(pageRVA + (ent & 0xFFF)) or '?'] += 1
        o += blkSize
    return total, per


def build_union(verbose=True):
    paths = all_dumps()
    if not paths:
        raise SystemExit('no dumps found under %s' % DUMPS)
    seed = Img(paths[0])
    total, per = check_no_text_relocs(seed)
    if per.get('.text', 0) != 0:
        raise SystemExit('ABORT: %d relocations target .text -- .text bytes are NOT '
                         'ImageBase-independent and cross-base unioning is INVALID.'
                         % per['.text'])
    if verbose:
        print('reloc audit: %d relocations, none into .text  %s' % (total, dict(per)))
    tb, _ = seed.bytes_of('.text')
    u = bytearray(tb)
    pages = len(tb) // 4096
    cov = bytearray(1 if any(tb[i * 4096:(i + 1) * 4096]) else 0 for i in range(pages))
    if verbose:
        print('seed %-14s %d/%d pages (%.2f%%)'
              % (os.path.basename(os.path.dirname(paths[0])) or 'merged',
                 sum(cov), pages, 100.0 * sum(cov) / pages))
    for p in paths[1:]:
        m = Img(p)
        b, _ = m.bytes_of('.text')
        added = 0
        for i in range(pages):
            if not cov[i] and any(b[i * 4096:(i + 1) * 4096]):
                u[i * 4096:(i + 1) * 4096] = b[i * 4096:(i + 1) * 4096]
                cov[i] = 1
                added += 1
        if verbose:
            print('  +%-14s %4d new pages -> %d (%.2f%%)'
                  % (os.path.basename(os.path.dirname(p)), added, sum(cov),
                     100.0 * sum(cov) / pages))
    os.makedirs(CACHE, exist_ok=True)
    open(os.path.join(CACHE, 'text_union.bin'), 'wb').write(bytes(u))
    open(os.path.join(CACHE, 'text_cov.bin'), 'wb').write(bytes(cov))
    return bytes(u), bytes(cov)


def load_union():
    tu = os.path.join(CACHE, 'text_union.bin')
    tc = os.path.join(CACHE, 'text_cov.bin')
    if not (os.path.exists(tu) and os.path.exists(tc)):
        return build_union(verbose=False)
    return open(tu, 'rb').read(), open(tc, 'rb').read()


# --------------------------------------------------------------------------
def find_exact(im, s, wide=True):
    """Exact literal, NUL-terminated, preceded by a 0x00 byte (a real literal start)."""
    pat = (s.encode('utf-16le') + b'\x00\x00') if wide else (s.encode('latin1') + b'\x00')
    out = []
    for sn in STRING_SECTIONS:
        if sn not in im._by:
            continue
        b, base = im.bytes_of(sn)
        p = 0
        while True:
            i = b.find(pat, p)
            if i < 0:
                break
            p = i + 1
            if i == 0 or b[i - 1] == 0:
                out.append(base + i)
    return out


def cmd_lit(a):
    th = Img(TUTHERO)
    mg = Img(MERGED)
    print('.rdata coverage: tutorial-hero 100.0%% readable (manifest), merged 99.64%% by page')
    print()
    print('%-46s %-9s %-9s %-9s %-9s' % ('LITERAL', 'W-tuthero', 'W-merged', 'A-tuthero', 'A-merged'))

    def row(s, tag):
        w1, w2 = find_exact(th, s, True), find_exact(mg, s, True)
        a1, a2 = find_exact(th, s, False), find_exact(mg, s, False)
        print('%-46s %-9d %-9d %-9d %-9d  %-8s %s'
              % (repr(s)[:44], len(w1), len(w2), len(a1), len(a2), tag,
                 [hex(x) for x in (w1 + a1)[:3]]))
        return len(w1) + len(a1)

    hits = [row(s, 'TARGET') for s in a.literals]
    ctrl = [row(s, 'CONTROL') for s in (a.control or [])]
    print()
    if a.control:
        print('CONTROL RESULT: %d/%d control literals FOUND.' % (sum(1 for c in ctrl if c), len(ctrl)))
        if not any(ctrl):
            print('  ==> INSTRUMENT FAILED ITS OWN CONTROL. Every zero above is'
                  ' COVERAGE-BLOCKED, not ABSENT.')
        elif all(ctrl):
            print('  ==> instrument verified. A zero above is ABSENT-from-.rdata.')
    else:
        print('NO CONTROL SUPPLIED -- every zero above is UNINTERPRETABLE. Pass --control.')


def cmd_pool(a):
    im = Img(a.image or TUTHERO)
    b, base = im.bytes_of('.rdata')
    lo, hi = a.lo - base, a.hi - base
    rx = re.compile(rb'(?:[\x20-\x7e]\x00){%d,}' % a.minlen)
    n = len(b)
    print('wide literal pool  %#x - %#x   image=%s' % (a.lo, a.hi, os.path.basename(im.path)))
    for m in rx.finditer(b[lo:hi]):
        s, e = lo + m.start(), lo + m.end()
        if not (e + 1 < n and b[e] == 0 and b[e + 1] == 0):
            continue
        if s > 0 and b[s - 1] != 0:
            continue
        print('  %#010x  %s' % (base + s, b[s:e].decode('utf-16le', 'replace')))


# --------------------------------------------------------------------------
_pd = None


def pdata():
    global _pd
    if _pd is None:
        beg, end = array('l'), array('l')
        with open(PDATA_CSV) as f:
            next(f)
            for line in f:
                x, y, _s, _u, _k = line.split(',')
                beg.append(int(x, 16))
                end.append(int(y, 16))
        _pd = (beg, end)
    return _pd


def cmd_tarray(a):
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64, x86_const as X
    MD = Cs(CS_ARCH_X86, CS_MODE_64)
    MD.detail = True
    STACK = {X.X86_REG_RSP, X.X86_REG_RBP}
    txt, cov = load_union()

    def covered(rva, n=1):
        p, q = (rva - TBASE) // 4096, (rva + n - 1 - TBASE) // 4096
        return all(cov[i] for i in range(max(p, 0), min(q, len(cov) - 1) + 1))

    def text(rva, n):
        return txt[rva - TBASE:rva - TBASE + n]

    beg, end = pdata()
    lo, hi = (a.region if a.region else (TBASE, TBASE + len(txt)))
    i0, i1 = bisect.bisect_left(beg, lo), bisect.bisect_left(beg, hi)

    recs, skipped, fnbytes, uncbytes = [], 0, 0, 0
    for i in range(i0, i1):
        s, e = beg[i], end[i]
        fnbytes += e - s
        if not covered(s, e - s):
            skipped += 1
            uncbytes += e - s
            continue
        for ins in MD.disasm(text(s, e - s), s):
            for op in ins.operands:
                if op.type == X.X86_OP_MEM and op.mem.base and op.mem.base not in STACK:
                    recs.append((ins.address, ins, op.mem.base, op.mem.disp, op.size, s))
    recs.sort(key=lambda r: r[0])
    addrs = [r[0] for r in recs]

    pairs = collections.Counter()
    ex = {}
    for ad, ins, base, disp, sz, fn in recs:
        if sz != 8 or ins.mnemonic not in ('mov', 'lea'):
            continue
        if ins.mnemonic == 'mov' and ins.operands[0].type != X.X86_OP_REG:
            continue
        j0 = bisect.bisect_left(addrs, ad - a.window)
        j1 = bisect.bisect_right(addrs, ad + a.window)
        for j in range(j0, j1):
            ad2, ins2, base2, disp2, sz2, _ = recs[j]
            if base2 != base or disp2 != disp + 8 or sz2 not in (4, 8):
                continue
            if ins2.mnemonic not in ('mov', 'movsxd', 'movsx', 'cmp', 'test', 'lea'):
                continue
            pairs[disp] += 1
            ex.setdefault(disp, (fn, ad, ins.mnemonic + ' ' + ins.op_str,
                                 ad2, ins2.mnemonic + ' ' + ins2.op_str))
            break

    print('scope %#x-%#x : %d pdata functions, %d fully covered, %d partial/undecrypted'
          % (lo, hi, i1 - i0, i1 - i0 - skipped, skipped))
    print('coverage by function bytes: %.1f%%   (an uncovered function CANNOT be ruled on)'
          % (100.0 * (fnbytes - uncbytes) / max(fnbytes, 1)))
    print()
    print('POSITIVE CONTROL -- TArray-shaped pairs found in this scope at OTHER offsets:')
    print('  %d distinct offsets, %d pairs total' % (len(pairs), sum(pairs.values())))
    for d, c in sorted(pairs.items())[:a.show]:
        fn, ad, s1, ad2, s2 = ex[d]
        print('   D=%#07x x%-4d fn %#x   %#x %-34s || %#x %s' % (d, c, fn, ad, s1, ad2, s2))
    print()
    for d in a.disps:
        c = pairs.get(d, 0)
        if c:
            fn, ad, s1, ad2, s2 = ex[d]
            print('TARGET D=%#x : %d TArray-shaped pair(s).  e.g. fn %#x  %#x %s || %#x %s'
                  % (d, c, fn, ad, s1, ad2, s2))
        else:
            verdict = ('ABSENT (controlled)' if pairs else
                       'COVERAGE-BLOCKED -- the control found nothing either')
            print('TARGET D=%#x : 0 TArray-shaped pairs -> %s' % (d, verdict))


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    sub.add_parser('textunion', help='build the cross-ImageBase .text union (+ reloc audit)')

    p = sub.add_parser('lit', help='exact literal presence with a control list')
    p.add_argument('literals', nargs='+')
    p.add_argument('--control', nargs='*', help='literals you KNOW are present')

    p = sub.add_parser('pool', help='dump the wide literal pool in an RVA window')
    p.add_argument('lo', type=lambda x: int(x, 0))
    p.add_argument('hi', type=lambda x: int(x, 0))
    p.add_argument('--image')
    p.add_argument('--minlen', type=int, default=2)

    p = sub.add_parser('tarray', help='TArray member-iteration scan at struct offset D')
    p.add_argument('disps', nargs='+', type=lambda x: int(x, 0))
    p.add_argument('--region', nargs=2, type=lambda x: int(x, 0))
    p.add_argument('--window', type=int, default=96)
    p.add_argument('--show', type=int, default=20)

    a = ap.parse_args()
    if a.cmd == 'textunion':
        build_union()
    elif a.cmd == 'lit':
        cmd_lit(a)
    elif a.cmd == 'pool':
        cmd_pool(a)
    elif a.cmd == 'tarray':
        cmd_tarray(a)


if __name__ == '__main__':
    main()
