import sys, collections
sys.path.insert(0,'scratchpad/s138/laneW2')
from pe import PE
from capstone import *
from capstone.x86 import *

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

def walk(pe, start, limit=0x4000, stop_at=None):
    """Recursive-descent within [start, start+limit). Returns dict rva->insn, sorted."""
    seen = {}
    todo = [start]
    while todo:
        a = todo.pop()
        while True:
            if a in seen: break
            if a < start or a >= start+limit: break
            code = pe.read(a, 32)
            if len(code) < 1: break
            try:
                ins = next(md.disasm(code, a))
            except StopIteration:
                break
            seen[a] = ins
            m = ins.mnemonic
            g = ins.group
            if m in ('ret','retf','jmp','ud2','int3'):
                if m == 'jmp' and ins.operands and ins.operands[0].type == X86_OP_IMM:
                    t = ins.operands[0].imm
                    if start <= t < start+limit: todo.append(t)
                break
            if m.startswith('j'):  # conditional
                if ins.operands and ins.operands[0].type == X86_OP_IMM:
                    t = ins.operands[0].imm
                    if start <= t < start+limit: todo.append(t)
            a = ins.address + ins.size
    return seen

def fmt(ins):
    return '0x%08X  %-26s %s %s' % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str)
