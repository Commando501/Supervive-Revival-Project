from vimg import VImg
from vcfg import G
im=VImg(); g=G(im,0x035EC850)
D=g.doms()
COND={'jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'}
for tgt,nm in [(0x035ECCEF,'gravity NewFallVelocity CALL'),(0x035ECCFB,'gravity write X,Y'),
               (0x035ECD06,'gravity write Z'),(0x035ED9BB,'clamp write')]:
    R=g.back(tgt)
    dom=[d for d in sorted(D[tgt]) if g.I[d].mnemonic in COND]
    print(f"\n### {nm} {tgt:#x} : {len(dom)} conditional branches DOMINATE it")
    for d in dom:
        others=[s for s in g.succ[d] if s!=d]
        # for each successor, can it still reach tgt?
        info=[]
        for s in sorted(g.succ[d]):
            info.append(f"{s:#x}{'=REACHES' if s in R else '=EXIT'}")
        kind='RECONVERGING' if all(s in R for s in g.succ[d]) else '*** TRUE EXIT ***'
        print(f"   {g.txt(d):58s} succ:{' '.join(info):34s} {kind}")
