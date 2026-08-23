from cfg import *
E=0x03603780
seen,succ=build(E,0x8000)
print("nodes:",len(succ))
print("rets:",["0x%08X"%a for a in succ if seen[a] and seen[a].mnemonic=='ret'])
CCM=0x03603B18
print("0x%08X = %s"%(CCM,(seen.get(CCM).mnemonic+" "+seen.get(CCM).op_str) if seen.get(CCM) else "NOT A BOUNDARY"))
CR=back(succ,CCM)
print("nodes that can reach ControlledCharacterMove:",len(CR))
print("--- bail edges before ControlledCharacterMove ---")
for a,ss in sorted(succ.items()):
    if a not in CR: continue
    for t in ss:
        if t not in CR and a!=CCM:
            print("  0x%08X %-38s -> 0x%08X"%(a,seen[a].mnemonic+" "+seen[a].op_str,t))
# find the dt register
print("--- first 30 insns ---")
for a in sorted(succ)[:0]:
    pass
import itertools
for i in md.disasm(DATA[E:E+0x140],E):
    print("  0x%08X %-40s"%(i.address,i.mnemonic+" "+i.op_str))
