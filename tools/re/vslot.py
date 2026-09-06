#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vslot.py -- OFFLINE: read a fixed vtable slot out of the cold dump's .rdata and
            classify it three ways:  BASE (== the UObject-level implementation),
            OVERRIDE (a distinct real body), or FOLDED-STUB (a neutered fold).

Also diffs two vtables slot-by-slot (the control that a derived class's vtable
really is distinct from its parent's).

  usage:  vslot.py slot <disp-hex> <BASE-rva-hex> <vtable-rva-hex>[:label] ...
          vslot.py diff <vtA-hex> <vtB-hex> [nslots]
          vslot.py params <lo-hex> <hi-hex>      # walk F*PropertyParams records
"""
import os, struct, sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
TUTHERO = os.path.join(REPO, 'dumps', 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe')

# Known folds in THIS image (docs/fk13-console-exec-settled.md, CLAUDE.md).
FOLDS = {0x00F7EC20: 'universal empty stub (c2 00 00 = ret 0)',
         0x00F7EB60: 'fold: returns false',
         0x00F7EB50: 'fold',
         0x00B9E1F0: 'fold'}

GEN = {0x00: 'Byte', 0x01: 'Int8', 0x02: 'Int16', 0x03: 'Int', 0x04: 'Int64',
       0x05: 'UInt16', 0x06: 'UInt32', 0x07: 'UInt64', 0x0A: 'Float', 0x0B: 'Double',
       0x0C: 'Bool', 0x0D: 'SoftClass', 0x0E: 'WeakObject', 0x0F: 'LazyObject',
       0x10: 'SoftObject', 0x11: 'Class', 0x12: 'Object', 0x13: 'Interface',
       0x14: 'Name', 0x15: 'Str', 0x16: 'Array', 0x17: 'Map', 0x18: 'Set',
       0x19: 'Struct', 0x1A: 'Delegate', 0x1B: 'InlineMcastDlgt',
       0x1C: 'SparseMcastDlgt', 0x1D: 'Text', 0x1E: 'Enum',
       0x1F: 'FieldPath', 0x20: 'LWCReal', 0x21: 'Optional', 0x22: 'VValue'}


class Img:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        d = self.d
        e = struct.unpack_from('<I', d, 0x3C)[0]
        nsec = struct.unpack_from('<H', d, e + 6)[0]
        szopt = struct.unpack_from('<H', d, e + 20)[0]
        self.imagebase = struct.unpack_from('<Q', d, e + 24 + 24)[0]
        self.sections = []
        for i in range(nsec):
            o = e + 24 + szopt + i * 40
            nm = d[o:o + 8].rstrip(b'\0').decode('latin1')
            vsz, va, rsz, rp = struct.unpack_from('<IIII', d, o + 8)
            self.sections.append((nm, va, vsz))
        self.size = max(va + vs for _, va, vs in self.sections)

    def sec(self, rva):
        for nm, va, vs in self.sections:
            if va <= rva < va + vs:
                return nm
        return None

    def q(self, rva):
        return struct.unpack_from('<Q', self.d, rva)[0]

    def rva_of(self, va):
        return va - self.imagebase

    def page_live(self, rva):
        p = rva & ~0xFFF
        return any(self.d[p:p + 0x1000])

    def cstr(self, rva, n=128):
        b = self.d[rva:rva + n]
        i = b.find(b'\0')
        return b[:i if i >= 0 else n].decode('latin1')


def cmd_slot(im, argv):
    disp = int(argv[0], 16)
    base = int(argv[1], 16)
    print('slot disp %#x  (= vtable index %d)   BASE impl = %#x' % (disp, disp // 8, base))
    print('%-40s %-12s %-12s %s' % ('CLASS (vtable rva)', 'slot value', 'verdict', 'note'))
    for spec in argv[2:]:
        vt, _, label = spec.partition(':')
        vt = int(vt, 16)
        va = im.q(vt + disp)
        rva = im.rva_of(va)
        if not (0 < rva < im.size):
            print('%-40s %-12s %-12s %s' % (label or hex(vt), hex(va), 'BAD', 'not an image pointer'))
            continue
        if rva == base:
            verdict, note = 'BASE', 'inherits UObject::ProcessConsoleExec verbatim'
        elif rva in FOLDS:
            verdict, note = 'FOLDED', FOLDS[rva]
        else:
            verdict = 'OVERRIDE'
            note = 'distinct body' + ('' if im.page_live(rva) else '  [.text page NOT decrypted -- COVERAGE-BLOCKED]')
        print('%-40s %-12s %-12s %s' % ('%-26s %#010x' % (label, vt), '%#09x' % rva, verdict, note))


def cmd_diff(im, argv):
    a, b = int(argv[0], 16), int(argv[1], 16)
    n = int(argv[2]) if len(argv) > 2 else 512
    same = diff = 0
    firsts = []
    for i in range(n):
        va, vb = im.q(a + i * 8), im.q(b + i * 8)
        if va == vb:
            same += 1
        else:
            diff += 1
            if len(firsts) < 24:
                firsts.append((i, im.rva_of(va), im.rva_of(vb)))
    print('vtable diff  A=%#x  B=%#x  over %d slots: %d identical, %d DIFFERENT (%.1f%% overridden)'
          % (a, b, n, same, diff, 100.0 * diff / n))
    for i, x, y in firsts:
        mark = '  <== slot 81 = ProcessConsoleExec' if i == 81 else ''
        print('   slot %3d (+%#05x)  A %#09x -> B %#09x%s' % (i, i * 8, x, y, mark))


def decode(im, rec):
    if rec + 0x40 > len(im.d):
        return None
    nm = im.q(rec)
    r = nm - im.imagebase
    if not (0 < r < im.size) or im.sec(r) not in ('.rdata', '.data'):
        return None
    s = im.cstr(r, 80)
    if not s or not s[0].isalpha() or not all(c.isalnum() or c == '_' for c in s):
        return None
    rep = im.q(rec + 8)
    if rep and not (0 < rep - im.imagebase < im.size):
        return None
    gen = struct.unpack_from('<I', im.d, rec + 0x18)[0]
    if gen >> 8 or (gen & 0x3F) not in GEN:
        return None
    ofl = struct.unpack_from('<I', im.d, rec + 0x1C)[0]
    if ofl not in (0x45, 0x05, 0x41, 0x01, 0x0D, 0x4D):
        return None
    adim, off = struct.unpack_from('<HH', im.d, rec + 0x30)
    if adim == 0 or adim > 64:
        return None
    return (s, off, adim, gen, ofl)


def cmd_params(im, argv):
    lo, hi = int(argv[0], 16), int(argv[1], 16)
    print('F*PropertyParams walk  %#x..%#x  (bool props have ElementSize where Offset sits -- flagged)'
          % (lo, hi))
    r = lo & ~7
    while r < hi:
        d = decode(im, r)
        if d:
            s, off, adim, gen, ofl = d
            ty = GEN[gen & 0x3F] + ('/ObjPtr' if gen & 0x40 else '')
            warn = '   <-- Bool: NOT an offset' if (gen & 0x3F) == 0x0C else ''
            print('  %#010x  off=%#06x (%5d) dim=%d  %-18s %s%s' % (r, off, off, adim, ty, s, warn))
        r += 8


def main():
    im = Img(TUTHERO)
    cmd = sys.argv[1]
    {'slot': cmd_slot, 'diff': cmd_diff, 'params': cmd_params}[cmd](im, sys.argv[2:])


if __name__ == '__main__':
    main()
