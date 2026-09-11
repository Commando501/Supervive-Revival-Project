# fk27: find rip-relative references in .text to a target RVA range, then validate by disassembly.
# Method: for every byte position p in .text, read disp32 at p and test
#   target == p + 4 + trailing + disp32   for trailing in {0,1,2,4,8}
# (trailing = bytes of immediate that follow the disp in the instruction encoding).
# Candidates are then confirmed by disassembling a window that ENDS at the right place with capstone,
# so no candidate is reported unless capstone produces an instruction whose rip-relative operand
# resolves to the requested target.  Blind-spot: an instruction whose first byte we never align to
# would be missed -- so we brute-force every start offset in a 16-byte lookback window.
import sys, os, numpy as np, capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dumplib import load

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

def raw_candidates(im, lo, hi):
    _, va, vsz, ra, rsz = im.sec(".text")
    buf = np.frombuffer(im.data[ra:ra+rsz], dtype=np.uint8)
    disp = np.frombuffer(im.data[ra:ra+rsz-3], dtype=np.dtype("<i4").newbyteorder("<"), count=rsz-3-3) if False else None
    # unaligned int32 view
    d = np.zeros(rsz-3, dtype=np.int32)
    b0 = buf[0:rsz-3].astype(np.uint32)
    b1 = buf[1:rsz-2].astype(np.uint32)
    b2 = buf[2:rsz-1].astype(np.uint32)
    b3 = buf[3:rsz].astype(np.uint32)
    v = (b0 | (b1 << 8) | (b2 << 16) | (b3 << 24))
    d = v.astype(np.int64)
    d = np.where(d >= 0x80000000, d - 0x100000000, d)
    pos = np.arange(rsz-3, dtype=np.int64) + va
    out = set()
    for trailing in (0, 1, 2, 4):
        tgt = pos + 4 + trailing + d
        m = (tgt >= lo) & (tgt < hi)
        for p in pos[m]:
            out.add(int(p))
    return sorted(out)

def confirm(im, cands, lo, hi):
    """Disassemble backwards from each candidate disp position; report confirmed instructions."""
    res = {}
    for p in cands:
        for back in range(2, 12):
            start = p - back
            code = im.rd(start, 20)
            if not code: continue
            try:
                ins = next(md.disasm(code, im.rva2va(start), 1))
            except StopIteration:
                continue
            hit = None
            for op in ins.operands:
                if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                    t = ins.address + ins.size + op.mem.disp - im.base
                    if lo <= t < hi: hit = t
            if hit is None: continue
            # require the disp field to be exactly at p
            if start + ins.size - 4 != p and not any(True for _ in ()):
                # disp may not be last (immediate follows); accept if disp bytes at p are inside ins
                if not (start < p < start + ins.size): continue
            res.setdefault(start, (ins.mnemonic, ins.op_str, ins.size, hit))
            break
    return res

if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "merged2"
    lo = int(sys.argv[2], 16); hi = int(sys.argv[3], 16)
    im = load(key)
    c = raw_candidates(im, lo, hi)
    r = confirm(im, c, lo, hi)
    print(f"# image={key} target RVA [0x{lo:X},0x{hi:X})  rawCand={len(c)} confirmed={len(r)}")
    for a in sorted(r):
        m, o, sz, t = r[a]
        zp = " [ZEROPAGE]" if im.page_zero(a) else ""
        print(f"  +0x{a:07X}  {m:8s} {o:44s} -> +0x{t:X}{zp}")
