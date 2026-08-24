# INDEPENDENT verifier image reader. Written from scratch, does not import peimg.py.
import struct, os
PATH = r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
IMAGEBASE = 0x7FF608F40000

class VImg:
    def __init__(self, path=PATH):
        self.buf = open(path,'rb').read()
        e_lfanew = struct.unpack_from('<I', self.buf, 0x3C)[0]
        assert self.buf[e_lfanew:e_lfanew+4] == b'PE\0\0', "not PE"
        coff = e_lfanew+4
        nsec, = struct.unpack_from('<H', self.buf, coff+2)
        szopt, = struct.unpack_from('<H', self.buf, coff+16)
        opt = coff+20
        self.magic, = struct.unpack_from('<H', self.buf, opt)
        self.imagebase, = struct.unpack_from('<Q', self.buf, opt+24)
        secs = opt+szopt
        self.sections = []
        for i in range(nsec):
            o = secs + 40*i
            name = self.buf[o:o+8].rstrip(b'\0').decode('latin1')
            vsz, va, rawsz, praw = struct.unpack_from('<IIII', self.buf, o+8)
            self.sections.append((name, va, vsz, praw, rawsz))
    def flat(self):
        return all(va == praw for (_n,va,_v,praw,_r) in self.sections)
    def sec_of(self, rva):
        for (n,va,vsz,praw,rawsz) in self.sections:
            if va <= rva < va + max(vsz, rawsz):
                return (n,va,vsz,praw,rawsz)
        return None
    def read(self, rva, n):
        # flat image: rva == file offset (verified)
        return self.buf[rva:rva+n]
    def page_nonzero(self, rva):
        p = rva & ~0xFFF
        return sum(1 for b in self.buf[p:p+0x1000] if b)

if __name__ == '__main__':
    im = VImg()
    print("imagebase in header: 0x%X  (expected 0x%X) match=%s" % (im.imagebase, IMAGEBASE, im.imagebase==IMAGEBASE))
    print("flat (va==praw for all sections):", im.flat())
    for s in im.sections:
        print("  %-9s va=0x%08X vsz=0x%08X praw=0x%08X raw=0x%08X" % s)
    print("filesize 0x%X" % len(im.buf))
    # brief control: known-DARK 0x5A6AC40 must read 0/4096
    print("CONTROL known-DARK 0x5A6AC40 page_nonzero =", im.page_nonzero(0x5A6AC40), "(expect 0)")
    print("CONTROL engine PerformMovement 0x035E9EC0 page_nonzero =", im.page_nonzero(0x035E9EC0))
