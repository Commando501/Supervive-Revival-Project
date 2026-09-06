import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
from capstone.x86 import *
I=VImg('dumps/merged14.dump.exe')
ins,succ,und,ind=cfg(I,0x035EC850)
# ALL memory writes, classified from operands[0].type==MEM (never regs_access)
byreg={}
for a in sorted(ins):
    o=mem_writes(ins[a])
    if o is None: continue
    base=ins[a].reg_name(o.mem.base) if o.mem.base else None
    idx =ins[a].reg_name(o.mem.index) if o.mem.index else None
    byreg.setdefault((base,idx),[]).append((a,o.mem.disp,o.size,ins[a].mnemonic))
print("ALL memory writes in engine PhysFalling, grouped by base register:")
tot=0
for k in sorted(byreg,key=lambda x:(str(x[0]),str(x[1]))):
    v=byreg[k]; tot+=len(v)
    print("   base=%-6s idx=%-6s : %3d writes  disps=%s" % (k[0],k[1],len(v),
        sorted({hex(d) for _,d,_,_ in v})[:14]))
print("   TOTAL memory writes:", tot)
print()
rsi=[x for x in byreg.get(('rsi',None),[])]
print("writes via rsi (L2's scan): %d ; disps in 0..0x18: %d" % (len(rsi),len([x for x in rsi if 0<=x[1]<=0x18])))
for a,d,s,m in rsi: print("     %08x %-8s [rsi+0x%x] size %d" % (a,m,d,s))
print()
# Could Velocity be written via rdi+0xe8 (the same address, different base)?
rdi=[x for x in byreg.get(('rdi',None),[])]
print("writes via rdi: %d ; any with disp in [0xe8,0x100)? %s" % (len(rdi),
      [(hex(a),hex(d),s) for a,d,s,m in rdi if 0xe8<=d<0x100]))
print("   all rdi write disps:", sorted({hex(d) for _,d,_,_ in rdi}))
