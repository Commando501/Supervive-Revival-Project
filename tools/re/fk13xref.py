#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fk13xref.py -- fast OFFLINE xref over the .text UNION built by fk13img.

Two modes, both numpy-vectorised and chunked so peak RSS stays ~200 MB:

  rip(target)   every byte offset o in .text where the little-endian dword at o,
                interpreted as a RIP displacement, lands exactly on `target`
                (i.e. dword(o) + o + 4 == target).  Each hit is then re-decoded
                with capstone from a few plausible instruction starts so a random
                data dword cannot masquerade as an instruction.
  ptr(rva)      every 8-byte-aligned slot in the whole image holding the ABSOLUTE
                address ImageBase+rva.  This is what finds UE reflection tables
                and vtable slots -- reflection stores absolute pointers, not
                rip-relative references (offline_xref.py's S102 lesson).

⚠ COVERAGE: a zero result is only meaningful if the pages that WOULD hold the
reference are decrypted.  `rip()` reports how many .text pages are live so a
null is never mistaken for absence.
"""
import os
import sys

import numpy as np
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fk13img as FI

MD = Cs(CS_ARCH_X86, CS_MODE_64)
_TEXT = None


def _text():
    global _TEXT
    if _TEXT is None:
        _TEXT = np.frombuffer(FI.img().rd(FI.TEXT_RVA, FI.TEXT_SIZE), dtype=np.uint8)
    return _TEXT


def rip(target, chunk=1 << 23):
    """-> sorted list of RVAs o such that i32(text[o:o+4]) + o + 4 == target."""
    t = _text()
    n = len(t)
    out = []
    for s in range(0, n - 4, chunk):
        e = min(s + chunk, n - 4)
        seg = t[s:e + 4]
        d = (seg[0:e - s].astype(np.int64)
             | (seg[1:e - s + 1].astype(np.int64) << 8)
             | (seg[2:e - s + 2].astype(np.int64) << 16)
             | (seg[3:e - s + 3].astype(np.int64) << 24))
        d = np.where(d >= 0x80000000, d - 0x100000000, d)
        idx = np.arange(s, e, dtype=np.int64)
        hit = np.nonzero(d + idx + 4 + FI.TEXT_RVA == target)[0]
        for h in hit:
            out.append(int(idx[h]) + FI.TEXT_RVA)
    return out


def rip_decoded(target, maxback=15):
    """rip() hits confirmed by decoding an instruction that actually carries the
    displacement.  Returns [(insn_rva, mnemonic, op_str)]."""
    im = FI.img()
    res = []
    for site in rip(target):
        # LONGEST first: `48 8d 15 disp32` (back=3) must win over `8d 15 disp32`
        # (back=2), which is the same bytes decoded one byte late.
        for back in range(maxback, 1, -1):
            a = site - back
            if a < FI.TEXT_RVA:
                continue
            code = im.rd(a, back + 8)
            try:
                ins = next(MD.disasm(code, a))
            except StopIteration:
                continue
            if ins.size == back + 4 and '[rip' in ins.op_str:
                res.append((a, ins.mnemonic, ins.op_str))
                break
    return res


def ptr(rva):
    """-> list of image RVAs holding the absolute qword ImageBase+rva."""
    im = FI.img()
    want = (im.base + rva).to_bytes(8, 'little')
    out = []
    d = im.d
    i = 0
    while True:
        i = d.find(want, i)
        if i < 0:
            break
        out.append(i)
        i += 1
    return out


def coverage():
    t = _text()
    pages = FI.TEXT_SIZE // FI.PAGE
    v = t[:pages * FI.PAGE].reshape(pages, FI.PAGE)
    live = int((v.any(axis=1)).sum())
    return live, pages


if __name__ == '__main__':
    FI.img()
    tgt = int(sys.argv[1], 16)
    live, tot = coverage()
    print('.text union coverage: %d/%d pages (%.1f%%)' % (live, tot, 100.0 * live / tot))
    mode = sys.argv[2] if len(sys.argv) > 2 else 'rip'
    if mode == 'ptr':
        for r in ptr(tgt):
            print('  ptr slot %#010x  sect=%s' % (r, FI.img().section_of(r)))
    else:
        for a, mn, ops in rip_decoded(tgt):
            print('  %#010x  %-8s %s' % (a, mn, ops))
