# Independent store enumeration: memory WRITES whose base register holds 'this'.
# Do NOT trust capstone's operand access flags alone -- audit them.
import capstone
from capstone import CS_AC_WRITE, CS_AC_READ
from capstone.x86 import *
from vimg import VImg
from vcfg import VCFG, CS
from vthis import analyse, GPRS, parent

im=VImg(); g=VCFG(im,0x035E9EC0)
entry={r:None for r in GPRS}; entry['rcx']=('this',0); entry['rsp']=('frame',0)
IN,OUT=analyse(g,entry)

# ---- AUDIT capstone access flags on first-operand-is-memory instructions ----
from collections import Counter, defaultdict
aud=defaultdict(Counter)
for a,ins in sorted(g.insns.items()):
    ops=ins.operands
    if ops and ops[0].type==X86_OP_MEM:
        aud[ins.mnemonic][ops[0].access]+=1
print("=== capstone access-flag audit: first operand is MEMORY ===")
for mn in sorted(aud):
    print("  %-10s %s" % (mn, dict(aud[mn])))
print("  (0x1=READ 0x2=WRITE 0x3=RW)")

# ---- classify stores by SEMANTICS, not by capstone flags ----
# Instructions where operand0 memory is written:
WRITE_MNEMS_O0 = set("""mov movabs movaps movups movsd movss movdqa movdqu movd movq movnti movntps movntdq
 movlps movhps movlpd movhpd movsldup stosb stosd stosq
 add sub and or xor adc sbb inc dec neg not shl shr sar rol ror rcl rcr
 cmpxchg xchg xadd bts btr btc setne sete setg setl setge setle seta setb setae setbe sets setns
 setp setnp seto setno cmovne""".split())
READ_ONLY_O0 = set("cmp test ucomiss ucomisd comiss comisd push jmp call bt".split())

rows=[]
for a,ins in sorted(g.insns.items()):
    ops=ins.operands
    if not ops or ops[0].type!=X86_OP_MEM: continue
    mn=ins.mnemonic
    if mn in READ_ONLY_O0: continue
    if mn not in WRITE_MNEMS_O0:
        print("  ?? unclassified mnemonic with mem operand0: 0x%x %s %s"%(a,mn,ins.op_str))
        continue
    mem=ops[0].mem
    if mem.base==0 or mem.index!=0: continue
    bn=parent(CS.reg_name(mem.base))
    st=IN.get(a) or {}
    v=st.get(bn)
    if v is None or v[0]!='this': continue
    off=v[1]+mem.disp
    rows.append((a,off,ops[0].size,mn,ins.op_str,ops[0].access))
print("\n=== 'this'-based stores: %d ===" % len(rows))
for a,off,sz,mn,ops_,acc in rows:
    print("  0x%08x  +0x%-5X w=%-3d acc=0x%x  %s %s" % (a,off,sz,acc,mn,ops_))
