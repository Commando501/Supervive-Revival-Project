# fk27: find instructions in .text whose 32-bit immediate equals one of a set of values,
# restricted to instructions that also touch memory (so we see flag TESTS, not constant loads),
# plus a separate list of `mov r32, imm32` sites.
# Blind spot: only immediates that survive as literal imm32 in a decoded (non-zero) page.
import sys, os, numpy as np, capstone, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dumplib import load
from funcs import func_of

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True

def scan(im, values):
    _, va, vsz, ra, rsz = im.sec(".text")
    buf = np.frombuffer(im.data[ra:ra+rsz], dtype=np.uint8)
    n = rsz - 3
    b0 = buf[0:n].astype(np.uint32); b1 = buf[1:n+1].astype(np.uint32)
    b2 = buf[2:n+2].astype(np.uint32); b3 = buf[3:n+3].astype(np.uint32)
    v = (b0 | (b1 << 8) | (b2 << 16) | (b3 << 24))
    mask = np.zeros(n, dtype=bool)
    for val in values: mask |= (v == np.uint32(val))
    pos = np.nonzero(mask)[0]
    out = []
    for p in pos:
        p = int(p)
        for back in range(1, 12):
            s = va + p - back
            try: ins = next(md.disasm(im.rd(s, back + 8), im.rva2va(s), 1))
            except StopIteration: continue
            if s + ins.size < va + p + 4: continue
            ok = any(o.type == capstone.x86.X86_OP_IMM and (o.imm & 0xFFFFFFFF) in values for o in ins.operands)
            if not ok: continue
            memop = any(o.type == capstone.x86.X86_OP_MEM for o in ins.operands)
            out.append((s, ins.mnemonic, ins.op_str, memop))
            break
    return out

if __name__ == "__main__":
    im = load(os.environ.get("FK27_IMG", "merged2"))
    vals = set(int(x, 16) for x in sys.argv[1:])
    hits = scan(im, vals)
    mem = [h for h in hits if h[3]]
    print(f"# imm32 in {[hex(v) for v in vals]}: total decoded sites={len(hits)}  with-memory-operand={len(mem)}")
    c = collections.Counter(h[1] for h in hits)
    print("  by mnemonic:", dict(c.most_common()))
    print("\n# sites WITH a memory operand (flag tests / RMW):")
    for (s, m, o, _) in mem:
        f = func_of(s)
        print(f"  +0x{s:07X}  {m:8s} {o:52s}  fn=+0x{f[0]:X}" if f else f"  +0x{s:07X}  {m:8s} {o:52s}  fn=?")
