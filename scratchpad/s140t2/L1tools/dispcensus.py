# L1: image-wide census of instructions referencing a disp32 range off ANY base register.
# WRITE classification is from operands[0].type == MEM  (S140 recorded defect: regs_access
# reports movups/movaps STORES as reads -- NEVER use regs_access for this).
import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
from pe import load
import capstone as CS
from capstone import x86 as X86

pe = load()
md = CS.Cs(CS.CS_ARCH_X86, CS.CS_MODE_64)
md.detail = True
TEXT = [s for s in pe.sections if s['name']=='.text'][0]
T0, T1 = TEXT['rva'], TEXT['rva']+TEXT['vsize']

def scan_disp(lo, hi):
    """Find every instruction in .text whose MEM operand has disp in [lo,hi].
       Only disp32 encodings are findable this way (disp8 cannot encode >0x7F)."""
    buf = pe.buf
    cands = {}   # addr -> list of (ins, disp, k)
    ambiguous = []
    for d in range(lo, hi+1):
        pat = struct.pack('<i', d)
        start = T0
        while True:
            p = buf.find(pat, start, T1)
            if p < 0: break
            start = p+1
            # try instruction starts up to 15 bytes back
            for k in range(1, 16):
                a = p - k
                if a < T0: continue
                got = list(md.disasm(buf[a:a+16], a, count=1))
                if not got: continue
                ins = got[0]
                if not (ins.address <= p < ins.address + ins.size): continue
                hit = False
                for i,op in enumerate(ins.operands):
                    if op.type == X86.X86_OP_MEM and op.mem.disp == d:
                        hit = True
                if hit:
                    cands.setdefault(ins.address, []).append((ins, d, k))
    return cands

def is_write(ins):
    """operands[0].type == MEM  => memory destination. Never regs_access."""
    if not ins.operands: return False
    return ins.operands[0].type == X86.X86_OP_MEM

def base_reg(ins, d):
    for op in ins.operands:
        if op.type == X86.X86_OP_MEM and op.mem.disp == d:
            b = ins.reg_name(op.mem.base) if op.mem.base else None
            ix = ins.reg_name(op.mem.index) if op.mem.index else None
            return b, ix
    return None, None
