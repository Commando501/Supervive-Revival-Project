# fk27: function-extent aware helpers built on tools/strxref/index/pdata_union.csv
# (the .pdata SECTION is 100% zero in every dumpimage capture -- CLAUDE.md S115-a/b -- so extents
#  must come from the union index, which is the union of 68 dumps' exception directories.)
import bisect, csv, os, sys, capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dumplib import load

PDATA = r"tools/strxref/index/pdata_union.csv"

_funcs = None
def funcs():
    global _funcs
    if _funcs is None:
        rows = []
        with open(PDATA, newline="") as f:
            r = csv.reader(f); next(r)
            for a in r:
                rows.append((int(a[0], 16), int(a[1], 16), int(a[4])))
        rows.sort()
        _funcs = rows
    return _funcs

def func_starts():
    return [f[0] for f in funcs()]

def func_of(rva):
    fs = funcs(); ks = func_starts()
    i = bisect.bisect_right(ks, rva) - 1
    if i < 0: return None
    b, e, seen = fs[i]
    if b <= rva < e: return (b, e, seen)
    return None

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

def dis_func(im, begin, end, maxbytes=4096, annotate=True):
    n = min(end - begin, maxbytes)
    code = im.rd(begin, n)
    out = []
    for ins in md.disasm(code, im.rva2va(begin)):
        rvo = ins.address - im.base
        ann = ""
        for op in ins.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                t = ins.address + ins.size + op.mem.disp - im.base
                ann += f"  ; ->+0x{t:X}"
        if ins.group(capstone.CS_GRP_CALL) or ins.group(capstone.CS_GRP_JUMP):
            for op in ins.operands:
                if op.type == capstone.x86.X86_OP_IMM:
                    ann += f"  ; {ins.mnemonic}->+0x{op.imm - im.base:X}"
        out.append((rvo, ins.mnemonic, ins.op_str, ins.size, ann, bytes(ins.bytes)))
    return out

def print_func(im, begin, end, maxbytes=4096):
    for (rvo, m, o, sz, ann, bs) in dis_func(im, begin, end, maxbytes):
        print(f"  +0x{rvo:07X}  {bs.hex():<24s} {m:10s} {o:44s}{ann}")
