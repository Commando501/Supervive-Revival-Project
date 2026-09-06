import sys, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import cfg as CFGMOD, capstone
X=capstone.x86
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
c = CFGMOD.CFG(im, 0x035EC850); ins=c.insns
E=0x035EC850
nodes=sorted(ins)
succ={n:set(c.succ.get(n,())) for n in nodes}
pred={n:set(c.pred.get(n,())) for n in nodes}

def fwd_reach(s, block=None):
    R=set(); st=[s]
    while st:
        n=st.pop()
        if n in R or (block and n in block): continue
        R.add(n)
        for d in succ.get(n,()): 
            if d not in R: st.append(d)
    return R

def bwd_reach(t):
    R=set(); st=[t]
    while st:
        n=st.pop()
        if n in R: continue
        R.add(n)
        for p in pred.get(n,()):
            if p not in R: st.append(p)
    return R

# iterative dominators
def doms():
    D={E:{E}}
    order=[n for n in nodes]
    allN=set(nodes)
    for n in nodes:
        if n!=E: D[n]=allN.copy()
    changed=True
    while changed:
        changed=False
        for n in nodes:
            if n==E: continue
            ps=[p for p in pred.get(n,()) if p in D]
            if not ps: continue
            new=set.intersection(*[D[p] for p in ps]) | {n}
            if new!=D[n]: D[n]=new; changed=True
    return D
D=doms()

COND={'jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'}
def guards(w):
    """conditional branches that DOMINATE w and whose other successor cannot reach w"""
    out=[]
    for d in sorted(D[w]):
        if d==w: continue
        i=ins[d]
        if i.mnemonic not in COND: continue
        for s in sorted(succ[d]):
            if w not in fwd_reach(s):
                taken = (s==i.operands[0].imm)
                out.append((d,i.mnemonic,i.op_str,'taken-branch EXITS' if taken else 'fallthrough EXITS'))
                break
    return out

VEL=[]
for r in nodes:
    i=ins[r]
    if not i.operands: continue
    op=i.operands[0]
    if op.type==X.X86_OP_MEM and op.mem.base:
        bn=i.reg_name(op.mem.base)
        if bn=='rsi' and op.mem.disp in (0,8,0x10): VEL.append((r,'rsi',op.mem.disp,op.size))
        if bn=='rdi' and op.mem.disp in (0xE8,0xF0,0xF8): VEL.append((r,'rdi',op.mem.disp-0xE8,op.size))
comp={0:'X',8:'Y',0x10:'Z'}
print("=== rsi dominance check: does 0x35EC9AC dominate every rsi-based Velocity write? ===")
bad=[r for r,b,d,s in VEL if b=='rsi' and 0x035EC9AC not in D[r]]
print(f"   sites={sum(1 for x in VEL if x[1]=='rsi')}  NOT dominated by the lea: {len(bad)} {[hex(x) for x in bad]}")
print("=== is the rsi REDEF at 0x35EE519 able to reach any rsi write? ===")
fr=fwd_reach(0x035EE519)
reach=[hex(r) for r,b,d,s in VEL if b=='rsi' and r in fr]
print(f"   forward-reachable rsi writes from the redef: {len(reach)} {reach}")

print(f"\n=== Q1: {len(VEL)} VELOCITY WRITE INSTRUCTIONS ===")
print(f"{'rva':<12}{'bytes':<22}{'insn':<40}{'via':<5}{'fields':<8}guards")
for r,b,d,sz in VEL:
    i=ins[r]
    if sz==16: f='X,Y' if d==0 else f'?{d:#x}'
    else: f=comp.get(d,f'?{d:#x}')
    g=guards(r)
    gs='; '.join(f"{hex(x[0])} {x[1]}" for x in g[:4]) or 'NONE (unconditional in fn)'
    print(f"{r:#010x}  {bytes(i.bytes).hex():<22}{i.mnemonic+' '+i.op_str:<40}{b:<5}{f:<8}{len(g)} guards: {gs}")

print("\n=== r13 definitions (value written to [rdi+0xf8] at 3 sites) ===")
for r in nodes:
    i=ins[r]
    try: rd,wr=i.regs_access()
    except Exception: wr=()
    if any(i.reg_name(w) in ('r13','r13d') for w in wr):
        print(f"   {c.txt(r)}")
