exec(open(r"scratchpad/s140/syn/adj.py").read().split("print(\"\n=== CONTROLS")[0])
import capstone as cs
JCC={'jo','jno','js','jns','je','jz','jne','jnz','jb','jnae','jc','jnb','jae','jnc','jbe','jna','ja','jnbe','jl','jnge','jge','jnl','jle','jng','jg','jnle','jp','jpe','jnp','jpo','jcxz','jecxz','jrcxz','loop','loope','loopne'}
def cfg(entry):
    insns={}; succ={}; work=[entry]; seen=set(); calls=[]; ijmp=[]; rets=[]; fails=0
    while work:
        a=work.pop()
        if a in seen: continue
        seen.add(a)
        blob=D[a:a+16]
        g=list(md.disasm(blob,a))
        if not g:
            fails+=1; continue
        i=g[0]; insns[a]=i; s=[]
        m=i.mnemonic
        if m=='ret' or m.startswith('ret'):
            rets.append(a)
        elif m=='jmp':
            op=i.operands[0]
            if op.type==cs.x86.X86_OP_IMM: s=[op.imm]
            else: ijmp.append(a)
        elif m in JCC:
            op=i.operands[0]
            s=[i.address+i.size]
            if op.type==cs.x86.X86_OP_IMM: s.append(op.imm)
        elif m=='call':
            op=i.operands[0]
            calls.append((a, op.imm if op.type==cs.x86.X86_OP_IMM else None))
            s=[i.address+i.size]
        elif m in ('int3','ud2'):
            pass
        else:
            s=[i.address+i.size]
        succ[a]=s
        for t in s:
            if t not in seen: work.append(t)
    return insns,succ,calls,ijmp,rets,fails
def preds(succ):
    p={}
    for u,vs in succ.items():
        for v in vs: p.setdefault(v,set()).add(u)
    return p
def reach(succ,start,ban=None):
    r=set(); w=[start]
    while w:
        n=w.pop()
        if n in r or n==ban: continue
        r.add(n)
        for t in succ.get(n,[]): 
            if t!=ban: w.append(t)
    return r
def rback(succ,tgt):
    p=preds(succ); r=set(); w=[tgt]
    while w:
        n=w.pop()
        if n in r: continue
        r.add(n)
        for t in p.get(n,()): w.append(t)
    return r

for E,name in [(0x035E9EC0,'ENGINE PerformMovement'),(0x055B8370,'ULokiCMC PerformMovement')]:
    insns,succ,calls,ijmp,rets,fails=cfg(E)
    direct=set(t for _,t in calls if t)
    print("\n=== %s %#x ==="%(name,E))
    print("  insns=%d calls=%d directsites=%d distinct=%d indirect=%d ijmp=%d rets=%s fails=%d"%(
        len(insns),len(calls),sum(1 for _,t in calls if t),len(direct),sum(1 for _,t in calls if not t),len(ijmp),[hex(r) for r in rets],fails))
    lo=min(insns); hi=max(a+insns[a].size for a in insns)
    cov=sum(insns[a].size for a in insns)
    print("  span %#x..%#x = %d bytes, covered %d, gaps %d"%(lo,hi,hi-lo,cov,hi-lo-cov))

# --- engine: exits, dominance ---
insns,succ,calls,ijmp,rets,fails=cfg(0x035E9EC0)
SNP=0x035EB13A; A50=0x035EB569
R=rback(succ,SNP)
print("\n=== ENGINE EXIT SET ===")
print("  |R| =",len(R))
exits=[]
for u in sorted(R):
    if insns[u].mnemonic=='call': continue
    for v in succ.get(u,[]):
        if v not in R and v!=u:
            exits.append((u,v))
for u,v in exits:
    print("  %#010x %-22s -> %#010x  %s"%(u,insns[u].bytes.hex(),v,"FORWARD" if v>u else "BACKWARD"))
print("  total exits =",len(exits))
nosucc=[u for u in R if not succ.get(u)]
print("  nodes in R with no successors:",[hex(x) for x in nosucc])
# backward edges in whole fn
be=[(u,v) for u,vs in succ.items() for v in vs if v<u]
print("  backward edges in whole function:",[(hex(u),hex(v)) for u,v in be])
# dominance by node removal
print("\n=== DOMINANCE (node-removal) ===")
for g in [0x035E9F1F,0x035E9F28,0x035E9F97,0x035E9FA4,0x035E9FBD,0x035EA25D]:
    dom = SNP not in reach(succ,0x035E9EC0,ban=g)
    print("  gate %#010x dominates SNP call: %s"%(g,dom))
print("  SNP dominates A50: ", A50 not in reach(succ,0x035E9EC0,ban=SNP))
print("  A50 dominates SNP: ", SNP not in reach(succ,0x035E9EC0,ban=A50))
print("  A50 in fwd(SNP): ", A50 in reach(succ,SNP))
print("  SNP in fwd(A50): ", SNP in reach(succ,A50))
for b in (0x035EB1A7,0x035EB7CF,0x035EB150):
    print("  A50 reachable from bail %#010x: %s"%(b,A50 in reach(succ,b)))
print("  SNP in a loop (reachable from own succ): ", SNP in reach(succ,0x035EB140))
# post-SNP divergence: which nodes reach A50, and which real edges leave that set
RA=rback(succ,A50)
div=[]
for u in sorted(RA):
    if insns[u].mnemonic=='call': continue
    for v in succ.get(u,[]):
        if v not in RA and v!=u: div.append((u,v))
print("  |reach_backward(A50)| =",len(RA))
print("  edges leaving RA:",[(hex(u),hex(v)) for u,v in div])
# is the ret reachable from SNP-return while avoiding A50?
print("  ret reachable from 0x35EB140 avoiding A50:", 0x035EB1CA in reach(succ,0x035EB140,ban=A50))
print("  ret reachable from 0x35EB150 (post-SNP bail):", 0x035EB1CA in reach(succ,0x035EB150))
print("  A50 reachable from 0x35EB1CB:", A50 in reach(succ,0x035EB1CB))

# --- loki PM: is Super unconditional ---
insns2,succ2,calls2,ijmp2,rets2,f2=cfg(0x055B8370)
SUP=0x055B85C1
R2=rback(succ2,SUP)
ex2=[]
for u in sorted(R2):
    if insns2[u].mnemonic=='call': continue
    for v in succ2.get(u,[]):
        if v not in R2 and v!=u: ex2.append((u,v))
print("\n=== LOKI PM SUPER ===")
print("  |R2|=%d entry in R2=%s exits=%s rets in R2=%s"%(len(R2),0x055B8370 in R2,[(hex(u),hex(v)) for u,v in ex2],[hex(r) for r in rets2 if r in R2]))
print("  Super dominates ret: ", 0x055B88DD not in reach(succ2,0x055B8370,ban=SUP))
