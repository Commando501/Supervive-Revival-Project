#!/usr/bin/env python
"""Resolve the OWNING UClass of a UHT FPropertyParams record.

record rva -> the single qword pointer to it (a PropPointers slot)
           -> walk the array to its base
           -> the single qword pointer to the array base is FClassParams+0x28
           -> FClassParams+0x00 = ClassNoRegisterFunc  (its wide string names the class)
Validated: ALokiGameState's FClassParams bitfield NumProperties==155 == walked length.
"""
import struct, sys, argparse
import propscan as P


def owner(img, rec_rva, verbose=False):
    d = img.d
    tgt = (rec_rva + img.base).to_bytes(8, 'little')
    slots = []
    i = 0
    while True:
        i = d.find(tgt, i)
        if i < 0:
            break
        if i % 8 == 0:
            slots.append(i)
        i += 1
    res = []
    for slot in slots:
        lo = slot
        while True:
            v = struct.unpack_from('<Q', d, lo - 8)[0]
            r = img.rva(v)
            if r is None or img.secof(r) != '.rdata':
                break
            if struct.unpack_from('<I', d, r + 0x1C)[0] != 0x45:
                break
            lo -= 8
        ap = (lo + img.base).to_bytes(8, 'little')
        j = 0
        found = []
        while True:
            j = d.find(ap, j)
            if j < 0:
                break
            if j % 8 == 0:
                found.append(j)
            j += 1
        for f in found:
            cp = f - 0x28
            fn = struct.unpack_from('<Q', d, cp)[0]
            bf = struct.unpack_from('<I', d, cp + 0x38)[0]
            res.append(dict(slot=slot, arr=lo, idx=(slot - lo) // 8, clsparams=cp,
                            ctor=img.rva(fn) if img.rva(fn) is not None else None,
                            nprops=(bf >> 15) & 0x7FF,
                            classflags=struct.unpack_from('<I', d, cp + 0x3C)[0]))
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('rec', type=lambda x: int(x, 0))
    ap.add_argument('--dump', default='s129')
    a = ap.parse_args()
    img = P.Img(P.DUMPS[a.dump])
    for r in owner(img, a.rec):
        print('slot 0x%08X  array 0x%08X idx %d  FClassParams 0x%08X  ctor rva 0x%X  NumProperties=%d ClassFlags=0x%08X'
              % (r['slot'], r['arr'], r['idx'], r['clsparams'], r['ctor'] or 0, r['nprops'], r['classflags']))
