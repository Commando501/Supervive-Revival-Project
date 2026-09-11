# fk27: find direct E8 (call) / E9 (jmp) rel32 sites in .text targeting a given RVA.
# Also reports the preceding ~24 bytes so the argument setup (e.g. `mov edx, imm32`) is visible.
# Blind spot: only DIRECT rel32 control transfers; indirect/vtable calls are invisible, and a
# never-decrypted (all-zero) page contributes nothing.  Coverage is reported by the caller.
import sys, os, numpy as np, capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dumplib import load
from funcs import func_of

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True

def find(im, target, ops=(0xE8, 0xE9)):
    _, va, vsz, ra, rsz = im.sec(".text")
    buf = np.frombuffer(im.data[ra:ra+rsz], dtype=np.uint8)
    n = rsz - 5
    b0 = buf[1:n+1].astype(np.uint32); b1 = buf[2:n+2].astype(np.uint32)
    b2 = buf[3:n+3].astype(np.uint32); b3 = buf[4:n+4].astype(np.uint32)
    v = (b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)).astype(np.int64)
    v = np.where(v >= 0x80000000, v - 0x100000000, v)
    pos = np.arange(n, dtype=np.int64) + va
    tgt = pos + 5 + v
    out = []
    for op in ops:
        m = (buf[0:n] == op) & (tgt == target)
        for p in pos[m]:
            out.append((int(p), "call" if op == 0xE8 else "jmp"))
    return sorted(out)

if __name__ == "__main__":
    key = os.environ.get("FK27_IMG", "merged2")
    im = load(key)
    for a in sys.argv[1:]:
        t = int(a, 16)
        hits = find(im, t)
        print(f"== direct rel32 transfers to +0x{t:X}  image={key}  n={len(hits)}")
        for (p, kind) in hits:
            f = func_of(p)
            fs = f"fn=+0x{f[0]:X}" if f else "fn=?"
            # decode a short window ending at p to expose arg setup
            pre = ""
            code = im.rd(p - 24, 24 + 5)
            best = []
            for back in range(24, 0, -1):
                ins = list(md.disasm(im.rd(p - back, back + 5), im.rva2va(p - back)))
                if ins and any(i.address - im.base == p for i in ins):
                    best = [i for i in ins if i.address - im.base < p][-4:]
                    break
            pre = " | ".join(f"{i.mnemonic} {i.op_str}" for i in best)
            print(f"   +0x{p:07X} {kind:4s} {fs:16s}  <= {pre}")
