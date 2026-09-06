"""Base-register provenance for every instruction touching byte +0x16C8.
Method: locate the outermost pdata function whose recursive-descent CFG contains the site,
then walk the instruction-graph predecessors to the reaching definitions of the base register."""
import sys, bisect, csv, json, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X86=capstone.x86
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img()

begins=[]; rows=[]
with open(r"G:/git/Supervive Revival Project/tools/strxref/index/pdata_union.csv") as f:
    r=csv.reader(f); next(r)
    for a,b,sz,u,seen in r: rows.append((int(a,16),int(b,16),int(sz),int(seen)))
rows.sort(); begins=[x[0] for x in rows]

SUB={'rax':'rax','eax':'rax','ax':'rax','al':'rax','ah':'rax',
     'rbx':'rbx','ebx':'rbx','bx':'rbx','bl':'rbx',
     'rcx':'rcx','ecx':'rcx','cx':'rcx','cl':'rcx',
     'rdx':'rdx','edx':'rdx','dx':'rdx','dl':'rdx',
     'rsi':'rsi','esi':'rsi','si':'rsi','sil':'rsi',
     'rdi':'rdi','edi':'rdi','di':'rdi','dil':'rdi',
     'rbp':'rbp','ebp':'rbp','bp':'rbp','bpl':'rbp',
     'rsp':'rsp','esp':'rsp',
     **{f'r{n}{s}':f'r{n}' for n in range(8,16) for s in ('','d','w','b')}}

def canon(n): return SUB.get(n,n)

def find_fn(site, window=0x20000):
    i=bisect.bisect_right(begins,site)-1
    out=[]
    while i>=0 and site-begins[i] <= window:
        b,e,sz,seen=rows[i]
        if b<=site<e or True:
            try:
                c=CFG(im,b,maxinsn=300000)
                if site in c.insns: out.append((b,e,seen,c))
            except Exception: pass
        i-=1
    return out

def reaching_defs(c, site, reg):
    reg=canon(reg); found=[]; seen=set(); st=list(c.pred.get(site,()))
    while st:
        n=st.pop()
        if n in seen: continue
        seen.add(n)
        i=c.insns.get(n)
        if i is None: continue
        try: rd,wr=i.regs_access()
        except Exception: rd,wr=(),()
        if any(canon(i.reg_name(x))==reg for x in wr):
            found.append(n); continue
        st.extend(c.pred.get(n,()))
    return found

hits=json.load(open('L6/hits.json'))
sites=sorted(int(k,16) for k in hits)
# add the 6 fallback-resolved sites
sites += [0x530abf9,0x530ac10,0x530c7ff,0x055C2438,0x055C2441,0x055C2469]
sites=sorted(set(sites))
print(f"{len(sites)} instructions touching byte +0x16C8\n")

results=[]
for s in sites:
    fns=find_fn(s)
    if not fns:
        print(f"{s:#010x}  *** no pdata fn contains it ***"); results.append((s,None,None,None)); continue
    b,e,seen,c=fns[-1]   # outermost
    i=c.insns[s]
    base=None
    for op in i.operands:
        if op.type==X86.X86_OP_MEM and op.mem.disp==0x16C8:
            base=i.reg_name(op.mem.base) if op.mem.base else None
    if base is None:
        print(f"{s:#010x}  fn {b:#x}  IMM form: {i.mnemonic} {i.op_str}"); results.append((s,b,'IMM',None)); continue
    defs=reaching_defs(c,s,base)
    dtxt=[c.txt(d).split('  ',1)[1] for d in defs] if defs else ['<ENTRY: register live-in>']
    print(f"{s:#010x}  fn {b:#010x}(seen={seen})  {i.mnemonic} {i.op_str}")
    for d,t in zip(defs or [None],dtxt):
        print(f"              base {base} <- {'%#x  '%d if d else '            '}{t}")
    results.append((s,b,base,dtxt))
json.dump([(hex(s),(hex(b) if b else None),base,d) for s,b,base,d in results], open('L6/prov.json','w'), indent=1)
