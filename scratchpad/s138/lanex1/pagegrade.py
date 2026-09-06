#!/usr/bin/env python
"""LANE X1 (S138) page-grader.

Grades an RVA's containing 4KiB page in a flat dumped PE (FILE OFFSET == RVA).
Reports non-zero bytes / 4096 for the page, and the .text-wide page census.

Written 2026-08-21, scratchpad/s138/lanex1/pagegrade.py.  Read-only.
"""
import struct, sys

PAGE = 0x1000

class Image:
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.d = f.read()
        d = self.d
        pe = struct.unpack_from('<I', d, 0x3c)[0]
        nsec = struct.unpack_from('<H', d, pe + 6)[0]
        optsz = struct.unpack_from('<H', d, pe + 20)[0]
        self.imagebase = struct.unpack_from('<Q', d, pe + 24 + 24)[0]
        so = pe + 24 + optsz
        self.secs = []
        for i in range(nsec):
            o = so + i * 40
            nm = d[o:o + 8].rstrip(b'\0').decode('latin1')
            vs, va, rs, pr = struct.unpack_from('<IIII', d, o + 8)
            self.secs.append((nm, va, vs, pr, rs))

    def sec_of(self, rva):
        for nm, va, vs, pr, rs in self.secs:
            if va <= rva < va + max(vs, rs):
                return nm
        return None

    def page_nonzero(self, rva):
        """Return (nonzero_bytes, 4096) for the page containing rva, or None if
        the page is outside the file."""
        p = rva & ~(PAGE - 1)
        if p + PAGE > len(self.d):
            return None
        return (PAGE - self.d[p:p + PAGE].count(0), PAGE)

    def text_census(self):
        for nm, va, vs, pr, rs in self.secs:
            if nm == '.text':
                n = 0
                tot = rs // PAGE
                for i in range(tot):
                    off = pr + i * PAGE
                    if self.d[off:off + PAGE].count(0) != PAGE:
                        n += 1
                return n, tot
        return None


def normalize(rva, imagebase):
    """Docs cite bare RVAs ('base+0x447F410' -> 0x447F410) but occasionally a
    live VA.  Strip the image base if the value clearly carries one."""
    if rva > imagebase:
        return rva - imagebase, True
    return rva, False


if __name__ == '__main__':
    img = Image(sys.argv[1] if len(sys.argv) > 1 else 'dumps/merged13.dump.exe')
    print('image      %s' % img.path)
    print('ImageBase  0x%x' % img.imagebase)
    for a in sys.argv[2:]:
        rva = int(a, 16)
        rva, stripped = normalize(rva, img.imagebase)
        r = img.page_nonzero(rva)
        sec = img.sec_of(rva)
        if r is None:
            print('0x%08X  page 0x%08X  OUT-OF-FILE' % (rva, rva & ~0xfff))
        else:
            nz, tot = r
            print('0x%08X  sec=%-8s page 0x%08X  %4d/%d  %s%s' % (
                rva, sec, rva & ~0xfff, nz, tot,
                'DARK' if nz == 0 else 'LIT',
                '  (base-stripped)' if stripped else ''))
