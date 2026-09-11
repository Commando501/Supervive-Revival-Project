import sys, struct, json, capstone, subprocess
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
from capstone.x86 import X86_OP_MEM, X86_OP_REG
data=load(); IB,secs=pehdr(data)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def u64(a): return struct.unpack_from('<Q',data,a)[0]
AC=0x08010428
ac=[u64(AC+i*8)-IB for i in range(289)]
def similarity(vt):
    same=0
    for i in range(289):
        v=u64(vt+i*8)
        if IB<v<IB+0xB000000 and (v-IB)==ac[i]: same+=1
    return same/289.0
# calibration
CAL={'AController':0x08010428,'AAIController':0x08431398,'APlayerController':0x081A82F8,
     'ALokiBotController':0x088CDE18,'ALokiPlayerController':0x08A1AEE0,
     'UNavigationSystemV1':0x0840FDC0,'ALokiAirship':0x08879678,'ULokiAttributeSet':0x08896900,
     'ALokiBaseItem':0x088AF890,'ALokiControlPoint':0x0890E420}
print("CALIBRATION of 'is AController-derived' test (fraction of AController's 289 slots shared):")
for n,v in CAL.items(): print("   %-24s %.3f"%(n,similarity(v)))
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
print("\nSCANNING %d distinct functions that WRITE [reg+0x488] for an installed AController-derived vtable:"%len(fns))
flag=[]
for f in fns:
    for vt in vt_install(f):
        if 0x7649000 < vt < 0x99C7000:   # .rdata
            s=similarity(vt)
            if s>0.5: flag.append((f,vt,s))
if flag:
    for f,vt,s in flag: print("   !! fn 0x%X installs vtable 0x%X similarity %.3f"%(f,vt,s))
else:
    print("   NONE -- no writer function is a constructor of an AController-derived class")
