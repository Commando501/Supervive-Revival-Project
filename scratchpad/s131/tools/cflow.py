#!/usr/bin/env python3
"""S131 lane C: control-flow-aware disassembler over the cold dump images.

  cflow.py fn <rva> [end_rva] [--dump D]     linear disasm of [rva,end)
  cflow.py path <rva> [--dump D] [--not <branch_rva>] [--stop <rva>]
      recursive-descent over reachable basic blocks, with the branch at
      <branch_rva> FORCED NOT-TAKEN (i.e. assume the getter succeeded).
"""
import sys, os, struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_IMM, CS_OP_MEM
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

ROOT = r"G:\git\Supervive Revival Project"
DUMPS = {
 "merged4": ROOT + r"\dumps\merged4.dump.exe",
 "merged3": ROOT + r"\dumps\merged3.dump.exe",
 "merged2": ROOT + r"\dumps\merged2.dump.exe",
 "ride":    ROOT + r"\dumps\s131-rideable-live\SUPERVIVE-Win64-Shipping.dump.exe",
 "pod":     ROOT + r"\dumps\s131-droppod-live\SUPERVIVE-Win64-Shipping.dump.exe",
 "tuthero": ROOT + r"\dumps\tutorial-hero\SUPERVIVE-Win64-Shipping.dump.exe",
 "s129":    ROOT + r"\dumps\s129-poolgate\SUPERVIVE-Win64-Shipping.dump.exe",
}
FOLD = {0xF7EC20:"FOLD ret0", 0xF7EB50:"FOLD xor eax,eax;ret", 0xF7EB60:"FOLD xor al,al;ret",
        0xB9E1F0:"FOLD mov al,1;ret", 0x12C7260:"FOLD(known)"}

class Img:
    def __init__(s, path):
        s.path=path; s.buf=open(path,'rb').read(); b=s.buf
        pe=struct.unpack_from('<I',b,0x3C)[0]
        s.base=struct.unpack_from('<Q',b,pe+0x30)[0]
        n=struct.unpack_from('<H',b,pe+6)[0]; opt=struct.unpack_from('<H',b,pe+0x14)[0]
        s.secs=[]
        for i in range(n):
            o=pe+0x18+opt+i*40
            nm=b[o:o+8].rstrip(b'\0').decode('latin1')
            vs,va,rs,rp=struct.unpack_from('<IIII',b,o+8)
            s.secs.append((nm,va,vs,rp,rs))
    def sec(s,rva):
        for x in s.secs:
            if x[1] <= rva < x[1]+max(x[2],x[4]): return x
        return None
    def read(s,rva,n):
        x=s.sec(rva)
        if not x: return None
        return s.buf[x[3]+(rva-x[1]) : x[3]+(rva-x[1])+n]
    def secname(s,rva):
        x=s.sec(rva); return x[0] if x else "?"
    def zero_page(s,rva):
        d=s.read(rva & ~0xFFF, 0x1000)
        return d is None or not any(d)
    def cstr(s,rva,maxn=200):
        d=s.read(rva,maxn)
        if not d: return None
        e=d.find(b'\0')
        if e<0: return None
        try: t=d[:e].decode('ascii')
        except: return None
        return t if t.isprintable() and len(t)>=3 else None
    def wstr(s,rva,maxn=400):
        d=s.read(rva,maxn)
        if not d: return None
        out=[]
        for i in range(0,len(d)-1,2):
            c=d[i]|(d[i+1]<<8)
            if c==0: break
            if c>0x7e or c<0x20: return None
            out.append(chr(c))
        t="".join(out)
        return t if len(t)>=3 else None

md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail=True

TERM = {'ret','jmp','int3','ud2'}
CC = {'je','jne','jz','jnz','ja','jae','jb','jbe','jg','jge','jl','jle','js','jns','jo','jno','jp','jnp','jcxz','jecxz','jrcxz'}

def annot(img, ins):
    """rip-relative data annotation"""
    notes=[]
    for op in ins.operands:
        if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
            tgt = ins.address + ins.size + op.mem.disp - img.base
            sec = img.secname(tgt)
            s = img.cstr(tgt) or img.wstr(tgt)
            extra = f' "{s}"' if s else ''
            if not s and sec in ('.rdata','.data'):
                q = img.read(tgt,8)
                if q and len(q)==8:
                    v=struct.unpack('<Q',q)[0]
                    if img.base <= v < img.base+len(img.buf):
                        t2=v-img.base
                        s2=img.cstr(t2) or img.wstr(t2)
                        extra=f' -> [0x{t2:07X}]' + (f' "{s2}"' if s2 else '')
            notes.append(f"; {sec}:0x{tgt:07X}{extra}")
    return "  ".join(notes)

