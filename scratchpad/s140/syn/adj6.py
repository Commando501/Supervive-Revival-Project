exec(open(r"scratchpad/s140/syn/adj3.py").read().split("for E,name in")[0])
import capstone as cs
print("=== CTOR DISPUTE: which vtable does each install? ===")
for f,nm in [(0x0559E180,'containing 0x0559EA48'),(0x0559F580,'containing 0x0559FDF4')]:
    ins,su,ca,ij,rt,fa=cfg(f)
    leas=[]
    for a in sorted(ins):
        i=ins[a]
        if i.mnemonic=='lea':
            for op in i.operands:
                if op.type==cs.x86.X86_OP_MEM and i.reg_name(op.mem.base)=='rip':
                    tgt=a+i.size+op.mem.disp
                    leas.append((a,tgt))
    # find first few rip-leas that are then stored to [reg]
    print("  fn %#010x (%s) insns=%d"%(f,nm,len(ins)))
    for a,t in leas[:6]:
        nxt=[x for x in sorted(ins) if x>a][:2]
        print("     lea @%#010x -> .rdata %#010x   next: %s"%(a,t,[ins[x].mnemonic+' '+ins[x].op_str for x in nxt]))
print("  vt 0x088E5CA8 +0x8C0 ->", hex(q(0x088E5CA8+0x8C0)-IB), " (expect APawn::SpawnDefaultController 0x3bbf3c0)")
print("  vt 0x088E5CA8 +0xC00 ->", hex(q(0x088E5CA8+0xC00)-IB))
print("  vt 0x088F8570 +0x8C0 ->", hex(q(0x088F8570+0x8C0)-IB))

print("\n=== EXIT5 OVERRIDE INVERSION (anchor GetBodyInstance @+0x810, read +0x4C0) ===")
GBI=(0x03C91C60+IB).to_bytes(8,'little')
rs,re_=0x0764a000,0x0764a000+0x237d000
hits=[]; i=D.find(GBI,rs,re_)
while i!=-1:
    if i%8==0: hits.append(i)
    i=D.find(GBI,i+1,re_)
vals={}
for h in hits:
    base=h-0x810
    if base<rs: continue
    v=q(base+0x4C0)-IB
    vals.setdefault(v,0); vals[v]+=1
print("  GetBodyInstance aligned .rdata occurrences:",len(hits))
print("  distinct [vt+0x4C0] values over those:",{hex(k):v for k,v in vals.items()})

print("\n=== engine StartNewPhysics 0x03600990 gates ===")
for ad,b,t in dis(0x03600990,26): print("   %#010x %-26s %s"%(ad,b,t))
