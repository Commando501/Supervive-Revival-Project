#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
callers_of.py -- OFFLINE: every `call rel32` / `jmp rel32` site targeting an RVA.

Scans a flat dumpimage .text (file offset == RVA).  Reports the enclosing
function from the recovered pdata union, plus a coverage note.

  usage:  callers_of.py <target-rva-hex> [more-rvas...]
  env:    CG_DUMP (default dumps/tutorial-hero/...), CG_TEXTUNION=1 to use the
          cross-ImageBase .text union built by exec_surface_probe.py textunion.
"""
import bisect, os, struct, sys
from array import array

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
TUTHERO = os.path.join(REPO, 'dumps', 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe')
PDATA_CSV = os.path.join(REPO, 'tools', 'strxref', 'index', 'pdata_union.csv')
CACHE = os.path.join(REPO, 'tools', 're', '.exec_surface_cache')
TBASE = 0x1000


def load_text():
    if os.environ.get('CG_TEXTUNION'):
        u = open(os.path.join(CACHE, 'text_union.bin'), 'rb').read()
        return u, TBASE, 'text_union'
    p = os.environ.get('CG_DUMP', TUTHERO)
    d = open(p, 'rb').read()
    e = struct.unpack_from('<I', d, 0x3C)[0]
    nsec = struct.unpack_from('<H', d, e + 6)[0]
    szopt = struct.unpack_from('<H', d, e + 20)[0]
    sh = e + 24 + szopt
    for i in range(nsec):
        o = sh + i * 40
        name = d[o:o + 8].rstrip(b'\0').decode('latin1')
        vsize, vaddr, rawsize, rawptr = struct.unpack_from('<IIII', d, o + 8)
        if name == '.text':
            return d[vaddr:vaddr + vsize], vaddr, os.path.basename(os.path.dirname(p))
    raise SystemExit('no .text')


_pd = None


def pdata():
    global _pd
    if _pd is None:
        beg, end = array('l'), array('l')
        with open(PDATA_CSV) as f:
            next(f)
            for line in f:
                x, y, _s, _u, _k = line.split(',')
                beg.append(int(x, 16)); end.append(int(y, 16))
        _pd = (beg, end)
    return _pd


def owner(rva):
    beg, end = pdata()
    i = bisect.bisect_right(beg, rva) - 1
    if i >= 0 and beg[i] <= rva < end[i]:
        return beg[i], end[i]
    return None, None


def main():
    txt, base, tag = load_text()
    targets = [int(a, 16) for a in sys.argv[1:]]
    print('image=%s  .text %#x..%#x  (%d bytes)' % (tag, base, base + len(txt), len(txt)))
    npages = len(txt) // 4096
    cov = sum(1 for i in range(npages) if any(txt[i * 4096:(i + 1) * 4096]))
    print('coverage: %d/%d pages non-zero (%.2f%%)  -- a zero page NEVER EXECUTED'
          % (cov, npages, 100.0 * cov / npages))
    for tgt in targets:
        hits = []
        for op, mn in ((0xE8, 'call'), (0xE9, 'jmp')):
            i = 0
            while True:
                i = txt.find(bytes([op]), i)
                if i < 0:
                    break
                site = base + i
                rel = struct.unpack_from('<i', txt, i + 1)[0]
                if site + 5 + rel == tgt:
                    fs, fe = owner(site)
                    hits.append((site, mn, fs, fe))
                i += 1
        print('\ntarget %#x : %d rel32 site(s)' % (tgt, len(hits)))
        for site, mn, fs, fe in sorted(hits):
            if fs is None:
                print('   %#09x  %-4s   fn ???      (no pdata entry)' % (site, mn))
            else:
                print('   %#09x  %-4s   fn %#09x  size %5d  +%#x'
                      % (site, mn, fs, fe - fs, site - fs))


if __name__ == '__main__':
    main()
