#!/usr/bin/env python
"""pe_hdr.py -- minimal READ-ONLY PE header dump, to positively identify which image the
hidden MEM_IMAGE allocations in the crashpad MemoryInfoList belong to.

usage: python pe_hdr.py <file.dll|.exe> ...
"""
import struct
import sys

CH = {0x20: 'CODE', 0x40: 'IDATA', 0x80: 'UDATA',
      0x20000000: 'EXEC', 0x40000000: 'READ', 0x80000000: 'WRITE'}


def chars(c):
    out = []
    for k in sorted(CH):
        if c & k:
            out.append(CH[k])
    return '|'.join(out)


def show(p):
    with open(p, 'rb') as f:
        head = f.read(0x2000)
    e_lfanew = struct.unpack_from('<I', head, 0x3C)[0]
    assert head[e_lfanew:e_lfanew + 4] == b'PE\0\0', "no PE sig"
    coff = e_lfanew + 4
    mach, nsec, tds, _p, _n, optsz, _ch = struct.unpack_from('<HHIIIHH', head, coff)
    opt = coff + 20
    magic = struct.unpack_from('<H', head, opt)[0]
    if magic == 0x20B:
        imgbase = struct.unpack_from('<Q', head, opt + 24)[0]
        secalign, filealign = struct.unpack_from('<II', head, opt + 32)
        sizeofimage, sizeofheaders = struct.unpack_from('<II', head, opt + 56)
    else:
        imgbase = struct.unpack_from('<I', head, opt + 28)[0]
        secalign, filealign = struct.unpack_from('<II', head, opt + 32)
        sizeofimage, sizeofheaders = struct.unpack_from('<II', head, opt + 56)
    print("file            : %s" % p)
    print("machine         : 0x%X   sections: %d   TimeDateStamp 0x%08X" % (mach, nsec, tds))
    print("ImageBase       : 0x%X" % imgbase)
    print("SizeOfImage     : 0x%X (%d)" % (sizeofimage, sizeofimage))
    print("SizeOfHeaders   : 0x%X" % sizeofheaders)
    print("SectionAlignment: 0x%X   FileAlignment: 0x%X" % (secalign, filealign))
    st = opt + optsz
    print("%-10s %-12s %-12s %-12s %-12s %s" %
          ("NAME", "VA(RVA)", "VSIZE", "RAWPTR", "RAWSIZE", "CHARACTERISTICS"))
    rows = []
    for i in range(nsec):
        s = st + i * 40
        nm = head[s:s + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rsz, rp = struct.unpack_from('<IIII', head, s + 8)
        ch = struct.unpack_from('<I', head, s + 36)[0]
        rows.append((nm, va, vsz, rp, rsz, ch))
        print("%-10s 0x%08X   0x%08X   0x%08X   0x%08X   0x%08X %s" %
              (nm, va, vsz, rp, rsz, ch, chars(ch)))
    # page-aligned region boundaries the OS would produce, merging equal-protection runs
    print("\nOS region boundaries predicted from the section table (protection runs):")
    def prot(ch):
        if ch & 0x20000000:
            return 'EXEC'
        if ch & 0x80000000:
            return 'WRITE'
        return 'READ'
    cur = None
    start = 0
    bounds = [0]
    align = secalign
    def up(x):
        return (x + align - 1) & ~(align - 1)
    prev_end = up(sizeofheaders)
    print("   +0x%08X  size 0x%08X  HEADERS" % (0, prev_end))
    bounds.append(prev_end)
    for nm, va, vsz, rp, rsz, ch in rows:
        end = up(va + vsz)
        print("   +0x%08X  size 0x%08X  %-10s %s" % (va, end - va, nm, prot(ch)))
        bounds.append(end)
    print("   boundaries: %s" % [hex(b) for b in bounds])


if __name__ == '__main__':
    for p in sys.argv[1:]:
        show(p)
        print()
