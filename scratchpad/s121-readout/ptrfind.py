#!/usr/bin/env python3
r"""ptrfind.py -- find every 8-aligned qword in a dumpimage snapshot equal to base+RVA,
and print the neighbouring qwords so a UHT registration record can be identified.
Offline, stdlib only."""
import struct, sys, argparse
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\s121-readout")
from logrec_scan import Image, DUMP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rva', help='target RVA, hex')
    ap.add_argument('--dump', default=DUMP)
    ap.add_argument('--ctx', type=int, default=4, help='neighbour qwords each side')
    a = ap.parse_args()
    img = Image(a.dump)
    target = img.base + int(a.rva, 16)
    print("image base 0x%X  target VA 0x%X (rva %s)" % (img.base, target, a.rva))
    tb = struct.pack('<Q', target)
    hits = 0
    for (name, va, vs, rp, rs) in img.sections:
        n = min(vs, rs)
        buf = img.buf
        start = rp
        end = rp + n
        i = buf.find(tb, start, end)
        while i >= 0:
            if (i - rp) % 8 == 0:
                hits += 1
                hit_rva = va + (i - rp)
                print("\n  HIT  .%s  qword @ rva 0x%08X" % (name, hit_rva))
                for k in range(-a.ctx, a.ctx + 1):
                    o = i + k * 8
                    if o < rp or o + 8 > end:
                        continue
                    v = struct.unpack_from('<Q', buf, o)[0]
                    tag = ''
                    if img.base <= v < img.base + img.sizeofimage:
                        r = v - img.base
                        sec = img.sec_of(r)
                        tag = ' -> .%s rva 0x%08X' % (sec, r)
                        if sec == '.rdata':
                            s = img.cstr(r, 80)
                            if s and all(32 <= ord(c) < 127 for c in s) and len(s) > 2:
                                tag += '  A%r' % s
                            else:
                                w = img.wstr(r, 60)
                                if w and len(w) > 2 and all(32 <= ord(c) < 127 for c in w):
                                    tag += '  U%r' % w
                    print("    [%+3d] rva 0x%08X = 0x%016X%s" % (k, va + (o - rp), v, tag))
            i = buf.find(tb, i + 1, end)
    print("\ntotal hits: %d" % hits)


if __name__ == '__main__':
    main()
