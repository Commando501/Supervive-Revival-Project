exec(open(r"scratchpad/s140/syn/adj3.py").read().split("for E,name in")[0])
import capstone as cs
print("=== ENGINE PM tail stores (rungs) ===")
for a in (0x035E9F82,0x035EA009,0x035EB130,0x035EB77D,0x035EB78D,0x035EB798,0x035EB7A2,0x035EB7AF,0x035EB7BB,0x035EB7C2):
    for ad,b,t in dis(a,1): print("   %#010x %-26s %s"%(ad,b,t))
print("\n=== LOKI PM receipt +0x16D0 ===")
for ad,b,t in dis(0x055B88B0,16): print("   %#010x %-26s %s"%(ad,b,t))
print("\n=== post-dominance of tail stores over 0x35EB1CB ===")
ins,su,ca,ij,rt,fa=cfg(0x035E9EC0)
def postdom(node,start):
    # node post-dominates start iff every path start->ret passes node
    return 0x035EB1CA not in reach(su,start,ban=node)
for s in (0x035EB520,0x035EB52D,0x035EB536,0x035EB77D,0x035EB78D,0x035EB798,0x035EB7A2,0x035EB7AF,0x035EB7BB,0x035EB7C2,0x035EB569):
    print("   %#010x postdom(0x35EB1CB)=%s postdom(0x35EB140)=%s"%(s,postdom(s,0x035EB1CB),postdom(s,0x035EB140)))
print("\n=== TimeSinceFallingStart UHT record ===")
nm=b"TimeSinceFallingStart\x00"
rs,re_=0x0764a000,0x0764a000+0x237d000
occ=[]; i=D.find(nm,rs,re_)
while i!=-1: occ.append(i); i=D.find(nm,i+1,re_)
print("  ascii occurrences in .rdata:",[hex(x) for x in occ])
for o in occ:
    pv=(o+IB).to_bytes(8,'little')
    ptrs=[]; j=D.find(pv,rs,re_)
    while j!=-1:
        if j%8==0: ptrs.append(j)
        j=D.find(pv,j+1,re_)
    print("  ptrs to it:",[hex(x) for x in ptrs])
    for p in ptrs:
        print("   record @%#010x bytes: %s"%(p,D[p:p+0x40].hex()))
        print("     Offset field guesses: +0x34=%#x  +0x38=%#x"%(struct.unpack_from('<I',D,p+0x34)[0],struct.unpack_from('<I',D,p+0x38)[0]))
