"""L5 HALF A step 3 (strict): CMC-plausible +0xE8/F0/F8 stores."""
import sys, json
sys.path.insert(0,'.')
from peimg import Img
import capstone as cs
from collections import defaultdict, Counter

IMG=r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im=Img(IMG)
TX=[s for s in im.sections if s['name']=='.text'][0]
tlo=TX['va']; praw=TX['praw']; data=im.data
md=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_64); md.detail=True

vt=json.load(open('cmc_vtables.json'))
LOKI=set(vt['loki']); ENG=set(vt['eng']); VTSET=LOKI|ENG

# RARE, high-information CMC offsets only.
RARE = {0x12B0:'TimeSinceFallingStart',0x16B0:'VelSnapshot',0x16C8:'VelSnapFlag'}
MED  = {0x328:'Acceleration',0x231:'MovementMode',0x290:'MinAnalogWalkSpeed',0x3E4:'MaxSimIter'}
CHARMOVE_OFF=0x458; GETLOKICMC=0x55AC8E0

hits=json.load(open('storehits_valid.json'))
byfn=defaultdict(list)
for h in hits: byfn[h.get('fn')].append(h)

def insns(fb,fe):
    return list(md.disasm(data[praw+(fb-tlo):praw+(fe-tlo)], fb))

rows=[]
for fb,hs in byfn.items():
    if fb is None: continue
    fe=max(h['fnend'] for h in hs)
    ins=insns(fb,fe)
    rare=set(); med=set(); l458=False; ccmc=False; framebp=False
    for i in ins:
        if i.mnemonic=='mov' and i.op_str=='rbp, rsp': framebp=True
        if i.mnemonic=='lea' and i.op_str.startswith('rbp,'): framebp=True
        for o in i.operands:
            if o.type==cs.x86.X86_OP_MEM and o.mem.base not in (0,cs.x86.X86_REG_RIP):
                d=o.mem.disp
                if d in RARE: rare.add(d)
                if d in MED: med.add(d)
                if d==CHARMOVE_OFF and i.mnemonic=='mov': l458=True
        if i.mnemonic=='call' and i.operands and i.operands[0].type==cs.x86.X86_OP_IMM and i.operands[0].imm==GETLOKICMC:
            ccmc=True
    score=[]
    if fb in LOKI: score.append('LOKI-CMC-VTABLE')
    if fb in ENG:  score.append('ENGINE-CMC-VTABLE')
    if rare: score.append('RARE:'+','.join(RARE[d] for d in sorted(rare)))
    if len(med)>=2: score.append('MED2:'+','.join(MED[d] for d in sorted(med)))
    if l458: score.append('LOADS-Char+0x458')
    if ccmc: score.append('CALLS-GetLokiCMC')
    if not score: continue
    strong = bool(rare) or (fb in VTSET) or l458 or ccmc
    if not strong: continue
    rows.append(dict(fn=fb, n=len(ins), framebp=framebp, why=score,
        stores=[dict(rva=h['rva'],disp=h['disp'],mnem=h['mnem'],op=h['op'],base=h['base']) for h in sorted(hs,key=lambda x:x['rva'])]))

rows.sort(key=lambda r:r['fn'])
tot=sum(len(r['stores']) for r in rows)
print(f"[STRICT] {len(rows)} functions, {tot} store instructions")
json.dump(rows, open('cmc_strict.json','w'))
for r in rows:
    stk = ' (rbp is a FRAME PTR here)' if r['framebp'] else ''
    print(f"\nFN {r['fn']:#09x} insns={r['n']}  [{'; '.join(r['why'])}]{stk}")
    for h in r['stores']:
        note=''
        if h['base'] in ('rbp','rsp') and r['framebp']: note='  <-- STACK, not an object'
        print(f"   {h['rva']:#09x} {h['mnem']:8s} {h['op']:36s} base={h['base']}{note}")
