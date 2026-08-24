import struct, sys
from capstone import *
from capstone.x86 import *

PATH = r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"

class Img:
    def __init__(self, path):
        self.buf = open(path,'rb').read()
        pe = struct.unpack_from('<I', self.buf, 0x3C)[0]
        assert self.buf[pe:pe+4] == b'PE\0\0'
        nsec = struct.unpack_from('<H', self.buf, pe+6)[0]
        optsz = struct.unpack_from('<H', self.buf, pe+20)[0]
        opt = pe+24
        magic = struct.unpack_from('<H', self.buf, opt)[0]
        assert magic == 0x20b, hex(magic)
        self.imagebase = struct.unpack_from('<Q', self.buf, opt+24)[0]
        self.secs=[]
        so = opt+optsz
        for i in range(nsec):
            b = so + i*40
            name = self.buf[b:b+8].rstrip(b'\0').decode('latin1')
            vsz, va, rsz, ptr = struct.unpack_from('<IIII', self.buf, b+8)
            self.secs.append((name,va,vsz,ptr,rsz))
    def flat(self):
        return [(n,va,ptr,va==ptr) for (n,va,vs,ptr,rs) in self.secs]
    def read(self, rva, n):
        return self.buf[rva:rva+n]
    def page_nonzero(self, rva):
        p = rva & ~0xFFF
        return sum(1 for b in self.buf[p:p+0x1000] if b)

im = Img(PATH)
print("ImageBase", hex(im.imagebase))
flat = im.flat()
print("sections flat:", sum(1 for f in flat if f[3]), "/", len(flat))
for f in flat:
    if not f[3]: print("  NOT FLAT:", f)

FOLDS = {0x00F7EC20:'c20000',0x00F7EB50:'33c0c3',0x00F7EB60:'32c0c3',0x00B9E1F0:'b001c3',0x00FC6CF0:'0f57c0c3'}
for a,exp in FOLDS.items():
    got = im.read(a, len(exp)//2).hex()
    print(f"fold {a:#x}: {got} {'PASS' if got==exp else 'FAIL exp '+exp}")
print("DARK control 0x5A6AC40 page nz =", im.page_nonzero(0x5A6AC40))
print("LIT  control 0x035E9EC0 page nz =", im.page_nonzero(0x035E9EC0))
