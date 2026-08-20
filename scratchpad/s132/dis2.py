#!/usr/bin/env python3
"""Disassemble with RVA-normalised operands (machine-computed; never hand arithmetic)."""
import sys, struct
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\s132")
from xr import load
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
FOLD={0xF7EC20:'FOLD ret0', 0xF7EB50:'FOLD xor eax;ret', 0xF7EB60:'FOLD xor al;ret', 0xB9E1F0:'FOLD mov al,1;ret'}
def go(dump, rva, n):
    img=load(dump); B=img.imagebase
    md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
    data=img.read(rva,n)
    pg=set()
    for p in range(rva & ~0xFFF, rva+n, 0x1000):
        if not any(img.read(p,0x1000)): pg.add(p)
    for p in sorted(pg): print(f"  ;; WARNING page 0x{p:08X} ALL-ZERO (undecrypted)")
    for ins in md.disasm(data, B+rva):
        r=ins.address-B
        s=f"  0x{r:08X}  {ins.bytes.hex():<20} {ins.mnemonic} {ins.op_str}"
        note=''
        if ins.mnemonic in ('call','jmp','je','jne','jb','jbe','ja','jae','jg','jge','jl','jle','js','jns'):
            try:
                t=int(ins.op_str,0)
                if t>=B:
                    tr=t-B
                    note=f"   ; -> rva 0x{tr:08X}"+(f"  [{FOLD[tr]}]" if tr in FOLD else "")
            except: pass
        if 'rip +' in ins.op_str or 'rip -' in ins.op_str:
            # compute target
            import re
            m=re.search(r'rip ([+-]) (0x[0-9a-f]+)', ins.op_str)
            if m:
                d=int(m.group(2),16)*(1 if m.group(1)=='+' else -1)
                tr=r+ins.size+d
                note+=f"   ; riprel -> rva 0x{tr:08X}"
        print(s+note)
if __name__=='__main__':
    dump='merged4'; a=sys.argv[1:]
    if '--dump' in a:
        i=a.index('--dump'); dump=a[i+1]; del a[i:i+2]
    go(dump,int(a[0],0), int(a[1],0) if len(a)>1 else 0x80)
