"""L5 HALF A (v2, SOUND): prefilter by disp bytes -> fully decode the containing pdata
function -> collect only instructions on real boundaries whose operands[0] is MEM with
disp in {0xE8,0xF0,0xF8}.  Writes classified from operands[0].type==MEM, NEVER regs_access."""
import sys, struct, json, csv, bisect
sys.path.insert(0,'.')
from peimg import Img
import capstone as cs
from collections import Counter, defaultdict

IMG=r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im=Img(IMG)
TX=[s for s in im.sections if s['name']=='.text'][0]
tlo=TX['va']; thi=TX['va']+TX['vsz']; praw=TX['praw']; data=im.data
md=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_64); md.detail=True

NP=(thi-tlo)//0x1000
lit=bytearray(NP)
for p in range(NP):
    o=praw+p*0x1000
    if any(data[o:o+0x1000]): lit[p]=1
print(f"[DENOM] .text pages {NP}, decrypted {sum(lit)} = {100*sum(lit)/NP:.2f}%  (all counts below are FLOORS over this)")

B=[];E=[]
import json as _j; _e=_j.load(open('extents.json')); B=_e['starts']; E=_e['ends']
if 0:
    f=None
    for row in []:
        pass
o=sorted(range(len(B)), key=lambda i:B[i]); B=[B[i] for i in o]; E=[E[i] for i in o]

def fn_of(rva):
    i=bisect.bisect_right(B,rva)-1
    for j in range(i, max(-1,i-8), -1):
        if j<0: break
        if B[j]<=rva<E[j]: return B[j],E[j]
    return None,None

# stage 1: candidate function set
TARGETS={0xE8,0xF0,0xF8}
cand=set(); noderow=0
for dv in TARGETS:
    pat=struct.pack('<i',dv); idx=data.find(pat,praw,praw+TX['vsz'])
    while idx!=-1:
        r=tlo+(idx-praw)
        if lit[(r-tlo)//0x1000]:
            fb,fe=fn_of(r)
            if fb is not None: cand.add((fb,fe))
            else: noderow+=1
        idx=data.find(pat,idx+1,praw+TX['vsz'])
print(f"[STAGE1] candidate pdata functions containing a 'disp32 == 0xE8/F0/F8' byte pattern: {len(cand)}")
print(f"[STAGE1] byte-pattern sites with NO pdata row (invisible to stage 2): {noderow}")

STORE={'mov','movups','movaps','movupd','movapd','movsd','movss','movdqu','movdqa','movq','movd',
       'vmovups','vmovaps','vmovsd','vmovss','vmovdqu','vmovdqa','vmovlpd','vmovhpd','vmovlps','vmovhps','vmovd','vmovq'}
RMW={'add','sub','adc','sbb','or','and','xor','inc','dec','xchg','cmpxchg','not','neg','shl','shr','sar'}

hits=[]; fnmeta={}
for fb,fe in sorted(cand):
    if fe<=fb or fe-fb > 0x30000: fe=min(fe, fb+0x30000)
    buf=data[praw+(fb-tlo):praw+(fe-tlo)]
    framebp=False; sigs=set(); l458=False; ccmc=False; n=0
    loc=[]
    for i in md.disasm(buf, fb):
        n+=1
        if (i.mnemonic=='mov' and i.op_str=='rbp, rsp') or (i.mnemonic=='lea' and i.op_str.startswith('rbp, [rsp')):
            framebp=True
        ops=i.operands
        for op in ops:
            if op.type==cs.x86.X86_OP_MEM and op.mem.base not in (0,cs.x86.X86_REG_RIP):
                d=op.mem.disp; bn=i.reg_name(op.mem.base)
                if bn not in ('rsp','rbp'):
                    if d in (0x12B0,0x16B0,0x16C8,0x328,0x231,0x290,0x3E4,0x3E0): sigs.add(d)
                    if d==0x458 and i.mnemonic=='mov': l458=True
        if i.mnemonic=='call' and ops and ops[0].type==cs.x86.X86_OP_IMM and ops[0].imm==0x55AC8E0: ccmc=True
        if ops and ops[0].type==cs.x86.X86_OP_MEM and ops[0].mem.disp in TARGETS \
           and ops[0].mem.base not in (0,cs.x86.X86_REG_RIP) and ops[0].mem.index==0 \
           and (i.mnemonic in STORE or i.mnemonic in RMW):
            loc.append(dict(rva=i.address, mnem=i.mnemonic, op=i.op_str, disp=ops[0].mem.disp,
                            base=i.reg_name(ops[0].mem.base), rmw=(i.mnemonic in RMW), bytes=i.bytes.hex()))
    if loc:
        fnmeta[fb]=dict(fn=fb,end=fe,n=n,framebp=framebp,sigs=sorted(sigs),l458=l458,ccmc=ccmc)
        for h in loc: h['fn']=fb
        hits.extend(loc)

print(f"[STAGE2] REAL store instructions to [reg+0xE8/F0/F8]: {len(hits)}  in {len(fnmeta)} functions")
print("  by disp:", Counter(hex(h['disp']) for h in hits))
print("  by mnemonic:", Counter(h['mnem'] for h in hits).most_common(12))
print("  by base reg:", Counter(h['base'] for h in hits).most_common())
json.dump({'hits':hits,'fns':fnmeta}, open('stores_v3.json','w'))
for t in (0x035D6520,0x035D6527,0x035D668E,0x035ED9BB,0x035ED9C3):
    print(f"  self-check {t:#x} present: {any(h['rva']==t for h in hits)}")
