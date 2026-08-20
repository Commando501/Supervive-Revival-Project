#!/usr/bin/env python3
"""S132 L4: UHT reflection-metadata decoder over the cold dump images."""
import sys, os, struct, re

DUMPS = {
    "merged4": r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe",
    "merged3": r"G:\git\Supervive Revival Project\dumps\merged3.dump.exe",
    "merged2": r"G:\git\Supervive Revival Project\dumps\merged2.dump.exe",
    "merged":  r"G:\git\Supervive Revival Project\dumps\merged.dump.exe",
    "tuthero": r"G:\git\Supervive Revival Project\dumps\tutorial-hero\SUPERVIVE-Win64-Shipping.dump.exe",
    "s129":    r"G:\git\Supervive Revival Project\dumps\s129-poolgate\SUPERVIVE-Win64-Shipping.dump.exe",
    "rideable": r"G:\git\Supervive Revival Project\dumps\s131-rideable-live\SUPERVIVE-Win64-Shipping.dump.exe",
}

class Img:
    def __init__(self, name):
        self.name = name
        path = DUMPS[name]
        self.path = path
        with open(path, "rb") as f:
            self.buf = f.read()
        b = self.buf
        e = struct.unpack_from("<I", b, 0x3C)[0]
        assert b[e:e+4] == b"PE\0\0"
        coff = e + 4
        nsec = struct.unpack_from("<H", b, coff+2)[0]
        szopt = struct.unpack_from("<H", b, coff+16)[0]
        opt = coff + 20
        self.imagebase = struct.unpack_from("<Q", b, opt+24)[0]
        self.sections = []
        sh = opt + szopt
        for i in range(nsec):
            o = sh + i*40
            nm = b[o:o+8].rstrip(b"\0").decode("latin1")
            vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", b, o+8)
            self.sections.append((nm, vaddr, vsize, rawptr, rawsize))
    def sec_of(self, rva):
        for s in self.sections:
            if s[1] <= rva < s[1] + max(s[2], s[4]):
                return s
        return None
    def off(self, rva):
        s = self.sec_of(rva)
        return None if not s else s[3] + (rva - s[1])
    def read(self, rva, n):
        o = self.off(rva)
        if o is None: return None
        return self.buf[o:o+n]
    def u64(self, rva):
        d = self.read(rva, 8)
        return None if d is None or len(d) < 8 else struct.unpack("<Q", d)[0]
    def u32(self, rva):
        d = self.read(rva, 4)
        return None if d is None or len(d) < 4 else struct.unpack("<I", d)[0]
    def u16(self, rva):
        d = self.read(rva, 2)
        return None if d is None or len(d) < 2 else struct.unpack("<H", d)[0]
    def va2rva(self, va):
        if va is None: return None
        if va >= self.imagebase: return va - self.imagebase
        return va
    def cstr(self, rva, maxlen=200):
        o = self.off(rva)
        if o is None: return None
        e = self.buf.find(b"\0", o, o+maxlen)
        if e < 0: return None
        try: return self.buf[o:e].decode("ascii")
        except Exception: return None
    def find_bytes(self, pat, secnames=None):
        res = []
        for nm, vaddr, vsize, rawptr, rawsize in self.sections:
            if secnames and nm not in secnames: continue
            data = self.buf[rawptr:rawptr+rawsize]
            i = 0
            while True:
                i = data.find(pat, i)
                if i < 0: break
                res.append((nm, vaddr + i))
                i += 1
        return res
    def find_qword(self, val, secnames=None):
        return self.find_bytes(struct.pack("<Q", val), secnames)

def img(name="merged4"):
    return Img(name)

if __name__ == "__main__":
    im = img(sys.argv[1] if len(sys.argv) > 1 else "merged4")
    print(im.path, hex(im.imagebase))
