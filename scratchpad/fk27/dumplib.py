# fk27 shared dump reader. Offline only. file-offset == RVA for dumpimage captures.
import os, struct, sys

IMAGES = {
    "merged2":  ("dumps/merged2.dump.exe", 0x7FF6AF000000),
    "tuthero":  ("dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe", 0x7FF6505C0000),
    "merged":   ("dumps/merged.dump.exe", 0x7FF6AF000000),
}

class Img:
    def __init__(self, key):
        path, base = IMAGES[key]
        self.key = key
        self.path = path
        self.data = open(path, "rb").read()
        self.sections = []
        e_lfanew = struct.unpack_from("<I", self.data, 0x3C)[0]
        assert self.data[e_lfanew:e_lfanew+4] == b"PE\0\0", "not a PE"
        nsec = struct.unpack_from("<H", self.data, e_lfanew+6)[0]
        optsz = struct.unpack_from("<H", self.data, e_lfanew+20)[0]
        opt = e_lfanew + 24
        self.imagebase_hdr = struct.unpack_from("<Q", self.data, opt+24)[0]
        self.base = base
        sh = opt + optsz
        for i in range(nsec):
            o = sh + i*40
            name = self.data[o:o+8].rstrip(b"\0").decode("latin1")
            vsz, va, rsz, ra = struct.unpack_from("<IIII", self.data, o+8)
            self.sections.append((name, va, vsz, ra, rsz))
    def sec(self, name):
        for s in self.sections:
            if s[0] == name: return s
        return None
    def rd(self, rva, n):
        if rva < 0 or rva+n > len(self.data): return b""
        return self.data[rva:rva+n]
    def u8(self, rva):  return self.data[rva]
    def u32(self, rva): return struct.unpack_from("<I", self.data, rva)[0]
    def i32(self, rva): return struct.unpack_from("<i", self.data, rva)[0]
    def u64(self, rva): return struct.unpack_from("<Q", self.data, rva)[0]
    def va2rva(self, va): return va - self.base
    def rva2va(self, rva): return rva + self.base
    def page_zero(self, rva):
        p = rva & ~0xFFF
        return self.data[p:p+0x1000] == b"\0"*0x1000
    def coverage(self, name=".text"):
        s = self.sec(name)
        if not s: return None
        _, va, vsz, ra, rsz = s
        n = (rsz+0xFFF)//0x1000
        z = 0
        for i in range(n):
            if self.data[ra+i*0x1000: ra+(i+1)*0x1000] == b"\0"*0x1000: z += 1
        return (n-z, n, 100.0*(n-z)/n)

def load(key="merged2"):
    os.chdir(os.environ.get("FK27_ROOT", r"G:\git\Supervive Revival Project"))
    return Img(key)

if __name__ == "__main__":
    for k in ("merged2", "tuthero"):
        im = load(k)
        print(f"== {k}  {im.path}  len=0x{len(im.data):X}  hdrImageBase=0x{im.imagebase_hdr:X} assumedBase=0x{im.base:X}")
        for (n, va, vsz, ra, rsz) in im.sections:
            print(f"   {n:10s} va=0x{va:08X} vsz=0x{vsz:08X} raw=0x{ra:08X} rsz=0x{rsz:08X}  fo==rva:{va==ra}")
        print("   .text page coverage:", im.coverage(".text"))
