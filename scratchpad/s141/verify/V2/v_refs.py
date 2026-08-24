import sys,struct; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
from capstone.x86 import *
I=VImg('dumps/merged14.dump.exe')
# Sound approach: disassemble every .text page that is non-zero, linearly at every byte offset is too slow.
# Instead: find all 4-byte little-endian disp values D such that some instr at addr A with length L has
# A+L+D == target. Search for the disp bytes, then SOUNDLY decode by trying every start in [hit-15, hit] and
# taking the LONGEST decode whose rip target matches. (longest-match-wins == L2's stated fix for L2-a)
TARGET=0x077F5180
tsec=[s for s in I.sections if s['name']=='.text'][0]
lo,hi=tsec['vaddr'], tsec['vaddr']+tsec['rawsz']
data=I.d[tsec['praw']:tsec['praw']+tsec['rawsz']]
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
hits=[]
import re
# candidate disp for instruction ending at E is TARGET-E; scan all positions
# brute: for each occurrence of any 4-byte value v at file pos p, the instr must end at TARGET-v.
# Equivalent: for instr ending at E, disp bytes at E-4. So scan every E: read dword at E-4, check E+d==TARGET
arr=memoryview(data)
res=[]
for e in range(4, len(data)):
    d4=int.from_bytes(arr[e-4:e],'little',signed=True)
    if (lo+e)+d4==TARGET:
        res.append(lo+e)
print("candidate instruction END addresses whose trailing disp32 targets 0x%08X: %d" % (TARGET,len(res)))
val=[]
for E in res:
    best=None
    for st in range(E-15,E):
        if st<lo: continue
        try: b=I.read(st,16)
        except KeyError: continue
        g=list(md.disasm(b,st))
        if not g: continue
        i=g[0]
        if i.address+i.size!=E: continue
        for o in i.operands:
            if o.type==X86_OP_MEM and i.reg_name(o.mem.base)=='rip' and i.address+i.size+o.mem.disp==TARGET:
                if best is None or i.size>best.size: best=i
    if best is not None: val.append(best)
print("validated (LONGEST-match) references: %d" % len(val))
for i in val:
    print("   %08x  %-22s %-8s %s" % (i.address,i.bytes.hex(),i.mnemonic,i.op_str))
print()
print("=== rax/other aliasing onto &Velocity in engine PhysFalling? ===")
ins,succ,_,_=cfg(I,0x035EC850)
for a in sorted(ins):
    i=ins[a]
    if i.id==X86_INS_LEA and i.operands[1].type==X86_OP_MEM:
        b=i.reg_name(i.operands[1].mem.base) if i.operands[1].mem.base else ''
        if b=='rdi' and 0xE0<=i.operands[1].mem.disp<=0x100:
            print("   %08x lea %s   <-- ALIAS of &Velocity" % (a,i.op_str))
    if i.id==X86_INS_MOV and i.operands[0].type==X86_OP_REG and i.operands[1].type==X86_OP_REG:
        if i.reg_name(i.operands[1].reg)=='rsi':
            print("   %08x mov %s   <-- copies rsi (&Velocity)" % (a,i.op_str))
