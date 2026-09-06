from cfg import *
E=0x035E9EC0; CALL=0x035EB13A
seen,succ=build(E)
print("CFG nodes:",len(succ))
rets=[a for a in succ if seen[a] and seen[a].mnemonic=='ret']
print("rets:",["0x%08X"%a for a in rets])
CR=back(succ,CALL)
print("nodes that can reach the SNP call:",len(CR))
print("--- TRUE BAIL EDGES (leave the can-reach set) ---")
out=[]
for a,ss in sorted(succ.items()):
    if a not in CR: continue
    for t in ss:
        if t not in CR:
            out.append((a,t))
for a,t in out:
    print("  0x%08X %-38s -> 0x%08X"%(a,seen[a].mnemonic+" "+seen[a].op_str,t))
print("count:",len(out))
print("--- the two xmm11 comparisons ---")
for a in (0x035EA3E4,0x035EB043):
    i=seen.get(a); print("  0x%08X %s   in-canreach=%s"%(a,i.mnemonic+" "+i.op_str,a in CR))
for a in (0x035EA494,0x035EB112):
    print("  target 0x%08X can reach SNP: %s"%(a, a in CR))
