import sys, struct, json, capstone
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
from capstone.x86 import X86_OP_MEM, X86_OP_REG
data=load(); IB,secs=pehdr(data)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def u64(a): return struct.unpack_from('<Q',data,a)[0]
AC=0x08010428
ac=[u64(AC+i*8)-IB for i in range(289)]
LO,HI=247,289          # AController-specific slot band (AActor ends ~247)
def score(vt, nslots_guess=289):
    same=0; tot=0
    for i in range(LO,HI):
        v=u64(vt+i*8)
        if not (IB<v<IB+0xB000000): continue
        tot+=1
        if (v-IB)==ac[i]: same+=1
    return same/max(tot,1), tot
CAL={'AController':0x08010428,'AAIController':0x08431398,'APlayerController':0x081A82F8,
     'ALokiBotController':0x088CDE18,'ALokiPlayerController':0x08A1AEE0,'ALokiAIController':0x08878580,
     'ALokiMinionAIController':0x089F8078,
     'UNavigationSystemV1':0x0840FDC0,'ALokiAirship':0x08879678,'ULokiAttributeSet':0x08896900,
     'ALokiBaseItem':0x088AF890,'ALokiControlPoint':0x0890E420,'ANiagaraActor':0x08301FF8,
     'ACineCameraActor':0x07D7C680}
print("CALIBRATION: fraction of AController-specific slots [%d,%d) matching AController"%(LO,HI))
for n,v in sorted(CAL.items(), key=lambda kv:-score(kv[1])[0]):
    s,t=score(v); print("   %-26s %.3f (n=%d)  %s"%(n,s,t,'<= AController-derived' if s>0.5 else ''))
def vt_install(b,n=0x140):
    ins=list(md.disasm(data[b:b+n], b)); pend={}; out=[]
    for z in ins:
        if z.mnemonic=='lea' and z.operands[0].type==X86_OP_REG and z.operands[1].mem.base==capstone.x86.X86_REG_RIP:
            pend[z.reg_name(z.operands[0].reg)]=z.address+z.size+z.operands[1].mem.disp
        elif z.mnemonic=='mov' and z.operands[0].type==X86_OP_MEM and z.operands[0].mem.disp==0 and z.operands[1].type==X86_OP_REG:
            r=z.reg_name(z.operands[1].reg)
            if r in pend: out.append(pend[r])
    return out
W=json.load(open('scratchpad/lanev5/writes_nonstack.json'))
fns=sorted(set(x['fn_b'] for x in W if x['fn_b']))
print("\n%d distinct functions WRITE [reg+0x488]. Which are ctors of an AController-derived class?"%len(fns))
flag=[]
for f in fns:
    for vt in vt_install(f):
        if 0x7649000 < vt < 0x99C7000:
            s,t=score(vt)
            if s>0.5 and t>20: flag.append((f,vt,s))
for f,vt,s in flag:
    ws=[x for x in W if x['fn_b']==f]
    print("   fn 0x%08X installs vtable 0x%08X  AController-score %.3f"%(f,vt,s))
    for x in ws: print("        WRITE 0x%08X %-30s %s %s"%(x['rva'],x['bytes'],x['mnem'],x['ops']))
print("   total AController-derived ctor writers: %d"%len(flag))