def disasm_range(img, lo, hi):
    out={}
    data=img.read(lo, hi-lo)
    if data is None: return out
    for ins in md.disasm(data, img.base+lo):
        out[ins.address-img.base]=ins
    return out

def brtgt(ins, base):
    if ins.operands and ins.operands[0].type==X86_OP_IMM:
        return ins.operands[0].imm - base
    return None

def walk(img, start, force_nt=(), force_t=(), stop=(), limit=4000, quiet=False):
    """Recursive descent. force_nt = branch RVAs assumed NOT taken (fallthrough only).
       force_t = branch RVAs assumed TAKEN. Returns (ordered_blocks, calls)."""
    seen=set(); blocks=[]; calls=[]; work=[start]; order=[]
    while work:
        p=work.pop(0)
        if p in seen: continue
        block=[]
        while True:
            if p in seen: break
            if p in stop: break
            seen.add(p)
            d=img.read(p,16)
            if d is None or not any(d):
                block.append((p,None,"<<UNMAPPED/ZERO PAGE>>")); break
            ins=next(md.disasm(d, img.base+p), None)
            if ins is None:
                block.append((p,None,"<<UNDECODABLE>>")); break
            block.append((p,ins,None))
            m=ins.mnemonic
            if m=='call':
                t=brtgt(ins,img.base)
                calls.append((p,t,ins))
                p=p+ins.size; continue
            if m in CC:
                t=brtgt(ins,img.base)
                if p in force_nt:
                    p=p+ins.size; continue
                if p in force_t:
                    if t is not None: p=t; continue
                    break
                if t is not None: work.append(t)
                p=p+ins.size; continue
            if m=='jmp':
                t=brtgt(ins,img.base)
                if t is not None and img.sec(t): work.append(t)
                break
            if m in ('ret','int3','ud2'): break
            p=p+ins.size
        if block: blocks.append(block)
    return blocks, calls

def fold_name(rva):
    return FOLD.get(rva)

def render(img, blocks, show_annot=True):
    lines=[]
    for b in blocks:
        lines.append("")
        for p,ins,err in b:
            if err: lines.append(f"  0x{p:08X}  {err}"); continue
            a = annot(img,ins) if show_annot else ""
            extra=""
            if ins.mnemonic=='call':
                t=brtgt(ins,img.base)
                if t is not None:
                    f=fold_name(t)
                    extra = f"   <== {f}" if f else ""
            lines.append(f"  0x{p:08X}  {ins.bytes.hex():<22} {ins.mnemonic:<7} {ins.op_str:<44} {a}{extra}")
    return "\n".join(lines)

if __name__=="__main__":
    a=sys.argv[1:]
    dump="merged4"
    if "--dump" in a:
        i=a.index("--dump"); dump=a[i+1]; del a[i:i+2]
    nt=[]; tk=[]; stop=[]
    while "--nt" in a:
        i=a.index("--nt"); nt.append(int(a[i+1],0)); del a[i:i+2]
    while "--t" in a:
        i=a.index("--t"); tk.append(int(a[i+1],0)); del a[i:i+2]
    while "--stop" in a:
        i=a.index("--stop"); stop.append(int(a[i+1],0)); del a[i:i+2]
    img=Img(DUMPS.get(dump,dump))
    cmd=a[0]
    if cmd=="fn":
        lo=int(a[1],0); hi=int(a[2],0)
        d=disasm_range(img,lo,hi)
        for r in sorted(d):
            ins=d[r]
            ann=annot(img,ins)
            ex=""
            if ins.mnemonic=='call':
                t=brtgt(ins,img.base)
                if t is not None and fold_name(t): ex=f"   <== {fold_name(t)}"
            print(f"  0x{r:08X}  {ins.bytes.hex():<22} {ins.mnemonic:<7} {ins.op_str:<44} {ann}{ex}")
    elif cmd=="path":
        st=int(a[1],0)
        blocks,calls=walk(img,st,force_nt=set(nt),force_t=set(tk),stop=set(stop))
        print(render(img,blocks))
        print("\n=== CALLS ON PATH ===")
        seenc=set()
        for site,t,ins in calls:
            key=(site,t)
            if key in seenc: continue
            seenc.add(key)
            if t is None:
                print(f"  0x{site:08X}  INDIRECT  {ins.op_str}")
            else:
                f=fold_name(t)
                z=img.zero_page(t)
                print(f"  0x{site:08X}  -> 0x{t:08X}  {'ZEROPAGE' if z else 'present'}  {f or ''}")
    elif cmd=="cov":
        lo=int(a[1],0); n=int(a[2],0) if len(a)>2 else 0x1000
        p=lo & ~0xFFF
        while p < lo+n:
            print(f"  page 0x{p:08X} {'ZERO' if img.zero_page(p) else 'present'}")
            p+=0x1000
