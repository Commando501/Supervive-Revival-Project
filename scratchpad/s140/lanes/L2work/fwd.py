import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X=capstone.x86
im=Img(); c=CFG(im,0x035E9EC0)
def fwd(start):
    S=set(); st=[start]
    while st:
        n=st.pop()
        if n in S: continue
        S.add(n)
        for d in c.succ.get(n,()): 
            if d not in S: st.append(d)
    return S
T=0x035EB13A
ex,R=c.exits_from(T)
for name,t in [("EPILOGUE 0x35EB1A7",0x035EB1A7),("BAIL 0x35EB7CF",0x035EB7CF),("BAIL 0x35EB150",0x035EB150)]:
    S=fwd(t)
    strs=[]; calls=[]
    for r in sorted(S):
        i=c.insns[r]
        for op in i.operands:
            if op.type==X.X86_OP_MEM and op.mem.base==X.X86_REG_RIP:
                tg=r+i.size+op.mem.disp; s=im.sec_of(tg)
                strs.append((r,i.mnemonic,i.op_str,tg,s['name'] if s else '?'))
        if i.mnemonic=='call':
            calls.append((r,i.op_str))
    print(f"--- {name}: {len(S)} insns forward-reachable, {len(strs)} rip-refs, {len(calls)} calls")
    for x in strs: print(f"     rip {x[0]:#010x} {x[1]} {x[2]} -> {x[3]:#010x} [{x[4]}]")
    for x in calls: print(f"     call {x[0]:#010x} {x[1]}")
    print()
