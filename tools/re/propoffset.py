#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
propoffset.py -- OFFLINE recovery of a UPROPERTY's *byte offset in the C++ class*
                 from UHT's generated FPropertyParams tables in .rdata.

WHY
---
usmap / schema.txt give the property NAME and type but NOT the struct offset, and
this build's object layout is non-stock, so stock offsets cannot be assumed.  UHT
emits `STRUCT_OFFSET(Class, Member)` as a literal uint16 in each
F*PropertyParams record, and .rdata is 100% readable in dumps/tutorial-hero.

LAYOUT (UE 5.4, UObjectGlobals.h:3428-3540, x64, WITH_METADATA=0):
    +0x00 const char* NameUTF8
    +0x08 const char* RepNotifyFuncUTF8
    +0x10 uint64      PropertyFlags
    +0x18 uint32      EPropertyGenFlags       (low 6 bits = type; 0x40 = ObjectPtr)
    +0x1C uint32      ObjectFlags
    +0x20 SetterFuncPtr
    +0x28 GetterFuncPtr
    +0x30 uint16      ArrayDim
    +0x32 uint16      Offset                  <-- what we want
    +0x38 UClass*(*ClassFunc)()               (object/class/struct props only)

Bool props use FBoolPropertyParams, which has ElementSize/SizeOfOuter where
Offset lives -- those are reported but flagged, do not read their "offset".

  usage:  propoffset.py <PropName> [PropName...]
          propoffset.py --control            run the built-in positive control
"""
import os, struct, sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
TUTHERO = os.path.join(REPO, 'dumps', 'tutorial-hero', 'SUPERVIVE-Win64-Shipping.dump.exe')

GEN = {0x00: 'Byte', 0x01: 'Int8', 0x02: 'Int16', 0x03: 'Int', 0x04: 'Int64',
       0x05: 'UInt16', 0x06: 'UInt32', 0x07: 'UInt64', 0x0A: 'Float', 0x0B: 'Double',
       0x0C: 'Bool', 0x0D: 'SoftClass', 0x0E: 'WeakObject', 0x0F: 'LazyObject',
       0x10: 'SoftObject', 0x11: 'Class', 0x12: 'Object', 0x13: 'Interface',
       0x14: 'Name', 0x15: 'Str', 0x16: 'Array', 0x17: 'Map', 0x18: 'Set',
       0x19: 'Struct', 0x1A: 'Delegate', 0x1B: 'InlineMulticastDelegate',
       0x1C: 'SparseMulticastDelegate', 0x1D: 'Text', 0x1E: 'Enum',
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

    def cstr(self, rva, n=96):
        b = self.d[rva:rva + n]
        i = b.find(b'\0')
        return b[:i if i >= 0 else n]


def find_name_ptrs(im, name):
    """RVAs of every .rdata qword pointing at an exact ASCII literal `name`."""
    pat = b'\x00' + name.encode() + b'\x00'
    strs = []
    for nm, va, vs in im.sections:
        if nm not in ('.rdata', '.data'):
            continue
        b = im.d[va:va + vs]
        p = 0
        while True:
            i = b.find(pat, p)
            if i < 0:
                break
            strs.append(va + i + 1)
            p = i + 1
    out = []
    for s in strs:
        needle = struct.pack('<Q', im.imagebase + s)
        for nm, va, vs in im.sections:
            if nm != '.rdata':
                continue
            b = im.d[va:va + vs]
            p = 0
            while True:
                i = b.find(needle, p)
                if i < 0:
                    break
                if (va + i) % 8 == 0:
                    out.append((va + i, s))
                p = i + 1
    return strs, out


def decode(im, rec):
    """Return a dict if `rec` looks like an F*PropertyParams, else None."""
    if rec + 0x40 > len(im.d):
        return None
    rep = im.q(rec + 0x08)
    if rep:
        r = rep - im.imagebase
        if not (0 < r < im.size and im.sec(r) in ('.rdata', '.data')):
            return None
    pflags = im.q(rec + 0x10)
    gen = struct.unpack_from('<I', im.d, rec + 0x18)[0]
    ofl = struct.unpack_from('<I', im.d, rec + 0x1C)[0]
    setter = im.q(rec + 0x20)
    getter = im.q(rec + 0x28)
    adim, off = struct.unpack_from('<HH', im.d, rec + 0x30)
    if gen >> 8:
        return None
    if (gen & 0x3F) not in GEN:
        return None
    if adim == 0 or adim > 64:
        return None
    for fp in (setter, getter):
        if fp and not (0 < fp - im.imagebase < im.size):
            return None
    return dict(rec=rec, pflags=pflags, gen=gen, objflags=ofl, arraydim=adim,
                offset=off, setter=setter, getter=getter,
                ty=GEN[gen & 0x3F] + ('/ObjPtr' if gen & 0x40 else ''))


def report(im, name, expect=None):
    strs, ptrs = find_name_ptrs(im, name)
    print('== %-28s  %d ASCII literal(s), %d aligned .rdata qword ref(s)'
          % (name, len(strs), len(ptrs)))
    recs = []
    for pr, sr in ptrs:
        d = decode(im, pr)
        if d:
            recs.append(d)
            cls = ''
            if (d['gen'] & 0x3F) in (0x11, 0x12, 0x0D, 0x0E, 0x0F, 0x10, 0x13, 0x19, 0x1E):
                cf = im.q(pr + 0x38)
                if 0 < cf - im.imagebase < im.size:
                    cls = '  ClassFunc=%#x' % (cf - im.imagebase)
            print('   params %#010x  off=%#06x (%5d)  dim=%d  gen=%#04x %-16s '
                  'pflags=%#018x objflags=%#x%s'
                  % (pr, d['offset'], d['offset'], d['arraydim'], d['gen'], d['ty'],
                     d['pflags'], d['objflags'], cls))
        else:
            print('   ptr    %#010x  -> not F*PropertyParams-shaped (name used elsewhere)' % pr)
    if expect is not None:
        got = sorted({r['offset'] for r in recs})
        ok = expect in got
        print('   CONTROL: expect %#x -> %s   (found %s)'
              % (expect, 'PASS' if ok else 'FAIL', [hex(g) for g in got]))
        return ok
    return None


def main():
    im = Img(TUTHERO)
    print('image=%s  ImageBase=%#x' % (os.path.basename(TUTHERO), im.imagebase))
    print('.rdata is 100.0%% readable in this dump (manifest) -> absence is meaningful\n')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--control' in sys.argv or not args:
        print('--- POSITIVE CONTROLS (offsets measured independently this session) ---')
        report(im, 'CheatManager', expect=0x520)
        report(im, 'CheatClass', expect=0x528)
        print()
    for a in args:
        report(im, a)


if __name__ == '__main__':
    main()
