import sys, capstone
sys.path.insert(0,r'G:/git/Supervive Revival Project/scratchpad/s141/verify')
from vimg import V

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
md.detail = True

def rd(v, start, end):
    """Recursive descent CFG from start, bounded to [start,end)."""
    seen={}; work=[start]
    UNC={capstone.x86.X86_INS_JMP, capstone.x86.X86_INS_RET, capstone.x86.X86_INS_INT3,
         capstone.x86.X86_INS_UD2}
    while work:
        a=work.pop()
        while True:
            if a in seen or not (start<=a<end): break
            try: i=next(md.disasm(v.read(a,16), a))
            except StopIteration: seen[a]=None; break
            seen[a]=i
            nxt=a+i.size
            grp=set(i.groups)
            if i.id in (capstone.x86.X86_INS_RET, capstone.x86.X86_INS_INT3, capstone.x86.X86_INS_UD2):
                break
            if capstone.x86.X86_GRP_JUMP in grp:
                op=i.operands[0]
                if op.type==capstone.x86.X86_OP_IMM:
                    t=op.imm
                    if start<=t<end and t not in seen: work.append(t)
                if i.id==capstone.x86.X86_INS_JMP: break
            a=nxt
    return seen
