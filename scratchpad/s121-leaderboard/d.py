import sys, os, pickle, bisect
sys.path.insert(0, os.path.dirname(__file__))
from img import Img, ripdest, RDATA_LO, RDATA_HI, TEXT_LO, TEXT_HI, DATA_LO
import capstone

img = Img(sys.argv[3] if len(sys.argv) > 3 else None) if len(sys.argv) > 3 else Img()

def ann(insn):
    d = ripdest(insn)
    s = ""
    if d is not None:
        s += "  ; ->%08x" % d
        if RDATA_LO <= d < RDATA_HI:
            # try utf16 then ascii
            w = img.wstr(d, 90)
            a = img.cstr(d, 90)
            if len(w) >= 3 and all(32 <= ord(c) < 127 for c in w[:40]):
                s += '  W"%s"' % w[:80]
            elif len(a) >= 4 and all(32 <= ord(c) < 127 for c in a):
                s += '  A"%s"' % a[:80]
            else:
                q = img.u64(d)
                s += "  [q=%016x]" % q
        elif d >= DATA_LO:
            s += "  [.data q=%016x]" % img.u64(d)
    if insn.mnemonic in ("call", "jmp") and insn.operands and insn.operands[0].type == capstone.x86.X86_OP_IMM:
        s += "   => %08x" % insn.operands[0].imm
    return s

def run(lo, hi):
    for insn in img.md.disasm(img.b[lo:hi], lo):
        print("%08x  %-22s %-7s %-40s%s" % (insn.address, insn.bytes.hex(), insn.mnemonic, insn.op_str, ann(insn)))

if __name__ == "__main__":
    lo = int(sys.argv[1], 16)
    hi = int(sys.argv[2], 16) if len(sys.argv) > 2 else lo + 0x200
    if hi < lo: hi = lo + hi
    run(lo, hi)
