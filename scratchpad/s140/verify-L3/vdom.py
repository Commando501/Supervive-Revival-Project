import capstone
from capstone.x86 import *
from vimg import VImg
from vcfg import VCFG, CS
from vthis import analyse, GPRS, parent
im=VImg(); g=VCFG(im,0x035E9EC0)
entry={r:None for r in GPRS}; entry['rcx']=('this',0); entry['rsp']=('frame',0)
IN,OUT=analyse(g,entry)
CALL=0x035EB13A
dom=g.dominators()
pdom,exits=g.postdominators()
print("nodes=%d  |dom(call)|=%d" % (len(g.insns), len(dom[CALL])))
R=g.reach_backward(CALL)
print("|reach_backward(call)| = %d" % len(R))
print("exits =", [hex(e) for e in sorted(exits)])

# recompute store list (same code as vstores)
WRITE_MNEMS_O0 = set("""mov movabs movaps movups movsd movss movdqa movdqu movd movq movnti movntps movntdq
 movlps movhps movlpd movhpd add sub and or xor adc sbb inc dec neg not shl shr sar rol ror
 cmpxchg xchg xadd bts btr btc""".split())
READ_ONLY_O0=set("cmp test ucomiss ucomisd comiss comisd push jmp call bt".split())
stores=[]
for a,ins in sorted(g.insns.items()):
    ops=ins.operands
    if not ops or ops[0].type!=X86_OP_MEM: continue
    if ins.mnemonic in READ_ONLY_O0 or ins.mnemonic not in WRITE_MNEMS_O0: continue
    mem=ops[0].mem
    if mem.base==0 or mem.index!=0: continue
    bn=parent(CS.reg_name(mem.base)); v=(IN.get(a) or {}).get(bn)
    if v is None or v[0]!='this': continue
    stores.append((a, v[1]+mem.disp, ops[0].size, ins))

print("\n=== stores that DOMINATE the StartNewPhysics call ===")
domcall=dom[CALL]
for a,off,sz,ins in stores:
    if a in domcall:
        print("  0x%08x +0x%-5X w=%-3d %s %s" % (a,off,sz,ins.mnemonic,ins.op_str))
print("\n=== stores in reach_backward(call) but NOT dominating (pre-call, conditional) ===")
n=0
for a,off,sz,ins in stores:
    if a in R and a not in domcall:
        n+=1
print("  count =", n)
print("\n=== stores NOT in reach_backward(call): post-call or bail ===")
for a,off,sz,ins in stores:
    if a not in R:
        pc = "POSTDOM(0x35EB1CB)" if a in pdom.get(0x035EB1CB,set()) else ""
        pcf = "POSTDOM(callfall 0x35EB140)" if a in pdom.get(0x035EB140,set()) else ""
        print("  0x%08x +0x%-5X w=%-3d %-42s %s %s" % (a,off,sz,"%s %s"%(ins.mnemonic,ins.op_str),pc,pcf))
