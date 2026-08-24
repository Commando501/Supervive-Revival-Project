import sys
sys.path.insert(0,'.')
import capstone
from capstone import x86
from peimg import Img
from cfg import CFG
im=Img(); c=CFG(im,0x055B8370); ENTRY=0x055B8370; SUPER=0x055B85C1
nodes=sorted(c.insns); idx={n:i for i,n in enumerate(nodes)}; N=len(nodes); ALL=(1<<N)-1
dom={n:(ALL if n!=ENTRY else (1<<idx[ENTRY])) for n in nodes}
ch=True
while ch:
    ch=False
    for n in nodes:
        if n==ENTRY: continue
        ps=[p for p in c.pred.get(n,()) if p in idx]
        acc=ALL
        for p in ps: acc&=dom[p]
        new=(acc|(1<<idx[n])) if ps else (1<<idx[n])
        if new!=dom[n]: dom[n]=new; ch=True
def dominates(a,b): return bool((dom[b]>>idx[a])&1)

RMW={'inc','dec','add','sub','and','or','xor','adc','sbb','neg','not','shl','shr','sar','rol','ror','btr','bts','btc','xadd','cmpxchg','lock'}
def is_store(i):
    if i.mnemonic=='call' or not i.operands: return False
    op0=i.operands[0]
    if op0.type!=x86.X86_OP_MEM: return False
    if op0.access & capstone.CS_AC_WRITE: return True
    m=i.mnemonic
    if m.startswith('mov') and len(i.operands)==2: return True      # movups/movaps/movdqu store form
    if m in RMW: return True
    return False

# CONTROL: the store set must include the two known-good stores AND the capstone-blind movups
print("=== STORE-DETECTOR CONTROLS ===")
must = {0x055b8414:'movss [rsi+0x12b0] (known writer #1)', 0x055b8856:'movups [rsi+0x12f0] (capstone-blind)',
        0x055b85b7:'mov byte [rsi+0x1308],0', 0x055b88cd:'movss [rsi+0x16d0]'}
found=set(a for a in nodes if is_store(c.insns[a]))
for a,d in must.items(): print(f'  {a:#x} {d}: {"FOUND" if a in found else "*** MISSED ***"}')
mustnot={0x055b841c:'movss xmm0,[rsi+0x12e8] (LOAD, must NOT be a store)',0x055b840c:'addss xmm0,[rsi+0x12b0] (reg-dest RMW load)',0x055b8424:'comiss (pure read)'}
for a,d in mustnot.items(): print(f'  {a:#x} {d}: {"*** FALSE POSITIVE ***" if a in found else "correctly excluded"}')
print()

print('=== ALL MEMORY STORES, ULokiCMC::PerformMovement (0x055B8370..0x055B88DE) ===')
for a in nodes:
    i=c.insns[a]
    if not is_store(i): continue
    m=i.operands[0].mem
    base=i.reg_name(m.base) if m.base else None
    if base=='rsp': continue
    ph='PRE ' if a<SUPER else 'POST'
    dm='DOM' if (a<SUPER and dominates(a,SUPER)) else ('   ' if a<SUPER else '---')
    print(f'{ph} {dm} {a:#010x}  {i.mnemonic:8s} {i.op_str:<48s}  base={base} disp={m.disp:#x} size={i.operands[0].size}')
print()
print('(stack [rsp+..] stores suppressed)')
