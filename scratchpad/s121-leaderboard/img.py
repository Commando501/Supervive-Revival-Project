"""Static image helper for merged2.dump.exe (file offset == RVA)."""
import struct, sys, os
import capstone

REPO = r"G:\git\Supervive Revival Project"
DEFAULT = os.path.join(REPO, "dumps", "merged2.dump.exe")
ALT = os.path.join(REPO, "dumps", "tutorial-hero", "SUPERVIVE-Win64-Shipping.dump.exe")

TEXT_LO, TEXT_HI = 0x1000, 0x1000 + 0x7649000
RDATA_LO, RDATA_HI = 0x764a000, 0x764a000 + 0x237d000
DATA_LO = 0x99c7000


class Img:
    def __init__(self, path=DEFAULT):
        self.path = path
        with open(path, "rb") as f:
            self.b = f.read()
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.md.detail = True

    def r(self, rva, n):
        return self.b[rva:rva + n]

    def u8(self, rva):  return self.b[rva]
    def u16(self, rva): return struct.unpack_from("<H", self.b, rva)[0]
    def u32(self, rva): return struct.unpack_from("<I", self.b, rva)[0]
    def i32(self, rva): return struct.unpack_from("<i", self.b, rva)[0]
    def u64(self, rva): return struct.unpack_from("<Q", self.b, rva)[0]

    def page_decrypted(self, rva):
        p = rva & ~0xFFF
        return any(self.b[p:p + 0x1000])

    def cstr(self, rva, maxn=400):
        e = self.b.find(b"\x00", rva, rva + maxn)
        if e < 0: e = rva + maxn
        try: return self.b[rva:e].decode("ascii")
        except Exception: return repr(self.b[rva:e])

    def wstr(self, rva, maxn=800):
        out = []
        i = rva
        while i < rva + maxn * 2:
            c = struct.unpack_from("<H", self.b, i)[0]
            if c == 0: break
            out.append(chr(c)); i += 2
        return "".join(out)

    def dis(self, rva, n=64):
        return list(self.md.disasm(self.b[rva:rva + n * 16], rva, n))

    def dis_range(self, lo, hi):
        return list(self.md.disasm(self.b[lo:hi], lo))


def ripdest(insn):
    """rip-relative memory target rva, or None."""
    for op in insn.operands:
        if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
            return insn.address + insn.size + op.mem.disp
    return None


def fmt(insn, img=None):
    s = "%08x  %-24s %s %s" % (insn.address, insn.bytes.hex(), insn.mnemonic, insn.op_str)
    d = ripdest(insn)
    if d is not None:
        s += "   ; ->%08x" % d
    return s
