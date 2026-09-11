import sys, struct
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

M4 = r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe"
img = fkdis.Img(M4)
IB = img.imagebase
print("ImageBase 0x%X" % IB)
md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True

data = img.read(0x55CD510, 0x2F0)
rows=[]
for ins in md.disasm(data, IB + 0x55CD510):
    r = ins.address - IB
    tgt = None
    kind = None
    # rel32 branch/call
    if ins.mnemonic in ("call","jmp") or ins.mnemonic.startswith("j"):
        for op in ins.operands:
            if op.type == 2:  # IMM
                tgt = op.imm - IB; kind="branch"
    # rip-relative memory
    for op in ins.operands:
        if op.type == 3 and op.mem.base == 41:  # X86_REG_RIP
            tgt = (ins.address + ins.size + op.mem.disp) - IB; kind="riprel"
    if tgt is not None:
        rows.append((r, ins.mnemonic, ins.op_str, kind, tgt))
for r,m,o,k,t in rows:
    sec = img.sec_of(t)
    print("0x%08X  %-8s %-40s %-7s -> RVA 0x%08X  [%s]" % (r,m,o,k,t, sec[0] if sec else "?"))
