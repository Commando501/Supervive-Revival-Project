import sys
sys.path.insert(0,'scratchpad/s139')
from img import DATA, IMAGEBASE, sec_of
from syms import name as symname
from capstone import *
from capstone.x86 import *
md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail=True

def walk(entry, maxbytes=0x4000, extra_starts=()):
    seen=set(); todo=[entry]+list(extra_starts); ins_map={}
    lo,hi = entry, entry+maxbytes
    while todo:
        a=todo.pop()
        if a in seen: continue
        while True:
            if a in seen: break
            if not (lo-0x2000 <= a < hi): break
            code=DATA[a:a+16]
            g=list(md.disasm(code,a,1))
            if not g: break
            ins=g[0]; seen.add(a); ins_map[a]=ins
            m=ins.mnemonic
            if m=='ret' or m.startswith('ret'): break
            if m=='jmp':
                if ins.op_str.startswith('0x'):
                    t=int(ins.op_str,16)
                    if lo-0x2000<=t<hi: a=t; continue
                break
            if m.startswith('j'):
                if ins.op_str.startswith('0x'):
                    t=int(ins.op_str,16)
                    if lo-0x2000<=t<hi: todo.append(t)
            if m in ('int3','ud2'): break
            a=ins.address+ins.size
    return ins_map

def fmt(ins):
    s="0x%08X  %-22s %-7s %s"%(ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str)
    ann=[]
    if ins.mnemonic in ('call','jmp') and ins.op_str.startswith('0x'):
        t=int(ins.op_str,16); nm=symname(t)
        if nm: ann.append("-> %s"%nm)
    for op in ins.operands:
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
            tgt=ins.address+ins.size+op.mem.disp
            ann.append("[rip-> 0x%08X %s]"%(tgt, sec_of(tgt)))
    if ann: s+="   ; "+"  ".join(ann)
    return s

if __name__=="__main__":
    e=int(sys.argv[1],16); mb=int(sys.argv[2],16) if len(sys.argv)>2 else 0x1000
    im=walk(e,mb)
    print("== 0x%08X  (%d instructions reached) =="%(e,len(im)))
    prev=None
    for a in sorted(im):
        if prev is not None and a!=prev: print("        ---- gap 0x%X ----"%(a-prev))
        print(fmt(im[a])); prev=a+im[a].size
