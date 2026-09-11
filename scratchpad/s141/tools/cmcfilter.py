"""L5 HALF A step 3: filter validated +0xE8/F0/F8 stores down to plausible CMC targets."""
import sys, json, bisect, csv
sys.path.insert(0,'.')
from peimg import Img
import capstone as cs
from collections import defaultdict, Counter

IMG=r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im=Img(IMG); IB=im.imagebase
TX=[s for s in im.sections if s['name']=='.text'][0]
tlo=TX['va']; praw=TX['praw']; data=im.data
md=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_64); md.detail=True

vt=json.load(open('cmc_vtables.json'))
VTSET = set(vt['loki']) | set(vt['eng'])
print(f"[SET] CMC vtable target functions (loki+eng, union): {len(VTSET)}")

# distinctive CMC field offsets (NOT generic ones like 0xC0/0x150)
CMC_SIG = {0x328:'Acceleration',0x231:'MovementMode',0x12B0:'TimeSinceFallingStart',
           0x16B0:'VelSnapshot',0x16C8:'VelSnapFlag',0x290:'MinAnalogWalkSpeed',
           0x3E0:'MaxSimTimeStep',0x3E4:'MaxSimIterations',0x1F0:'GravQuatA',0x210:'GravQuatB'}
CHARMOVE_OFF = 0x458   # ACharacter::CharacterMovement  [M]
GETLOKICMC   = 0x55AC8E0

hits=json.load(open('storehits_valid.json'))
byfn=defaultdict(list)
for h in hits:
    byfn[h.get('fn')].append(h)

def insns(fb, fe):
    b=data[praw+(fb-tlo):praw+(fe-tlo)]
    return list(md.disasm(b, fb))

fninfo={}
for fb in byfn:
    if fb is None: continue
    fe = max(h['fnend'] for h in byfn[fb])
    ins = insns(fb, fe)
    sig=set(); loads458=False; callcmc=False
    for i in ins:
        for o in i.operands:
            if o.type==cs.x86.X86_OP_MEM and o.mem.base not in (0,cs.x86.X86_REG_RIP):
                d=o.mem.disp
                if d in CMC_SIG: sig.add(d)
                if d==CHARMOVE_OFF and i.mnemonic=='mov': loads458=True
        if i.mnemonic=='call' and i.operands and i.operands[0].type==cs.x86.X86_OP_IMM:
            if i.operands[0].imm==GETLOKICMC: callcmc=True
    fninfo[fb]=dict(sig=sig, loads458=loads458, callcmc=callcmc, onvt=(fb in VTSET), n=len(ins))

survivors=[]
for fb, hs in byfn.items():
    if fb is None: continue
    fi=fninfo[fb]
    reasons=[]
    if fi['onvt']: reasons.append('CMC-VTABLE')
    if fi['sig']:  reasons.append('CMCSIG:'+','.join(CMC_SIG[d] for d in sorted(fi['sig'])))
    if fi['loads458']: reasons.append('LOADS-ACharacter+0x458')
    if fi['callcmc']: reasons.append('CALLS-GetLokiCharacterMovement')
    if reasons:
        survivors.append((fb, fi, hs, reasons))

nohit_fn = sum(1 for h in hits if h.get('fn') is None)
print(f"[IN ] validated stores {len(hits)} across {len(byfn)-(1 if None in byfn else 0)} pdata functions (+{nohit_fn} with no pdata row)")
nsurv_st = sum(len(h) for _,_,h,_ in survivors)
print(f"[OUT] survivors: {len(survivors)} functions, {nsurv_st} store instructions")
survivors.sort(key=lambda x:x[0])
json.dump([[fb, sorted(fi['sig']), fi['onvt'], fi['loads458'], fi['callcmc'],
            [dict(rva=h['rva'],disp=h['disp'],mnem=h['mnem'],op=h['op'],base=h['base']) for h in hs], r]
           for fb,fi,hs,r in survivors], open('cmc_survivors.json','w'))
for fb,fi,hs,r in survivors:
    print(f"\nFN {fb:#09x}  insns={fi['n']}  [{'; '.join(r)}]")
    for h in sorted(hs,key=lambda x:x['rva']):
        print(f"    {h['rva']:#09x}  {h['mnem']:8s} {h['op']:34s}  disp={h['disp']:#x} base={h['base']}")
