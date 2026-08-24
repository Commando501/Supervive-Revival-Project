from vimg import VImg
from vcfg import G
im=VImg(); g=G(im,0x035EC850)
D=g.doms()
# true loop back-edges: s->d where d dominates s
loopback=[(s,d) for s in g.succ for d in g.succ[s] if d in D.get(s,()) ]
addrback=[(s,d) for s in g.succ for d in g.succ[s] if d<=s]
print(f"ADDRESS-backward edges (d<=s): {len(addrback)}")
print(f"LOOP back-edges (d dominates s): {len(loopback)} -> {[(hex(s),hex(d)) for s,d in loopback]}")
print()
for tgt,nm in [(0x035ECA2C,'first Velocity write'),(0x035ECCEF,'gravity NewFallVelocity call'),
               (0x035ED9BB,'clamp write X,Y'),(0x035ED9C3,'clamp write Z')]:
    R=g.back(tgt)
    exits=[]
    for s in sorted(R):
        for d in sorted(g.succ.get(s,())):
            if d not in R: exits.append((s,d))
    bwexit=[(s,d) for s,d in exits if d<=s]
    dead=[s for s in R if s!=tgt and not g.succ.get(s) and g.I[s].mnemonic not in ('ret','retf')]
    print(f"{nm:32s} |R|={len(R):5d} exits={len(exits):3d} backward-exits={len(bwexit)} dead-ends={len(dead)}")
R=g.back(0x035ECCEF)
exits=sorted({(s,d) for s in R for d in g.succ.get(s,()) if d not in R})
print("\nEXIT EDGES for gravity site:")
for s,d in exits: print("   ",g.txt(s),"  ->",hex(d))
