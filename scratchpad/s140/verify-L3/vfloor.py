# How big is the FLOOR?  Classify every memory WRITE in engine PerformMovement by base provenance.
import capstone
from capstone.x86 import *
from vimg import VImg
from vcfg import VCFG, CS
from vthis import analyse, GPRS, parent
im=VImg(); g=VCFG(im,0x035E9EC0)
entry={r:None for r in GPRS}; entry['rcx']=('this',0); entry['rsp']=('frame',0)
IN,OUT=analyse(g,entry)
WRITE_MNEMS_O0 = set("""mov movabs movaps movups movsd movss movdqa movdqu movd movq movnti movntps movntdq
 movlps movhps movlpd movhpd add sub and or xor adc sbb inc dec neg not shl shr sar rol ror
 cmpxchg xchg xadd bts btr btc""".split())
READ_ONLY_O0=set("cmp test ucomiss ucomisd comiss comisd push jmp call bt".split())
cats={'this':0,'frame':0,'rip':0,'UNKNOWN':0}
unk=[]
for a,ins in sorted(g.insns.items()):
    ops=ins.operands
    if not ops or ops[0].type!=X86_OP_MEM: continue
    if ins.mnemonic in READ_ONLY_O0 or ins.mnemonic not in WRITE_MNEMS_O0: continue
    mem=ops[0].mem
    if mem.base==0 and mem.index==0:
        cats['rip']+=1; continue
    bn=parent(CS.reg_name(mem.base)) if mem.base else None
    if bn in ('rip',): cats['rip']+=1; continue
    v=(IN.get(a) or {}).get(bn) if bn else None
    if bn=='rsp' or bn=='rbp' or (v and v[0]=='frame'):
        cats['frame']+=1
    elif v and v[0]=='this':
        cats['this']+=1
    else:
        cats['UNKNOWN']+=1; unk.append((a,bn,ins))
print("memory-write classification in engine PerformMovement:")
for k,v in cats.items(): print("   %-8s %d" % (k,v))
print("\nUNKNOWN-base memory writes (the true FLOOR -- any of these COULD be a this-field store):")
for a,bn,ins in unk:
    print("   0x%08x base=%-5s %s %s" % (a,bn,ins.mnemonic,ins.op_str))
